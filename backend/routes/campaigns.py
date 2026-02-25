"""
Campaign routes — CRUD, start, pause, duplicate, stats.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from db import (get_db, User, Campaign, CampaignAccount, CampaignLead, Step,
                SentEmail, EmailAccount, get_plan_limits)
from auth import get_current_user

router = APIRouter()


class CampaignCreate(BaseModel):
    name: str
    send_days: str = "mon,tue,wed,thu,fri"
    send_window_start: int = 9
    send_window_end: int = 17
    timezone: str = "UTC"
    rotation_strategy: str = "round_robin"
    daily_limit: int = 50
    stop_on_reply: bool = True
    track_opens: bool = True
    track_clicks: bool = True


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    send_days: Optional[str] = None
    send_window_start: Optional[int] = None
    send_window_end: Optional[int] = None
    timezone: Optional[str] = None
    rotation_strategy: Optional[str] = None
    daily_limit: Optional[int] = None
    stop_on_reply: Optional[bool] = None
    track_opens: Optional[bool] = None
    track_clicks: Optional[bool] = None
    account_ids: Optional[List[str]] = None


@router.get("")
def list_campaigns(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).filter(Campaign.user_id == user.id).order_by(Campaign.created_at.desc()).all()
    return [_serialize(db, c) for c in campaigns]


@router.post("")
def create_campaign(req: CampaignCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    limits = get_plan_limits(user.plan)
    count = db.query(Campaign).filter(Campaign.user_id == user.id).count()
    if count >= limits["campaigns"]:
        raise HTTPException(403, f"Plan limit reached ({limits['campaigns']} campaigns). Upgrade to add more.")

    campaign = Campaign(
        user_id=user.id,
        name=req.name,
        send_days=req.send_days,
        send_window_start=req.send_window_start,
        send_window_end=req.send_window_end,
        timezone=req.timezone,
        rotation_strategy=req.rotation_strategy,
        daily_limit=req.daily_limit,
        stop_on_reply=req.stop_on_reply,
        track_opens=req.track_opens,
        track_clicks=req.track_clicks,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _serialize(db, campaign)


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    campaign = _get_campaign(db, user.id, campaign_id)
    result = _serialize(db, campaign)

    # Include steps
    steps = db.query(Step).filter(Step.campaign_id == campaign.id).order_by(Step.step_number).all()
    result["steps"] = [{
        "id": s.id, "step_number": s.step_number, "delay_days": s.delay_days,
        "subject": s.subject, "body": s.body, "variants": s.variants or [],
    } for s in steps]

    # Include assigned accounts
    links = db.query(CampaignAccount).filter(CampaignAccount.campaign_id == campaign.id).all()
    account_ids = [l.account_id for l in links]
    accounts = db.query(EmailAccount).filter(EmailAccount.id.in_(account_ids)).all() if account_ids else []
    result["accounts"] = [{
        "id": a.id, "email": a.email, "from_name": a.from_name,
        "sends_today": a.sends_today, "daily_limit": a.daily_limit, "status": a.status,
    } for a in accounts]

    return result


@router.put("/{campaign_id}")
def update_campaign(campaign_id: str, req: CampaignUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    campaign = _get_campaign(db, user.id, campaign_id)

    for field in ["name", "send_days", "send_window_start", "send_window_end",
                   "timezone", "rotation_strategy", "daily_limit",
                   "stop_on_reply", "track_opens", "track_clicks"]:
        val = getattr(req, field, None)
        if val is not None:
            setattr(campaign, field, val)

    # Update account assignments
    if req.account_ids is not None:
        db.query(CampaignAccount).filter(CampaignAccount.campaign_id == campaign.id).delete()
        for aid in req.account_ids:
            db.add(CampaignAccount(campaign_id=campaign.id, account_id=aid))

    db.commit()
    return _serialize(db, campaign)


@router.delete("/{campaign_id}")
def delete_campaign(campaign_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    campaign = _get_campaign(db, user.id, campaign_id)
    db.delete(campaign)
    db.commit()
    return {"ok": True}


@router.post("/{campaign_id}/start")
def start_campaign(campaign_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    campaign = _get_campaign(db, user.id, campaign_id)

    # Validate campaign has steps, accounts, and leads
    steps = db.query(Step).filter(Step.campaign_id == campaign.id).count()
    if steps == 0:
        raise HTTPException(400, "Add at least one email step before starting")

    accounts = db.query(CampaignAccount).filter(CampaignAccount.campaign_id == campaign.id).count()
    if accounts == 0:
        raise HTTPException(400, "Assign at least one email account before starting")

    leads = db.query(CampaignLead).filter(
        CampaignLead.campaign_id == campaign.id, CampaignLead.status == "active"
    ).count()
    if leads == 0:
        raise HTTPException(400, "Import leads before starting")

    # Set all active leads to ready for send
    db.query(CampaignLead).filter(
        CampaignLead.campaign_id == campaign.id,
        CampaignLead.status == "active",
        CampaignLead.current_step == 0,
    ).update({CampaignLead.next_send_at: datetime.utcnow()})

    campaign.status = "active"
    db.commit()
    return {"status": "active", "message": "Campaign started!"}


@router.post("/{campaign_id}/pause")
def pause_campaign(campaign_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    campaign = _get_campaign(db, user.id, campaign_id)
    campaign.status = "paused"
    db.commit()
    return {"status": "paused"}


@router.post("/{campaign_id}/duplicate")
def duplicate_campaign(campaign_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    original = _get_campaign(db, user.id, campaign_id)

    new_campaign = Campaign(
        user_id=user.id,
        name=f"{original.name} (Copy)",
        send_days=original.send_days,
        send_window_start=original.send_window_start,
        send_window_end=original.send_window_end,
        timezone=original.timezone,
        rotation_strategy=original.rotation_strategy,
        daily_limit=original.daily_limit,
        stop_on_reply=original.stop_on_reply,
        track_opens=original.track_opens,
        track_clicks=original.track_clicks,
    )
    db.add(new_campaign)
    db.flush()

    # Copy steps
    steps = db.query(Step).filter(Step.campaign_id == original.id).all()
    for s in steps:
        db.add(Step(
            campaign_id=new_campaign.id, step_number=s.step_number,
            delay_days=s.delay_days, subject=s.subject, body=s.body,
            variants=s.variants,
        ))

    # Copy account assignments
    links = db.query(CampaignAccount).filter(CampaignAccount.campaign_id == original.id).all()
    for l in links:
        db.add(CampaignAccount(campaign_id=new_campaign.id, account_id=l.account_id, weight=l.weight))

    db.commit()
    return _serialize(db, new_campaign)


@router.get("/{campaign_id}/stats")
def campaign_stats(campaign_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    campaign = _get_campaign(db, user.id, campaign_id)
    sent = db.query(SentEmail).filter(SentEmail.campaign_id == campaign.id)

    total = sent.count()
    opened = sent.filter(SentEmail.opened_at.isnot(None)).count()
    clicked = sent.filter(SentEmail.clicked_at.isnot(None)).count()
    replied = sent.filter(SentEmail.replied_at.isnot(None)).count()
    bounced = sent.filter(SentEmail.bounced_at.isnot(None)).count()

    leads_total = db.query(CampaignLead).filter(CampaignLead.campaign_id == campaign.id).count()
    leads_active = db.query(CampaignLead).filter(
        CampaignLead.campaign_id == campaign.id, CampaignLead.status == "active"
    ).count()
    leads_completed = db.query(CampaignLead).filter(
        CampaignLead.campaign_id == campaign.id, CampaignLead.status == "completed"
    ).count()

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
        "leads_total": leads_total,
        "leads_active": leads_active,
        "leads_completed": leads_completed,
    }


def _get_campaign(db: Session, user_id: str, campaign_id: str) -> Campaign:
    c = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user_id).first()
    if not c:
        raise HTTPException(404, "Campaign not found")
    return c


def _serialize(db: Session, c: Campaign) -> dict:
    sent = db.query(SentEmail).filter(SentEmail.campaign_id == c.id)
    leads_count = db.query(CampaignLead).filter(CampaignLead.campaign_id == c.id).count()
    steps_count = db.query(Step).filter(Step.campaign_id == c.id).count()
    accounts_count = db.query(CampaignAccount).filter(CampaignAccount.campaign_id == c.id).count()

    total_sent = sent.count()
    total_opened = sent.filter(SentEmail.opened_at.isnot(None)).count()
    total_replied = sent.filter(SentEmail.replied_at.isnot(None)).count()

    return {
        "id": c.id,
        "name": c.name,
        "status": c.status,
        "rotation_strategy": c.rotation_strategy,
        "daily_limit": c.daily_limit,
        "timezone": c.timezone,
        "send_window_start": c.send_window_start,
        "send_window_end": c.send_window_end,
        "send_days": c.send_days,
        "stop_on_reply": c.stop_on_reply,
        "track_opens": c.track_opens,
        "track_clicks": c.track_clicks,
        "leads_count": leads_count,
        "steps_count": steps_count,
        "accounts_count": accounts_count,
        "total_sent": total_sent,
        "total_opened": total_opened,
        "total_replied": total_replied,
        "open_rate": round(total_opened / total_sent * 100, 1) if total_sent else 0,
        "reply_rate": round(total_replied / total_sent * 100, 1) if total_sent else 0,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }
