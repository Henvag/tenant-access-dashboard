from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_admin
from app.billing.plans import retention_cutoff
from app.db import get_db
from app.models import AuditEvent, User
from app.schemas.audit import AuditEventOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventOut])
async def list_audit_events(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AuditEventOut]:
    cutoff = retention_cutoff(_admin.tenant) if _admin.tenant else None
    query = (
        select(AuditEvent)
        .options(selectinload(AuditEvent.user))
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )
    if cutoff is not None:
        query = query.where(AuditEvent.created_at >= cutoff)
    result = await db.scalars(query)
    events = list(result.all())
    return [
        AuditEventOut(
            id=event.id,
            email=event.email,
            display_name=event.user.display_name if event.user else None,
            event_type=event.event_type,
            idp=event.idp,
            error_code=event.error_code,
            ip_address=event.ip_address,
            details=event.details,
            created_at=event.created_at,
        )
        for event in events
    ]
