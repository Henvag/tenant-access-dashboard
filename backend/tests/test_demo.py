"""Public read-only demo: sign-in without an IdP, sample data, and no writes."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import main
from app.auth.audit import record_app_event
from app.auth.rls import set_tenant_rls
from app.db import get_db
from app.demo import DEMO_TENANT_ID, SEED_MARKER, database_enforces_rls, ensure_demo_owner
from app.models import AuditEvent, AuditEventType, IdentityProvider, Tenant, User
from app.oauth.service import role_claim
from app.rate_limit import auth_limiter
from tests.conftest import _admin_url

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def client(
    app_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with app_session_factory() as session:
            yield session

    main.app.dependency_overrides[get_db] = override_db
    auth_limiter.reset()
    transport = ASGITransport(app=main.app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver", follow_redirects=False
    ) as http:
        yield http
    main.app.dependency_overrides.pop(get_db, None)


async def _enter_demo(http: AsyncClient) -> None:
    response = await http.post("/auth/demo")
    assert response.status_code == 303
    assert response.cookies.get("session")


async def test_demo_signs_in_as_owner_of_sample_company(client: AsyncClient):
    await _enter_demo(client)

    me = (await client.get("/auth/me")).json()
    assert me["demo"] is True
    assert me["tenant_name"] == "Nordlys Analytics"
    assert me["workspace_domain"] == "nordlys.example"
    assert me["is_owner"] is True
    assert me["plan"] == "team"

    people = (await client.get("/users")).json()
    assert len(people) == 9
    assert sum(1 for p in people if p["disabled"]) == 1

    apps = {a["name"]: a for a in (await client.get("/apps")).json()}
    assert set(apps) == {"Grafana", "Outline", "Gitea"}
    assert apps["Outline"]["access_policy"] == "assigned"
    assert apps["Outline"]["grant_count"] == 4
    # Nothing in the demo points at a real relying party.
    for app in apps.values():
        assert app["launch_url"] is None
        assert all(".nordlys.example/" in uri for uri in app["redirect_uris"])

    events = (await client.get("/audit")).json()
    types = {e["event_type"] for e in events}
    assert {"login", "app_login", "app_login_denied", "role_changed"} <= types


async def test_demo_session_cannot_write(client: AsyncClient):
    await _enter_demo(client)
    people = (await client.get("/users")).json()
    member = next(p for p in people if p["role"] == "user" and not p["disabled"])

    attempts = [
        client.patch(f"/users/{member['id']}", json={"role": "admin"}),
        client.post(
            "/apps",
            json={
                "name": "Evil",
                "redirect_uris": ["https://evil.example/cb"],
                "launch_url": None,
                "access_policy": "everyone",
            },
        ),
        client.put("/ask", json={"api_key": "AIza-test-key-1234"}),
        client.post("/billing/checkout", json={"plan": "business"}),
        client.post("/invites/company/rotate"),
    ]
    for attempt in attempts:
        response = await attempt
        assert response.status_code == 403, response.text
        assert response.json()["detail"] == "demo_read_only"

    # Entering the demo again is the one write a demo session may make.
    await _enter_demo(client)


async def test_demo_seed_is_idempotent(
    client: AsyncClient, app_session_factory: async_sessionmaker[AsyncSession]
):
    await _enter_demo(client)
    await _enter_demo(client)
    async with app_session_factory() as session:
        await set_tenant_rls(session, DEMO_TENANT_ID)
        count = await session.scalar(select(func.count()).select_from(User))
        tenants = await session.scalar(
            select(func.count()).select_from(Tenant).where(Tenant.id == DEMO_TENANT_ID)
        )
    assert count == 9
    assert tenants == 1


async def test_refresh_keeps_activity_recent_and_prunes_visitor_rows(
    app_session_factory: async_sessionmaker[AsyncSession],
):
    async with app_session_factory() as session:
        await ensure_demo_owner(session)
        await session.commit()

    # Age everything by a week and add an old visitor row.
    async with app_session_factory() as session:
        await set_tenant_rls(session, DEMO_TENANT_ID)
        await session.execute(
            update(AuditEvent).values(created_at=AuditEvent.created_at - timedelta(days=7))
        )
        stale = AuditEvent(
            tenant_id=DEMO_TENANT_ID,
            email="ingrid.berg@nordlys.example",
            event_type=AuditEventType.app_login,
            idp=IdentityProvider.google,
            details={"app": "Grafana"},
            created_at=datetime.now(UTC) - timedelta(days=2),
        )
        session.add(stale)
        await session.flush()
        stale_id = stale.id
        await session.commit()

    async with app_session_factory() as session:
        await ensure_demo_owner(session)
        await session.commit()

    async with app_session_factory() as session:
        await set_tenant_rls(session, DEMO_TENANT_ID)
        newest = await session.scalar(
            select(func.max(AuditEvent.created_at)).where(AuditEvent.user_agent == SEED_MARKER)
        )
        gone = await session.scalar(select(AuditEvent).where(AuditEvent.id == stale_id))
    assert newest is not None
    assert datetime.now(UTC) - newest < timedelta(hours=1)
    assert gone is None


async def test_demo_visitors_leave_no_ip_and_relying_parties_see_a_member(
    app_session_factory: async_sessionmaker[AsyncSession],
):
    async with app_session_factory() as session:
        owner = await ensure_demo_owner(session)
        request = SimpleNamespace(
            headers={"user-agent": "Visitor Browser", "x-forwarded-for": "198.51.100.7"},
            client=SimpleNamespace(host="198.51.100.7"),
        )
        event = await record_app_event(
            session,
            tenant_id=DEMO_TENANT_ID,
            event_type=AuditEventType.app_login,
            email=owner.email,
            user_id=owner.id,
            idp=owner.idp,
            request=request,
            details={"app": "Grafana"},
        )
        assert event.ip_address is None
        assert event.user_agent is None
        tenant = await session.scalar(select(Tenant).where(Tenant.id == DEMO_TENANT_ID))
        assert role_claim(owner, tenant) == "member"
        # The same admin in any other company keeps their real role claim.
        assert role_claim(owner, SimpleNamespace(id=uuid4(), owner_user_id=None)) == "admin"
        await session.rollback()


async def test_demo_refuses_to_start_when_the_role_bypasses_rls(
    client: AsyncClient, prepared_database: None
):
    """The test superuser stands in for a production role with BYPASSRLS."""
    engine = create_async_engine(_admin_url(), poolclass=NullPool)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as session:
            assert await database_enforces_rls(session) is False

        async def superuser_db() -> AsyncIterator[AsyncSession]:
            async with factory() as session:
                yield session

        main.app.dependency_overrides[get_db] = superuser_db
        response = await client.post("/auth/demo")
        assert response.status_code == 302
        assert "error=demo_unavailable" in response.headers["location"]
        assert not response.cookies.get("session")
    finally:
        await engine.dispose()


async def test_app_role_enforces_rls(app_session_factory: async_sessionmaker[AsyncSession]):
    async with app_session_factory() as session:
        assert await database_enforces_rls(session) is True
