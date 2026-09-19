import pytest
from sqlalchemy import select

from app.auth.audit import record_login_failure
from app.auth.rls import set_tenant_rls
from app.models import AuditEvent, AuditEventType, IdentityProvider, Tenant
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


pytestmark = pytest.mark.asyncio


class _FakeRequest:
    def __init__(self) -> None:
        self.headers = {"user-agent": "pytest"}
        self.client = type("C", (), {"host": "127.0.0.1"})()


async def test_record_login_failure_for_known_tenant(
    app_session_factory: async_sessionmaker[AsyncSession],
):
    suffix = uuid4().hex[:8]
    domain = f"fail-{suffix}.com"
    async with app_session_factory() as session:
        tenant = Tenant(name="Fail Co", workspace_domain=domain)
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

    async with app_session_factory() as session:
        event = await record_login_failure(
            session,
            email=f"ada@{domain}",
            idp=IdentityProvider.google,
            error_code="identity_conflict",
            request=_FakeRequest(),  # type: ignore[arg-type]
        )
        await session.commit()
        assert event is not None
        assert event.event_type == AuditEventType.login_failed
        assert event.error_code == "identity_conflict"

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        codes = list(await session.scalars(select(AuditEvent.error_code)))
        assert codes == ["identity_conflict"]


async def test_record_login_failure_skips_unknown_tenant(
    app_session_factory: async_sessionmaker[AsyncSession],
):
    async with app_session_factory() as session:
        event = await record_login_failure(
            session,
            email=f"nobody-{uuid4().hex[:8]}@no-such-tenant.example",
            idp=IdentityProvider.microsoft,
            error_code="no_tenant",
            request=_FakeRequest(),  # type: ignore[arg-type]
        )
        assert event is None
