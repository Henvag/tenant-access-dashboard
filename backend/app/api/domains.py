"""Company domains proved by DNS, and the sign-in policy that goes with them."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import dns_check
from app.api.deps import require_admin
from app.auth.audit import record_admin_event
from app.auth.rls import set_tenant_rls
from app.db import get_db
from app.domain import CONSUMER_DOMAINS, is_personal_workspace, normalize_workspace_domain
from app.models import AuditEventType, Tenant, TenantDomain, User

router = APIRouter(prefix="/company", tags=["domains"])

MAX_DOMAINS = 5
RECORD_PREFIX = "_tenant-access"
VALUE_PREFIX = "tenant-access-verification="


class DomainCreate(BaseModel):
    domain: str = Field(min_length=3, max_length=253)


class DomainOut(BaseModel):
    id: UUID
    domain: str
    verified: bool
    verified_at: datetime | None
    last_checked_at: datetime | None
    record_name: str
    record_value: str


class DomainsOut(BaseModel):
    primary_domain: str
    personal_workspace: bool
    require_managed_accounts: bool
    domains: list[DomainOut]
    max_domains: int


class SignInPolicy(BaseModel):
    require_managed_accounts: bool


def record_name(domain: str) -> str:
    return f"{RECORD_PREFIX}.{domain}"


def record_value(row: TenantDomain) -> str:
    return VALUE_PREFIX + row.verification_token


def _out(row: TenantDomain) -> DomainOut:
    return DomainOut(
        id=row.id,
        domain=row.domain,
        verified=row.verified_at is not None,
        verified_at=row.verified_at,
        last_checked_at=row.last_checked_at,
        record_name=record_name(row.domain),
        record_value=record_value(row),
    )


def _require_owner(user: User) -> None:
    if user.tenant is None or user.tenant.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner_required")


def _require_company(tenant: Tenant) -> None:
    if is_personal_workspace(tenant.workspace_domain):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="personal_workspace_domains"
        )


async def _domain_taken(db: AsyncSession, tenant_id: UUID, domain: str) -> bool:
    """Another company already signs in on this domain, as primary or verified."""
    primary = await db.scalar(
        select(Tenant.id).where(Tenant.workspace_domain == domain, Tenant.id != tenant_id)
    )
    if primary is not None:
        return True
    verified = await db.scalar(
        select(TenantDomain.id).where(
            TenantDomain.domain == domain,
            TenantDomain.verified_at.is_not(None),
            TenantDomain.tenant_id != tenant_id,
        )
    )
    return verified is not None


async def _get_row(db: AsyncSession, user: User, domain_id: UUID) -> TenantDomain:
    row = await db.scalar(
        select(TenantDomain).where(
            TenantDomain.id == domain_id, TenantDomain.tenant_id == user.tenant_id
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="domain_not_found")
    return row


async def _summary(db: AsyncSession, user: User) -> DomainsOut:
    tenant = await db.get(Tenant, user.tenant_id)
    rows = (
        await db.scalars(
            select(TenantDomain)
            .where(TenantDomain.tenant_id == user.tenant_id)
            .order_by(TenantDomain.created_at)
        )
    ).all()
    return DomainsOut(
        primary_domain=tenant.workspace_domain,
        personal_workspace=is_personal_workspace(tenant.workspace_domain),
        require_managed_accounts=tenant.require_managed_accounts,
        domains=[_out(row) for row in rows],
        max_domains=MAX_DOMAINS,
    )


@router.get("/domains", response_model=DomainsOut)
async def list_domains(
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> DomainsOut:
    return await _summary(db, admin)


@router.post("/domains", response_model=DomainOut, status_code=status.HTTP_201_CREATED)
async def add_domain(
    body: DomainCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DomainOut:
    _require_owner(admin)
    tenant = admin.tenant
    _require_company(tenant)
    try:
        domain = normalize_workspace_domain(body.domain)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    if domain in CONSUMER_DOMAINS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="domain_consumer")
    if domain == tenant.workspace_domain:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="domain_exists")
    existing = await db.scalar(
        select(TenantDomain.id).where(
            TenantDomain.tenant_id == tenant.id, TenantDomain.domain == domain
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="domain_exists")
    if await _domain_taken(db, tenant.id, domain):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="domain_taken")
    count = await db.scalar(
        select(func.count()).select_from(TenantDomain).where(TenantDomain.tenant_id == tenant.id)
    )
    if (count or 0) >= MAX_DOMAINS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="domain_limit_reached")

    row = TenantDomain(
        tenant_id=tenant.id,
        domain=domain,
        verification_token=secrets.token_urlsafe(24),
        created_by=admin.id,
    )
    db.add(row)
    await db.flush()
    await record_admin_event(
        db,
        actor=admin,
        event_type=AuditEventType.domain_added,
        request=request,
        details={"domain": domain},
    )
    await db.commit()
    return _out(row)


@router.post("/domains/{domain_id}/verify", response_model=DomainOut)
async def verify_domain(
    domain_id: UUID,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DomainOut:
    _require_owner(admin)
    row = await _get_row(db, admin, domain_id)
    if row.verified_at is not None:
        return _out(row)
    if await _domain_taken(db, admin.tenant_id, row.domain):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="domain_taken")
    try:
        values = await dns_check.txt_records(record_name(row.domain))
    except dns_check.DnsLookupError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="dns_lookup_failed"
        ) from None

    row.last_checked_at = datetime.now(UTC)
    if record_value(row) not in values:
        await db.commit()
        raise HTTPException(status_code=422, detail="dns_record_missing")

    row.verified_at = datetime.now(UTC)
    try:
        await db.flush()
    except IntegrityError:
        # Another company verified it a moment ago.
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="domain_taken") from None
    await record_admin_event(
        db,
        actor=admin,
        event_type=AuditEventType.domain_verified,
        request=request,
        details={"domain": row.domain},
    )
    await db.commit()
    return _out(row)


@router.delete("/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_domain(
    domain_id: UUID,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    _require_owner(admin)
    row = await _get_row(db, admin, domain_id)
    domain = row.domain
    await db.delete(row)
    await db.flush()
    await record_admin_event(
        db,
        actor=admin,
        event_type=AuditEventType.domain_removed,
        request=request,
        details={"domain": domain},
    )
    await db.commit()


@router.put("/sign-in-policy", response_model=DomainsOut)
async def set_sign_in_policy(
    body: SignInPolicy,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DomainsOut:
    _require_owner(admin)
    tenant = await db.get(Tenant, admin.tenant_id)
    _require_company(tenant)
    if tenant.require_managed_accounts != body.require_managed_accounts:
        tenant.require_managed_accounts = body.require_managed_accounts
        await record_admin_event(
            db,
            actor=admin,
            event_type=AuditEventType.sign_in_policy_changed,
            request=request,
            details={"require_managed_accounts": body.require_managed_accounts},
        )
        await db.commit()
        await set_tenant_rls(db, admin.tenant_id)
    return await _summary(db, admin)
