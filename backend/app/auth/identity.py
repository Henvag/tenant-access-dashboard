from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rls import set_tenant_rls
from app.domain import normalize_workspace_domain
from app.models import Tenant, User, UserRole
from app.models.user import IdentityProvider


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


def email_from_oidc_claims(claims: dict) -> str:
    email = (claims.get("email") or "").strip().lower()
    if email and "@" in email:
        return email
    preferred = (claims.get("preferred_username") or "").strip().lower()
    if preferred and "@" in preferred:
        return preferred
    return ""


async def upsert_user_from_oidc(
    session: AsyncSession,
    *,
    email: str,
    idp: IdentityProvider,
    oidc_sub: str,
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

    user = await session.scalar(
        select(User).where(User.idp == idp, User.oidc_sub == oidc_sub)
    )
    if user is None:
        user = await session.scalar(select(User).where(User.email == email))
        # Same email + same IdP but different subject → conflict.
        # Same email + different IdP → link (update idp/sub on the existing row).
        if user is not None and user.idp == idp and user.oidc_sub != oidc_sub:
            raise LoginError("identity_conflict")

    now = datetime.now(UTC)
    if user is None:
        user_count = await session.scalar(select(func.count()).select_from(User)) or 0
        user = User(
            tenant_id=tenant.id,
            email=email,
            idp=idp,
            oidc_sub=oidc_sub,
            role=UserRole.admin if user_count == 0 else UserRole.user,
            display_name=display_name,
            last_login_at=now,
        )
        session.add(user)
        await session.flush()
        if user_count == 0:
            tenant.owner_user_id = user.id
    else:
        if user.disabled_at is not None:
            raise LoginError("user_disabled")
        user.email = email
        user.idp = idp
        user.oidc_sub = oidc_sub
        user.display_name = display_name
        user.last_login_at = now

    # Heal tenants whose owner was never set (e.g. 007 backfill blocked by FORCE RLS).
    if tenant.owner_user_id is None and user.role == UserRole.admin:
        tenant.owner_user_id = user.id

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
