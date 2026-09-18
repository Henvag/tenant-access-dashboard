from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, AuditEventType, IdentityProvider, User


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
    """Append a login audit row. Caller must already have set RLS for the tenant."""
    event = AuditEvent(
        tenant_id=user.tenant_id,
        user_id=user.id,
        email=user.email,
        event_type=AuditEventType.login,
        idp=idp,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    session.add(event)
    await session.flush()
    return event
