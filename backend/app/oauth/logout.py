"""Offboarding: which apps a person has, and ending their sessions there.

When an admin disables or deletes a person, every app they could open or have
signed in to is listed. Apps that registered a back-channel logout URL receive a
logout_token. Other apps keep their own session until it runs out; we never
block the disable on them, but the audit entry says which apps those were.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AccessPolicy,
    AppGrant,
    AuditEvent,
    AuditEventType,
    OAuthClient,
    User,
    UserRole,
)
from app.oauth import keys
from app.config import settings

logger = logging.getLogger("app.logout")

_LOGOUT_EVENT = "http://schemas.openid.net/event/backchannel-logout"

# Result of ending a session in one app, stored in the audit entry.
LOGGED_OUT = "logged_out"
LOGOUT_FAILED = "failed"
NOT_SUPPORTED = "not_supported"


@dataclass
class PersonApp:
    client: OAuthClient
    has_access: bool
    last_used_at: datetime | None

    @property
    def can_log_out(self) -> bool:
        return bool(self.client.backchannel_logout_uri)


async def apps_for_person(db: AsyncSession, user: User) -> list[PersonApp]:
    """Apps the person can open today, or has signed in to before. RLS must be set.

    Access is judged as if the person were still active, so the list is the same
    before and after they are disabled.
    """
    clients = list(
        (
            await db.scalars(
                select(OAuthClient)
                .where(OAuthClient.tenant_id == user.tenant_id, OAuthClient.disabled_at.is_(None))
                .order_by(OAuthClient.name)
            )
        ).all()
    )
    if not clients:
        return []

    granted = set(
        (
            await db.scalars(
                select(AppGrant.client_pk).where(
                    AppGrant.user_id == user.id,
                    AppGrant.client_pk.in_([c.id for c in clients]),
                )
            )
        ).all()
    )
    # App sign-ins store the app's name in details. Latest per name.
    app_name = AuditEvent.details["app"].astext
    used_rows = await db.execute(
        select(app_name, func.max(AuditEvent.created_at))
        .where(
            AuditEvent.tenant_id == user.tenant_id,
            AuditEvent.user_id == user.id,
            AuditEvent.event_type == AuditEventType.app_login,
        )
        .group_by(app_name)
    )
    last_used = {name: when for name, when in used_rows.all() if name}

    apps: list[PersonApp] = []
    for client in clients:
        if client.access_policy == AccessPolicy.everyone:
            has_access = True
        elif client.access_policy == AccessPolicy.admins:
            has_access = user.role == UserRole.admin
        else:
            has_access = client.id in granted
        used = last_used.get(client.name)
        if has_access or used is not None:
            apps.append(PersonApp(client=client, has_access=has_access, last_used_at=used))
    return apps


async def end_app_sessions(db: AsyncSession, user: User) -> list[dict[str, str]]:
    """Send back-channel logout to the person's apps. One result per app, for the audit log."""
    apps = await apps_for_person(db, user)
    targets = [a for a in apps if a.can_log_out]
    outcome: dict[str, bool] = {}
    if targets:
        key = await keys.active_key(db)
        async with httpx.AsyncClient(timeout=3.0) as client:
            results = await asyncio.gather(
                *[_post_logout(client, key, user, a.client) for a in targets]
            )
        outcome = {a.client.client_id: ok for a, ok in zip(targets, results)}

    summary = []
    for app in apps:
        if not app.can_log_out:
            result = NOT_SUPPORTED
        elif outcome.get(app.client.client_id):
            result = LOGGED_OUT
        else:
            result = LOGOUT_FAILED
        summary.append({"app": app.client.name, "client_id": app.client.client_id, "result": result})
    return summary


def offboarding_details(actor: User, apps: list[dict[str, str]]) -> dict:
    """Audit details for a disable or delete: who did it and what happened per app."""
    return {
        "by": actor.email,
        "apps": apps,
        "logout_notified": sum(1 for a in apps if a["result"] == LOGGED_OUT),
        "logout_failed": sum(1 for a in apps if a["result"] == LOGOUT_FAILED),
    }


async def _post_logout(client: httpx.AsyncClient, key, user: User, app: OAuthClient) -> bool:
    token = _logout_token(key, user=user, audience=app.client_id)
    try:
        response = await client.post(
            app.backchannel_logout_uri or "",
            data={"logout_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    except httpx.HTTPError:
        logger.info("backchannel logout %s failed", app.client_id)
        return False
    if response.status_code < 300:
        return True
    logger.info("backchannel logout %s returned %s", app.client_id, response.status_code)
    return False


def _logout_token(key, *, user: User, audience: str) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": settings.public_origin,
        "sub": str(user.id),
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=2)).timestamp()),
        "jti": str(uuid4()),
        "events": {_LOGOUT_EVENT: {}},
    }
    return keys.sign(key, claims, typ="logout+jwt")
