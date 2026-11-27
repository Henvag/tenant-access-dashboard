"""Disabling a person lists their apps, logs them out where it can, and audits each app."""

import base64
import json
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from itsdangerous import TimestampSigner
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import main
from app.auth.rls import set_tenant_rls
from app.config import settings
from app.db import get_db
from app.models import (
    AccessPolicy,
    AppGrant,
    AuditEvent,
    AuditEventType,
    IdentityProvider,
    OAuthClient,
    Tenant,
    User,
    UserRole,
)
from app.oauth import keys, logout

pytestmark = pytest.mark.asyncio


def _cookie(user: User) -> dict[str, str]:
    payload = {"user_id": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role.value}
    data = base64.b64encode(json.dumps(payload).encode())
    return {"session": TimestampSigner(settings.session_secret).sign(data).decode()}


@pytest.fixture
async def client(
    app_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with app_session_factory() as session:
            yield session

    main.app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://testserver"
    ) as http:
        yield http
    main.app.dependency_overrides.clear()


@pytest.fixture
def sent_logouts(monkeypatch) -> list[str]:
    """Record back-channel logouts instead of posting them. Outline's endpoint is down."""
    sent: list[str] = []

    async def fake_post(_client, _key, _user, app: OAuthClient) -> bool:
        sent.append(app.name)
        return app.name != "Outline"

    monkeypatch.setattr(logout, "_post_logout", fake_post)
    return sent


def _app(tenant: Tenant, name: str, policy: AccessPolicy, logout_uri: str | None) -> OAuthClient:
    return OAuthClient(
        tenant_id=tenant.id,
        name=name,
        client_id=f"{name.lower()}-{uuid4().hex[:8]}",
        client_secret_hash="x",
        redirect_uris=[f"https://{name.lower()}.example/callback"],
        access_policy=policy,
        backchannel_logout_uri=logout_uri,
    )


async def _seed(factory: async_sessionmaker[AsyncSession]) -> tuple[Tenant, User, User]:
    suffix = uuid4().hex[:8]
    domain = f"offboard-{suffix}.no"
    async with factory() as session:
        # Signing key exists before the request, as in production.
        await keys.active_key(session)
    async with factory() as session:
        tenant = Tenant(name=f"Offboard {suffix}", workspace_domain=domain)
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

    async with factory() as session:
        await set_tenant_rls(session, tenant.id)
        owner = User(
            tenant_id=tenant.id,
            email=f"owner@{domain}",
            idp=IdentityProvider.google,
            oidc_sub=f"owner-{suffix}",
            role=UserRole.admin,
        )
        anna = User(
            tenant_id=tenant.id,
            email=f"anna@{domain}",
            idp=IdentityProvider.google,
            oidc_sub=f"anna-{suffix}",
            role=UserRole.user,
        )
        session.add_all([owner, anna])
        await session.flush()
        (await session.get(Tenant, tenant.id)).owner_user_id = owner.id

        grafana = _app(tenant, "Grafana", AccessPolicy.everyone, "https://grafana.example/logout")
        outline = _app(tenant, "Outline", AccessPolicy.assigned, "https://outline.example/logout")
        gitea = _app(tenant, "Gitea", AccessPolicy.assigned, None)
        portainer = _app(tenant, "Portainer", AccessPolicy.admins, "https://portainer.example/x")
        session.add_all([grafana, outline, gitea, portainer])
        await session.flush()
        session.add(AppGrant(tenant_id=tenant.id, client_pk=outline.id, user_id=anna.id))
        # Anna lost her Gitea grant, but signed in there earlier and may still have a session.
        session.add(
            AuditEvent(
                tenant_id=tenant.id,
                user_id=anna.id,
                email=anna.email,
                event_type=AuditEventType.app_login,
                idp=IdentityProvider.google,
                details={"app": "Gitea"},
            )
        )
        await session.flush()
        await session.refresh(owner)
        await session.refresh(anna)
        await session.commit()
    return tenant, owner, anna


async def test_lists_the_apps_a_person_has(app_session_factory, client, sent_logouts):
    _tenant, owner, anna = await _seed(app_session_factory)

    response = await client.get(f"/users/{anna.id}/apps", cookies=_cookie(owner))

    assert response.status_code == 200
    apps = {a["name"]: a for a in response.json()}
    # Portainer is admins only, so it is not hers.
    assert set(apps) == {"Gitea", "Grafana", "Outline"}
    assert apps["Grafana"]["can_log_out"] is True
    assert apps["Gitea"]["can_log_out"] is False
    assert apps["Gitea"]["has_access"] is False
    assert apps["Gitea"]["last_used_at"] is not None
    assert sent_logouts == []


async def test_disable_logs_out_and_audits_each_app(app_session_factory, client, sent_logouts):
    tenant, owner, anna = await _seed(app_session_factory)

    response = await client.patch(
        f"/users/{anna.id}", json={"disabled": True}, cookies=_cookie(owner)
    )

    assert response.status_code == 200
    assert response.json()["disabled"] is True
    assert sorted(sent_logouts) == ["Grafana", "Outline"]

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        event = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.tenant_id == tenant.id,
                AuditEvent.event_type == AuditEventType.user_disabled,
            )
        )
    assert event is not None
    assert event.email == anna.email
    assert event.details["by"] == owner.email
    results = {a["app"]: a["result"] for a in event.details["apps"]}
    assert results == {
        "Gitea": logout.NOT_SUPPORTED,
        "Grafana": logout.LOGGED_OUT,
        "Outline": logout.LOGOUT_FAILED,
    }
    assert event.details["logout_notified"] == 1
    assert event.details["logout_failed"] == 1


async def test_person_apps_is_admin_only(app_session_factory, client, sent_logouts):
    _tenant, _owner, anna = await _seed(app_session_factory)

    response = await client.get(f"/users/{anna.id}/apps", cookies=_cookie(anna))

    assert response.status_code == 403
