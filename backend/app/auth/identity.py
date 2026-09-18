from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rls import set_tenant_rls
from app.domain import normalize_workspace_domain
from app.models import Tenant, User, UserRole


class LoginError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def workspace_domain_from_claims(email: str, hosted_domain: str | None) -> str:
    if "@" not in email:
        raise LoginError("missing_claims")
    email_domain = email.rsplit("@", 1)[1].lower()
    raw = hosted_domain.strip().lower() if hosted_domain else email_domain
    if hosted_domain and raw != email_domain:
        raise LoginError("domain_mismatch")
    try:
        return normalize_workspace_domain(raw)
    except ValueError:
        raise LoginError("invalid_domain") from None


async def upsert_user_from_oidc(
    session: AsyncSession,
    *,
    email: str,
    google_sub: str,
    display_name: str | None,
    hosted_domain: str | None,
) -> User:
    domain = workspace_domain_from_claims(email, hosted_domain)
    tenant = await session.scalar(
        select(Tenant).where(Tenant.workspace_domain == domain).with_for_update()
    )
    if tenant is None:
        raise LoginError("no_tenant")

    await set_tenant_rls(session, tenant.id)

    user = await session.scalar(select(User).where(User.google_sub == google_sub))
    if user is None:
        user = await session.scalar(select(User).where(User.email == email))
        if user is not None and user.google_sub != google_sub:
            raise LoginError("identity_conflict")

    now = datetime.now(UTC)
    if user is None:
        user_count = await session.scalar(select(func.count()).select_from(User)) or 0
        user = User(
            tenant_id=tenant.id,
            email=email,
            google_sub=google_sub,
            role=UserRole.admin if user_count == 0 else UserRole.user,
            display_name=display_name,
            last_login_at=now,
        )
        session.add(user)
        await session.flush()
    else:
        user.email = email
        user.display_name = display_name
        user.last_login_at = now

    return user


def write_login_session(session_data: dict, user: User) -> None:
    session_data.clear()
    session_data["user_id"] = str(user.id)
    session_data["tenant_id"] = str(user.tenant_id)
    session_data["role"] = user.role.value


def read_login_session(session_data: dict) -> tuple[UUID, UUID] | None:
    user_id = session_data.get("user_id")
    tenant_id = session_data.get("tenant_id")
    if not user_id or not tenant_id:
        return None
    try:
        return UUID(user_id), UUID(tenant_id)
    except ValueError:
        return None
