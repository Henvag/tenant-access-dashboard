from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.rls import set_tenant_rls
from app.models import (
    AuditEvent,
    AuditEventType,
    IdentityProvider,
    Tenant,
    User,
    UserRole,
)


pytestmark = pytest.mark.asyncio


async def test_rls_hides_other_tenant_users(app_session_factory: async_sessionmaker[AsyncSession]):
    suffix = uuid4().hex[:8]
    async with app_session_factory() as session:
        acme = Tenant(name="Acme", workspace_domain=f"acme-{suffix}.com")
        beta = Tenant(name="Beta", workspace_domain=f"beta-{suffix}.com")
        session.add_all([acme, beta])
        await session.commit()
        await session.refresh(acme)
        await session.refresh(beta)

    async with app_session_factory() as session:
        await set_tenant_rls(session, acme.id)
        session.add(
            User(
                tenant_id=acme.id,
                email=f"ada@{acme.workspace_domain}",
                idp=IdentityProvider.google,
                oidc_sub=f"sub-acme-{suffix}",
                role=UserRole.admin,
            )
        )
        await session.commit()

    async with app_session_factory() as session:
        await set_tenant_rls(session, beta.id)
        session.add(
            User(
                tenant_id=beta.id,
                email=f"bob@{beta.workspace_domain}",
                idp=IdentityProvider.google,
                oidc_sub=f"sub-beta-{suffix}",
                role=UserRole.admin,
            )
        )
        await session.commit()

    async with app_session_factory() as session:
        await set_tenant_rls(session, acme.id)
        emails = set(await session.scalars(select(User.email)))
        assert emails == {f"ada@{acme.workspace_domain}"}

    async with app_session_factory() as session:
        await set_tenant_rls(session, beta.id)
        emails = set(await session.scalars(select(User.email)))
        assert emails == {f"bob@{beta.workspace_domain}"}


async def test_insert_without_tenant_context_is_rejected(
    app_session_factory: async_sessionmaker[AsyncSession],
):
    suffix = uuid4().hex[:8]
    async with app_session_factory() as session:
        tenant = Tenant(name="Lone", workspace_domain=f"lone-{suffix}.com")
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

    async with app_session_factory() as session:
        session.add(
            User(
                tenant_id=tenant.id,
                email=f"eve@{tenant.workspace_domain}",
                idp=IdentityProvider.google,
                oidc_sub=f"sub-lone-{suffix}",
                role=UserRole.user,
            )
        )
        with pytest.raises(DBAPIError):
            await session.commit()


async def test_rls_hides_other_tenant_audit_events(
    app_session_factory: async_sessionmaker[AsyncSession],
):
    suffix = uuid4().hex[:8]
    async with app_session_factory() as session:
        acme = Tenant(name="Acme", workspace_domain=f"acme-audit-{suffix}.com")
        beta = Tenant(name="Beta", workspace_domain=f"beta-audit-{suffix}.com")
        session.add_all([acme, beta])
        await session.commit()
        await session.refresh(acme)
        await session.refresh(beta)

    async with app_session_factory() as session:
        await set_tenant_rls(session, acme.id)
        session.add(
            AuditEvent(
                tenant_id=acme.id,
                email=f"ada@{acme.workspace_domain}",
                event_type=AuditEventType.login,
                idp=IdentityProvider.google,
            )
        )
        await session.commit()

    async with app_session_factory() as session:
        await set_tenant_rls(session, beta.id)
        session.add(
            AuditEvent(
                tenant_id=beta.id,
                email=f"bob@{beta.workspace_domain}",
                event_type=AuditEventType.login,
                idp=IdentityProvider.microsoft,
            )
        )
        await session.commit()

    async with app_session_factory() as session:
        await set_tenant_rls(session, acme.id)
        emails = set(await session.scalars(select(AuditEvent.email)))
        assert emails == {f"ada@{acme.workspace_domain}"}

    async with app_session_factory() as session:
        await set_tenant_rls(session, beta.id)
        emails = set(await session.scalars(select(AuditEvent.email)))
        assert emails == {f"bob@{beta.workspace_domain}"}


async def test_app_role_is_not_superuser(app_engine):
    async with app_engine.connect() as connection:
        is_super = await connection.scalar(text("SELECT current_setting('is_superuser')"))
        bypass = await connection.scalar(
            text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
        )
    assert is_super == "off"
    assert bypass is False
