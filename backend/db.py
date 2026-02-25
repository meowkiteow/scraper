"""
Database layer — SQLAlchemy ORM models + session management.
SQLite for dev, PostgreSQL for prod. Swap by changing DATABASE_URL.
"""

import os
import uuid
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean, Text,
    DateTime, ForeignKey, JSON, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./coldmail.db")

# SQLite needs check_same_thread=False for multi-threaded access
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def gen_uuid():
    return str(uuid.uuid4())


# ═════════════════════════════════════════════════════════════
# MODELS
# ═════════════════════════════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), default="")
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    plan = Column(String(50), default="free")  # free, starter, growth, enterprise
    plan_status = Column(String(50), default="active")  # active, trialing, canceled, past_due
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    accounts = relationship("EmailAccount", back_populates="user", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="user", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="user", cascade="all, delete-orphan")


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    from_name = Column(String(255), default="")
    provider = Column(String(50), default="custom")  # gmail, outlook, custom

    # SMTP
    smtp_host = Column(String(255))
    smtp_port = Column(Integer, default=587)
    smtp_username = Column(String(255))
    smtp_password_encrypted = Column(Text)  # Fernet encrypted

    # IMAP
    imap_host = Column(String(255))
    imap_port = Column(Integer, default=993)
    imap_username = Column(String(255))
    imap_password_encrypted = Column(Text)  # Fernet encrypted

    # Limits
    daily_limit = Column(Integer, default=40)
    sends_today = Column(Integer, default=0)

    # Warmup
    warmup_enabled = Column(Boolean, default=False)
    warmup_daily_target = Column(Integer, default=40)
    warmup_ramp_days = Column(Integer, default=30)
    warmup_score = Column(Float, default=0.0)
    warmup_started_at = Column(DateTime, nullable=True)

    # DNS
    dns_spf_ok = Column(Boolean, nullable=True)
    dns_dkim_ok = Column(Boolean, nullable=True)
    dns_dmarc_ok = Column(Boolean, nullable=True)
    last_dns_check = Column(DateTime, nullable=True)

    # Status
    status = Column(String(50), default="active")  # active, warming, error, paused
    signature_html = Column(Text, default="")
    last_error = Column(Text, nullable=True)
    last_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", back_populates="accounts")
    campaign_links = relationship("CampaignAccount", back_populates="account", cascade="all, delete-orphan")


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="draft")  # draft, active, paused, completed

    # Schedule
    rotation_strategy = Column(String(50), default="round_robin")  # round_robin, weighted, random
    daily_limit = Column(Integer, default=50)
    timezone = Column(String(100), default="UTC")
    send_window_start = Column(Integer, default=9)  # hour
    send_window_end = Column(Integer, default=17)  # hour
    send_days = Column(String(100), default="mon,tue,wed,thu,fri")

    # Options
    stop_on_reply = Column(Boolean, default=True)
    track_opens = Column(Boolean, default=True)
    track_clicks = Column(Boolean, default=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="campaigns")
    steps = relationship("Step", back_populates="campaign", cascade="all, delete-orphan",
                         order_by="Step.step_number")
    account_links = relationship("CampaignAccount", back_populates="campaign", cascade="all, delete-orphan")
    leads = relationship("CampaignLead", back_populates="campaign", cascade="all, delete-orphan")
    sent_emails = relationship("SentEmail", back_populates="campaign", cascade="all, delete-orphan")


