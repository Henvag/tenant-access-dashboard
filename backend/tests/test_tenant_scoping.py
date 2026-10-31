"""Tenant isolation must hold even when the database role skips RLS.

Neon's default owner role has BYPASSRLS. These tests run the same code with a
superuser connection (RLS ignored) to check the explicit tenant filters, and
check that production refuses to start on such a role.
"""

import os
from collections.abc import AsyncIterator
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.users import list_users, patch_user
from app.auth.rls import set_tenant_rls
from app.config import settings
from app.models import IdentityProvider, Tenant, User, UserRole
from app.rls_guard import RlsBypassError, ensure_rls_enforced, role_bypasses_rls
from app.schemas.user import UserPatch

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def bypass_engine(prepared_database: None) -> AsyncIterator[AsyncEngine]:
    # conftest's DATABASE_URL is the superuser used for migrations.
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


async def _seed(factory: async_sessionmaker[AsyncSession]) -> tuple[Tenant, User, User]:
    suffix = uuid4().hex[:8]
    domain = f"scope-{suffix}.com"
    async with factory() as session:
        tenant = Tenant(name=f"Scope {suffix}", workspace_domain=domain)
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
        )
        member = User(
            tenant_id=tenant.id,
            email=f"member@{domain}",
            idp=IdentityProvider.google,
            oidc_sub=f"member-{suffix}",
            role=UserRole.user,
        )
        session.add_all([admin, member])
        await session.flush()
        tenant.owner_user_id = admin.id
        await session.commit()
        return tenant, admin, member


async def test_guard_accepts_restricted_role(app_engine: AsyncEngine) -> None:
    _, bypasses = await role_bypasses_rls(app_engine)
    assert bypasses is False
    await ensure_rls_enforced(app_engine)


async def test_guard_rejects_bypassing_role_in_production(
    bypass_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, bypasses = await role_bypasses_rls(bypass_engine)
    assert bypasses is True

    monkeypatch.setattr(settings, "environment", "development")
    await ensure_rls_enforced(bypass_engine)  # warns only

    monkeypatch.setattr(settings, "environment", "production")
    with pytest.raises(RlsBypassError):
        await ensure_rls_enforced(bypass_engine)


async def test_users_api_stays_in_tenant_without_rls(
    app_session_factory: async_sessionmaker[AsyncSession], bypass_engine: AsyncEngine
) -> None:
    tenant_a, admin_a, _ = await _seed(app_session_factory)
    tenant_b, _, member_b = await _seed(app_session_factory)

    bypass_factory = async_sessionmaker(bypass_engine, expire_on_commit=False, class_=AsyncSession)
    async with bypass_factory() as session:
        listed = await list_users(admin=admin_a, db=session)
        domains = {row.email.split("@", 1)[1] for row in listed}
        assert domains == {tenant_a.workspace_domain}

        request = SimpleNamespace(headers={}, client=None)
        with pytest.raises(HTTPException) as exc:
            await patch_user(
                member_b.id,
                UserPatch(disabled=True),
                request,  # type: ignore[arg-type]
                admin=admin_a,
                db=session,
            )
        assert exc.value.status_code == 404
        assert tenant_b.id != tenant_a.id
