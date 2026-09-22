"""Billing plans, status, and seat/app limits (Stripe optional)."""

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import main
from app.auth.identity import LoginError, upsert_user_from_oidc
from app.auth.rls import set_tenant_rls
from app.billing.plans import PlanId, effective_plan_id, limits_for
from app.config import settings
from app.db import get_db
from app.models import IdentityProvider, Tenant, TenantPlan, User, UserRole
from app.oauth import keys


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
    domain = f"bill-{suffix}.com"
    async with factory() as session:
        tenant = Tenant(name=f"Bill Co {suffix}", workspace_domain=domain)
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

    async with factory() as session:
        await set_tenant_rls(session, tenant.id)
        admin = User(
            tenant_id=tenant.id,
            email=f"owner@{domain}",
            idp=IdentityProvider.google,
            oidc_sub=f"owner-{suffix}",
            role=UserRole.admin,
            display_name="Owner",
        )
        session.add(admin)
        await session.flush()
        t = await session.scalar(select(Tenant).where(Tenant.id == tenant.id))
        assert t is not None
        t.owner_user_id = admin.id
        await session.commit()
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
    ) as ac:
        yield ac
    main.app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_plans_public(client: AsyncClient) -> None:
    res = await client.get("/billing/plans")
    assert res.status_code == 200
    plans = {p["id"]: p for p in res.json()}
    assert plans["free"]["max_apps"] == 3
    assert plans["team"]["price_monthly_nok"] == 99
    assert plans["business"]["max_users"] == 250


@pytest.mark.asyncio
async def test_billing_status_and_me_plan(
    client: AsyncClient,
    app_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant, admin = await _seed(app_session_factory)
    cookie = _session_cookie(admin)

    status = await client.get("/billing/status", cookies={"session": cookie})
    assert status.status_code == 200
    body = status.json()
    assert body["plan"] == "free"
    assert body["users_used"] == 1
    assert body["stripe_configured"] is False
    assert body["can_manage"] is True

    me = await client.get("/auth/me", cookies={"session": cookie})
    assert me.status_code == 200
    assert me.json()["plan"] == "free"
    assert me.json()["max_apps"] == limits_for(PlanId.free).max_apps

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        t = await session.get(Tenant, tenant.id)
        assert t is not None
        t.plan = TenantPlan.team
        await session.commit()

    me2 = await client.get("/auth/me", cookies={"session": cookie})
    assert me2.json()["plan"] == "team"
    assert me2.json()["max_apps"] == limits_for(PlanId.team).max_apps


@pytest.mark.asyncio
async def test_checkout_requires_stripe(
    client: AsyncClient,
    app_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, admin = await _seed(app_session_factory)
    cookie = _session_cookie(admin)
    res = await client.post(
        "/billing/checkout",
        cookies={"session": cookie},
        json={"plan": "team", "method": "card_monthly"},
    )
    assert res.status_code == 503
    assert res.json()["detail"] == "stripe_unconfigured"


@pytest.mark.asyncio
async def test_seat_limit_blocks_new_user(
    app_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    suffix = uuid4().hex[:8]
    domain = f"seats-{suffix}.com"
    async with app_session_factory() as session:
        tenant = Tenant(name="Seats", workspace_domain=domain, plan=TenantPlan.free)
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

    # Fill free seats (max 10).
    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        for i in range(10):
            session.add(
                User(
                    tenant_id=tenant.id,
                    email=f"u{i}@{domain}",
                    idp=IdentityProvider.google,
                    oidc_sub=f"sub-{suffix}-{i}",
                    role=UserRole.admin if i == 0 else UserRole.user,
                )
            )
        await session.commit()

    async with app_session_factory() as session:
        with pytest.raises(LoginError) as exc:
            await upsert_user_from_oidc(
                session,
                email=f"overflow@{domain}",
                idp=IdentityProvider.google,
                oidc_sub=f"overflow-{suffix}",
                display_name="Too Many",
                hosted_domain=domain,
            )
        assert exc.value.code == "seat_limit_reached"


def test_effective_plan_expired_prepaid() -> None:
    from datetime import UTC, datetime, timedelta

    class Fake:
        plan = TenantPlan.team
        plan_expires_at = datetime.now(UTC) - timedelta(days=1)
        stripe_subscription_id = None

    assert effective_plan_id(Fake()) == PlanId.free


def test_retention_cutoff_follows_plan() -> None:
    from datetime import UTC, datetime

    from app.billing.plans import retention_cutoff

    moment = datetime(2026, 9, 23, tzinfo=UTC)

    class Fake:
        def __init__(self, plan: TenantPlan) -> None:
            self.plan = plan
            self.plan_expires_at = None
            self.stripe_subscription_id = "sub_123" if plan != TenantPlan.free else None

    assert retention_cutoff(Fake(TenantPlan.free), now=moment) == datetime(2026, 9, 9, tzinfo=UTC)
    assert retention_cutoff(Fake(TenantPlan.team), now=moment) == datetime(2026, 6, 25, tzinfo=UTC)
