"""Owners can delete a person or the whole company."""

import base64
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import stripe
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from itsdangerous import TimestampSigner
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request

from app import main
from app.auth.partners import companies_for_identity, join_partner_companies
from app.auth.rls import set_tenant_rls
from app.billing import stripe_service
from app.config import settings
from app.db import get_db
from app.models import (
    AuditEvent,
    AuditEventType,
    IdentityMembership,
    IdentityProvider,
    PartnerInvite,
    Tenant,
    User,
    UserRole,
    WebhookDelivery,
    WebhookEndpoint,
)

pytestmark = pytest.mark.asyncio


def _request() -> Request:
    return Request(
        {"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("203.0.113.9", 1)}
    )


def _cookie(user: User) -> dict[str, str]:
    payload = {"user_id": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role.value}
    data = base64.b64encode(json.dumps(payload).encode())
    return {"session": TimestampSigner(settings.session_secret).sign(data).decode()}


async def _company(factory: async_sessionmaker[AsyncSession], prefix: str) -> tuple[Tenant, User]:
    suffix = uuid4().hex[:8]
    domain = f"{prefix}-{suffix}.no"
    async with factory() as session:
        tenant = Tenant(name=f"{prefix} {suffix}", workspace_domain=domain)
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
        session.add(owner)
        await session.flush()
        row = await session.get(Tenant, tenant.id)
        row.owner_user_id = owner.id
        await session.refresh(owner)
        await session.commit()
    return tenant, owner


async def _person(factory, tenant: Tenant, name: str, role: UserRole = UserRole.user) -> User:
    async with factory() as session:
        await set_tenant_rls(session, tenant.id)
        user = User(
            tenant_id=tenant.id,
            email=f"{name}@{tenant.workspace_domain}",
            idp=IdentityProvider.google,
            oidc_sub=f"{name}-{uuid4().hex[:8]}",
            role=role,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        await session.commit()
        return user


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


async def test_owner_deletes_person_and_audit_keeps_events_without_their_address(
    app_session_factory, client
):
    tenant, owner = await _company(app_session_factory, "slett")
    member = await _person(app_session_factory, tenant, "ola")
    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        session.add_all(
            [
                AuditEvent(
                    tenant_id=tenant.id,
                    user_id=member.id,
                    email=member.email,
                    event_type=AuditEventType.login,
                    idp=IdentityProvider.google,
                    ip_address="198.51.100.7",
                    user_agent="Firefox",
                ),
                AuditEvent(
                    tenant_id=tenant.id,
                    user_id=None,
                    email=member.email,
                    event_type=AuditEventType.login_failed,
                    idp=IdentityProvider.google,
                    error_code="user_disabled",
                    ip_address="198.51.100.7",
                ),
                # The member acted on the owner: their address sits in details.
                AuditEvent(
                    tenant_id=tenant.id,
                    user_id=owner.id,
                    email=owner.email,
                    event_type=AuditEventType.app_access_granted,
                    idp=IdentityProvider.google,
                    ip_address="192.0.2.1",
                    details={"app": "Grafana", "by": member.email},
                ),
            ]
        )
        endpoint = WebhookEndpoint(
            tenant_id=tenant.id,
            url="https://hooks.example.com/in",
            secret_encrypted="x",
            secret_hint="abcd",
        )
        session.add(endpoint)
        await session.flush()
        session.add_all(
            [
                WebhookDelivery(
                    tenant_id=tenant.id,
                    endpoint_id=endpoint.id,
                    event_type="login",
                    payload={
                        "type": "login",
                        "data": {"email": member.email, "ip_address": "198.51.100.7"},
                    },
                    status="succeeded",
                ),
                WebhookDelivery(
                    tenant_id=tenant.id,
                    endpoint_id=endpoint.id,
                    event_type="app_access_granted",
                    payload={
                        "type": "app_access_granted",
                        "data": {"email": owner.email, "details": {"by": member.email}},
                    },
                    status="pending",
                ),
            ]
        )
        session.add(
            PartnerInvite(
                tenant_id=tenant.id,
                email=member.email,
                expires_at=datetime(2099, 1, 1, tzinfo=UTC),
            )
        )
        await session.commit()

    response = await client.delete(f"/users/{member.id}", cookies=_cookie(owner))
    assert response.status_code == 204, response.text

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        assert await session.get(User, member.id) is None
        events = list(
            (
                await session.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.tenant_id == tenant.id)
                    .order_by(AuditEvent.created_at)
                )
            ).all()
        )
        by_type = {e.event_type: e for e in events}
        for kind in (AuditEventType.login, AuditEventType.login_failed):
            row = by_type[kind]
            assert row.email == ""
            assert row.ip_address is None and row.user_agent is None
        grant = by_type[AuditEventType.app_access_granted]
        assert grant.email == owner.email
        assert grant.ip_address == "192.0.2.1"
        assert grant.details == {"app": "Grafana", "by": ""}
        deleted = by_type[AuditEventType.user_deleted]
        assert deleted.email == owner.email
        assert all(member.email not in json.dumps(e.details or {}) for e in events)

        payloads = [
            d.payload
            for d in (
                await session.scalars(
                    select(WebhookDelivery).where(WebhookDelivery.tenant_id == tenant.id)
                )
            ).all()
        ]
        assert member.email not in json.dumps(payloads)
        login_payload = next(p for p in payloads if p["type"] == "login")
        assert login_payload["data"] == {"email": ""}

        invites = await session.scalar(
            select(func.count())
            .select_from(PartnerInvite)
            .where(PartnerInvite.tenant_id == tenant.id)
        )
        assert invites == 0

    # Their open session ends with the row.
    me = await client.get("/auth/me", cookies=_cookie(member))
    assert me.status_code == 401


