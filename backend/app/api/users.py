from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db import get_db
from app.models import User
from app.schemas.user import TenantUserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[TenantUserOut])
async def list_users(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[User]:
    result = await db.scalars(
        select(User).order_by(User.role.asc(), User.email.asc())
    )
    return list(result.all())
