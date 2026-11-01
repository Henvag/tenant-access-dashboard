"""Encrypt company API keys at rest.

The key comes from DATA_ENCRYPTION_KEY, kept separate from SESSION_SECRET so
rotating the cookie key doesn't destroy stored API keys and one leaked value
doesn't expose both. Values encrypted earlier with the session-derived key
still decrypt, and are re-encrypted with the data key the next time they're
saved.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.config import settings


def _derive(secret: str) -> Fernet:
    digest = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _fernet() -> MultiFernet:
    keys: list[Fernet] = []
    if settings.data_encryption_key:
        keys.append(_derive(settings.data_encryption_key))
    # Legacy: before DATA_ENCRYPTION_KEY existed, the session secret was the key.
    keys.append(_derive(settings.session_secret))
    return MultiFernet(keys)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("agent_secret_unreadable") from exc


def key_hint(value: str) -> str:
    cleaned = value.strip()
    return cleaned[-4:] if cleaned else ""
