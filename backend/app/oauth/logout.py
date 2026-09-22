"""OIDC back-channel logout when an admin disables a person.

Apps that registered a logout URL receive a logout_token. Apps that did not
keep their own session; this call never blocks the disable itself.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OAuthClient, User
from app.oauth import keys
from app.config import settings

logger = logging.getLogger("app.logout")

_LOGOUT_EVENT = "http://schemas.openid.net/event/backchannel-logout"


async def notify_disabled_user(db: AsyncSession, user: User) -> dict[str, int]:
    clients = list(
        (
            await db.scalars(
                select(OAuthClient).where(OAuthClient.backchannel_logout_uri.is_not(None))
            )
        ).all()
    )
    targets = [c for c in clients if c.backchannel_logout_uri and not c.disabled]
    if not targets:
        return {"notified": 0, "failed": 0}

    key = await keys.active_key(db)
    async with httpx.AsyncClient(timeout=3.0) as client:
        results = await asyncio.gather(
            *[_post_logout(client, key, user, app) for app in targets]
        )
    notified = sum(1 for ok in results if ok)
    return {"notified": notified, "failed": len(results) - notified}


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
