"""
Email Account routes — CRUD, test, DNS check, warmup toggle.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from db import get_db, User, EmailAccount, get_plan_limits, WarmupLog
from auth import get_current_user
from encryption import encrypt, decrypt
from email_sender import test_smtp, send_email
from dns_checker import check_all as check_dns_all

router = APIRouter()


class AccountCreate(BaseModel):
    email: str
    from_name: str = ""
    provider: str = "custom"
    smtp_host: str
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
    imap_host: Optional[str] = None
    imap_port: int = 993
    daily_limit: int = 40
    signature_html: str = ""


class AccountUpdate(BaseModel):
    from_name: Optional[str] = None
    daily_limit: Optional[int] = None
    signature_html: Optional[str] = None
    smtp_password: Optional[str] = None


@router.get("")
def list_accounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    accounts = db.query(EmailAccount).filter(EmailAccount.user_id == user.id).order_by(EmailAccount.created_at.desc()).all()
    return [_serialize(a) for a in accounts]


@router.post("")
def create_account(req: AccountCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Check plan limits
    limits = get_plan_limits(user.plan)
    count = db.query(EmailAccount).filter(EmailAccount.user_id == user.id).count()
    if count >= limits["accounts"]:
        raise HTTPException(403, f"Plan limit reached ({limits['accounts']} accounts). Upgrade to add more.")

    # Check duplicate
    existing = db.query(EmailAccount).filter(
        EmailAccount.user_id == user.id, EmailAccount.email == req.email
    ).first()
    if existing:
        raise HTTPException(400, "Account already exists")

    imap_host = req.imap_host or req.smtp_host.replace("smtp", "imap")

    account = EmailAccount(
        user_id=user.id,
        email=req.email,
        from_name=req.from_name,
        provider=req.provider,
        smtp_host=req.smtp_host,
        smtp_port=req.smtp_port,
        smtp_username=req.smtp_username,
        smtp_password_encrypted=encrypt(req.smtp_password),
        imap_host=imap_host,
        imap_port=req.imap_port,
        imap_username=req.smtp_username,
        imap_password_encrypted=encrypt(req.smtp_password),
        daily_limit=req.daily_limit,
        signature_html=req.signature_html,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _serialize(account)


@router.get("/{account_id}")
def get_account(account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = _get_account(db, user.id, account_id)
    return _serialize(account)


@router.put("/{account_id}")
def update_account(account_id: str, req: AccountUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = _get_account(db, user.id, account_id)
    if req.from_name is not None:
        account.from_name = req.from_name
    if req.daily_limit is not None:
        account.daily_limit = req.daily_limit
    if req.signature_html is not None:
        account.signature_html = req.signature_html
    if req.smtp_password is not None:
        account.smtp_password_encrypted = encrypt(req.smtp_password)
        account.imap_password_encrypted = encrypt(req.smtp_password)
    db.commit()
    return _serialize(account)


@router.delete("/{account_id}")
def delete_account(account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = _get_account(db, user.id, account_id)
    db.delete(account)
    db.commit()
    return {"ok": True}


@router.post("/{account_id}/test-smtp")
def test_smtp_conn(account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = _get_account(db, user.id, account_id)
    password = decrypt(account.smtp_password_encrypted)
    success, msg = test_smtp(account.smtp_host, account.smtp_port, account.smtp_username, password)
    return {"success": success, "message": msg}


@router.post("/{account_id}/send-test")
def send_test(account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = _get_account(db, user.id, account_id)
    body = f"""<div style="font-family:Arial,sans-serif;padding:20px;">
    <h2>✅ Test Email Successful!</h2>
    <p>Sent from <strong>{account.email}</strong>.</p>
    <p>Your SMTP connection is working correctly.</p>
    <p style="color:#666;font-size:12px;">Sent at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
    </div>"""

    success, result = send_email(
        smtp_host=account.smtp_host, smtp_port=account.smtp_port,
        smtp_username=account.smtp_username,
        smtp_password_encrypted=account.smtp_password_encrypted,
        from_email=account.email, from_name=account.from_name,
        to_email=account.email, subject="Test Email — Cold Email Platform",
        body_html=body,
    )
    if success:
        account.last_sent_at = datetime.utcnow()
        account.last_error = None
        db.commit()
    return {"success": success, "message": result if not success else "Test email sent!"}


@router.post("/{account_id}/check-dns")
def check_dns(account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = _get_account(db, user.id, account_id)
    result = check_dns_all(account.email)
    account.dns_spf_ok = result["spf"]
    account.dns_dkim_ok = result["dkim"]
    account.dns_dmarc_ok = result["dmarc"]
    account.last_dns_check = datetime.utcnow()
    db.commit()
    return result


class QuickSendRequest(BaseModel):
    to_email: str
    subject: str
    body_html: str


@router.post("/{account_id}/quick-send")
def quick_send(account_id: str, req: QuickSendRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Send a single email to any recipient directly (no campaign needed)."""
    account = _get_account(db, user.id, account_id)

    if account.sends_today >= account.daily_limit:
        raise HTTPException(429, f"Daily limit reached ({account.daily_limit}). Try again tomorrow.")

    success, result = send_email(
        smtp_host=account.smtp_host, smtp_port=account.smtp_port,
        smtp_username=account.smtp_username,
        smtp_password_encrypted=account.smtp_password_encrypted,
        from_email=account.email, from_name=account.from_name,
        to_email=req.to_email, subject=req.subject,
        body_html=req.body_html, signature_html=account.signature_html or "",
    )

    if success:
        account.sends_today += 1
        account.last_sent_at = datetime.utcnow()
        account.last_error = None
        db.commit()
        return {"success": True, "message": f"Email sent to {req.to_email}!"}
    else:
        account.last_error = result
        db.commit()
        return {"success": False, "message": result}


