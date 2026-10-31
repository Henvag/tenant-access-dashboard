from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rls import set_tenant_rls
from app.billing.plans import limits_for_tenant
from app.domain import normalize_workspace_domain, workspace_key_for_email
from app.models import AppGrant, PendingAppGrant, Tenant, User, UserRole
from app.models.user import IdentityProvider


class LoginError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def workspace_domain_from_claims(email: str, hosted_domain: str | None) -> str:
    """Tenant key for a verified email: its domain, or the address for Gmail/Outlook."""
    if "@" not in email:
        raise LoginError("missing_claims")
    email_domain = email.rsplit("@", 1)[1].lower()
    if hosted_domain:
        hosted = hosted_domain.strip().lower()
        if hosted != email_domain:
            raise LoginError("domain_mismatch")
        try:
            return normalize_workspace_domain(hosted)
        except ValueError:
            raise LoginError("invalid_domain") from None
    try:
        return workspace_key_for_email(email)
    except ValueError:
        raise LoginError("invalid_domain") from None


# Personal Microsoft accounts (outlook.com, hotmail.com, ...) all sign in from
# this one Entra tenant, and Microsoft verifies their email addresses.
MICROSOFT_CONSUMER_TENANT_ID = "9188040d-6c67-4c5b-b112-36a304b66dad"


def _claim_is_true(value: object) -> bool:
    return value is True or (isinstance(value, str) and value.lower() in {"true", "1"}) or value == 1


def google_verified_email(claims: dict) -> str | None:
    """Google's email, only when Google says it is verified."""
    if not _claim_is_true(claims.get("email_verified")):
        return None
    email = (claims.get("email") or "").strip().lower()
    return email if "@" in email else None


def microsoft_verified_email(claims: dict) -> str | None:
    """Microsoft's email, only when we can trust that it belongs to the user.

    With the multi-tenant /common endpoint, anyone can create an Entra
    directory and set any address as a user's email or UPN, so those claims
    alone prove nothing (the "nOAuth" pattern). Accept:
    - personal Microsoft accounts, whose addresses Microsoft verifies, and
    - work accounts whose token carries ``xms_edov`` = true, meaning the
      email domain is verified by the directory that issued the token.
    """
    tid = str(claims.get("tid") or "")
    if not tid or claims.get("iss") != f"https://login.microsoftonline.com/{tid}/v2.0":
        return None
    if tid == MICROSOFT_CONSUMER_TENANT_ID:
        email = email_from_oidc_claims(claims)
        return email or None
    if not _claim_is_true(claims.get("xms_edov")):
        return None
    email = (claims.get("email") or "").strip().lower()
    return email if "@" in email else None


def email_from_oidc_claims(claims: dict) -> str:
    email = (claims.get("email") or "").strip().lower()
    if email and "@" in email:
        return email
    preferred = (claims.get("preferred_username") or "").strip().lower()
    if preferred and "@" in preferred:
        return preferred
    return ""


async def _fulfill_pending_app_grants(session: AsyncSession, user: User) -> None:
    """Turn pending email grants into real AppGrant rows on first login."""
    pending = list(
        (
            await session.scalars(
                select(PendingAppGrant).where(PendingAppGrant.email == user.email)
            )
        ).all()
    )
    if not pending:
        return
    existing_client_pks = set(
        (
            await session.scalars(
                select(AppGrant.client_pk).where(AppGrant.user_id == user.id)
            )
        ).all()
    )
    for row in pending:
        if row.client_pk not in existing_client_pks:
            session.add(
                AppGrant(
                    tenant_id=user.tenant_id,
                    client_pk=row.client_pk,
                    user_id=user.id,
                    granted_by=row.granted_by,
                )
            )
            existing_client_pks.add(row.client_pk)
        await session.delete(row)


async def upsert_user_from_oidc(
    session: AsyncSession,
    *,
    email: str,
    idp: IdentityProvider,
    oidc_sub: str,
    display_name: str | None,
    hosted_domain: str | None,
    new_tenant_name: str | None = None,
) -> User:
    """Sign in a user whose email the caller has already verified with the IdP.

    ``new_tenant_name`` is set when the person chose "Register company": if no
    tenant exists for their verified domain yet, it is created and they become
    its owner. Nobody can register a domain they cannot sign in with.
    """
    domain = workspace_domain_from_claims(email, hosted_domain)
    tenant = await session.scalar(
        select(Tenant).where(Tenant.workspace_domain == domain).with_for_update()
    )
    if tenant is None:
        if not new_tenant_name:
            raise LoginError("no_tenant")
        tenant = Tenant(name=new_tenant_name, workspace_domain=domain)
        session.add(tenant)
        await session.flush()

    await set_tenant_rls(session, tenant.id)

    user = await session.scalar(
        select(User).where(
            User.tenant_id == tenant.id, User.idp == idp, User.oidc_sub == oidc_sub
        )
    )
    if user is None:
        # Never attach a new identity to an existing account by email alone:
        # a different subject or provider claiming the same address is how
        # unverified-email takeovers (nOAuth) work. Keep the first identity.
        existing = await session.scalar(
            select(User).where(User.tenant_id == tenant.id, User.email == email)
        )
        if existing is not None:
            raise LoginError("identity_conflict")

    now = datetime.now(UTC)
    if user is None:
        user_count = (
            await session.scalar(
                select(func.count()).select_from(User).where(User.tenant_id == tenant.id)
            )
            or 0
        )
        max_users = limits_for_tenant(tenant).max_users
        if user_count >= max_users:
            raise LoginError("seat_limit_reached")
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
        user.display_name = display_name
        user.last_login_at = now

    # Heal tenants whose owner was never set (e.g. 007 backfill blocked by FORCE RLS).
    if tenant.owner_user_id is None and user.role == UserRole.admin:
        tenant.owner_user_id = user.id

    await _fulfill_pending_app_grants(session, user)
    return user


def write_login_session(session_data: dict, user: User) -> None:
    # Keep a parked /oauth/authorize query across re-login so SSO can resume.
    from app.oauth.pending import PENDING_AUTHORIZE_KEY

    pending = session_data.get(PENDING_AUTHORIZE_KEY)
    session_data.clear()
    session_data["user_id"] = str(user.id)
    session_data["tenant_id"] = str(user.tenant_id)
    session_data["role"] = user.role.value
    if pending:
        session_data[PENDING_AUTHORIZE_KEY] = pending


def read_login_session(session_data: dict) -> tuple[UUID, UUID] | None:
    user_id = session_data.get("user_id")
    tenant_id = session_data.get("tenant_id")
    if not user_id or not tenant_id:
        return None
    try:
        return UUID(user_id), UUID(tenant_id)
    except ValueError:
        return None
