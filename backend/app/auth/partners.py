"""Partner mode: outside admins who belong to several companies.

One sign-in identity (provider + account ID) can hold an account row in more
than one company. Each row lives under its company's RLS like any other user;
``identity_memberships`` only records which companies an identity may enter,
so sign-in and the company switcher can find them before a company is chosen.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rls import set_tenant_rls
from app.models import (
    AuditEventType,
    IdentityMembership,
    IdentityProvider,
    PartnerInvite,
    Tenant,
    User,
    UserRole,
)

INVITE_TTL = timedelta(days=7)
# Outside admins don't use the client's seats, so cap them per company.
MAX_OUTSIDE_ADMINS = 3


class PartnerError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


async def remember_membership(session: AsyncSession, user: User) -> None:
    """Record that this identity has an account row in the user's company."""
    stmt = (
        pg_insert(IdentityMembership)
        .values(
            idp=user.idp,
            oidc_sub=user.oidc_sub,
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
        .on_conflict_do_update(
            index_elements=["idp", "oidc_sub", "tenant_id"],
            set_={"user_id": user.id},
        )
    )
    await session.execute(stmt)


async def count_outside_admins(session: AsyncSession, tenant_id: UUID) -> int:
    """Active outside admins. Caller must have set RLS for ``tenant_id``."""
    return (
        await session.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.tenant_id == tenant_id,
                User.external.is_(True),
                User.disabled_at.is_(None),
            )
        )
        or 0
    )


async def count_open_invites(session: AsyncSession, tenant_id: UUID) -> int:
    now = datetime.now(UTC)
    return (
        await session.scalar(
            select(func.count())
            .select_from(PartnerInvite)
            .where(
                PartnerInvite.tenant_id == tenant_id,
                PartnerInvite.accepted_at.is_(None),
                PartnerInvite.expires_at > now,
            )
        )
        or 0
    )


async def join_partner_companies(
    session: AsyncSession,
    *,
    email: str,
    idp: IdentityProvider,
    oidc_sub: str,
    display_name: str | None,
    request: Request,
) -> list[User]:
    """Accept open invites for an email the IdP has already verified.

    Each accepted invite creates an external admin row in the inviting company,
    under that company's RLS scope. Returns the rows created now. An invite
    whose company already has a different account for this address stays open:
    attaching a second identity to an address is how email takeovers work.
    """
    from app.auth.audit import record_admin_event

    now = datetime.now(UTC)
    invites = list(
        (
            await session.scalars(
                select(PartnerInvite)
                .where(
                    PartnerInvite.email == email.lower(),
                    PartnerInvite.accepted_at.is_(None),
                    PartnerInvite.expires_at > now,
                )
                .order_by(PartnerInvite.created_at)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    joined: list[User] = []
    for invite in invites:
        await set_tenant_rls(session, invite.tenant_id)
        existing = await session.scalar(
            select(User).where(
                User.tenant_id == invite.tenant_id,
                User.idp == idp,
                User.oidc_sub == oidc_sub,
            )
        )
        if existing is not None:
            invite.accepted_at = now
            invite.accepted_user_id = existing.id
            await remember_membership(session, existing)
            continue
        same_address = await session.scalar(
            select(User.id).where(User.tenant_id == invite.tenant_id, User.email == email.lower())
        )
        if same_address is not None:
            continue
        if await count_outside_admins(session, invite.tenant_id) >= MAX_OUTSIDE_ADMINS:
            continue
        user = User(
            tenant_id=invite.tenant_id,
            email=email.lower(),
            idp=idp,
            oidc_sub=oidc_sub,
            role=UserRole.admin,
            display_name=display_name,
            external=True,
        )
        session.add(user)
        await session.flush()
        invite.accepted_at = now
        invite.accepted_user_id = user.id
        await remember_membership(session, user)
        await record_admin_event(
            session,
            actor=user,
            event_type=AuditEventType.partner_joined,
            request=request,
            details={"email": user.email},
        )
        joined.append(user)
    return joined


async def companies_for_identity(
    session: AsyncSession, *, idp: IdentityProvider, oidc_sub: str
) -> list[tuple[UUID, str, str]]:
    """(tenant_id, name, workspace_domain) for every company this identity is in."""
    rows = await session.execute(
        select(Tenant.id, Tenant.name, Tenant.workspace_domain)
        .join(IdentityMembership, IdentityMembership.tenant_id == Tenant.id)
        .where(IdentityMembership.idp == idp, IdentityMembership.oidc_sub == oidc_sub)
        .order_by(Tenant.name)
    )
    return [(row[0], row[1], row[2]) for row in rows.all()]


async def first_partner_user(
    session: AsyncSession, *, idp: IdentityProvider, oidc_sub: str
) -> User | None:
    """An active account row in any company this identity belongs to, oldest first."""
    memberships = list(
        (
            await session.scalars(
                select(IdentityMembership)
                .where(IdentityMembership.idp == idp, IdentityMembership.oidc_sub == oidc_sub)
                .order_by(IdentityMembership.created_at)
            )
        ).all()
    )
    for membership in memberships:
        user = await _member_row(session, membership)
        if user is not None and user.disabled_at is None:
            return user
    return None


async def _member_row(session: AsyncSession, membership: IdentityMembership) -> User | None:
    await set_tenant_rls(session, membership.tenant_id)
    return await session.scalar(
        select(User).where(
            User.id == membership.user_id,
            User.tenant_id == membership.tenant_id,
            User.idp == membership.idp,
            User.oidc_sub == membership.oidc_sub,
        )
    )


async def switch_company(
    session: AsyncSession, *, current: User, tenant_id: UUID, request: Request
) -> User:
    """The caller's own account row in ``tenant_id``, after checking membership."""
    from app.auth.audit import record_admin_event

    membership = await session.scalar(
        select(IdentityMembership).where(
            IdentityMembership.idp == current.idp,
            IdentityMembership.oidc_sub == current.oidc_sub,
            IdentityMembership.tenant_id == tenant_id,
        )
    )
    if membership is None:
        raise PartnerError("company_not_found")
    user = await _member_row(session, membership)
    if user is None:
        raise PartnerError("company_not_found")
    if user.disabled_at is not None:
        raise PartnerError("user_disabled")
    if user.id != current.id:
        user.last_login_at = datetime.now(UTC)
        await record_admin_event(
            session,
            actor=user,
            event_type=AuditEventType.company_switched,
            request=request,
        )
    return user
