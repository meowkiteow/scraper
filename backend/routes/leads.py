"""
Lead routes — global lead database, campaign imports, suppression lists.
"""

import csv
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from db import (get_db, User, Lead, CampaignLead, Campaign, Unsubscribe, Bounce,
                get_plan_limits)
from auth import get_current_user, decode_unsubscribe_token

router = APIRouter()


class LeadImport(BaseModel):
    leads: List[dict]  # [{email, first_name, last_name, company, ...}]


@router.get("")
def list_leads(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
):
    query = db.query(Lead).filter(Lead.user_id == user.id)

    if status:
        query = query.filter(Lead.status == status)
    if source:
        query = query.filter(Lead.source == source)
    if search:
        query = query.filter(
            (Lead.email.ilike(f"%{search}%")) |
            (Lead.first_name.ilike(f"%{search}%")) |
            (Lead.company.ilike(f"%{search}%"))
        )

    total = query.count()
    leads = query.order_by(Lead.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    return {
        "leads": [_serialize_lead(l) for l in leads],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@router.get("/suppression")
def suppression_lists(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    unsubs = db.query(Unsubscribe).filter(Unsubscribe.user_id == user.id).all()
    bounces = db.query(Bounce).filter(Bounce.user_id == user.id).all()
    return {
        "unsubscribes": [{"email": u.email, "date": u.unsubscribed_at.isoformat() if u.unsubscribed_at else None, "source": u.source} for u in unsubs],
        "bounces": [{"email": b.email, "type": b.bounce_type, "date": b.bounced_at.isoformat() if b.bounced_at else None} for b in bounces],
    }


@router.post("/export")
def export_leads(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: Optional[str] = None,
):
    query = db.query(Lead).filter(Lead.user_id == user.id)
    if status:
        query = query.filter(Lead.status == status)

    leads = query.all()
    rows = []
    for l in leads:
        rows.append({
            "email": l.email, "first_name": l.first_name, "last_name": l.last_name,
            "company": l.company, "title": l.title, "phone": l.phone,
            "website": l.website, "city": l.city, "state": l.state,
            "country": l.country, "industry": l.industry,
            "source": l.source, "status": l.status,
        })
    return {"leads": rows, "total": len(rows)}


@router.post("/unsubscribe")
def public_unsubscribe(token: str, db: Session = Depends(get_db)):
    """Public endpoint — no auth required."""
    payload = decode_unsubscribe_token(token)
    if not payload:
        raise HTTPException(400, "Invalid or expired unsubscribe link")

    user_id = payload["user_id"]
    email = payload["email"]

    # Add to unsubscribe list
    existing = db.query(Unsubscribe).filter(
        Unsubscribe.user_id == user_id, Unsubscribe.email == email
    ).first()
    if not existing:
        db.add(Unsubscribe(user_id=user_id, email=email, source="link"))

    # Update lead status
    lead = db.query(Lead).filter(Lead.user_id == user_id, Lead.email == email).first()
    if lead:
        lead.status = "unsubscribed"

    # Update campaign lead status
    if lead:
        db.query(CampaignLead).filter(CampaignLead.lead_id == lead.id).update(
            {CampaignLead.status: "unsubscribed"}
        )

    db.commit()
    return {"message": "You have been unsubscribed successfully."}


# ── Campaign-specific lead operations ──

@router.get("/campaigns/{campaign_id}")
def get_campaign_leads(
    campaign_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    query = db.query(CampaignLead).filter(CampaignLead.campaign_id == campaign_id)
    if status:
        query = query.filter(CampaignLead.status == status)

    total = query.count()
    cls = query.offset((page - 1) * per_page).limit(per_page).all()

    results = []
    for cl in cls:
        lead = db.query(Lead).filter(Lead.id == cl.lead_id).first()
        if lead:
            results.append({
                "id": cl.id,
                "lead_id": lead.id,
                "email": lead.email,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "company": lead.company,
                "status": cl.status,
                "current_step": cl.current_step,
                "last_sent_at": cl.last_sent_at.isoformat() if cl.last_sent_at else None,
                "next_send_at": cl.next_send_at.isoformat() if cl.next_send_at else None,
            })

    return {"leads": results, "total": total, "page": page, "per_page": per_page}


@router.post("/campaigns/{campaign_id}")
def import_leads_to_campaign(
    campaign_id: str,
    req: LeadImport,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    # Check plan limits
    limits = get_plan_limits(user.plan)
    current_count = db.query(Lead).filter(Lead.user_id == user.id).count()

    # Get suppression lists
    unsubscribed = set(
        u.email for u in db.query(Unsubscribe).filter(Unsubscribe.user_id == user.id).all()
    )
    bounced = set(
        b.email for b in db.query(Bounce).filter(
            Bounce.user_id == user.id, Bounce.bounce_type == "hard"
        ).all()
    )
    existing_in_campaign = set(
        cl.lead_id for cl in db.query(CampaignLead).filter(CampaignLead.campaign_id == campaign_id).all()
    )

    added = 0
    skipped = 0

    for lead_data in req.leads:
        email = (lead_data.get("email") or "").strip().lower()
        if not email or "@" not in email:
            skipped += 1
            continue
        if email in unsubscribed or email in bounced:
            skipped += 1
            continue
        if current_count + added >= limits["leads"]:
            break

        # Find or create lead
        lead = db.query(Lead).filter(Lead.user_id == user.id, Lead.email == email).first()
        if not lead:
            lead = Lead(
                user_id=user.id,
                email=email,
                first_name=lead_data.get("first_name", ""),
                last_name=lead_data.get("last_name", ""),
                company=lead_data.get("company", ""),
                title=lead_data.get("title", ""),
                phone=lead_data.get("phone", ""),
                website=lead_data.get("website", ""),
                city=lead_data.get("city", ""),
                state=lead_data.get("state", ""),
                country=lead_data.get("country", ""),
                industry=lead_data.get("industry", ""),
                source=lead_data.get("source", "manual"),
                tags=lead_data.get("tags", []),
                custom_fields=lead_data.get("custom_fields", {}),
            )
            db.add(lead)
            db.flush()

        # Skip if already in this campaign
        if lead.id in existing_in_campaign:
            skipped += 1
            continue

        # Add to campaign
        cl = CampaignLead(campaign_id=campaign_id, lead_id=lead.id)
        db.add(cl)
        existing_in_campaign.add(lead.id)
        added += 1

    db.commit()
    return {"added": added, "skipped": skipped}


@router.delete("/campaigns/{campaign_id}/{lead_id}")
def remove_lead_from_campaign(
    campaign_id: str, lead_id: str,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    cl = db.query(CampaignLead).filter(
        CampaignLead.campaign_id == campaign_id, CampaignLead.lead_id == lead_id
    ).first()
    if cl:
        db.delete(cl)
        db.commit()
    return {"ok": True}


def _serialize_lead(l: Lead) -> dict:
    return {
        "id": l.id,
        "email": l.email,
        "first_name": l.first_name,
        "last_name": l.last_name,
        "company": l.company,
        "title": l.title,
        "phone": l.phone,
        "website": l.website,
        "city": l.city,
        "state": l.state,
        "country": l.country,
        "industry": l.industry,
        "source": l.source,
        "status": l.status,
        "tags": l.tags or [],
        "created_at": l.created_at.isoformat() if l.created_at else None,
    }
