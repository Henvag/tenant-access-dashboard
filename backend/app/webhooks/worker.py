"""Background sender for queued webhook deliveries (one per process)."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rls import set_tenant_rls
from app.models import WebhookOutbox
from app.webhooks.service import load_for_send, next_attempt_after, send_delivery

log = logging.getLogger(__name__)

POLL_SECONDS = 5.0
BATCH = 20


async def run_once(factory: async_sessionmaker[AsyncSession]) -> int:
    """Send every due delivery once. Returns how many were attempted."""
    async with factory() as session:
        rows = list(
            (
                await session.execute(
                    select(WebhookOutbox.delivery_id, WebhookOutbox.tenant_id)
                    .where(WebhookOutbox.next_attempt_at <= func.now())
                    .order_by(WebhookOutbox.next_attempt_at)
                    .limit(BATCH)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for delivery_id, tenant_id in rows:
            # The outbox is tenant-free; the delivery and endpoint are read
            # under that tenant's RLS context only.
            await set_tenant_rls(session, tenant_id)
            outbox = await session.get(WebhookOutbox, delivery_id)
            loaded = await load_for_send(session, delivery_id)
            if loaded is None or outbox is None:
                if outbox is not None:
                    await session.delete(outbox)
                continue
            delivery, endpoint = loaded
            if not endpoint.enabled:
                delivery.status = "failed"
                delivery.last_error = "endpoint_disabled"
                await session.delete(outbox)
                continue
            ok = await send_delivery(session, delivery, endpoint)
            retry_at = None if ok else next_attempt_after(delivery.attempts)
            if retry_at is None:
                await session.delete(outbox)
            else:
                outbox.next_attempt_at = retry_at
        await session.commit()
        return len(rows)


async def run_forever(factory: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            await run_once(factory)
        except asyncio.CancelledError:
            raise
        except Exception:  # keep sending after a bad batch or a DB blip
            log.exception("webhook worker batch failed")
        await asyncio.sleep(POLL_SECONDS)
