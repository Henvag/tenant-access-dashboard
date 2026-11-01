from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.identity import LoginError, find_tenant_for_domain, workspace_domain_from_claims
from app.auth.rls import set_tenant_rls
from app.demo import is_demo_tenant
from app.http_client import client_ip
from app.models import AuditEvent, AuditEventType, IdentityProvider, Tenant, User, UserRole


async def _append(session: AsyncSession, event: AuditEvent) -> AuditEvent:
    """Write the audit row and queue its webhooks in the same transaction."""
    from app.webhooks.service import enqueue_for_event

    session.add(event)
    await session.flush()
    await enqueue_for_event(session, event)
    return event


def _client_ip(request: Request) -> str | None:
    return client_ip(request)


def _visitor_fields(tenant_id, request: Request) -> tuple[str | None, str | None]:
    """IP and user agent to store. Demo visitors share one audit log, so never theirs."""
    if is_demo_tenant(tenant_id):
        return None, None
    return _client_ip(request), _user_agent(request)

def _user_agent(request: Request) -> str | None:
    raw = request.headers.get("user-agent")
    if not raw:
        return None
    return raw[:512]


async def record_login(
    session: AsyncSession,
    *,
    user: User,
    idp: IdentityProvider,
    request: Request,
) -> AuditEvent:
    """Append a successful login row. Caller must already have set RLS for the tenant."""
    ip_address, user_agent = _visitor_fields(user.tenant_id, request)
    event = AuditEvent(
        tenant_id=user.tenant_id,
        user_id=user.id,
        email=user.email,
        event_type=AuditEventType.login,
        idp=idp,
        error_code=None,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return await _append(session, event)


async def record_login_failure(
    session: AsyncSession,
    *,
    email: str,
    idp: IdentityProvider,
    error_code: str,
    request: Request,
    hosted_domain: str | None = None,
) -> AuditEvent | None:
    """
    Record a failed sign-in when the email domain maps to an existing tenant.

    Skips no_tenant / invalid domain — there is no tenant admin who should see those.
    """
    try:
        domain = workspace_domain_from_claims(email, hosted_domain)
    except LoginError:
        return None

    tenant = await find_tenant_for_domain(session, domain)
    if tenant is None:
        return None

    await set_tenant_rls(session, tenant.id)
    user = await session.scalar(select(User).where(User.email == email.lower()))
    event = AuditEvent(
        tenant_id=tenant.id,
        user_id=user.id if user else None,
        email=email.lower(),
        event_type=AuditEventType.login_failed,
        idp=idp,
        error_code=error_code[:64],
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    return await _append(session, event)


async def record_user_access_change(
    session: AsyncSession,
    *,
    actor: User,
    target: User,
    disabled: bool,
    request: Request,
    details: dict | None = None,
) -> AuditEvent:
    """Append user_disabled / user_enabled. Caller must already have RLS set."""
    event = AuditEvent(
        tenant_id=target.tenant_id,
        user_id=target.id,
        email=target.email,
        event_type=AuditEventType.user_disabled if disabled else AuditEventType.user_enabled,
        idp=actor.idp,
        error_code=None,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
        details=details,
    )
    return await _append(session, event)


async def record_app_event(
    session: AsyncSession,
    *,
    tenant_id,
    event_type: AuditEventType,
    email: str,
    idp: IdentityProvider,
    request: Request,
    user_id=None,
    error_code: str | None = None,
    details: dict | None = None,
) -> AuditEvent:
    """Append an app_* event (registration, grants, app sign-ins). RLS must be set."""
    ip_address, user_agent = _visitor_fields(tenant_id, request)
    event = AuditEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        email=email,
        event_type=event_type,
        idp=idp,
        error_code=error_code[:64] if error_code else None,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
    )
    return await _append(session, event)


async def record_role_change(
    session: AsyncSession,
    *,
    actor: User,
    target: User,
    from_role: UserRole,
    to_role: UserRole,
    request: Request,
) -> AuditEvent:
    """Append role_changed. Caller must already have RLS set."""
    event = AuditEvent(
        tenant_id=target.tenant_id,
        user_id=target.id,
        email=target.email,
        event_type=AuditEventType.role_changed,
        idp=actor.idp,
        error_code=f"{from_role.value}->{to_role.value}"[:64],
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
        details={"from_role": from_role.value, "to_role": to_role.value},
    )
    return await _append(session, event)


async def record_admin_event(
    session: AsyncSession,
    *,
    actor: User,
    event_type: AuditEventType,
    request: Request,
    details: dict | None = None,
) -> AuditEvent:
    """Append a workspace setting change made by ``actor`` (domains, webhooks, export)."""
    ip_address, user_agent = _visitor_fields(actor.tenant_id, request)
    event = AuditEvent(
        tenant_id=actor.tenant_id,
        user_id=actor.id,
        email=actor.email,
        event_type=event_type,
        idp=actor.idp,
        error_code=None,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
    )
    return await _append(session, event)
