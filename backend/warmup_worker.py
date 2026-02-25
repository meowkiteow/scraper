"""
Warmup Worker — warms up email accounts by sending/receiving between the pool.
"""

import time
import random
import threading
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from db import SessionLocal, EmailAccount, WarmupLog
from email_sender import send_email
from imap_reader import fetch_replies, move_from_spam

logging.basicConfig(level=logging.INFO, format='%(asctime)s [WARMUP] %(message)s')
logger = logging.getLogger("warmup_worker")

_warmup_running = False
_warmup_thread = None

WARMUP_SUBJECTS = [
    "Quick question about our meeting",
    "Following up on last week",
    "Re: Project update",
    "Can you review this?",
    "Thanks for sending that over",
    "Checking in",
    "Are we still on for Thursday?",
    "FYI - updated the document",
    "Re: Schedule change",
    "Got a minute?",
]

WARMUP_BODIES = [
    "Hey, just wanted to follow up on our conversation. Let me know your thoughts when you get a chance!",
    "Thanks for getting back to me. I'll review and send my feedback by EOD.",
    "Sounds good! I'll loop in the team and we can discuss next steps.",
    "Great, I've updated the spreadsheet with the latest numbers. Take a look when you get a chance.",
    "Perfect, let's plan to meet next week. What day works best for you?",
    "Just checking in on this. Any updates on your end?",
    "Appreciate the quick response. I'll get back to you shortly.",
    "Noted. I'll make the changes and share the updated version tomorrow.",
]

WARMUP_REPLIES = [
    "Sounds good, thanks!",
    "Got it, will do!",
    "Thanks for the update!",
    "Perfect, I'll take a look.",
    "Appreciated! Talk soon.",
    "Great, looking forward to it!",
    "Will check and get back to you.",
    "Thanks! See you then.",
]


def _calc_daily_target(account: EmailAccount) -> int:
    """Calculate how many warmup emails to send today based on ramp schedule."""
    if not account.warmup_started_at:
        return 2

    days_warming = (datetime.utcnow() - account.warmup_started_at).days
    target = account.warmup_daily_target or 40
    ramp_days = account.warmup_ramp_days or 30

    if days_warming <= 3:
        return 2
    elif days_warming <= 7:
        return 5
    elif days_warming <= 14:
        return 10
    elif days_warming <= 21:
        return 20
    elif days_warming <= ramp_days:
        return min(30, target)
    else:
        return target


def _warmup_cycle():
    """One warmup cycle — send and receive warmup emails."""
    db = SessionLocal()
    try:
        # Get all warmup-enabled accounts
        accounts = db.query(EmailAccount).filter(
            EmailAccount.warmup_enabled == True,
            EmailAccount.status.in_(["active", "warming"])
        ).all()

        if len(accounts) < 2:
            logger.info("Need at least 2 warmup-enabled accounts. Skipping.")
            return

        for account in accounts:
            try:
                daily_target = _calc_daily_target(account)

                # Count how many warmup emails sent today
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
                sent_today = db.query(WarmupLog).filter(
                    WarmupLog.sender_account_id == account.id,
                    WarmupLog.sent_at >= today_start
                ).count()

                remaining = daily_target - sent_today
                if remaining <= 0:
                    continue

                # Pick random target accounts from the pool (not self)
                targets = [a for a in accounts if a.id != account.id]
                random.shuffle(targets)
                targets = targets[:min(remaining, 3)]  # Send max 3 per cycle

                for target in targets:
                    subject = random.choice(WARMUP_SUBJECTS)
                    body = random.choice(WARMUP_BODIES)

                    success, result = send_email(
                        smtp_host=account.smtp_host,
                        smtp_port=account.smtp_port,
                        smtp_username=account.smtp_username,
                        smtp_password_encrypted=account.smtp_password_encrypted,
                        from_email=account.email,
                        from_name=account.from_name,
                        to_email=target.email,
                        subject=subject,
                        body_html=f"<p>{body}</p>",
                    )

                    if success:
                        log = WarmupLog(
                            sender_account_id=account.id,
                            receiver_account_id=target.id,
                            direction="sent",
                        )
                        db.add(log)
                        account.sends_today += 1
                        db.commit()
                        logger.info(f"🔥 Warmup: {account.email} → {target.email}")
                    else:
                        logger.warning(f"Warmup send failed: {account.email} → {target.email}: {result}")

                    time.sleep(random.randint(10, 30))

                # --- RECEIVE SIDE: check inbox, read warmup emails, reply ---
                try:
                    replies = fetch_replies(
                        account.imap_host, account.imap_port,
                        account.imap_username, account.imap_password_encrypted,
                    )

                    for reply in replies:
                        # Check if it's from another warmup account
                        sender = db.query(EmailAccount).filter(
                            EmailAccount.email == reply["from_email"],
                            EmailAccount.warmup_enabled == True
                        ).first()

                        if sender:
                            # This is a warmup email — move from spam if needed
                            move_from_spam(
                                account.imap_host, account.imap_port,
                                account.imap_username, account.imap_password_encrypted,
                                reply["subject"]
                            )

                            # Reply (50% chance)
                            if random.random() < 0.5:
                                reply_body = random.choice(WARMUP_REPLIES)
                                send_email(
                                    smtp_host=account.smtp_host,
                                    smtp_port=account.smtp_port,
                                    smtp_username=account.smtp_username,
                                    smtp_password_encrypted=account.smtp_password_encrypted,
                                    from_email=account.email,
                                    from_name=account.from_name,
                                    to_email=reply["from_email"],
                                    subject=f"Re: {reply['subject']}",
                                    body_html=f"<p>{reply_body}</p>",
                                    in_reply_to=reply.get("message_id"),
                                )
                                logger.info(f"🔥 Warmup reply: {account.email} → {reply['from_email']}")

                except Exception as e:
                    logger.warning(f"Warmup IMAP error for {account.email}: {e}")

                # Update warmup score
                total_sent = db.query(WarmupLog).filter(
                    WarmupLog.sender_account_id == account.id
                ).count()
                total_replied = db.query(WarmupLog).filter(
                    WarmupLog.receiver_account_id == account.id,
                    WarmupLog.replied_at.isnot(None)
                ).count()

                if total_sent > 0:
                    account.warmup_score = min(100, (total_replied / max(total_sent, 1)) * 100 + total_sent * 0.5)
                account.status = "warming" if account.warmup_enabled else "active"
                db.commit()

            except Exception as e:
                logger.error(f"Warmup error for {account.email}: {e}")
                continue

    finally:
        db.close()


def _warmup_loop():
    """Main warmup loop — runs every hour."""
    global _warmup_running
    logger.info("🔥 Warmup worker started!")

    while _warmup_running:
        try:
            _warmup_cycle()
        except Exception as e:
            logger.error(f"Warmup cycle error: {e}")

        # Wait 1 hour before next cycle
        for _ in range(3600):
            if not _warmup_running:
                break
            time.sleep(1)

    logger.info("Warmup worker stopped.")


def start_warmup():
    global _warmup_running, _warmup_thread
    if _warmup_running:
        return False
    _warmup_running = True
    _warmup_thread = threading.Thread(target=_warmup_loop, daemon=True)
    _warmup_thread.start()
    return True


def stop_warmup():
    global _warmup_running
    _warmup_running = False


def is_warmup_running():
    return _warmup_running