async def test_only_the_owner_deletes_people_and_never_themselves(app_session_factory, client):
    tenant, owner = await _company(app_session_factory, "regel")
    admin = await _person(app_session_factory, tenant, "kari", UserRole.admin)
    member = await _person(app_session_factory, tenant, "per")
    _, other_owner = await _company(app_session_factory, "annet")

    response = await client.delete(f"/users/{member.id}", cookies=_cookie(admin))
    assert response.status_code == 403
    assert response.json()["detail"] == "owner_required"

    response = await client.delete(f"/users/{owner.id}", cookies=_cookie(owner))
    assert response.status_code == 400
    assert response.json()["detail"] == "cannot_delete_owner"

    # Another company's person is not found, not deleted.
    response = await client.delete(f"/users/{other_owner.id}", cookies=_cookie(owner))
    assert response.status_code == 404

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        assert await session.get(User, member.id) is not None


async def test_deleting_an_outside_admin_leaves_their_other_companies(
    app_session_factory, client
):
    home, _ = await _company(app_session_factory, "fjordit")
    consultant = await _person(app_session_factory, home, "kari", UserRole.admin)
    client_co, client_owner = await _company(app_session_factory, "bakeri")
    async with app_session_factory() as session:
        session.add(
            PartnerInvite(
                tenant_id=client_co.id,
                email=consultant.email,
                expires_at=datetime(2099, 1, 1, tzinfo=UTC),
            )
        )
        await session.commit()
    async with app_session_factory() as session:
        # Her home row is remembered at sign-in; the invite adds the client.
        session.add(
            IdentityMembership(
                idp=consultant.idp,
                oidc_sub=consultant.oidc_sub,
                tenant_id=home.id,
                user_id=consultant.id,
            )
        )
        await session.commit()
        joined = await join_partner_companies(
            session,
            email=consultant.email,
            idp=consultant.idp,
            oidc_sub=consultant.oidc_sub,
            display_name="Kari",
            request=_request(),
        )
        await session.commit()
    assert len(joined) == 1
    outside_row = joined[0]

    response = await client.delete(f"/users/{outside_row.id}", cookies=_cookie(client_owner))
    assert response.status_code == 204, response.text

    async with app_session_factory() as session:
        companies = await companies_for_identity(
            session, idp=consultant.idp, oidc_sub=consultant.oidc_sub
        )
        assert [c[0] for c in companies] == [home.id]
        await set_tenant_rls(session, home.id)
        assert await session.get(User, consultant.id) is not None


