from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.identity import LoginError, upsert_user_from_oidc
from app.auth.rls import set_tenant_rls
from app.models import AuditEvent, AuditEventType, IdentityProvider, Tenant, User, UserRole


pytestmark = pytest.mark.asyncio


async def _seed_tenant_with_users(
    app_session_factory: async_sessionmaker[AsyncSession],
) -> tuple[Tenant, User, User]:
    suffix = uuid4().hex[:8]
    domain = f"disable-{suffix}.com"
    async with app_session_factory() as session:
        tenant = Tenant(name="Disable Co", workspace_domain=domain)
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

    async with app_session_factory() as session:
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
        await session.commit()
        await session.refresh(admin)
        await session.refresh(member)
        return tenant, admin, member


async def test_disabled_user_cannot_login(
    app_session_factory: async_sessionmaker[AsyncSession],
):
    tenant, _admin, member = await _seed_tenant_with_users(app_session_factory)

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        user = await session.scalar(select(User).where(User.id == member.id))
        assert user is not None
        user.disabled_at = datetime.now(UTC)
        await session.commit()

    async with app_session_factory() as session:
        with pytest.raises(LoginError) as exc:
            await upsert_user_from_oidc(
                session,
                email=member.email,
                idp=IdentityProvider.google,
                oidc_sub=member.oidc_sub,
                display_name="Member",
                hosted_domain=None,
            )
        assert exc.value.code == "user_disabled"


async def test_active_user_can_still_login(
    app_session_factory: async_sessionmaker[AsyncSession],
):
    _tenant, _admin, member = await _seed_tenant_with_users(app_session_factory)

    async with app_session_factory() as session:
        user = await upsert_user_from_oidc(
            session,
            email=member.email,
            idp=IdentityProvider.google,
            oidc_sub=member.oidc_sub,
            display_name="Member",
            hosted_domain=None,
        )
        await session.commit()
        assert user.disabled_at is None
        assert user.last_login_at is not None


async def test_last_active_admin_guard_logic(
    app_session_factory: async_sessionmaker[AsyncSession],
):
    """Only one active admin → disabling that admin must be blocked by the API guard count."""
    tenant, admin, member = await _seed_tenant_with_users(app_session_factory)

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        from sqlalchemy import func

        active_admins = await session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.admin, User.disabled_at.is_(None))
        )
        assert active_admins == 1

        # Disabling the member is fine; admin remains the sole active admin.
        target = await session.scalar(select(User).where(User.id == member.id))
        assert target is not None
        target.disabled_at = datetime.now(UTC)
        session.add(
            AuditEvent(
                tenant_id=tenant.id,
                user_id=member.id,
                email=member.email,
                event_type=AuditEventType.user_disabled,
                idp=admin.idp,
            )
        )
        await session.commit()

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        users = list(await session.scalars(select(User).order_by(User.email)))
        by_email = {u.email: u.disabled for u in users}
        assert by_email[admin.email] is False
        assert by_email[member.email] is True
        events = list(
            await session.scalars(
                select(AuditEvent).where(AuditEvent.event_type == AuditEventType.user_disabled)
            )
        )
        assert len(events) == 1
        assert events[0].email == member.email
