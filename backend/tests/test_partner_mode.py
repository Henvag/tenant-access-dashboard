"""Partner mode: one identity as an outside admin in several companies."""

import base64
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from itsdangerous import TimestampSigner
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request

from app import main
from app.auth.identity import LoginError, upsert_user_from_oidc
from app.auth.partners import (
    MAX_OUTSIDE_ADMINS,
    PartnerError,
    companies_for_identity,
    first_partner_user,
    join_partner_companies,
    switch_company,
)
from app.auth.rls import set_tenant_rls
from app.config import settings
from app.db import get_db
from app.models import (
    AuditEvent,
    AuditEventType,
    IdentityProvider,
    PartnerInvite,
    Tenant,
    User,
    UserRole,
)

pytestmark = pytest.mark.asyncio


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("203.0.113.9", 1)})


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


async def _invite(factory, tenant: Tenant, email: str) -> None:
    async with factory() as session:
        session.add(
            PartnerInvite(
                tenant_id=tenant.id,
                email=email,
                expires_at=datetime(2099, 1, 1, tzinfo=UTC),
            )
        )
        await session.commit()


async def _join(factory, email: str, sub: str) -> list[User]:
    async with factory() as session:
        joined = await join_partner_companies(
            session,
            email=email,
            idp=IdentityProvider.google,
            oidc_sub=sub,
            display_name="Kari",
            request=_request(),
        )
        await session.commit()
        return joined


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


async def test_consultant_joins_client_and_keeps_home_company(app_session_factory):
    firm, _ = await _company(app_session_factory, "itfirma")
    client_co, _ = await _company(app_session_factory, "bakeri")
    email = f"kari@{firm.workspace_domain}"
    sub = f"kari-{uuid4().hex[:8]}"

    # Kari signs in at home first: a normal member of her own firm.
    async with app_session_factory() as session:
        home = await upsert_user_from_oidc(
            session, email=email, idp=IdentityProvider.google, oidc_sub=sub,
            display_name="Kari", hosted_domain=firm.workspace_domain,
        )
        await session.commit()
    assert home.tenant_id == firm.id and not home.external

    await _invite(app_session_factory, client_co, email)
    joined = await _join(app_session_factory, email, sub)
    assert len(joined) == 1
    outside = joined[0]
    assert outside.tenant_id == client_co.id
    assert outside.external and outside.role == UserRole.admin
    assert outside.id != home.id

    async with app_session_factory() as session:
        companies = await companies_for_identity(session, idp=IdentityProvider.google, oidc_sub=sub)
        assert {c[0] for c in companies} == {firm.id, client_co.id}
        await set_tenant_rls(session, client_co.id)
        events = (
            await session.scalars(
                select(AuditEvent.event_type).where(AuditEvent.tenant_id == client_co.id)
            )
        ).all()
        assert AuditEventType.partner_joined in events

    # A second sign-in accepts nothing new.
    assert await _join(app_session_factory, email, sub) == []


async def test_consultant_without_home_company_lands_in_client(app_session_factory):
    client_co, _ = await _company(app_session_factory, "klient")
    email = f"ola@solo-{uuid4().hex[:6]}.no"
    sub = f"ola-{uuid4().hex[:8]}"

    async with app_session_factory() as session:
        with pytest.raises(LoginError) as err:
            await upsert_user_from_oidc(
                session, email=email, idp=IdentityProvider.google, oidc_sub=sub,
                display_name="Ola", hosted_domain=None,
            )
        assert err.value.code == "no_tenant"

    await _invite(app_session_factory, client_co, email)
    await _join(app_session_factory, email, sub)
    async with app_session_factory() as session:
        user = await first_partner_user(session, idp=IdentityProvider.google, oidc_sub=sub)
        assert user is not None and user.tenant_id == client_co.id


async def test_invite_never_attaches_a_second_identity_to_an_address(app_session_factory):
    client_co, owner = await _company(app_session_factory, "takeover")
    # The invite names the owner's own address; a different identity claims it.
    await _invite(app_session_factory, client_co, owner.email)
    joined = await _join(app_session_factory, owner.email, f"attacker-{uuid4().hex[:6]}")
    assert joined == []
    async with app_session_factory() as session:
        invite = await session.scalar(
            select(PartnerInvite).where(PartnerInvite.tenant_id == client_co.id)
        )
        assert invite.accepted_at is None