class CampaignAccount(Base):
    __tablename__ = "campaign_accounts"

    id = Column(String, primary_key=True, default=gen_uuid)
    campaign_id = Column(String, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(String, ForeignKey("email_accounts.id", ondelete="CASCADE"), nullable=False)
    weight = Column(Integer, default=1)
    sends_today = Column(Integer, default=0)

    campaign = relationship("Campaign", back_populates="account_links")
    account = relationship("EmailAccount", back_populates="campaign_links")


class Step(Base):
    __tablename__ = "steps"

    id = Column(String, primary_key=True, default=gen_uuid)
    campaign_id = Column(String, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    delay_days = Column(Integer, default=0)
    subject = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    variants = Column(JSON, default=list)  # [{subject, body}, ...]

    campaign = relationship("Campaign", back_populates="steps")
    sent_emails = relationship("SentEmail", back_populates="step")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    first_name = Column(String(255), default="")
    last_name = Column(String(255), default="")
    company = Column(String(255), default="")
    title = Column(String(255), default="")
    phone = Column(String(100), default="")
    website = Column(String(500), default="")
    city = Column(String(255), default="")
    state = Column(String(255), default="")
    country = Column(String(255), default="")
    industry = Column(String(255), default="")
    source = Column(String(50), default="manual")  # csv, maps, manual, api
    status = Column(String(50), default="active")  # active, unsubscribed, bounced, replied
    tags = Column(JSON, default=list)
    custom_fields = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="leads")
    campaign_links = relationship("CampaignLead", back_populates="lead", cascade="all, delete-orphan")


class CampaignLead(Base):
    __tablename__ = "campaign_leads"

    id = Column(String, primary_key=True, default=gen_uuid)
    campaign_id = Column(String, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(String, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    current_step = Column(Integer, default=0)
    status = Column(String(50), default="active")  # active, paused, completed, unsubscribed, bounced, replied
    last_sent_at = Column(DateTime, nullable=True)
    next_send_at = Column(DateTime, nullable=True)

    campaign = relationship("Campaign", back_populates="leads")
    lead = relationship("Lead", back_populates="campaign_links")


class SentEmail(Base):
    __tablename__ = "sent_emails"

    id = Column(String, primary_key=True, default=gen_uuid)
    campaign_id = Column(String, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("email_accounts.id"), nullable=False)
    step_id = Column(String, ForeignKey("steps.id"), nullable=False)

    message_id = Column(String(500))
    subject = Column(Text)
    body_preview = Column(Text)
    sent_at = Column(DateTime, default=func.now())

    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    replied_at = Column(DateTime, nullable=True)
    bounced_at = Column(DateTime, nullable=True)

    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    variant_index = Column(Integer, default=0)

    tracking_id = Column(String, unique=True, nullable=True)

    campaign = relationship("Campaign", back_populates="sent_emails")
    step = relationship("Step", back_populates="sent_emails")


class WarmupLog(Base):
    __tablename__ = "warmup_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    sender_account_id = Column(String, ForeignKey("email_accounts.id"), nullable=False)
    receiver_account_id = Column(String, ForeignKey("email_accounts.id"), nullable=False)
    direction = Column(String(20))  # sent, received
    sent_at = Column(DateTime, default=func.now())
    replied_at = Column(DateTime, nullable=True)
    marked_read_at = Column(DateTime, nullable=True)


class InboxMessage(Base):
    __tablename__ = "inbox_messages"

    id = Column(String, primary_key=True, default=gen_uuid)
    account_id = Column(String, ForeignKey("email_accounts.id"), nullable=False, index=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=True)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True)

    from_email = Column(String(255))
    subject = Column(Text)
    body = Column(Text)
    received_at = Column(DateTime, default=func.now())
    is_read = Column(Boolean, default=False)
    label = Column(String(50), default="none")  # interested, not_interested, meeting_booked, unsubscribe, follow_up, none
    thread_id = Column(String(500), nullable=True)
    message_id_header = Column(String(500), nullable=True)


class Unsubscribe(Base):
    __tablename__ = "unsubscribes"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    unsubscribed_at = Column(DateTime, default=func.now())
    source = Column(String(50), default="link")  # link, manual, reply


class Bounce(Base):
    __tablename__ = "bounces"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    bounce_type = Column(String(20), default="hard")  # hard, soft
    bounced_at = Column(DateTime, default=func.now())
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=True)


class ProspectorJob(Base):
    __tablename__ = "prospector_jobs"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    query = Column(String(500), nullable=False)
    location = Column(String(500), nullable=False)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    total_results = Column(Integer, default=0)
    results = Column(JSON, default=list)
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)


# ═════════════════════════════════════════════════════════════
# PLAN LIMITS
# ═════════════════════════════════════════════════════════════

PLAN_LIMITS = {
    "free":       {"campaigns": 1, "accounts": 1,  "leads": 100,   "daily_sends": 50},
    "starter":    {"campaigns": 5, "accounts": 5,  "leads": 5000,  "daily_sends": 500},
    "growth":     {"campaigns": 25, "accounts": 25, "leads": 50000, "daily_sends": 5000},
    "enterprise": {"campaigns": 999, "accounts": 999, "leads": 999999, "daily_sends": 99999},
}


def get_plan_limits(plan: str) -> dict:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])


# ═════════════════════════════════════════════════════════════
# INIT
# ═════════════════════════════════════════════════════════════

def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
