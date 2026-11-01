import csv
import io
import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_admin
from app.auth.audit import record_admin_event
from app.billing.plans import retention_cutoff
from app.db import get_db
from app.demo import is_demo_tenant
from app.models import AuditEvent, AuditEventType, User
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
        .where(AuditEvent.tenant_id == _admin.tenant_id)
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


MAX_EXPORT_ROWS = 10_000
CSV_COLUMNS = (
    "created_at",
    "event_type",
    "email",
    "display_name",
    "idp",
    "error_code",
    "ip_address",
    "details",
)
# A cell starting with one of these runs as a formula in Excel or Sheets.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


@router.get("/export.csv")
async def export_audit_csv(
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    days: int | None = Query(default=None, ge=1, le=365),
) -> Response:
    """Every audit row the plan still shows (or the last ``days``), newest first."""
    now = datetime.now(UTC)
    cutoff = retention_cutoff(admin.tenant, now=now) if admin.tenant else None
    if days is not None:
        wanted = now - timedelta(days=days)
        cutoff = max(cutoff, wanted) if cutoff else wanted
    query = (
        select(AuditEvent)
        .where(AuditEvent.tenant_id == admin.tenant_id)
        .options(selectinload(AuditEvent.user))
        .order_by(AuditEvent.created_at.desc())
        .limit(MAX_EXPORT_ROWS)
    )
    if cutoff is not None:
        query = query.where(AuditEvent.created_at >= cutoff)
    events = list((await db.scalars(query)).all())

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for event in events:
        writer.writerow(
            [
                csv_safe(event.created_at.isoformat()),
                csv_safe(event.event_type.value),
                csv_safe(event.email),
                csv_safe(event.user.display_name if event.user else None),
                csv_safe(event.idp.value),
                csv_safe(event.error_code),
                csv_safe(event.ip_address),
                csv_safe(json.dumps(event.details, sort_keys=True) if event.details else None),
            ]
        )

    if not is_demo_tenant(admin.tenant_id):
        await record_admin_event(
            db,
            actor=admin,
            event_type=AuditEventType.audit_exported,
            request=request,
            details={"rows": len(events), "days": days},
        )
        await db.commit()

    filename = f"audit-{now.strftime('%Y-%m-%d')}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
