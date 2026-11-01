"""Outside admins (partner mode): the owner invites someone from another domain.

The invited person signs in with Google or Microsoft using exactly that
address; sign-in then adds them to this company as an admin. They never use
one of the company's seats, and each company can have at most
``MAX_OUTSIDE_ADMINS`` of them (active ones plus open invites).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.auth.audit import record_admin_event
from app.auth.partners import (
    INVITE_TTL,
    MAX_OUTSIDE_ADMINS,
    count_open_invites,
    count_outside_admins,
)
from app.auth.rls import set_tenant_rls
from app.db import get_db
from app.models import AuditEventType, PartnerInvite, TenantDomain, User

router = APIRouter(prefix="/partners", tags=["partners"])


class PartnerInviteIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class PartnerInviteOut(BaseModel):
    id: UUID
    email: str
    created_at: datetime
    expires_at: datetime


class PartnersOut(BaseModel):
    invites: list[PartnerInviteOut]
    outside_admins: int
    limit: int


def _require_owner(user: User) -> None:
    if user.tenant is None or user.tenant.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner_required")


def _normalize_email(raw: str) -> str:
    email = raw.strip().lower()
    local, sep, domain = email.rpartition("@")
    if not sep or not local or "." not in domain or " " in email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_email")
    return email


def _out(row: PartnerInvite) -> PartnerInviteOut:
    return PartnerInviteOut(
        id=row.id, email=row.email, created_at=row.created_at, expires_at=row.expires_at
    )


async def _open_invites(db: AsyncSession, tenant_id: UUID) -> list[PartnerInvite]:
    now = datetime.now(UTC)
    return list(
        (
            await db.scalars(
                select(PartnerInvite)
                .where(
                    PartnerInvite.tenant_id == tenant_id,
                    PartnerInvite.accepted_at.is_(None),
                    PartnerInvite.expires_at > now,
                )
                .order_by(PartnerInvite.created_at.desc())
            )
        ).all()
    )


@router.get("", response_model=PartnersOut)
async def list_partners(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PartnersOut:
    _require_owner(admin)
    invites = await _open_invites(db, admin.tenant_id)
    return PartnersOut(
        invites=[_out(row) for row in invites],
        outside_admins=await count_outside_admins(db, admin.tenant_id),
        limit=MAX_OUTSIDE_ADMINS,
    )


@router.post("/invites", response_model=PartnerInviteOut, status_code=status.HTTP_201_CREATED)
async def create_invite(
    body: PartnerInviteIn,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PartnerInviteOut:
    _require_owner(admin)
    tenant = admin.tenant
    email = _normalize_email(body.email)
    domain = email.rsplit("@", 1)[1]

    # People on the company's own domains sign in normally; an invite would
    # let them skip the sign-in policy and the seat count.
    own = domain == tenant.workspace_domain or email == tenant.workspace_domain
    if not own:
        own = (
            await db.scalar(
                select(TenantDomain.id).where(
                    TenantDomain.tenant_id == tenant.id,
                    TenantDomain.domain == domain,
                    TenantDomain.verified_at.is_not(None),
                )
            )
        ) is not None
    if own:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="own_domain")

    await set_tenant_rls(db, tenant.id)
    member = await db.scalar(
        select(User.id).where(User.tenant_id == tenant.id, User.email == email)
    )
    if member is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_member")

    used = await count_outside_admins(db, tenant.id) + await count_open_invites(db, tenant.id)
    if used >= MAX_OUTSIDE_ADMINS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="outside_admin_limit")

    # An expired, never-used invite for the same address would block the unique index.
    stale = await db.scalar(
        select(PartnerInvite).where(
            PartnerInvite.tenant_id == tenant.id,
            PartnerInvite.email == email,
            PartnerInvite.accepted_at.is_(None),
        )
    )
    if stale is not None:
        if stale.expires_at > datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_invited")
        await db.delete(stale)
        await db.flush()

    now = datetime.now(UTC)
    row = PartnerInvite(
        tenant_id=tenant.id,
        email=email,
        created_by=admin.id,
        created_at=now,
        expires_at=now + INVITE_TTL,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_invited") from None
    await record_admin_event(
        db,
        actor=admin,
        event_type=AuditEventType.partner_invited,
        request=request,
        details={"email": email},
    )
    out = _out(row)
    await db.commit()
    return out


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    invite_id: UUID,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    _require_owner(admin)
    row = await db.scalar(
        select(PartnerInvite).where(
            PartnerInvite.id == invite_id,
            PartnerInvite.tenant_id == admin.tenant_id,
            PartnerInvite.accepted_at.is_(None),
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invite_not_found")
    email = row.email
    await db.delete(row)
    await record_admin_event(
        db,
        actor=admin,
        event_type=AuditEventType.partner_invite_revoked,
        request=request,
        details={"email": email},
    )
    await db.commit()
