from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.identity import upsert_user_from_oidc
from app.models import IdentityProvider, Tenant, UserRole


pytestmark = pytest.mark.asyncio


async def test_first_user_becomes_owner(
    app_session_factory: async_sessionmaker[AsyncSession],
):
    suffix = uuid4().hex[:8]
    domain = f"owner-{suffix}.com"
    async with app_session_factory() as session:
        tenant = Tenant(name="Owner Co", workspace_domain=domain)
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
        tenant_id = tenant.id

    async with app_session_factory() as session:
        first = await upsert_user_from_oidc(
            session,
            email=f"founder@{domain}",
            idp=IdentityProvider.google,
            oidc_sub=f"founder-{suffix}",
            display_name="Founder",
            hosted_domain=None,
        )
        first_id = first.id
        await session.commit()
        assert first.role == UserRole.admin

    async with app_session_factory() as session:
        tenant = await session.scalar(select(Tenant).where(Tenant.id == tenant_id))
        assert tenant is not None
        assert tenant.owner_user_id == first_id

    async with app_session_factory() as session:
        second = await upsert_user_from_oidc(
            session,
            email=f"member@{domain}",
            idp=IdentityProvider.google,
            oidc_sub=f"member-{suffix}",
            display_name="Member",
            hosted_domain=None,
        )
        await session.commit()
        assert second.role == UserRole.user

    async with app_session_factory() as session:
        tenant = await session.scalar(select(Tenant).where(Tenant.id == tenant_id))
        assert tenant is not None
        assert tenant.owner_user_id == first_id
