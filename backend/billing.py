"""
Stripe Billing — subscription management + webhook handler.
"""

import os
import stripe
from dotenv import load_dotenv

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

PRICE_MAP = {
    "starter": os.getenv("STRIPE_PRICE_STARTER", ""),
    "growth": os.getenv("STRIPE_PRICE_GROWTH", ""),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE", ""),
}


def create_customer(email: str, name: str) -> str | None:
    """Create a Stripe customer. Returns customer ID."""
    if not stripe.api_key:
        return None
    try:
        customer = stripe.Customer.create(email=email, name=name)
        return customer.id
    except Exception:
        return None


def create_checkout_session(customer_id: str, plan: str, success_url: str, cancel_url: str) -> str | None:
    """Create a Stripe Checkout Session. Returns the session URL."""
    if not stripe.api_key or plan not in PRICE_MAP or not PRICE_MAP[plan]:
        return None

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": PRICE_MAP[plan], "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return session.url
    except Exception:
        return None


def create_portal_session(customer_id: str, return_url: str) -> str | None:
    """Create a Stripe Billing Portal session. Returns the portal URL."""
    if not stripe.api_key or not customer_id:
        return None
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return session.url
    except Exception:
        return None


def handle_webhook_event(payload: bytes, sig_header: str) -> dict | None:
    """
    Verify and parse a Stripe webhook event.
    Returns the event object or None if verification fails.
    """
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret:
        return None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        return event
    except Exception:
        return None


def get_subscription_details(subscription_id: str) -> dict | None:
    """Get current subscription details from Stripe."""
    if not stripe.api_key or not subscription_id:
        return None
    try:
        sub = stripe.Subscription.retrieve(subscription_id)
        return {
            "id": sub.id,
            "status": sub.status,
            "plan": sub.plan.id if sub.plan else None,
            "current_period_end": sub.current_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end,
        }
    except Exception:
        return None
