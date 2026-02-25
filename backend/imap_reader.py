"""
IMAP Reader — fetches replies and warmup emails from email accounts.
"""

import imaplib
import email
import re
from email.header import decode_header
from datetime import datetime
from typing import Optional

from encryption import decrypt


def _connect_imap(host: str, port: int, username: str, password_encrypted: str):
    """Connect to IMAP server."""
    password = decrypt(password_encrypted)
    imap = imaplib.IMAP4_SSL(host, port)
    imap.login(username, password)
    return imap


def _decode_subject(msg) -> str:
    """Decode email subject header."""
    subject = msg.get('Subject', '')
    if not subject:
        return ''
    decoded = decode_header(subject)
    parts = []
    for data, encoding in decoded:
        if isinstance(data, bytes):
            parts.append(data.decode(encoding or 'utf-8', errors='replace'))
        else:
            parts.append(data)
    return ''.join(parts)


def _extract_body(msg) -> str:
    """Extract text/plain body from email message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == 'text/plain':
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                except Exception:
                    body = str(part.get_payload())
                break
            elif content_type == 'text/html' and not body:
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                except Exception:
                    body = str(part.get_payload())
    else:
        try:
            body = msg.get_payload(decode=True).decode('utf-8', errors='replace')
        except Exception:
            body = str(msg.get_payload())
    return body


def fetch_replies(
    imap_host: str,
    imap_port: int,
    imap_username: str,
    imap_password_encrypted: str,
    since_hours: int = 24
) -> list[dict]:
    """
    Fetch unread emails from inbox.
    Returns list of {from_email, subject, body, message_id, in_reply_to, references, received_at}
    """
    replies = []
    try:
        imap = _connect_imap(imap_host, imap_port, imap_username, imap_password_encrypted)
        imap.select('INBOX')

        # Search for unseen messages
        _, msg_ids = imap.search(None, 'UNSEEN')
        if not msg_ids[0]:
            imap.close()
            imap.logout()
            return replies

        for msg_id in msg_ids[0].split():
            try:
                _, msg_data = imap.fetch(msg_id, '(RFC822)')
                msg = email.message_from_bytes(msg_data[0][1])

                from_header = msg.get('From', '')
                from_email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', from_header)
                from_email = from_email_match.group(0) if from_email_match else from_header

                replies.append({
                    "from_email": from_email,
                    "subject": _decode_subject(msg),
                    "body": _extract_body(msg),
                    "message_id": msg.get('Message-ID', ''),
                    "in_reply_to": msg.get('In-Reply-To', ''),
                    "references": msg.get('References', ''),
                    "received_at": datetime.utcnow().isoformat(),
                })
            except Exception:
                continue

        imap.close()
        imap.logout()
    except Exception:
        pass

    return replies


def mark_as_read(
    imap_host: str, imap_port: int,
    imap_username: str, imap_password_encrypted: str,
    message_uid: str
):
    """Mark a specific message as read."""
    try:
        imap = _connect_imap(imap_host, imap_port, imap_username, imap_password_encrypted)
        imap.select('INBOX')
        imap.store(message_uid, '+FLAGS', '\\Seen')
        imap.close()
        imap.logout()
    except Exception:
        pass


def move_from_spam(
    imap_host: str, imap_port: int,
    imap_username: str, imap_password_encrypted: str,
    subject_contains: str
) -> int:
    """Move emails matching subject from Spam to Inbox. Returns count moved."""
    moved = 0
    try:
        imap = _connect_imap(imap_host, imap_port, imap_username, imap_password_encrypted)

        # Try common spam folder names
        spam_folders = ['[Gmail]/Spam', 'Junk', 'Spam', 'Junk Email', 'INBOX.Spam']
        for folder in spam_folders:
            try:
                status, _ = imap.select(folder)
                if status != 'OK':
                    continue

                _, msg_ids = imap.search(None, f'SUBJECT "{subject_contains}"')
                if not msg_ids[0]:
                    continue

                for msg_id in msg_ids[0].split():
                    imap.copy(msg_id, 'INBOX')
                    imap.store(msg_id, '+FLAGS', '\\Deleted')
                    moved += 1

                imap.expunge()
                break
            except Exception:
                continue

        imap.close()
        imap.logout()
    except Exception:
        pass

    return moved
