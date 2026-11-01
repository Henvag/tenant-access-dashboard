"""Standard Webhooks signatures (https://www.standardwebhooks.com).

Each request carries ``webhook-id``, ``webhook-timestamp`` and
``webhook-signature: v1,<base64 HMAC-SHA256>`` over ``id.timestamp.body``,
keyed with the base64 part of a ``whsec_...`` secret. Any Standard Webhooks
library (Svix, standardwebhooks on PyPI/npm) can verify them.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

SECRET_PREFIX = "whsec_"


def new_secret() -> str:
    return SECRET_PREFIX + base64.b64encode(secrets.token_bytes(32)).decode()


def _key(secret: str) -> bytes:
    raw = secret[len(SECRET_PREFIX):] if secret.startswith(SECRET_PREFIX) else secret
    return base64.b64decode(raw)


def sign(secret: str, msg_id: str, timestamp: int, body: bytes) -> str:
    to_sign = f"{msg_id}.{timestamp}.".encode() + body
    digest = hmac.new(_key(secret), to_sign, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def verify(secret: str, msg_id: str, timestamp: int, body: bytes, header: str) -> bool:
    expected = sign(secret, msg_id, timestamp, body).split(",", 1)[1]
    for part in header.split():
        version, _, value = part.partition(",")
        if version == "v1" and hmac.compare_digest(value, expected):
            return True
    return False
