"""
Credential encryption using Fernet symmetric encryption.
Encrypts SMTP/IMAP passwords at rest.
"""

import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

# Derive Fernet key from SECRET_KEY (or generate one)
_secret = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
# Fernet requires exactly 32 url-safe base64-encoded bytes
import base64
import hashlib

_key = base64.urlsafe_b64encode(hashlib.sha256(_secret.encode()).digest())
_fernet = Fernet(_key)


def encrypt(plaintext: str) -> str:
    """Encrypt a string. Returns base64-encoded ciphertext."""
    if not plaintext:
        return ""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a string. Returns plaintext."""
    if not ciphertext:
        return ""
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except Exception:
        # If decryption fails (e.g., key changed), return empty
        return ""
