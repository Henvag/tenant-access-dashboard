from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.identity import LoginError, workspace_domain_from_claims
from app.auth.rls import set_tenant_rls
from app.models import AuditEvent, AuditEventType, IdentityProvider, Tenant, User


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64] or None
    if request.client and request.client.host:
        return request.client.host[:64]
    return None


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
    event = AuditEvent(
        tenant_id=user.tenant_id,
        user_id=user.id,
        email=user.email,
        event_type=AuditEventType.login,
        idp=idp,
        error_code=None,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    session.add(event)
    await session.flush()
    return event


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

    tenant = await session.scalar(select(Tenant).where(Tenant.workspace_domain == domain))
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
    session.add(event)
    await session.flush()
    return event
