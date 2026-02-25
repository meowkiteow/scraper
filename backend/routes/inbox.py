"""
Inbox routes — unified inbox for replies across all accounts.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from db import (get_db, User, InboxMessage, EmailAccount, SentEmail, CampaignLead, Lead)
from auth import get_current_user
from imap_reader import fetch_replies

router = APIRouter()


@router.get("")
def list_inbox(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    label: Optional[str] = None,
    is_read: Optional[bool] = None,
    page: int = 1,
    per_page: int = 50,
):
    # Get all user's account IDs
    account_ids = [a.id for a in db.query(EmailAccount).filter(EmailAccount.user_id == user.id).all()]
    if not account_ids:
        return {"messages": [], "total": 0, "page": page}

    query = db.query(InboxMessage).filter(InboxMessage.account_id.in_(account_ids))

    if label and label != "all":
        query = query.filter(InboxMessage.label == label)
    if is_read is not None:
        query = query.filter(InboxMessage.is_read == is_read)

    total = query.count()
    messages = query.order_by(InboxMessage.received_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    results = []
    for m in messages:
        # Try to find associated lead
        lead_info = None
        if m.lead_id:
            lead = db.query(Lead).filter(Lead.id == m.lead_id).first()
            if lead:
                lead_info = {"email": lead.email, "first_name": lead.first_name, "company": lead.company}

        results.append({
            "id": m.id,
            "from_email": m.from_email,
            "subject": m.subject,
            "body": m.body[:300] if m.body else "",
            "received_at": m.received_at.isoformat() if m.received_at else None,
            "is_read": m.is_read,
            "label": m.label,
            "campaign_id": m.campaign_id,
            "lead": lead_info,
            "account_id": m.account_id,
        })

    return {"messages": results, "total": total, "page": page, "per_page": per_page,
            "unread_count": db.query(InboxMessage).filter(
                InboxMessage.account_id.in_(account_ids), InboxMessage.is_read == False
            ).count()}


@router.get("/{message_id}")
def get_message(message_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account_ids = [a.id for a in db.query(EmailAccount).filter(EmailAccount.user_id == user.id).all()]
    msg = db.query(InboxMessage).filter(
        InboxMessage.id == message_id, InboxMessage.account_id.in_(account_ids)
    ).first()
    if not msg:
        raise HTTPException(404, "Message not found")

    return {
        "id": msg.id,
        "from_email": msg.from_email,
        "subject": msg.subject,
        "body": msg.body,
        "received_at": msg.received_at.isoformat() if msg.received_at else None,
        "is_read": msg.is_read,
        "label": msg.label,
        "campaign_id": msg.campaign_id,
        "lead_id": msg.lead_id,
        "account_id": msg.account_id,
        "thread_id": msg.thread_id,
    }


class LabelUpdate(BaseModel):
    label: str  # interested, not_interested, meeting_booked, unsubscribe, follow_up, none


@router.post("/{message_id}/label")
def set_label(message_id: str, req: LabelUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account_ids = [a.id for a in db.query(EmailAccount).filter(EmailAccount.user_id == user.id).all()]
    msg = db.query(InboxMessage).filter(
        InboxMessage.id == message_id, InboxMessage.account_id.in_(account_ids)
    ).first()
    if not msg:
        raise HTTPException(404, "Message not found")
    msg.label = req.label
    db.commit()
    return {"ok": True, "label": msg.label}


@router.post("/{message_id}/mark-read")
def mark_read(message_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account_ids = [a.id for a in db.query(EmailAccount).filter(EmailAccount.user_id == user.id).all()]
    msg = db.query(InboxMessage).filter(
        InboxMessage.id == message_id, InboxMessage.account_id.in_(account_ids)
    ).first()
    if not msg:
        raise HTTPException(404, "Message not found")
    msg.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/sync")
def sync_inbox(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Trigger IMAP sync for all user accounts."""
    accounts = db.query(EmailAccount).filter(
        EmailAccount.user_id == user.id,
        EmailAccount.status.in_(["active", "warming"])
    ).all()

    total_new = 0
    errors = []

    for account in accounts:
        try:
            replies = fetch_replies(
                account.imap_host, account.imap_port,
                account.imap_username, account.imap_password_encrypted,
            )

            for reply in replies:
                # Check if we already have this message
                existing = db.query(InboxMessage).filter(
                    InboxMessage.account_id == account.id,
                    InboxMessage.from_email == reply["from_email"],
                    InboxMessage.subject == reply["subject"],
                ).first()
                if existing:
                    continue

                # Try to match to a sent email / campaign
                campaign_id = None
                lead_id = None
                in_reply_to = reply.get("in_reply_to", "")
                if in_reply_to:
                    sent = db.query(SentEmail).filter(SentEmail.message_id == in_reply_to).first()
                    if sent:
                        campaign_id = sent.campaign_id
                        lead_id = sent.lead_id
                        # Mark sent email as replied
                        sent.replied_at = datetime.utcnow()
                        # Update campaign lead status
                        cl = db.query(CampaignLead).filter(
                            CampaignLead.campaign_id == campaign_id,
                            CampaignLead.lead_id == lead_id
                        ).first()
                        if cl:
                            cl.status = "replied"

                msg = InboxMessage(
                    account_id=account.id,
                    campaign_id=campaign_id,
                    lead_id=lead_id,
                    from_email=reply["from_email"],
                    subject=reply["subject"],
                    body=reply["body"],
                    message_id_header=reply.get("message_id"),
                    thread_id=in_reply_to or reply.get("message_id"),
                )
                db.add(msg)
                total_new += 1

        except Exception as e:
            errors.append(f"{account.email}: {str(e)}")

    db.commit()
    return {"new_messages": total_new, "errors": errors}
