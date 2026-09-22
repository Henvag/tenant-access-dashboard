"""Company logo stored on the tenant row (Render disk does not persist files)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db import get_db
from app.models import CompanyInviteToken, Tenant, User

router = APIRouter(tags=["company"])

MAX_LOGO_BYTES = 200_000
ALLOWED_TYPES = {
    "image/png": "image/png",
    "image/jpeg": "image/jpeg",
    "image/webp": "image/webp",
    "image/svg+xml": "image/svg+xml",
}


def _require_owner(user: User) -> None:
    tenant = user.tenant
    if tenant is None or tenant.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner_required")


def _logo_response(tenant: Tenant) -> Response:
    if not tenant.logo_bytes or not tenant.logo_media_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="logo_not_found")
    return Response(
        content=bytes(tenant.logo_bytes),
        media_type=tenant.logo_media_type,
        headers={
            "Cache-Control": "private, max-age=60",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
        },
    )


def _accept_logo(content_type: str | None, data: bytes) -> str:
    media = (content_type or "").split(";")[0].strip().lower()
    if media not in ALLOWED_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="logo_type")
    if not data or len(data) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="logo_too_large")
    if media == "image/svg+xml":
        lowered = data.lower()
        if b"<script" in lowered or b"javascript:" in lowered:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="logo_type")
    return ALLOWED_TYPES[media]


@router.get("/company/logo")
async def company_logo(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    tenant = await db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="logo_not_found")
    return _logo_response(tenant)


@router.put("/company/logo", status_code=status.HTTP_204_NO_CONTENT)
async def upload_logo(
    file: UploadFile = File(...),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _require_owner(user)
    data = await file.read()
    media = _accept_logo(file.content_type, data)
    tenant = await db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_missing")
    tenant.logo_bytes = data
    tenant.logo_media_type = media
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/company/logo", status_code=status.HTTP_204_NO_CONTENT)
async def clear_logo(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _require_owner(user)
    tenant = await db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_missing")
    tenant.logo_bytes = None
    tenant.logo_media_type = None
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/public/invites/{token}/logo")
async def public_invite_logo(token: str, db: AsyncSession = Depends(get_db)) -> Response:
    if not token or len(token) > 64:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invite_not_found")
    row = await db.scalar(select(CompanyInviteToken).where(CompanyInviteToken.token == token))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invite_not_found")
    tenant = await db.get(Tenant, row.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invite_not_found")
    return _logo_response(tenant)