async def test_outside_admins_are_capped(app_session_factory):
    client_co, _ = await _company(app_session_factory, "cap")
    for n in range(MAX_OUTSIDE_ADMINS + 1):
        email = f"tech{n}@msp-{uuid4().hex[:6]}.no"
        await _invite(app_session_factory, client_co, email)
        joined = await _join(app_session_factory, email, f"tech{n}-{uuid4().hex[:6]}")
        assert len(joined) == (1 if n < MAX_OUTSIDE_ADMINS else 0)


async def test_outside_admins_use_no_seats(app_session_factory):
    client_co, _ = await _company(app_session_factory, "seats")
    await _invite(app_session_factory, client_co, "kari@itfirma-seats.no")
    await _join(app_session_factory, "kari@itfirma-seats.no", f"k-{uuid4().hex[:6]}")
    async with app_session_factory() as session:
        row = await session.get(Tenant, client_co.id)
        row.plan_expires_at = None
        await session.commit()
    # Free plan has 10 seats: the owner plus 9 more people still fit.
    for n in range(9):
        async with app_session_factory() as session:
            await upsert_user_from_oidc(
                session, email=f"p{n}@{client_co.workspace_domain}", idp=IdentityProvider.google,
                oidc_sub=f"p{n}-{uuid4().hex[:6]}", display_name=None,
                hosted_domain=client_co.workspace_domain,
            )
            await session.commit()


async def test_switch_requires_membership_and_respects_rls(app_session_factory):
    firm, _ = await _company(app_session_factory, "home")
    client_a, owner_a = await _company(app_session_factory, "a")
    client_b, owner_b = await _company(app_session_factory, "b")
    email = f"kari@{firm.workspace_domain}"
    sub = f"kari-{uuid4().hex[:8]}"
    async with app_session_factory() as session:
        home = await upsert_user_from_oidc(
            session, email=email, idp=IdentityProvider.google, oidc_sub=sub,
            display_name="Kari", hosted_domain=firm.workspace_domain,
        )
        await session.commit()
    await _invite(app_session_factory, client_a, email)
    await _join(app_session_factory, email, sub)

    async with app_session_factory() as session:
        target = await switch_company(session, current=home, tenant_id=client_a.id, request=_request())
        await session.commit()
    assert target.tenant_id == client_a.id and target.external

    # Not a member of B: refused, and nothing of B is visible from A's scope.
    async with app_session_factory() as session:
        with pytest.raises(PartnerError) as err:
            await switch_company(session, current=home, tenant_id=client_b.id, request=_request())
        assert err.value.code == "company_not_found"
    async with app_session_factory() as session:
        await set_tenant_rls(session, client_a.id)
        seen = (await session.scalars(select(User.id))).all()
        assert owner_b.id not in seen and owner_a.id in seen

    # Switched off by the client: switching in is refused.
    async with app_session_factory() as session:
        await set_tenant_rls(session, client_a.id)
        row = await session.get(User, target.id)
        row.disabled_at = datetime.now(UTC)
        await session.commit()
    async with app_session_factory() as session:
        with pytest.raises(PartnerError) as err:
            await switch_company(session, current=home, tenant_id=client_a.id, request=_request())
        assert err.value.code == "user_disabled"


async def test_invite_api_rules(client, app_session_factory):
    tenant, owner = await _company(app_session_factory, "api")
    cookies = _cookie(owner)

    own = await client.post("/partners/invites", json={"email": f"x@{tenant.workspace_domain}"}, cookies=cookies)
    assert own.status_code == 400 and own.json()["detail"] == "own_domain"

    member = await client.post("/partners/invites", json={"email": owner.email}, cookies=cookies)
    assert member.status_code == 400  # owner's address is on the own domain

    for n in range(MAX_OUTSIDE_ADMINS):
        ok = await client.post("/partners/invites", json={"email": f"t{n}@msp.no"}, cookies=cookies)
        assert ok.status_code == 201, ok.text
    dup = await client.post("/partners/invites", json={"email": "t0@msp.no"}, cookies=cookies)
    assert dup.status_code in (400, 409)
    full = await client.post("/partners/invites", json={"email": "extra@msp.no"}, cookies=cookies)
    assert full.status_code == 400 and full.json()["detail"] == "outside_admin_limit"

    listing = await client.get("/partners", cookies=cookies)
    assert listing.status_code == 200
    invites = listing.json()["invites"]
    assert len(invites) == MAX_OUTSIDE_ADMINS

    gone = await client.delete(f"/partners/invites/{invites[0]['id']}", cookies=cookies)
    assert gone.status_code == 204
    again = await client.post("/partners/invites", json={"email": "extra@msp.no"}, cookies=cookies)
    assert again.status_code == 201


