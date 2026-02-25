"""
Campaign Sending Worker — background thread that sends queued emails.
Runs continuously, checks every 60 seconds for pending sends.
"""

import time
import random
import uuid
import threading
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from db import SessionLocal, Campaign, CampaignLead, CampaignAccount, Step, SentEmail, \
    EmailAccount, Lead, Unsubscribe, Bounce
from email_sender import render_template, send_email
from auth import create_unsubscribe_token

logging.basicConfig(level=logging.INFO, format='%(asctime)s [CAMPAIGN] %(message)s')
logger = logging.getLogger("campaign_worker")

_worker_running = False
_worker_thread = None


def _get_pending_leads(db: Session) -> list:
    """Find leads due for their next email across all active campaigns."""
    now = datetime.utcnow()

    results = db.query(CampaignLead, Campaign).join(
        Campaign, CampaignLead.campaign_id == Campaign.id
    ).filter(
        Campaign.status == "active",
        CampaignLead.status == "active",
        CampaignLead.next_send_at <= now,
    ).limit(20).all()

    return results


def _pick_account(db: Session, campaign: Campaign) -> EmailAccount | None:
    """Pick the best sending account for this campaign using its rotation strategy."""
    links = db.query(CampaignAccount).filter(
        CampaignAccount.campaign_id == campaign.id
    ).all()

    if not links:
        return None

    account_ids = [link.account_id for link in links]
    accounts = db.query(EmailAccount).filter(
        EmailAccount.id.in_(account_ids),
        EmailAccount.status.in_(["active", "warming"]),
        EmailAccount.sends_today < EmailAccount.daily_limit
    ).all()

    if not accounts:
        return None

    if campaign.rotation_strategy == "round_robin":
        return min(accounts, key=lambda a: a.sends_today)
    elif campaign.rotation_strategy == "weighted":
        weights = {link.account_id: link.weight for link in links}
        weighted = [(a, weights.get(a.id, 1)) for a in accounts]
        total = sum(w for _, w in weighted)
        r = random.uniform(0, total)
        cumulative = 0
        for acc, w in weighted:
            cumulative += w
            if r <= cumulative:
                return acc
        return accounts[0]
    else:  # random
        return random.choice(accounts)


def _is_suppressed(db: Session, user_id: str, email: str) -> bool:
    """Check unsubscribes and bounces before sending."""
    unsub = db.query(Unsubscribe).filter(
        Unsubscribe.user_id == user_id,
        Unsubscribe.email == email
    ).first()
    if unsub:
        return True

    bounce = db.query(Bounce).filter(
        Bounce.user_id == user_id,
        Bounce.email == email,
        Bounce.bounce_type == "hard"
    ).first()
    if bounce:
        return True

    return False


