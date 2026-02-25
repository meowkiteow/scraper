"""
Step routes — add, update, delete, reorder campaign steps.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from db import get_db, User, Campaign, Step
from auth import get_current_user

router = APIRouter()


class StepCreate(BaseModel):
    step_number: int
    delay_days: int = 0
    subject: str
    body: str
    variants: Optional[List[dict]] = None


class StepUpdate(BaseModel):
    delay_days: Optional[int] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    variants: Optional[List[dict]] = None


@router.post("/{campaign_id}/steps")
def add_step(campaign_id: str, req: StepCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    step = Step(
        campaign_id=campaign.id,
        step_number=req.step_number,
        delay_days=req.delay_days,
        subject=req.subject,
        body=req.body,
        variants=req.variants or [],
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return _serialize(step)


@router.put("/steps/{step_id}")
def update_step(step_id: str, req: StepUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    step = db.query(Step).join(Campaign).filter(Step.id == step_id, Campaign.user_id == user.id).first()
    if not step:
        raise HTTPException(404, "Step not found")

    if req.delay_days is not None:
        step.delay_days = req.delay_days
    if req.subject is not None:
        step.subject = req.subject
    if req.body is not None:
        step.body = req.body
    if req.variants is not None:
        step.variants = req.variants

    db.commit()
    return _serialize(step)


@router.delete("/steps/{step_id}")
def delete_step(step_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    step = db.query(Step).join(Campaign).filter(Step.id == step_id, Campaign.user_id == user.id).first()
    if not step:
        raise HTTPException(404, "Step not found")

    campaign_id = step.campaign_id
    db.delete(step)

    # Re-number remaining steps
    remaining = db.query(Step).filter(Step.campaign_id == campaign_id).order_by(Step.step_number).all()
    for i, s in enumerate(remaining):
        s.step_number = i + 1

    db.commit()
    return {"ok": True}


@router.post("/steps/{step_id}/reorder")
def reorder_step(step_id: str, new_position: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    step = db.query(Step).join(Campaign).filter(Step.id == step_id, Campaign.user_id == user.id).first()
    if not step:
        raise HTTPException(404, "Step not found")

    all_steps = db.query(Step).filter(Step.campaign_id == step.campaign_id).order_by(Step.step_number).all()

    # Remove from current position and insert at new
    all_steps = [s for s in all_steps if s.id != step.id]
    all_steps.insert(max(0, new_position - 1), step)

    for i, s in enumerate(all_steps):
        s.step_number = i + 1

    db.commit()
    return {"ok": True}


def _serialize(s: Step) -> dict:
    return {
        "id": s.id,
        "campaign_id": s.campaign_id,
        "step_number": s.step_number,
        "delay_days": s.delay_days,
        "subject": s.subject,
        "body": s.body,
        "variants": s.variants or [],
    }
