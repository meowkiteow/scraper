"""
Email Sender — SMTP sending, template rendering, tracking injection.
"""

import smtplib
import ssl
import re
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import unescape
from datetime import datetime
from typing import Optional

import spintax
from encryption import decrypt


def render_template(text: str, lead: dict, sender: Optional[dict] = None) -> str:
    """
    Replace {{variable}} placeholders with lead data, then resolve spintax.
    """
    if not text:
        return text

    variables = {
        "first_name": lead.get("first_name", ""),
        "last_name": lead.get("last_name", ""),
        "email": lead.get("email", ""),
        "company": lead.get("company", ""),
        "title": lead.get("title", ""),
        "website": lead.get("website", ""),
        "phone": lead.get("phone", ""),
        "city": lead.get("city", ""),
        "state": lead.get("state", ""),
        "country": lead.get("country", ""),
        "industry": lead.get("industry", ""),
    }

    if sender:
        variables["sender_name"] = sender.get("from_name", "")
        variables["sender_email"] = sender.get("email", "")

    # Custom fields
    custom = lead.get("custom_fields") or {}
    if isinstance(custom, str):
        import json
        try:
            custom = json.loads(custom)
        except Exception:
            custom = {}
    variables.update(custom)

    # Replace {{variables}}
    for key, value in variables.items():
        text = text.replace("{{" + key + "}}", str(value or ""))

    # Clean up unreplaced variables
    text = re.sub(r'\{\{[^}]+\}\}', '', text)

    # Resolve spintax
    text = spintax.render(text)

    return text


def html_to_plain(html: str) -> str:
    """Strip HTML tags to plain text."""
    text = re.sub(r'<br\s*/?>', '\n', html)
    text = re.sub(r'<p[^>]*>', '\n', text)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def test_smtp(host: str, port: int, username: str, password: str) -> tuple[bool, str]:
    """Test SMTP connection. Returns (success, message)."""
    try:
        if port == 465:
            ctx = ssl.create_default_context()
            server = smtplib.SMTP_SSL(host, port, context=ctx, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            server.starttls()
        server.login(username, password)
        server.quit()
        return True, "Connection successful"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed. Check username/password. For Gmail, use an App Password."
    except smtplib.SMTPConnectError:
        return False, f"Could not connect to {host}:{port}. Check host and port."
    except Exception as e:
        return False, str(e)


def send_email(
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password_encrypted: str,
    from_email: str,
    from_name: str,
    to_email: str,
    subject: str,
    body_html: str,
    signature_html: str = "",
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Send a single email via SMTP.
    Returns (success, message_id_or_error).
    """
    password = decrypt(smtp_password_encrypted)

    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f'{from_name} <{from_email}>' if from_name else from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg['Reply-To'] = from_email

        # Message-ID for threading
        domain = from_email.split('@')[1]
        message_id = f"<{uuid.uuid4()}@{domain}>"
        msg['Message-ID'] = message_id

        # Threading headers
        if in_reply_to:
            msg['In-Reply-To'] = in_reply_to
            msg['References'] = references or in_reply_to

        # Append signature
        full_body = body_html
        if signature_html:
            full_body += "<br>" + signature_html

        # Attach plain text + HTML
        plain = html_to_plain(full_body)
        msg.attach(MIMEText(plain, 'plain', 'utf-8'))
        msg.attach(MIMEText(full_body, 'html', 'utf-8'))

        # Connect and send
        if smtp_port == 465:
            ctx = ssl.create_default_context()
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx, timeout=15)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.starttls()

        server.login(smtp_username, password)
        server.send_message(msg)
        server.quit()

        return True, message_id

    except Exception as e:
        return False, str(e)
