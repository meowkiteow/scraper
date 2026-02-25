"""
Analytics routes — global overview, campaign analytics, step breakdown, account health.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from db import (get_db, User, Campaign, SentEmail, CampaignLead, Step,
                EmailAccount, CampaignAccount)
from auth import get_current_user

router = APIRouter()


@router.get("/overview")
def global_overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Global stats for the user."""
    campaigns = db.query(Campaign).filter(Campaign.user_id == user.id).all()
    campaign_ids = [c.id for c in campaigns]

    if not campaign_ids:
        return {
            "total_sent": 0, "total_opened": 0, "total_clicked": 0,
            "total_replied": 0, "total_bounced": 0,
            "open_rate": 0, "click_rate": 0, "reply_rate": 0,
            "active_campaigns": 0, "total_campaigns": 0,
            "total_leads": 0,
        }

    sent_q = db.query(SentEmail).filter(SentEmail.campaign_id.in_(campaign_ids))
    total = sent_q.count()
    opened = sent_q.filter(SentEmail.opened_at.isnot(None)).count()
    clicked = sent_q.filter(SentEmail.clicked_at.isnot(None)).count()
    replied = sent_q.filter(SentEmail.replied_at.isnot(None)).count()
    bounced = sent_q.filter(SentEmail.bounced_at.isnot(None)).count()

    active = sum(1 for c in campaigns if c.status == "active")
    total_leads = db.query(CampaignLead).filter(CampaignLead.campaign_id.in_(campaign_ids)).count()

    return {
        "total_sent": total,
        "total_opened": opened,
        "total_clicked": clicked,
        "total_replied": replied,
        "total_bounced": bounced,
        "open_rate": round(opened / total * 100, 1) if total else 0,
        "click_rate": round(clicked / total * 100, 1) if total else 0,
        "reply_rate": round(replied / total * 100, 1) if total else 0,
        "bounce_rate": round(bounced / total * 100, 1) if total else 0,
        "active_campaigns": active,
        "total_campaigns": len(campaigns),
        "total_leads": total_leads,
    }


@router.get("/campaigns/{campaign_id}")
def campaign_analytics(campaign_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Daily time-series stats for a campaign — last 30 days."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    if not campaign:
        return {"daily": [], "total": {}}

    days = 30
    daily = []
    for i in range(days):
        date = datetime.utcnow().date() - timedelta(days=days - 1 - i)
        start = datetime.combine(date, datetime.min.time())
        end = datetime.combine(date, datetime.max.time())

        sent_q = db.query(SentEmail).filter(
            SentEmail.campaign_id == campaign_id,
            SentEmail.sent_at >= start,
            SentEmail.sent_at <= end,
        )
        daily.append({
            "date": date.isoformat(),
            "sent": sent_q.count(),
            "opened": sent_q.filter(SentEmail.opened_at.isnot(None)).count(),
            "replied": sent_q.filter(SentEmail.replied_at.isnot(None)).count(),
        })

    return {"daily": daily}


@router.get("/campaigns/{campaign_id}/steps")
def step_analytics(campaign_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Per-step breakdown with A/B variant stats."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    if not campaign:
        return {"steps": []}

    steps = db.query(Step).filter(Step.campaign_id == campaign_id).order_by(Step.step_number).all()
    results = []

    for step in steps:
        sent_q = db.query(SentEmail).filter(SentEmail.step_id == step.id)
        total = sent_q.count()
        opened = sent_q.filter(SentEmail.opened_at.isnot(None)).count()
        clicked = sent_q.filter(SentEmail.clicked_at.isnot(None)).count()
        replied = sent_q.filter(SentEmail.replied_at.isnot(None)).count()
        bounced = sent_q.filter(SentEmail.bounced_at.isnot(None)).count()

        # A/B variant breakdown
        variant_stats = []
        max_variant = (step.variants and len(step.variants)) or 0
        for vi in range(max_variant + 1):
            v_q = sent_q.filter(SentEmail.variant_index == vi)
            v_total = v_q.count()
            v_opened = v_q.filter(SentEmail.opened_at.isnot(None)).count()
            v_replied = v_q.filter(SentEmail.replied_at.isnot(None)).count()
            variant_stats.append({
                "variant": vi,
                "label": "Original" if vi == 0 else f"Variant {chr(64 + vi)}",
                "sent": v_total,
                "opened": v_opened,
                "replied": v_replied,
                "open_rate": round(v_opened / v_total * 100, 1) if v_total else 0,
                "reply_rate": round(v_replied / v_total * 100, 1) if v_total else 0,
            })

        results.append({
            "step_number": step.step_number,
            "subject": step.subject,
            "delay_days": step.delay_days,
            "sent": total,
            "opened": opened,
            "clicked": clicked,
            "replied": replied,
            "bounced": bounced,
            "open_rate": round(opened / total * 100, 1) if total else 0,
            "reply_rate": round(replied / total * 100, 1) if total else 0,
            "variants": variant_stats,
        })

    return {"steps": results}


@router.get("/accounts/{account_id}")
def account_analytics(account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Per-account sending health."""
    account = db.query(EmailAccount).filter(
        EmailAccount.id == account_id, EmailAccount.user_id == user.id
    ).first()
    if not account:
        return {}

    sent_q = db.query(SentEmail).filter(SentEmail.account_id == account_id)
    total = sent_q.count()
    bounced = sent_q.filter(SentEmail.bounced_at.isnot(None)).count()
    opened = sent_q.filter(SentEmail.opened_at.isnot(None)).count()

    return {
        "account_email": account.email,
        "total_sent": total,
        "total_bounced": bounced,
        "total_opened": opened,
        "bounce_rate": round(bounced / total * 100, 1) if total else 0,
        "open_rate": round(opened / total * 100, 1) if total else 0,
        "sends_today": account.sends_today,
        "daily_limit": account.daily_limit,
        "warmup_score": account.warmup_score,
        "status": account.status,
    }
