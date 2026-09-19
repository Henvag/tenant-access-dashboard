from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Tenant
from app.schemas.tenant import TenantCreate, TenantOut

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(body: TenantCreate, db: AsyncSession = Depends(get_db)) -> Tenant:
    existing = await db.scalar(
        select(Tenant).where(Tenant.workspace_domain == body.workspace_domain)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="tenant_exists",
        )

    tenant = Tenant(name=body.name, workspace_domain=body.workspace_domain)
    db.add(tenant)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="tenant_exists",
        ) from None

    await db.refresh(tenant)
    return tenant
