"""Outbound webhooks: queue audit events, send them signed, retry with backoff.

Enqueueing happens inside the request's transaction (an outbox), so a webhook
exists only if the audit row it describes was committed. A background task
(``worker.py``) sends due deliveries.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.secrets import decrypt_secret
from app.demo import is_demo_tenant
from app.models import AuditEvent, AuditEventType, WebhookDelivery, WebhookEndpoint, WebhookOutbox
from app.webhooks.signing import sign

MAX_ENDPOINTS = 3
SEND_TIMEOUT_SECONDS = 5.0
# Delay before attempt n+1, after attempt n failed. Six attempts over about 7 hours.
RETRY_DELAYS = (
    timedelta(seconds=30),
    timedelta(minutes=2),
    timedelta(minutes=10),
    timedelta(hours=1),
    timedelta(hours=6),
)
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1
KEEP_DELIVERIES = timedelta(days=30)
TEST_EVENT_TYPE = "webhook.test"

EVENT_TYPES = tuple(item.value for item in AuditEventType)


class WebhookUrlError(ValueError):
    pass


def validate_url_shape(url: str) -> str:
    """https only, a hostname, no credentials. Address checks happen at send time."""
    cleaned = url.strip()
    parts = urlsplit(cleaned)
    if parts.scheme != "https" or not parts.hostname:
        raise WebhookUrlError("https_url_required")
    if parts.username or parts.password:
        raise WebhookUrlError("webhook_url_invalid")
    if len(cleaned) > 2048:
        raise WebhookUrlError("webhook_url_invalid")
    host = parts.hostname.lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".internal"):
        raise WebhookUrlError("webhook_url_private")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise WebhookUrlError("webhook_url_private")
    return cleaned


async def assert_public_host(url: str) -> None:
    """Refuse to send to private, loopback or link-local addresses (SSRF)."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = parts.port or 443
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            host, port, type=socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise WebhookUrlError("webhook_dns_failed") from exc
    if not infos:
        raise WebhookUrlError("webhook_dns_failed")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise WebhookUrlError("webhook_url_private")


def event_payload(event: AuditEvent) -> dict:
    return {
        "type": event.event_type.value,
        "timestamp": (event.created_at or datetime.now(UTC)).isoformat(),
        "data": {
            "id": str(event.id),
            "tenant_id": str(event.tenant_id),
            "email": event.email,
            "idp": event.idp.value,
            "error_code": event.error_code,
            "ip_address": event.ip_address,
            "details": event.details,
        },
    }


def endpoint_wants(endpoint: WebhookEndpoint, event_type: str) -> bool:
    if event_type == TEST_EVENT_TYPE:
        return True
    return endpoint.event_types is None or event_type in endpoint.event_types


async def enqueue_for_event(session: AsyncSession, event: AuditEvent) -> int:
    """Queue one delivery per subscribed endpoint. RLS must already be set for the tenant."""
    if is_demo_tenant(event.tenant_id):
        return 0
    endpoints = list(
        (
            await session.scalars(
                select(WebhookEndpoint).where(
                    WebhookEndpoint.tenant_id == event.tenant_id,
                    WebhookEndpoint.enabled.is_(True),
                )
            )
        ).all()
    )
    targets = [ep for ep in endpoints if endpoint_wants(ep, event.event_type.value)]
    if not targets:
        return 0
    if event.created_at is None:
        await session.refresh(event, ["created_at"])
    payload = event_payload(event)
    now = datetime.now(UTC)
    for endpoint in targets:
        delivery = WebhookDelivery(
            tenant_id=event.tenant_id,
            endpoint_id=endpoint.id,
            event_type=event.event_type.value,
            payload=payload,
            status="pending",
            attempts=0,
        )
        session.add(delivery)
        await session.flush()
        session.add(
            WebhookOutbox(delivery_id=delivery.id, tenant_id=event.tenant_id, next_attempt_at=now)
        )
    # Keep the delivery log short.
    await session.execute(
        delete(WebhookDelivery).where(
            WebhookDelivery.tenant_id == event.tenant_id,
            WebhookDelivery.created_at < now - KEEP_DELIVERIES,
            WebhookDelivery.status != "pending",
        )
    )
    await session.flush()
    return len(targets)


async def _post(url: str, headers: dict[str, str], body: bytes) -> httpx.Response:
    async with httpx.AsyncClient(timeout=SEND_TIMEOUT_SECONDS, follow_redirects=False) as client:
        return await client.post(url, content=body, headers=headers)


async def send_delivery(
    session: AsyncSession,
    delivery: WebhookDelivery,
    endpoint: WebhookEndpoint,
) -> bool:
    """One attempt. Updates the delivery row; returns True when the receiver answered 2xx."""
    body = json.dumps(delivery.payload, separators=(",", ":"), sort_keys=True).encode()
    msg_id = f"msg_{delivery.id.hex}"
    timestamp = int(time.time())
    delivery.attempts += 1
    delivery.last_attempt_at = datetime.now(UTC)
    delivery.response_status = None
    delivery.last_error = None
    ok = False
    try:
        await assert_public_host(endpoint.url)
        secret = decrypt_secret(endpoint.secret_encrypted)
        headers = {
            "content-type": "application/json",
            "user-agent": "TenantAccess-Webhooks/1",
            "webhook-id": msg_id,
            "webhook-timestamp": str(timestamp),
            "webhook-signature": sign(secret, msg_id, timestamp, body),
        }
        response = await _post(endpoint.url, headers, body)
        delivery.response_status = response.status_code
        ok = 200 <= response.status_code < 300
        if not ok:
            delivery.last_error = f"HTTP {response.status_code}"
    except WebhookUrlError as exc:
        delivery.last_error = str(exc)
    except ValueError as exc:  # secret unreadable
        delivery.last_error = str(exc)[:255]
    except httpx.TimeoutException:
        delivery.last_error = "timeout"
    except httpx.HTTPError as exc:
        delivery.last_error = type(exc).__name__[:255]

    if ok:
        delivery.status = "succeeded"
    elif delivery.attempts >= MAX_ATTEMPTS:
        delivery.status = "failed"
    else:
        delivery.status = "pending"
    await session.flush()
    return ok


def next_attempt_after(attempts: int) -> datetime | None:
    """When to retry after ``attempts`` failed tries; None when out of retries."""
    if attempts >= MAX_ATTEMPTS:
        return None
    return datetime.now(UTC) + RETRY_DELAYS[attempts - 1]


async def load_for_send(
    session: AsyncSession, delivery_id: UUID
) -> tuple[WebhookDelivery, WebhookEndpoint] | None:
    delivery = await session.get(WebhookDelivery, delivery_id)
    if delivery is None:
        return None
    endpoint = await session.get(WebhookEndpoint, delivery.endpoint_id)
    if endpoint is None:
        return None
    return delivery, endpoint
