"""
Billing routes — Stripe checkout, portal, webhooks.
"""

import os
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from db import get_db, User, get_plan_limits
from auth import get_current_user
from billing import (create_checkout_session, create_portal_session,
                     handle_webhook_event, get_subscription_details)

router = APIRouter()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

PLANS = [
    {
        "id": "free", "name": "Free", "price": 0,
        "limits": get_plan_limits("free"),
        "features": ["1 email account", "1 campaign", "100 leads", "50 sends/day"],
    },
    {
        "id": "starter", "name": "Starter", "price": 49,
        "limits": get_plan_limits("starter"),
        "features": ["5 email accounts", "5 campaigns", "5,000 leads", "500 sends/day", "Email warmup", "DNS checks"],
    },
    {
        "id": "growth", "name": "Growth", "price": 99,
        "limits": get_plan_limits("growth"),
        "features": ["25 email accounts", "25 campaigns", "50,000 leads", "5,000 sends/day", "Email warmup", "Priority support"],
    },
    {
        "id": "enterprise", "name": "Enterprise", "price": 299,
        "limits": get_plan_limits("enterprise"),
        "features": ["Unlimited accounts", "Unlimited campaigns", "Unlimited leads", "Unlimited sends", "Dedicated support", "Custom integrations"],
    },
]


@router.get("/plans")
def list_plans():
    return {"plans": PLANS}


@router.get("/subscription")
def current_subscription(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub_details = None
    if user.stripe_subscription_id:
        sub_details = get_subscription_details(user.stripe_subscription_id)

    return {
        "plan": user.plan,
        "plan_status": user.plan_status,
        "limits": get_plan_limits(user.plan),
        "stripe_subscription": sub_details,
    }


@router.post("/checkout")
def create_checkout(plan: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if plan not in ["starter", "growth", "enterprise"]:
        raise HTTPException(400, "Invalid plan")

    if not user.stripe_customer_id:
        raise HTTPException(400, "No Stripe customer ID. Contact support.")

    url = create_checkout_session(
        customer_id=user.stripe_customer_id,
        plan=plan,
        success_url=f"{FRONTEND_URL}/billing?success=true",
        cancel_url=f"{FRONTEND_URL}/billing?canceled=true",
    )

    if not url:
        raise HTTPException(500, "Could not create checkout session. Check Stripe configuration.")

    return {"url": url}


@router.post("/portal")
def billing_portal(user: User = Depends(get_current_user)):
    if not user.stripe_customer_id:
        raise HTTPException(400, "No Stripe customer ID")

    url = create_portal_session(
        customer_id=user.stripe_customer_id,
        return_url=f"{FRONTEND_URL}/billing",
    )

    if not url:
        raise HTTPException(500, "Could not create portal session")

    return {"url": url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events — no auth required."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    event = handle_webhook_event(payload, sig)
    if not event:
        raise HTTPException(400, "Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "customer.subscription.created":
        _update_user_plan(db, data)
    elif event_type == "customer.subscription.updated":
        _update_user_plan(db, data)
    elif event_type == "customer.subscription.deleted":
        customer_id = data.get("customer")
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            user.plan = "free"
            user.plan_status = "canceled"
            user.stripe_subscription_id = None
            db.commit()
    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            user.plan_status = "past_due"
            db.commit()

    return {"received": True}


def _update_user_plan(db: Session, subscription_data: dict):
    """Update user plan from Stripe subscription data."""
    customer_id = subscription_data.get("customer")
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return

    user.stripe_subscription_id = subscription_data.get("id")
    user.plan_status = subscription_data.get("status", "active")

    # Determine plan tier from price ID
    items = subscription_data.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id", "")
        price_starter = os.getenv("STRIPE_PRICE_STARTER", "")
        price_growth = os.getenv("STRIPE_PRICE_GROWTH", "")
        price_enterprise = os.getenv("STRIPE_PRICE_ENTERPRISE", "")

        if price_id == price_starter:
            user.plan = "starter"
        elif price_id == price_growth:
            user.plan = "growth"
        elif price_id == price_enterprise:
            user.plan = "enterprise"

    db.commit()
