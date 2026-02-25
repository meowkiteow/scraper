"""
DNS Checker — validates SPF, DKIM, and DMARC records for email sending domains.
"""

import dns.resolver
from typing import Optional


def check_spf(domain: str) -> tuple[bool, Optional[str]]:
    """Check if domain has a valid SPF record."""
    try:
        answers = dns.resolver.resolve(domain, 'TXT')
        for rdata in answers:
            txt = rdata.to_text().strip('"')
            if txt.startswith('v=spf1'):
                return True, txt
        return False, "No SPF record found. Add a TXT record: v=spf1 include:_spf.google.com ~all"
    except dns.resolver.NoAnswer:
        return False, "No TXT records found for domain."
    except dns.resolver.NXDOMAIN:
        return False, "Domain does not exist."
    except Exception as e:
        return False, f"DNS lookup error: {str(e)}"


def check_dkim(domain: str) -> tuple[bool, Optional[str]]:
    """Check common DKIM selectors."""
    selectors = ['google', 'default', 'mail', 'dkim', 'selector1', 'selector2', 'k1']

    for selector in selectors:
        dkim_domain = f"{selector}._domainkey.{domain}"
        try:
            answers = dns.resolver.resolve(dkim_domain, 'TXT')
            for rdata in answers:
                txt = rdata.to_text().strip('"')
                if 'v=DKIM1' in txt or 'k=rsa' in txt:
                    return True, f"DKIM found (selector: {selector})"
            # Found a record but doesn't look like DKIM
            return True, f"TXT record found at {dkim_domain} (may be DKIM)"
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            continue
        except Exception:
            continue

    return False, "No DKIM record found. Check your email provider's setup guide."


def check_dmarc(domain: str) -> tuple[bool, Optional[str]]:
    """Check if domain has a DMARC record."""
    dmarc_domain = f"_dmarc.{domain}"
    try:
        answers = dns.resolver.resolve(dmarc_domain, 'TXT')
        for rdata in answers:
            txt = rdata.to_text().strip('"')
            if txt.startswith('v=DMARC1'):
                return True, txt
        return False, "TXT record found at _dmarc but doesn't contain v=DMARC1"
    except dns.resolver.NoAnswer:
        return False, "No DMARC record found. Add: v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com"
    except dns.resolver.NXDOMAIN:
        return False, "No DMARC record found."
    except Exception as e:
        return False, f"DNS lookup error: {str(e)}"


def check_all(email: str) -> dict:
    """
    Run all DNS checks for the domain part of an email address.
    Returns {spf: bool, dkim: bool, dmarc: bool, details: {spf: str, dkim: str, dmarc: str}}
    """
    domain = email.split('@')[-1] if '@' in email else email

    spf_ok, spf_detail = check_spf(domain)
    dkim_ok, dkim_detail = check_dkim(domain)
    dmarc_ok, dmarc_detail = check_dmarc(domain)

    return {
        "domain": domain,
        "spf": spf_ok,
        "dkim": dkim_ok,
        "dmarc": dmarc_ok,
        "details": {
            "spf": spf_detail,
            "dkim": dkim_detail,
            "dmarc": dmarc_detail,
        }
    }
