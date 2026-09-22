"""Company invite links (copyable) and public invite lookup."""

from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db import get_db
from app.models import CompanyInviteToken, Tenant, User

router = APIRouter(tags=["invites"])


class CompanyInviteOut(BaseModel):
    token: str
    url: str
    created_at: datetime


class PublicInviteOut(BaseModel):
    tenant_name: str
    workspace_domain: str
    has_logo: bool = False


def _invite_url(request: Request, token: str) -> str:
    # Prefer the SPA origin (frontend) over the API host when behind a proxy.
    origin = request.headers.get("origin") or str(request.base_url).rstrip("/")
    return f"{origin}/?invite={token}"


def _new_token() -> str:
    return secrets.token_urlsafe(24)


@router.get("/invites/company", response_model=CompanyInviteOut | None)
async def get_company_invite(
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CompanyInviteOut | None:
    row = await db.scalar(
        select(CompanyInviteToken).where(CompanyInviteToken.tenant_id == admin.tenant_id)
    )
    if row is None:
        return None
    return CompanyInviteOut(
        token=row.token,
        url=_invite_url(request, row.token),
        created_at=row.created_at,
    )


@router.post("/invites/company", response_model=CompanyInviteOut, status_code=status.HTTP_200_OK)
async def ensure_company_invite(
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CompanyInviteOut:
    """Return the existing company invite, creating one if needed."""
    row = await db.scalar(
        select(CompanyInviteToken).where(CompanyInviteToken.tenant_id == admin.tenant_id)
    )
    if row is None:
        row = CompanyInviteToken(
            token=_new_token(),
            tenant_id=admin.tenant_id,
            created_by=admin.id,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return CompanyInviteOut(
        token=row.token,
        url=_invite_url(request, row.token),
        created_at=row.created_at,
    )


@router.post("/invites/company/rotate", response_model=CompanyInviteOut)
async def rotate_company_invite(
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CompanyInviteOut:
    existing = await db.scalar(
        select(CompanyInviteToken).where(CompanyInviteToken.tenant_id == admin.tenant_id)
    )
    if existing is not None:
        await db.delete(existing)
        await db.flush()
    row = CompanyInviteToken(
        token=_new_token(),
        tenant_id=admin.tenant_id,
        created_by=admin.id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return CompanyInviteOut(
        token=row.token,
        url=_invite_url(request, row.token),
        created_at=row.created_at,
    )


@router.get("/public/invites/{token}", response_model=PublicInviteOut)
async def lookup_public_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> PublicInviteOut:
    """Unauthenticated: resolve invite token to company name + domain."""
    if not token or len(token) > 64:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invite_not_found")
    row = await db.scalar(select(CompanyInviteToken).where(CompanyInviteToken.token == token))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invite_not_found")
    tenant = await db.scalar(select(Tenant).where(Tenant.id == row.tenant_id))
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invite_not_found")
    return PublicInviteOut(
        tenant_name=tenant.name,
        workspace_domain=tenant.workspace_domain,
        has_logo=bool(tenant.logo_bytes),
    )
