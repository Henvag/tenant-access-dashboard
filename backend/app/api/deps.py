from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.identity import read_login_session
from app.auth.rls import set_tenant_rls
from app.db import get_db
from app.models import User, UserRole


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    identities = read_login_session(request.session)
    if identities is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_signed_in")

    user_id, tenant_id = identities
    await set_tenant_rls(db, tenant_id)
    user = await db.scalar(
        select(User).where(User.id == user_id).options(selectinload(User.tenant))
    )
    if user is None or user.tenant_id != tenant_id:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_signed_in")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_required",
        )
    return user