async def test_owner_deletes_the_whole_company(app_session_factory, client):
    tenant, owner = await _company(app_session_factory, "borte")
    member = await _person(app_session_factory, tenant, "ola")
    other, other_owner = await _company(app_session_factory, "blir")
    # A consultant from the other company is an outside admin here.
    async with app_session_factory() as session:
        session.add(
            PartnerInvite(
                tenant_id=tenant.id,
                email=other_owner.email,
                expires_at=datetime(2099, 1, 1, tzinfo=UTC),
            )
        )
        await session.commit()
        await join_partner_companies(
            session,
            email=other_owner.email,
            idp=other_owner.idp,
            oidc_sub=other_owner.oidc_sub,
            display_name=None,
            request=_request(),
        )
        await session.commit()
    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        session.add(
            AuditEvent(
                tenant_id=tenant.id,
                user_id=member.id,
                email=member.email,
                event_type=AuditEventType.login,
                idp=IdentityProvider.google,
            )
        )
        await session.commit()

    response = await client.request(
        "DELETE", "/company", json={"confirm": "wrong.no"}, cookies=_cookie(owner)
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "confirm_mismatch"

    response = await client.request(
        "DELETE", "/company", json={"confirm": "borte"}, cookies=_cookie(member)
    )
    assert response.status_code == 403

    response = await client.request(
        "DELETE",
        "/company",
        json={"confirm": f"  {tenant.workspace_domain.upper()} "},
        cookies=_cookie(owner),
    )
    assert response.status_code == 204, response.text

    async with app_session_factory() as session:
        assert await session.get(Tenant, tenant.id) is None
        await set_tenant_rls(session, tenant.id)
        users = await session.scalar(
            select(func.count()).select_from(User).where(User.tenant_id == tenant.id)
        )
        events = await session.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.tenant_id == tenant.id)
        )
        assert users == 0 and events == 0
        memberships = await session.scalar(
            select(func.count())
            .select_from(IdentityMembership)
            .where(IdentityMembership.tenant_id == tenant.id)
        )
        assert memberships == 0
        assert await session.get(Tenant, other.id) is not None
        await set_tenant_rls(session, other.id)
        assert await session.get(User, other_owner.id) is not None

    me = await client.get("/auth/me", cookies=_cookie(owner))
    assert me.status_code == 401


async def test_company_stays_when_billing_cannot_be_stopped(
    app_session_factory, client, monkeypatch
):
    tenant, owner = await _company(app_session_factory, "betaler")
    async with app_session_factory() as session:
        row = await session.get(Tenant, tenant.id)
        row.stripe_subscription_id = f"sub_{uuid4().hex[:12]}"
        await session.commit()

    def refuse(_tenant):
        raise HTTPException(status_code=502, detail="billing_cancel_failed")

    monkeypatch.setattr(stripe_service, "cancel_subscription", refuse)
    response = await client.request(
        "DELETE", "/company", json={"confirm": tenant.workspace_domain}, cookies=_cookie(owner)
    )
    assert response.status_code == 502
    async with app_session_factory() as session:
        assert await session.get(Tenant, tenant.id) is not None

    cancelled: list[str] = []
    monkeypatch.setattr(
        stripe_service,
        "cancel_subscription",
        lambda t: cancelled.append(t.stripe_subscription_id),
    )
    response = await client.request(
        "DELETE", "/company", json={"confirm": tenant.workspace_domain}, cookies=_cookie(owner)
    )
    assert response.status_code == 204
    assert len(cancelled) == 1


async def test_cancel_subscription_tolerates_one_already_gone(monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_x")
    tenant = Tenant(name="x", workspace_domain="x.no", stripe_subscription_id="sub_1")

    def gone(_sub_id):
        raise stripe.InvalidRequestError("No such subscription", param="id")

    monkeypatch.setattr(stripe.Subscription, "cancel", gone)
    stripe_service.cancel_subscription(tenant)

    def down(_sub_id):
        raise stripe.APIConnectionError("network")

    monkeypatch.setattr(stripe.Subscription, "cancel", down)
    with pytest.raises(HTTPException) as caught:
        stripe_service.cancel_subscription(tenant)
    assert caught.value.detail == "billing_cancel_failed"

    # No subscription (free plan, or a Vipps year): nothing to call.
    stripe_service.cancel_subscription(Tenant(name="y", workspace_domain="y.no"))
