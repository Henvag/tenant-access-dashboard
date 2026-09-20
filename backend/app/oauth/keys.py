"""RS256 signing keys for the tokens we issue.

Keys live in Postgres (both Render and Fly have ephemeral disks) and are cached
in-process for a few minutes. Rotation = insert a new key, set retired_at on the
old one; JWKS keeps publishing retired keys until their tokens have expired.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from joserfc import jwt
from joserfc.jwk import KeySet, RSAKey
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SigningKey

ALG = "RS256"
_CACHE_TTL_SECONDS = 300
# Retired keys stay in JWKS long enough for any outstanding token to be verified.
_RETIRED_GRACE = timedelta(hours=24)


class _Cache:
    active: SigningKey | None = None
    jwks: dict | None = None
    loaded_at: float = 0.0

    @classmethod
    def fresh(cls) -> bool:
        return cls.active is not None and time.monotonic() - cls.loaded_at < _CACHE_TTL_SECONDS

    @classmethod
    def clear(cls) -> None:
        cls.active = None
        cls.jwks = None
        cls.loaded_at = 0.0


def _generate() -> SigningKey:
    key = RSAKey.generate_key(2048, private=True)
    return SigningKey(
        kid=key.thumbprint(),
        private_pem=key.as_pem(private=True).decode(),
        public_pem=key.as_pem(private=False).decode(),
    )


def _public_jwk(key: SigningKey) -> dict:
    jwk = RSAKey.import_key(key.public_pem).as_dict(private=False)
    jwk.update({"kid": key.kid, "use": "sig", "alg": ALG})
    return jwk


async def _load(db: AsyncSession) -> None:
    """Load (creating on first use) the active key and the public JWKS."""
    rows = list(
        (await db.scalars(select(SigningKey).order_by(SigningKey.created_at.desc()))).all()
    )
    active = next((k for k in rows if k.retired_at is None), None)
    if active is None:
        active = _generate()
        db.add(active)
        await db.commit()
        rows.insert(0, active)

    cutoff = datetime.now(UTC) - _RETIRED_GRACE
    publishable = [k for k in rows if k.retired_at is None or k.retired_at > cutoff]
    _Cache.active = active
    _Cache.jwks = {"keys": [_public_jwk(k) for k in publishable]}
    _Cache.loaded_at = time.monotonic()


async def active_key(db: AsyncSession) -> SigningKey:
    if not _Cache.fresh():
        await _load(db)
    assert _Cache.active is not None
    return _Cache.active


async def public_jwks(db: AsyncSession) -> dict:
    if not _Cache.fresh():
        await _load(db)
    assert _Cache.jwks is not None
    return _Cache.jwks


def sign(key: SigningKey, claims: dict, *, typ: str | None = None) -> str:
    header: dict = {"alg": ALG, "kid": key.kid}
    if typ:
        header["typ"] = typ
    private = RSAKey.import_key(key.private_pem, {"kid": key.kid})
    return jwt.encode(header, claims, private, algorithms=[ALG])


async def verify(db: AsyncSession, token: str, *, issuer: str) -> dict | None:
    """Verify a token we issued. Returns claims or None if invalid/expired."""
    jwks = await public_jwks(db)
    try:
        decoded = jwt.decode(token, KeySet.import_key_set(jwks), algorithms=[ALG])
        registry = jwt.JWTClaimsRegistry(iss={"essential": True, "value": issuer})
        registry.validate(decoded.claims)
    except Exception:
        return None
    return dict(decoded.claims)


def reset_cache() -> None:
    """Test hook."""
    _Cache.clear()
