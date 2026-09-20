"""Provider-side helpers: client credentials, PKCE, auth codes, access decisions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AccessPolicy, AppGrant, OAuthClient, OAuthCode, Tenant, User, UserRole

CODE_TTL = timedelta(seconds=60)
TOKEN_TTL = timedelta(hours=1)
SUPPORTED_SCOPES = {"openid", "email", "profile"}


# ---------- credentials ----------


def new_client_id() -> str:
    return "tad_" + secrets.token_hex(16)


def new_client_secret() -> str:
    return secrets.token_urlsafe(40)


def hash_secret(secret: str) -> str:
    # Secrets are 320-bit random strings; a plain SHA-256 is enough and lets us
    # verify without a salt lookup. Not appropriate for user-chosen passwords.
    return hashlib.sha256(secret.encode()).hexdigest()


def verify_secret(secret: str, secret_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(secret), secret_hash)


# ---------- PKCE ----------


def pkce_matches(verifier: str, challenge: str, method: str) -> bool:
    if method != "S256" or not (43 <= len(verifier) <= 128):
        return False
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return hmac.compare_digest(expected, challenge)


# ---------- access decisions ----------


def role_claim(user: User, tenant: Tenant) -> str:
    if tenant.owner_user_id is not None and user.id == tenant.owner_user_id:
        return "owner"
    return "admin" if user.role == UserRole.admin else "member"


async def access_denial_reason(
    db: AsyncSession, *, client: OAuthClient, user: User
) -> str | None:
    """None when the user may sign in to this app, otherwise a short reason code."""
    if client.disabled:
        return "app_disabled"
    if user.disabled:
        return "user_disabled"
    if user.tenant_id != client.tenant_id:
        return "wrong_tenant"
    if client.access_policy == AccessPolicy.everyone:
        return None
    if client.access_policy == AccessPolicy.admins:
        return None if user.role == UserRole.admin else "admins_only"
    granted = await db.scalar(
        select(
            exists().where(AppGrant.client_pk == client.id, AppGrant.user_id == user.id)
        )
    )
    return None if granted else "not_assigned"


async def can_access(db: AsyncSession, *, client: OAuthClient, user: User) -> bool:
    return await access_denial_reason(db, client=client, user=user) is None


# ---------- authorization codes ----------


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def issue_code(
    db: AsyncSession,
    *,
    client: OAuthClient,
    user: User,
    redirect_uri: str,
    scope: str,
    nonce: str | None,
    code_challenge: str,
    code_challenge_method: str,
) -> str:
    code = secrets.token_urlsafe(32)
    db.add(
        OAuthCode(
            tenant_id=client.tenant_id,
            client_pk=client.id,
            user_id=user.id,
            code_hash=_hash_code(code),
            redirect_uri=redirect_uri,
            scope=scope,
            nonce=nonce,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=datetime.now(UTC) + CODE_TTL,
        )
    )
    await db.flush()
    return code


async def consume_code(
    db: AsyncSession,
    *,
    code: str,
    client: OAuthClient,
    redirect_uri: str,
    code_verifier: str = "",
) -> OAuthCode | None:
    """Atomically mark a code used. Returns None for any mismatch (caller answers invalid_grant)."""
    row = await db.scalar(
        select(OAuthCode).where(OAuthCode.code_hash == _hash_code(code)).with_for_update()
    )
    if row is None:
        return None
    now = datetime.now(UTC)
    pkce_ok = (
        True
        if not row.code_challenge
        else pkce_matches(code_verifier, row.code_challenge, row.code_challenge_method)
    )
    if (
        row.client_pk != client.id
        or row.used_at is not None
        or row.expires_at < now
        or row.redirect_uri != redirect_uri
        or not pkce_ok
    ):
        # Burn the code on any failed attempt so it cannot be retried.
        row.used_at = now
        await db.flush()
        return None
    row.used_at = now
    await db.flush()
    return row


async def purge_expired_codes(db: AsyncSession, tenant_id: UUID) -> None:
    """Best-effort cleanup for the current tenant; called opportunistically."""
    from sqlalchemy import delete

    await db.execute(
        delete(OAuthCode).where(
            OAuthCode.tenant_id == tenant_id,
            OAuthCode.expires_at < datetime.now(UTC) - timedelta(minutes=10),
        )
    )
