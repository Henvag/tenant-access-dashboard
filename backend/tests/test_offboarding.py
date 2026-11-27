"""Disabling a person lists their apps, logs them out where it can, and audits each app."""

import base64
import json
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
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


# ---------- sign-out connectors (Grafana, Outline, Gitea) ----------


class FakeApps:
    """Grafana, Outline and Gitea admin APIs, recording what we asked them to do."""

    def __init__(self, email: str):
        self.email = email
        self.calls: list[str] = []
        self.reject_key = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        self.calls.append(f"{request.method} {host}{path}")
        if self.reject_key:
            return httpx.Response(401, json={"message": "invalid"})
        if host == "grafana.example":
            if path == "/api/users":
                return httpx.Response(200, json=[])
            if path == "/api/users/lookup":
                return httpx.Response(200, json={"id": 7, "email": self.email})
            if path == "/api/admin/users/7/logout":
                return httpx.Response(200, json={"message": "User auth token revoked"})
        if host == "outline.example":
            if path == "/api/auth.info":
                return httpx.Response(200, json={"data": {"user": {"role": "admin"}}})
            if path == "/api/users.list":
                return httpx.Response(200, json={"data": [{"id": "o-1", "email": self.email}]})
            if path in ("/api/users.suspend", "/api/users.activate"):
                return httpx.Response(200, json={"data": {}})
        if host == "gitea.example":
            if path == "/api/v1/admin/users" and request.method == "GET":
                page = request.url.params.get("page", "1")
                users = [{"login": "anna", "email": self.email, "source_id": 2, "login_name": "anna"}]
                return httpx.Response(200, json=users if page == "1" else [])
            if path == "/api/v1/admin/users/anna":
                self.calls.append(f"BODY {request.content.decode()}")
                return httpx.Response(200, json={})
        return httpx.Response(404)


@pytest.fixture
def fake_apps(monkeypatch) -> FakeApps:
    from app.oauth import connectors

    fake = FakeApps(email="")

    async def public(_url: str) -> None:
        return None

    monkeypatch.setattr(connectors, "assert_public_host", public)
    monkeypatch.setattr(connectors, "_transport", httpx.MockTransport(fake.handler))
    return fake


async def _app_id(factory, tenant: Tenant, name: str):
    async with factory() as session:
        await set_tenant_rls(session, tenant.id)
        return await session.scalar(
            select(OAuthClient.id).where(OAuthClient.tenant_id == tenant.id, OAuthClient.name == name)
        )


async def test_saving_a_signout_key_checks_it_first(app_session_factory, client, fake_apps):
    tenant, owner, _anna = await _seed(app_session_factory)
    grafana_id = await _app_id(app_session_factory, tenant, "Grafana")
    body = {"kind": "grafana", "base_url": "https://grafana.example/", "secret": "admin:hunter2"}

    fake_apps.reject_key = True
    rejected = await client.put(f"/apps/{grafana_id}/signout", json=body, cookies=_cookie(owner))
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "signout_key_rejected"

    fake_apps.reject_key = False
    saved = await client.put(f"/apps/{grafana_id}/signout", json=body, cookies=_cookie(owner))
    assert saved.status_code == 200
    out = saved.json()
    assert out["signout_kind"] == "grafana"
    assert out["signout_base_url"] == "https://grafana.example"
    assert out["signout_key_hint"] == "admin"
    assert "hunter2" not in saved.text

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        stored = await session.get(OAuthClient, grafana_id)
        assert stored.signout_secret and "hunter2" not in stored.signout_secret

    cleared = await client.delete(f"/apps/{grafana_id}/signout", cookies=_cookie(owner))
    assert cleared.json()["signout_kind"] is None


async def test_signout_rejects_private_addresses(app_session_factory, client):
    tenant, owner, _anna = await _seed(app_session_factory)
    grafana_id = await _app_id(app_session_factory, tenant, "Grafana")
    body = {"kind": "grafana", "base_url": "https://127.0.0.1", "secret": "admin:x"}

    response = await client.put(f"/apps/{grafana_id}/signout", json=body, cookies=_cookie(owner))

    assert response.status_code == 400
    assert response.json()["detail"] == "signout_url_private"


async def test_disable_signs_out_through_connectors_and_enable_restores(
    app_session_factory, client, fake_apps, sent_logouts
):
    tenant, owner, anna = await _seed(app_session_factory)
    fake_apps.email = anna.email
    for name, kind, secret in (
        ("Grafana", "grafana", "admin:pw"),
        ("Outline", "outline", "ol_api_key"),
        ("Gitea", "gitea", "gitea_token"),
    ):
        app_id = await _app_id(app_session_factory, tenant, name)
        saved = await client.put(
            f"/apps/{app_id}/signout",
            json={"kind": kind, "base_url": f"https://{name.lower()}.example", "secret": secret},
            cookies=_cookie(owner),
        )
        assert saved.status_code == 200, saved.text

    listed = await client.get(f"/users/{anna.id}/apps", cookies=_cookie(owner))
    assert all(a["can_log_out"] for a in listed.json())

    fake_apps.calls.clear()
    disabled = await client.patch(
        f"/users/{anna.id}", json={"disabled": True}, cookies=_cookie(owner)
    )
    assert disabled.status_code == 200
    # Connectors replace back-channel logout for these apps.
    assert sent_logouts == []
    assert "POST grafana.example/api/admin/users/7/logout" in fake_apps.calls
    assert "POST outline.example/api/users.suspend" in fake_apps.calls
    assert any('"prohibit_login":true' in c for c in fake_apps.calls)

    fake_apps.calls.clear()
    enabled = await client.patch(
        f"/users/{anna.id}", json={"disabled": False}, cookies=_cookie(owner)
    )
    assert enabled.status_code == 200
    assert "POST outline.example/api/users.activate" in fake_apps.calls
    assert any('"prohibit_login":false' in c for c in fake_apps.calls)
    assert not any("grafana" in c for c in fake_apps.calls)

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        events = {
            e.event_type: e.details
            for e in await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.tenant_id == tenant.id,
                    AuditEvent.event_type.in_(
                        [AuditEventType.user_disabled, AuditEventType.user_enabled]
                    ),
                )
            )
        }
    off = {a["app"]: a["result"] for a in events[AuditEventType.user_disabled]["apps"]}
    assert off == {"Gitea": "suspended", "Grafana": "logged_out", "Outline": "suspended"}
    on = {a["app"]: a["result"] for a in events[AuditEventType.user_enabled]["apps"]}
    assert on == {"Gitea": "restored", "Outline": "restored"}
