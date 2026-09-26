"""Company invite links and pending app grants by email."""

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import main
from app.auth.identity import upsert_user_from_oidc
from app.auth.rls import set_tenant_rls
from app.config import settings
from app.db import get_db
from app.models import AppGrant, IdentityProvider, PendingAppGrant, Tenant, User, UserRole
from app.oauth import keys

pytestmark = pytest.mark.asyncio


def _session_cookie(user: User) -> str:
    import base64
    import json

    from itsdangerous import TimestampSigner

    payload = {
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "role": user.role.value,
    }
    data = base64.b64encode(json.dumps(payload).encode())
    return TimestampSigner(settings.session_secret).sign(data).decode()


async def _seed(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[Tenant, User]:
    suffix = uuid4().hex[:8]
    domain = f"invite-{suffix}.com"
    async with factory() as session:
        tenant = Tenant(name=f"Invite Co {suffix}", workspace_domain=domain)
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

    async with factory() as session:
        await set_tenant_rls(session, tenant.id)
        admin = User(
            tenant_id=tenant.id,
            email=f"admin@{domain}",
            idp=IdentityProvider.google,
            oidc_sub=f"admin-{suffix}",
            role=UserRole.admin,
            display_name="Ada Admin",
        )
        session.add(admin)
        await session.flush()
        t = await session.scalar(select(Tenant).where(Tenant.id == tenant.id))
        assert t is not None
        t.owner_user_id = admin.id
        await session.commit()
        await set_tenant_rls(session, tenant.id)
        await session.refresh(admin)
    return tenant, admin


@pytest.fixture
async def client(
    app_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with app_session_factory() as session:
            yield session

    main.app.dependency_overrides[get_db] = override_db
    keys.reset_cache()
    transport = ASGITransport(app=main.app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver", follow_redirects=False
    ) as http:
        yield http
    main.app.dependency_overrides.clear()


async def test_company_invite_create_lookup_rotate(
    client: AsyncClient, app_session_factory: async_sessionmaker[AsyncSession]
):
    tenant, admin = await _seed(app_session_factory)
    cookie = {"session": _session_cookie(admin)}

    empty = await client.get("/invites/company", cookies=cookie)
    assert empty.status_code == 200 and empty.json() is None

    created = await client.post("/invites/company", cookies=cookie)
    assert created.status_code == 200
    body = created.json()
    assert body["token"]
    assert f"invite={body['token']}" in body["url"]

    again = await client.post("/invites/company", cookies=cookie)
    assert again.json()["token"] == body["token"]

    public = await client.get(f"/public/invites/{body['token']}")
    assert public.status_code == 200
    assert public.json() == {
        "tenant_name": tenant.name,
        "workspace_domain": tenant.workspace_domain,
        "has_logo": False,
    }

    rotated = await client.post("/invites/company/rotate", cookies=cookie)
    assert rotated.status_code == 200
    assert rotated.json()["token"] != body["token"]
    gone = await client.get(f"/public/invites/{body['token']}")
    assert gone.status_code == 404


async def test_pending_grant_fulfills_on_login(
    client: AsyncClient, app_session_factory: async_sessionmaker[AsyncSession]
):
    tenant, admin = await _seed(app_session_factory)
    cookie = {"session": _session_cookie(admin)}
    domain = tenant.workspace_domain

    created = await client.post(
        "/apps",
        json={
            "name": "Grafana",
            "redirect_uris": ["https://grafana.example.com/login/generic_oauth"],
            "access_policy": "assigned",
        },
        cookies=cookie,
    )
    assert created.status_code == 201
    app_id = created.json()["id"]

    pending_email = f"newbie@{domain}"
    grants = await client.put(
        f"/apps/{app_id}/grants",
        json={"user_ids": [], "emails": [pending_email]},
        cookies=cookie,
    )
    assert grants.status_code == 200
    assert grants.json()["pending_emails"] == [pending_email]
    assert grants.json()["user_ids"] == []

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        user = await upsert_user_from_oidc(
            session,
            email=pending_email,
            idp=IdentityProvider.google,
            oidc_sub=f"newbie-{uuid4().hex[:8]}",
            display_name="New Person",
            hosted_domain=domain,
        )
        await session.commit()
        user_id = user.id

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        remaining = (
            await session.scalars(
                select(PendingAppGrant).where(PendingAppGrant.email == pending_email)
            )
        ).all()
        assert remaining == []
        grant = await session.scalar(
            select(AppGrant).where(AppGrant.user_id == user_id)
        )
        assert grant is not None

    listed = await client.get(f"/apps/{app_id}/grants", cookies=cookie)
    assert listed.json() == {"user_ids": [str(user_id)], "pending_emails": []}


async def test_pending_email_must_match_tenant_domain(
    client: AsyncClient, app_session_factory: async_sessionmaker[AsyncSession]
):
    _tenant, admin = await _seed(app_session_factory)
    cookie = {"session": _session_cookie(admin)}
    created = await client.post(
        "/apps",
        json={
            "name": "Outline",
            "redirect_uris": ["https://outline.example.com/auth/oidc.callback"],
            "access_policy": "assigned",
        },
        cookies=cookie,
    )
    app_id = created.json()["id"]
    bad = await client.put(
        f"/apps/{app_id}/grants",
        json={"emails": ["outsider@other-company.com"]},
        cookies=cookie,
    )
    assert bad.status_code == 400
    assert bad.json()["detail"] == "email_domain_mismatch"
