import asyncio
import re
import urllib.parse
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import logging

# Set up logging to avoid printing to console when not needed, but keep it available for debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Basic Regex for email extraction
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

def extract_emails_from_html(html_content):
    """Uses regex and BeautifulSoup to find emails in raw HTML."""
    soup = BeautifulSoup(html_content, 'html.parser')
    text_content = soup.get_text()
    
    # Find all emails in text
    emails = re.findall(EMAIL_REGEX, text_content)
    
    # Also check mailto links in case they are hidden from get_text()
    for a in soup.find_all('a', href=True):
        if a['href'].startswith('mailto:'):
            emails.append(a['href'].replace('mailto:', '').split('?')[0])
            
    # Remove duplicates and common false positives (like image extensions)
    valid_emails = set()
    for email in emails:
        email = email.lower()
        if not email.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')):
            valid_emails.add(email)
            
    return list(valid_emails)

async def crawl_website_for_email(url):
    """Visits a website and searches its homepage and contact page for emails."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        
        # 1. Check Homepage (short timeout to avoid hanging)
        response = requests.get(url, headers=headers, timeout=(3, 4))
        emails = extract_emails_from_html(response.text)
        
        if emails:
            return emails
            
        # 2. If no email on homepage, try common 'contact' pages
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        soup = BeautifulSoup(response.text, 'html.parser')
        contact_links = []
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if 'contact' in href or 'about' in href:
                if href.startswith('http'):
                    contact_links.append(a['href'])
                elif href.startswith('/'):
                    contact_links.append(base_url + a['href'])
                else:
                    contact_links.append(base_url + '/' + a['href'])
                    
        # Try the first valid contact link we found
        if contact_links:
            contact_url = contact_links[0]
            logger.info(f"Checking contact page: {contact_url}")
            contact_response = requests.get(contact_url, headers=headers, timeout=(3, 4))
            emails = extract_emails_from_html(contact_response.text)
            
        return emails
        
    except Exception as e:
        logger.warning(f"Failed to crawl {url}: {e}")
        return []

async def scrape_google_maps(keyword, location, limit=10, status_callback=None, 
                             result_callback=None,
                             extract_emails=True, extract_phone=True, 
                             extract_website=True, extract_reviews=True,
                             stop_check=None, skip_names=None):
    """
    Automates Google Maps to search for businesses and extract their details.
    stop_check: callable that returns True when scraping should stop.
    skip_names: set of business names (lowercase) to skip (already scraped).
    """
    search_query = f"{keyword} in {location}"
    skip_set = {n.lower().strip() for n in (skip_names or [])}
    logger.info(f"Starting scrape for: {search_query} (skipping {len(skip_set)} previously scraped)")
    
    if status_callback:
        if skip_set:
            status_callback(f"Starting headless browser... (skipping {len(skip_set)} already scraped)")
        else:
            status_callback(f"Starting headless browser...")

    results = []

    async with async_playwright() as p:
        # Launch Chromium in headless mode (no visible browser window)
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            java_script_enabled=True,
        )
        # Hide webdriver flag
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()

        # Go directly to search results URL — skip the fragile search box entirely
        search_url_query = urllib.parse.quote(search_query)
        maps_url = f"https://www.google.com/maps/search/{search_url_query}"
        
        if status_callback: status_callback(f"Navigating to Google Maps...")
        await page.goto(maps_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        
        # Handle consent overlay (some regions)
        try:
            consent_button = page.locator("button:has-text('Accept all')")
            if await consent_button.is_visible(timeout=2000):
                await consent_button.click()
                await page.wait_for_timeout(2000)
        except:
            pass
        
        if status_callback: status_callback(f"Waiting for results to load...")
        
        # Wait for results to load
        try:
            await page.wait_for_selector('div[role="feed"]', timeout=10000)
            feed_locator = 'div[role="feed"]'
        except:
            try:
                await page.wait_for_selector('a[href*="/maps/place/"]', timeout=5000)
                feed_locator = None
            except:
                logger.warning("Could not find search results. Trying to proceed anyway...")
                feed_locator = None
        
        if status_callback: status_callback(f"Extracting business listings...")
        
        # We need to scroll the feed to load more listings if limit > 10
        # For simplicity in this v1, we'll try to extract what's immediately visible
        # and do a bit of scrolling.
        
        previously_scraped = set()
        no_new_cards_count = 0  # Track consecutive rounds with no new cards
        
        # Scroll loop — runs until Maps has no more results
        for scroll_round in range(100):
            if len(results) >= limit:
                logger.info(f"Reached limit of {limit}. Done.")
                break
                
            # Find all visible business cards
            if feed_locator:
                business_cards = await page.locator(f'{feed_locator} > div > div > a').all()
            else:
                business_cards = await page.locator('a[href*="/maps/place/"]').all()
            
            new_cards_this_round = 0
            
            for card in business_cards:
                if len(results) >= limit:
                    break
                # Check stop flag before each card
                if stop_check and stop_check():
                    logger.info("Stop requested by user.")
                    await browser.close()
                    return results
                    
                href = await card.get_attribute('href')
                if not href or href in previously_scraped:
                    continue
                
                # This is a new card we haven't processed yet
                new_cards_this_round += 1
                previously_scraped.add(href)
                
                name = await card.get_attribute('aria-label')
                if not name:
                    continue

                # Skip businesses already scraped in previous runs
                if name.lower().strip() in skip_set:
                    logger.info(f"Skipping already-scraped: {name}")
                    continue
                    
                if status_callback: status_callback(f"[{len(results)+1}] Checking {name}...")
                
                try:
                    await card.click(timeout=5000)
                except Exception as e:
                    logger.warning(f"Could not click card {name}, skipping: {e}")
                    continue
                
                try:
                    # Wait for details pane to load
                    await page.wait_for_timeout(2500)
                    
                    # ── Extract Website ──
                    website = None
                    if extract_website or extract_emails:
                        # Primary: aria-label starting with "Website:"
                        website_selectors = [
                            'a[aria-label^="Website:"]',
                            'a[aria-label="Open website"]',
                            'a[data-item-id="authority"]',
                        ]
                        for ws in website_selectors:
                            try:
                                el = page.locator(ws).first
                                if await el.is_visible(timeout=1500):
                                    website = await el.get_attribute('href')
                                    if website:
                                        break
                            except:
                                continue
                        
                    # ── Extract Phone Number ──
                    # Phone numbers are in .Io6YTe spans as plain text (e.g. "+1 212-766-6600")
                    # We iterate all .Io6YTe elements and match against a phone regex
                    phone = None
                    if extract_phone:
                        try:
                            info_elements = await page.locator('.Io6YTe').all()
                            for el in info_elements:
                                text = (await el.text_content() or "").strip()
                                # Match phone patterns: +1 212-766-6600, (212) 555-1234, 0123456789, etc.
                                if re.match(r'^[\+\d\s\-\(\)\.]{7,20}$', text) and re.search(r'\d{3}', text):
                                    phone = text
                                    break
                        except:
                            pass
                        
                    # ── Extract Rating & Reviews ──
                    rating = None
                    reviews = None
                    if extract_reviews:
                        # Rating: inside .F7nice, the aria-hidden span has the numeric rating
                        try:
                            rating_el = page.locator('div.F7nice span[aria-hidden="true"]').first
                            if await rating_el.is_visible(timeout=1000):
                                rating = await rating_el.text_content()
                        except:
                            pass
                        
                        # Reviews: inside .F7nice, a span with role="img" and aria-label containing "reviews"
                        try:
                            reviews_el = page.locator('div.F7nice span[role="img"][aria-label*="review"]').first
                            if await reviews_el.is_visible(timeout=1000):
                                reviews_label = await reviews_el.get_attribute('aria-label')
                                # aria-label is like "257 reviews" — extract the number
                                if reviews_label:
                                    numbers = re.findall(r'[\d,]+', reviews_label)
                                    if numbers:
                                        reviews = numbers[0].replace(',', '')
                        except:
                            pass

                    # Check stop flag before crawling website (the slowest part)
                    if stop_check and stop_check():
                        logger.info("Stop requested by user.")
                        await browser.close()
                        return results

                    # Extract Emails
                    emails = []
                    if extract_emails and website:
                        if status_callback: status_callback(f"[{len(results)+1}/{limit}] Crawling website for {name}...")
                        emails = await crawl_website_for_email(website)
                        
                    business_data = {"Name": name}
                    if extract_reviews:
                        business_data["Rating"] = rating if rating else "N/A"
                        business_data["Total Reviews"] = reviews if reviews else "0"
                    if extract_phone:
                        business_data["Phone"] = phone if phone else "N/A"
                    if extract_website:
                        business_data["Website"] = website if website else "No website on Maps"
                    if extract_emails:
                        business_data["Emails"] = ", ".join(emails) if emails else "None found"
                    
                    results.append(business_data)
                    logger.info(f"Scraped {len(results)}/{limit}: {name}")
                    
                    # Push result to UI immediately
                    if result_callback:
                        result_callback(business_data)
                    
                    if status_callback: 
                        progress_pct = min(100, int((len(results) / limit) * 100))
                        status_callback(f"Scraped {len(results)}: {name}", progress_pct)
                    
                except Exception as e:
                    logger.warning(f"Error scraping details for {name}: {e}")
                    continue
            
            # ---- After processing all cards in this round ----
            if len(results) >= limit:
                logger.info(f"Reached limit of {limit}. Done.")
                break
            
            # Check stop flag between scroll rounds
            if stop_check and stop_check():
                logger.info("Stop requested by user.")
                await browser.close()
                return results

            # If this scroll round found ZERO new cards, Maps has no more to show
            if new_cards_this_round == 0:
                no_new_cards_count += 1
                if no_new_cards_count >= 2:
                    logger.info(f"No new cards found after {no_new_cards_count} scroll attempts. Ending.")
                    if status_callback: status_callback(f"No more results on Maps. Found {len(results)} businesses total.")
                    break
            else:
                no_new_cards_count = 0  # Reset if we found new cards
                
            # Scroll down the feed list to load more
            if feed_locator:
                try:
                    feed = page.locator(feed_locator)
                    await feed.evaluate('element => element.scrollTop = element.scrollHeight')
                except:
                    pass
            else:
                await page.mouse.wheel(0, 500)
            await page.wait_for_timeout(2000)
            
        await browser.close()
        
    return results

if __name__ == "__main__":
    # Small test script you can run directly to verify the logic
    # python scraper.py
    async def test():
        def print_status(msg, progress=None):
            pct = f" [{progress}%]" if progress else ""
            print(f"> {msg}{pct}")
        
        res = await scrape_google_maps("Web Design Agency", "London", limit=3, status_callback=print_status)
        print("\n--- RESULTS ---")
        for r in res:
            print(r)
            
    asyncio.run(test())
