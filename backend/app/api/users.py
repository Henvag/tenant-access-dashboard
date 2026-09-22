from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.auth.audit import record_role_change, record_user_access_change
from app.db import get_db
from app.models import Tenant, User, UserRole
from app.oauth.logout import notify_disabled_user
from app.schemas.user import TenantUserOut, UserPatch

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[TenantUserOut])
async def list_users(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[TenantUserOut]:
    owner_id = await _owner_id(db, admin.tenant_id)
    result = await db.scalars(
        select(User).order_by(User.role.asc(), User.email.asc())
    )
    return [_to_out(user, owner_id) for user in result.all()]


@router.patch("/{user_id}", response_model=TenantUserOut)
async def patch_user(
    user_id: UUID,
    body: UserPatch,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantUserOut:
    target = await db.scalar(select(User).where(User.id == user_id))
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    owner_id = await _owner_id(db, admin.tenant_id)
    actor_is_owner = owner_id is not None and admin.id == owner_id
    target_is_owner = owner_id is not None and target.id == owner_id

    if body.disabled is not None:
        await _apply_disabled(
            db,
            actor=admin,
            target=target,
            disabled=body.disabled,
            actor_is_owner=actor_is_owner,
            target_is_owner=target_is_owner,
            request=request,
        )
    else:
        assert body.role is not None
        await _apply_role(
            db,
            actor=admin,
            target=target,
            new_role=body.role,
            actor_is_owner=actor_is_owner,
            target_is_owner=target_is_owner,
            request=request,
        )

    out = _to_out(target, owner_id)
    await db.commit()
    return out


async def _owner_id(db: AsyncSession, tenant_id: UUID) -> UUID | None:
    return await db.scalar(select(Tenant.owner_user_id).where(Tenant.id == tenant_id))


async def _apply_disabled(
    db: AsyncSession,
    *,
    actor: User,
    target: User,
    disabled: bool,
    actor_is_owner: bool,
    target_is_owner: bool,
    request: Request,
) -> None:
    currently_disabled = target.disabled_at is not None
    if currently_disabled == disabled:
        return

    if disabled:
        if target.id == actor.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cannot_disable_self",
            )
        if target_is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="cannot_disable_owner",
            )
        if not actor_is_owner and target.role == UserRole.admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="cannot_disable_admin",
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
        logout = await notify_disabled_user(db, target)
        details = {"logout_notified": logout["notified"], "logout_failed": logout["failed"]}
    else:
        target.disabled_at = None
        details = None

    await record_user_access_change(
        db,
        actor=actor,
        target=target,
        disabled=disabled,
        request=request,
        details=details,
    )


async def _apply_role(
    db: AsyncSession,
    *,
    actor: User,
    target: User,
    new_role: UserRole,
    actor_is_owner: bool,
    target_is_owner: bool,
    request: Request,
) -> None:
    if not actor_is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="owner_required",
        )
    if target.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cannot_change_own_role",
        )
    if target_is_owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cannot_change_owner_role",
        )
    if target.role == new_role:
        return

    if new_role == UserRole.user and target.role == UserRole.admin:
        active_admins = await db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.admin, User.disabled_at.is_(None))
        )
        if (active_admins or 0) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cannot_demote_last_admin",
            )

    from_role = target.role
    target.role = new_role
    await record_role_change(
        db,
        actor=actor,
        target=target,
        from_role=from_role,
        to_role=new_role,
        request=request,
    )


def _to_out(user: User, owner_id: UUID | None) -> TenantUserOut:
    return TenantUserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        last_login_at=user.last_login_at,
        disabled=user.disabled,
        is_owner=owner_id is not None and user.id == owner_id,
    )