def _send_one(db: Session, cl: CampaignLead, campaign: Campaign):
    """Send the next email in sequence for this lead."""
    lead = db.query(Lead).filter(Lead.id == cl.lead_id).first()
    if not lead:
        return

    # Check suppression
    if _is_suppressed(db, campaign.user_id, lead.email):
        cl.status = "unsubscribed"
        db.commit()
        logger.info(f"Skipping suppressed: {lead.email}")
        return

    # Get next step
    next_step_num = cl.current_step + 1
    step = db.query(Step).filter(
        Step.campaign_id == campaign.id,
        Step.step_number == next_step_num
    ).first()

    if not step:
        cl.status = "completed"
        db.commit()
        logger.info(f"Lead {lead.email} completed all steps.")
        return

    # Pick sending account
    account = _pick_account(db, campaign)
    if not account:
        logger.warning(f"No available accounts for campaign '{campaign.name}'")
        return

    # Prepare lead data
    lead_data = {
        "first_name": lead.first_name, "last_name": lead.last_name,
        "email": lead.email, "company": lead.company,
        "title": lead.title, "website": lead.website,
        "phone": lead.phone, "city": lead.city,
        "state": lead.state, "country": lead.country,
        "industry": lead.industry, "custom_fields": lead.custom_fields or {},
    }
    sender_data = {"from_name": account.from_name, "email": account.email}

    # Pick variant (A/B testing)
    variant_index = 0
    subject_template = step.subject
    body_template = step.body
    if step.variants and len(step.variants) > 0:
        variant_index = random.randint(0, len(step.variants))
        if variant_index > 0 and variant_index <= len(step.variants):
            variant = step.variants[variant_index - 1]
            subject_template = variant.get("subject", step.subject)
            body_template = variant.get("body", step.body)

    # Render template
    subject = render_template(subject_template, lead_data, sender_data)
    body = render_template(body_template, lead_data, sender_data)

    # Add unsubscribe footer
    unsub_token = create_unsubscribe_token(campaign.user_id, lead.email)
    import os
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    body += f'<br><br><small style="color:#999;"><a href="{frontend_url}/unsubscribe?token={unsub_token}" style="color:#999;">Unsubscribe</a></small>'

    # Get previous message_id for threading
    in_reply_to = None
    references = None
    if next_step_num > 1:
        prev = db.query(SentEmail).filter(
            SentEmail.lead_id == lead.id,
            SentEmail.campaign_id == campaign.id
        ).order_by(SentEmail.sent_at.desc()).first()
        if prev and prev.message_id:
            in_reply_to = prev.message_id
            all_prev = db.query(SentEmail.message_id).filter(
                SentEmail.lead_id == lead.id,
                SentEmail.campaign_id == campaign.id
            ).all()
            references = " ".join(p.message_id for p in all_prev if p.message_id)

    # SEND
    success, result = send_email(
        smtp_host=account.smtp_host,
        smtp_port=account.smtp_port,
        smtp_username=account.smtp_username,
        smtp_password_encrypted=account.smtp_password_encrypted,
        from_email=account.email,
        from_name=account.from_name,
        to_email=lead.email,
        subject=subject,
        body_html=body,
        signature_html=account.signature_html or "",
        in_reply_to=in_reply_to,
        references=references,
    )

    if success:
        message_id = result
        tracking_id = str(uuid.uuid4())

        # Record sent email
        sent = SentEmail(
            campaign_id=campaign.id, lead_id=lead.id,
            account_id=account.id, step_id=step.id,
            message_id=message_id, subject=subject,
            body_preview=body[:200], tracking_id=tracking_id,
            variant_index=variant_index,
        )
        db.add(sent)

        # Update lead progress
        next_step = db.query(Step).filter(
            Step.campaign_id == campaign.id,
            Step.step_number == next_step_num + 1
        ).first()

        cl.current_step = next_step_num
        cl.last_sent_at = datetime.utcnow()
        if next_step:
            cl.next_send_at = datetime.utcnow() + timedelta(days=next_step.delay_days)
        else:
            cl.status = "completed"
            cl.next_send_at = None

        # Update account counter
        account.sends_today += 1
        account.last_sent_at = datetime.utcnow()

        db.commit()
        logger.info(f"✅ Sent step {next_step_num} to {lead.email} via {account.email}")

    else:
        error = result
        logger.error(f"❌ Failed: {lead.email} — {error}")
        account.last_error = error[:200]

        # Handle bounces
        if any(kw in error.lower() for kw in ['bounce', 'rejected', 'not exist', '550', '551', '553']):
            cl.status = "bounced"
            bounce = Bounce(
                user_id=campaign.user_id, email=lead.email,
                bounce_type="hard", campaign_id=campaign.id
            )
            db.add(bounce)
            lead.status = "bounced"

        db.commit()


def _worker_loop():
    """Main loop — runs continuously."""
    global _worker_running
    logger.info("🚀 Campaign sending worker started!")

    while _worker_running:
        try:
            db = SessionLocal()
            try:
                # Reset daily counts at midnight UTC
                now = datetime.utcnow()
                if now.hour == 0 and now.minute == 0:
                    db.query(EmailAccount).update({EmailAccount.sends_today: 0})
                    db.query(CampaignAccount).update({CampaignAccount.sends_today: 0})
                    db.commit()

                pending = _get_pending_leads(db)

                if pending:
                    logger.info(f"Found {len(pending)} pending sends.")
                    for cl, campaign in pending:
                        if not _worker_running:
                            break

                        # Check send window
                        current_hour = now.hour
                        if not (campaign.send_window_start <= current_hour < campaign.send_window_end):
                            continue

                        # Check send day
                        today = now.strftime('%a').lower()[:3]
                        if today not in (campaign.send_days or "mon,tue,wed,thu,fri").split(','):
                            continue

                        try:
                            _send_one(db, cl, campaign)
                        except Exception as e:
                            logger.error(f"Error sending to lead: {e}")
                            continue

                        # Random delay 30-90s
                        delay = random.randint(30, 90)
                        time.sleep(delay)
                else:
                    time.sleep(60)
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Worker error: {e}")
            time.sleep(30)

    logger.info("Campaign worker stopped.")


def start_worker():
    global _worker_running, _worker_thread
    if _worker_running:
        return False
    _worker_running = True
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()
    return True


def stop_worker():
    global _worker_running
    _worker_running = False


def is_worker_running():
    return _worker_running