@router.post("/{account_id}/warmup/toggle")
def toggle_warmup(account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = _get_account(db, user.id, account_id)
    account.warmup_enabled = not account.warmup_enabled
    if account.warmup_enabled and not account.warmup_started_at:
        account.warmup_started_at = datetime.utcnow()
        account.status = "warming"
    elif not account.warmup_enabled:
        account.status = "active"
    db.commit()
    return {"warmup_enabled": account.warmup_enabled, "status": account.status}


@router.get("/{account_id}/warmup/stats")
def warmup_stats(account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = _get_account(db, user.id, account_id)
    sent = db.query(WarmupLog).filter(WarmupLog.sender_account_id == account.id).count()
    received = db.query(WarmupLog).filter(WarmupLog.receiver_account_id == account.id).count()
    replied = db.query(WarmupLog).filter(
        WarmupLog.receiver_account_id == account.id, WarmupLog.replied_at.isnot(None)
    ).count()

    days_warming = 0
    if account.warmup_started_at:
        days_warming = (datetime.utcnow() - account.warmup_started_at).days

    return {
        "warmup_score": account.warmup_score,
        "days_warming": days_warming,
        "total_sent": sent,
        "total_received": received,
        "total_replied": replied,
    }


def _get_account(db: Session, user_id: str, account_id: str) -> EmailAccount:
    account = db.query(EmailAccount).filter(
        EmailAccount.id == account_id, EmailAccount.user_id == user_id
    ).first()
    if not account:
        raise HTTPException(404, "Account not found")
    return account


def _serialize(a: EmailAccount) -> dict:
    return {
        "id": a.id,
        "email": a.email,
        "from_name": a.from_name,
        "provider": a.provider,
        "smtp_host": a.smtp_host,
        "smtp_port": a.smtp_port,
        "daily_limit": a.daily_limit,
        "sends_today": a.sends_today,
        "warmup_enabled": a.warmup_enabled,
        "warmup_score": a.warmup_score,
        "warmup_started_at": a.warmup_started_at.isoformat() if a.warmup_started_at else None,
        "dns_spf_ok": a.dns_spf_ok,
        "dns_dkim_ok": a.dns_dkim_ok,
        "dns_dmarc_ok": a.dns_dmarc_ok,
        "last_dns_check": a.last_dns_check.isoformat() if a.last_dns_check else None,
        "status": a.status,
        "signature_html": a.signature_html,
        "last_error": a.last_error,
        "last_sent_at": a.last_sent_at.isoformat() if a.last_sent_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
