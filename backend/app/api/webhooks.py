"""Admin API for outbound webhooks (signed with Standard Webhooks)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.secrets import encrypt_secret
from app.api.deps import require_admin
from app.auth.audit import record_admin_event
from app.db import get_db
from app.models import AuditEventType, User, WebhookDelivery, WebhookEndpoint
from app.webhooks.service import (
    EVENT_TYPES,
    MAX_ENDPOINTS,
    TEST_EVENT_TYPE,
    WebhookUrlError,
    send_delivery,
    validate_url_shape,
)
from app.webhooks.signing import new_secret

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    # None or empty = every event.
    event_types: list[str] | None = None


class WebhookOut(BaseModel):
    id: UUID
    url: str
    event_types: list[str] | None
    enabled: bool
    secret_hint: str
    created_at: datetime


class WebhookCreated(WebhookOut):
    # Shown once. Stored encrypted, because signing needs the plain value.
    secret: str


class DeliveryOut(BaseModel):
    id: UUID
    event_type: str
    status: str
    attempts: int
    response_status: int | None
    last_error: str | None
    created_at: datetime
    last_attempt_at: datetime | None


class WebhookList(BaseModel):
    endpoints: list[WebhookOut]
    event_types: list[str]
    max_endpoints: int


def _out(endpoint: WebhookEndpoint) -> WebhookOut:
    return WebhookOut(
        id=endpoint.id,
        url=endpoint.url,
        event_types=endpoint.event_types,
        enabled=endpoint.enabled,
        secret_hint=endpoint.secret_hint,
        created_at=endpoint.created_at,
    )


async def _get_endpoint(db: AsyncSession, admin: User, endpoint_id: UUID) -> WebhookEndpoint:
    endpoint = await db.scalar(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id, WebhookEndpoint.tenant_id == admin.tenant_id
        )
    )
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="webhook_not_found")
    return endpoint


@router.get("", response_model=WebhookList)
async def list_webhooks(
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> WebhookList:
    rows = (
        await db.scalars(
            select(WebhookEndpoint)
            .where(WebhookEndpoint.tenant_id == admin.tenant_id)
            .order_by(WebhookEndpoint.created_at)
        )
    ).all()
    return WebhookList(
        endpoints=[_out(row) for row in rows],
        event_types=list(EVENT_TYPES),
        max_endpoints=MAX_ENDPOINTS,
    )


@router.post("", response_model=WebhookCreated, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> WebhookCreated:
    try:
        url = validate_url_shape(body.url)
    except WebhookUrlError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    event_types: list[str] | None = None
    if body.event_types:
        unknown = sorted(set(body.event_types) - set(EVENT_TYPES))
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="webhook_event_unknown"
            )
        event_types = sorted(set(body.event_types))

    count = await db.scalar(
        select(func.count())
        .select_from(WebhookEndpoint)
        .where(WebhookEndpoint.tenant_id == admin.tenant_id)
    )
    if (count or 0) >= MAX_ENDPOINTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="webhook_limit_reached")

    secret = new_secret()
    endpoint = WebhookEndpoint(
        tenant_id=admin.tenant_id,
        url=url,
        secret_encrypted=encrypt_secret(secret),
        secret_hint=secret[-4:],
        event_types=event_types,
        enabled=True,
        created_by=admin.id,
    )
    db.add(endpoint)
    await db.flush()
    await db.refresh(endpoint, ["created_at"])
    await record_admin_event(
        db,
        actor=admin,
        event_type=AuditEventType.webhook_created,
        request=request,
        details={"url": url},
    )
    await db.commit()
    return WebhookCreated(**_out(endpoint).model_dump(), secret=secret)


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    endpoint_id: UUID,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    endpoint = await _get_endpoint(db, admin, endpoint_id)
    url = endpoint.url
    await db.delete(endpoint)
    await db.flush()
    await record_admin_event(
        db,
        actor=admin,
        event_type=AuditEventType.webhook_deleted,
        request=request,
        details={"url": url},
    )
    await db.commit()


@router.get("/{endpoint_id}/deliveries", response_model=list[DeliveryOut])
async def list_deliveries(
    endpoint_id: UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[DeliveryOut]:
    await _get_endpoint(db, admin, endpoint_id)
    rows = (
        await db.scalars(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.endpoint_id == endpoint_id,
                WebhookDelivery.tenant_id == admin.tenant_id,
            )
            .order_by(WebhookDelivery.created_at.desc())
            .limit(20)
        )
    ).all()
    return [
        DeliveryOut(
            id=row.id,
            event_type=row.event_type,
            status=row.status,
            attempts=row.attempts,
            response_status=row.response_status,
            last_error=row.last_error,
            created_at=row.created_at,
            last_attempt_at=row.last_attempt_at,
        )
        for row in rows
    ]


@router.post("/{endpoint_id}/test", response_model=DeliveryOut)
async def send_test(
    endpoint_id: UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DeliveryOut:
    """Send one ``webhook.test`` event right away and report how the receiver answered."""
    endpoint = await _get_endpoint(db, admin, endpoint_id)
    delivery = WebhookDelivery(
        tenant_id=admin.tenant_id,
        endpoint_id=endpoint.id,
        event_type=TEST_EVENT_TYPE,
        payload={
            "type": TEST_EVENT_TYPE,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {"tenant_id": str(admin.tenant_id), "sent_by": admin.email},
        },
        status="pending",
        attempts=0,
    )
    db.add(delivery)
    await db.flush()
    await send_delivery(db, delivery, endpoint)
    if delivery.status == "pending":
        # A test is one attempt; it is not retried.
        delivery.status = "failed"
    await db.refresh(delivery, ["created_at"])
    await db.commit()
    return DeliveryOut(
        id=delivery.id,
        event_type=delivery.event_type,
        status=delivery.status,
        attempts=delivery.attempts,
        response_status=delivery.response_status,
        last_error=delivery.last_error,
        created_at=delivery.created_at,
        last_attempt_at=delivery.last_attempt_at,
    )