async def test_only_the_owner_can_invite(client, app_session_factory):
    tenant, _owner = await _company(app_session_factory, "admins")
    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        admin = User(
            tenant_id=tenant.id,
            email=f"admin@{tenant.workspace_domain}",
            idp=IdentityProvider.google,
            oidc_sub=f"admin-{uuid4().hex[:6]}",
            role=UserRole.admin,
        )
        session.add(admin)
        await session.flush()
        await session.refresh(admin)
        await session.commit()
    res = await client.post("/partners/invites", json={"email": "t@msp.no"}, cookies=_cookie(admin))
    assert res.status_code == 403


async def test_companies_endpoint_and_switch(client, app_session_factory):
    firm, _ = await _company(app_session_factory, "ep")
    client_co, _ = await _company(app_session_factory, "epc")
    email = f"kari@{firm.workspace_domain}"
    sub = f"kari-{uuid4().hex[:8]}"
    async with app_session_factory() as session:
        home = await upsert_user_from_oidc(
            session, email=email, idp=IdentityProvider.google, oidc_sub=sub,
            display_name="Kari", hosted_domain=firm.workspace_domain,
        )
        await session.commit()
    await _invite(app_session_factory, client_co, email)
    await _join(app_session_factory, email, sub)

    listing = await client.get("/auth/companies", cookies=_cookie(home))
    assert listing.status_code == 200
    rows = {row["tenant_id"]: row for row in listing.json()}
    assert rows[str(firm.id)]["current"] is True
    assert str(client_co.id) in rows

    res = await client.post("/auth/switch", json={"tenant_id": str(client_co.id)}, cookies=_cookie(home))
    assert res.status_code == 200
    me = await client.get("/auth/me", cookies={"session": res.cookies["session"]})
    assert me.json()["tenant_id"] == str(client_co.id)
    assert me.json()["external"] is True

    stranger, _ = await _company(app_session_factory, "nope")
    res = await client.post("/auth/switch", json={"tenant_id": str(stranger.id)}, cookies=_cookie(home))
    assert res.status_code == 404


class _FakeGoogle:
    def __init__(self, userinfo: dict) -> None:
        self._userinfo = userinfo

    async def authorize_access_token(self, request):
        return {"userinfo": self._userinfo}


async def test_callback_signs_consultant_into_inviting_company(client, app_session_factory, monkeypatch):
    from app.api import auth as auth_api

    client_co, _ = await _company(app_session_factory, "cb")
    email = f"ola@solo-{uuid4().hex[:6]}.no"
    sub = f"ola-{uuid4().hex[:8]}"
    await _invite(app_session_factory, client_co, email)

    monkeypatch.setattr(settings, "google_client_id", "test-client")
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")
    monkeypatch.setattr(
        auth_api,
        "_oauth_client",
        lambda request, provider: _FakeGoogle(
            {"sub": sub, "email": email, "email_verified": True, "name": "Ola"}
        ),
    )
    res = await client.get("/auth/callback", follow_redirects=False)
    assert res.status_code in (302, 307)
    assert "error=" not in res.headers["location"]
    me = await client.get("/auth/me", cookies={"session": res.cookies["session"]})
    assert me.status_code == 200
    assert me.json()["tenant_id"] == str(client_co.id)
    assert me.json()["external"] is True


async def test_callback_without_company_or_invite_still_fails(client, app_session_factory, monkeypatch):
    from app.api import auth as auth_api

    monkeypatch.setattr(settings, "google_client_id", "test-client")
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")
    monkeypatch.setattr(
        auth_api,
        "_oauth_client",
        lambda request, provider: _FakeGoogle(
            {"sub": f"n-{uuid4().hex[:6]}", "email": f"n@none-{uuid4().hex[:6]}.no",
             "email_verified": True}
        ),
    )
    res = await client.get("/auth/callback", follow_redirects=False)
    assert "error=no_tenant" in res.headers["location"]
