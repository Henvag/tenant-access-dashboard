from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.auth.audit import record_user_access_change
from app.db import get_db
from app.models import User, UserRole
from app.schemas.user import TenantUserOut, UserDisabledUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[TenantUserOut])
async def list_users(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[TenantUserOut]:
    result = await db.scalars(
        select(User).order_by(User.role.asc(), User.email.asc())
    )
    return [_to_out(user) for user in result.all()]


@router.patch("/{user_id}", response_model=TenantUserOut)
async def set_user_disabled(
    user_id: UUID,
    body: UserDisabledUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantUserOut:
    target = await db.scalar(select(User).where(User.id == user_id))
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    currently_disabled = target.disabled_at is not None
    if currently_disabled == body.disabled:
        return _to_out(target)

    if body.disabled:
        if target.id == admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cannot_disable_self",
            )
        if target.role == UserRole.admin:
            active_admins = await db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.role == UserRole.admin, User.disabled_at.is_(None))
            )
            if (active_admins or 0) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="cannot_disable_last_admin",
                )
        target.disabled_at = datetime.now(UTC)
    else:
        target.disabled_at = None

    await record_user_access_change(
        db,
        actor=admin,
        target=target,
        disabled=body.disabled,
        request=request,
    )
    await db.commit()
    await db.refresh(target)
    return _to_out(target)


def _to_out(user: User) -> TenantUserOut:
    return TenantUserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        last_login_at=user.last_login_at,
        disabled=user.disabled,
    )