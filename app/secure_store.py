"""Encryption at rest for the few values that must be recoverable by staff (a bank routing / account number for a refund).

Fernet (AES-128-CBC + HMAC) with a key derived from `DATA_ENCRYPTION_KEY` (preferred) or, failing that, from the application's `SECRET_KEY`.
If the `cryptography` package or a real key is missing the store REFUSES to encrypt (`available()` is False): sensitive data is never stored in the clear
as a fallback. Rotate by setting DATA_ENCRYPTION_KEY; old values then need re-entry (they are not readable with the new key).
"""

import base64
import hashlib
import os

from flask import current_app

_INSECURE = "dev-only-insecure-key"


def _key():
    raw = os.environ.get("DATA_ENCRYPTION_KEY") or (current_app.config.get("SECRET_KEY") if current_app else None) or ""
    if not raw or raw == _INSECURE:
        return None
    return base64.urlsafe_b64encode(hashlib.sha256(("og-secure-store:" + raw).encode("utf-8")).digest())


def available():
    try:
        import cryptography  # noqa: F401
    except ImportError:
        return False
    return _key() is not None


def encrypt(text):
    from cryptography.fernet import Fernet

    if not available():
        raise RuntimeError("Encryption is not available: install `cryptography` and set SECRET_KEY / DATA_ENCRYPTION_KEY.")
    return Fernet(_key()).encrypt(str(text).encode("utf-8")).decode("ascii")


def decrypt(token):
    from cryptography.fernet import Fernet, InvalidToken

    if not token or not available():
        return None
    try:
        return Fernet(_key()).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def mask_tail(value, keep=4):
    v = "".join(ch for ch in str(value or "") if ch.isalnum())
    return ("•" * max(len(v) - keep, 0) + v[-keep:]) if v else ""
