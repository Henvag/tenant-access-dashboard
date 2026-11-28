"""Background worker for queued account changes (one per process), like webhooks/worker.py."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rls import set_tenant_rls
from app.models import AppAccount, ProvisionOutbox
from app.provisioning.service import sync_account

log = logging.getLogger(__name__)

POLL_SECONDS = 5.0
BATCH = 20


async def run_once(factory: async_sessionmaker[AsyncSession]) -> int:
    """Work through every due account once. Returns how many were tried."""
    async with factory() as session:
        rows = list(
            (
                await session.execute(
                    select(ProvisionOutbox.account_id, ProvisionOutbox.tenant_id)
                    .where(ProvisionOutbox.next_attempt_at <= func.now())
                    .order_by(ProvisionOutbox.next_attempt_at)
                    .limit(BATCH)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for account_id, tenant_id in rows:
            await set_tenant_rls(session, tenant_id)
            outbox = await session.get(ProvisionOutbox, account_id)
            account = await session.get(AppAccount, account_id)
            if outbox is None:
                continue
            if account is None:
                await session.delete(outbox)
                continue
            try:
                retry_at = await sync_account(session, account)
            except Exception:  # one odd account must not stop the others
                log.exception("provisioning account %s failed", account_id)
                retry_at = datetime.now(UTC) + timedelta(minutes=10)
            if retry_at is None:
                # Core delete: the account row may be gone already, taking this with it.
                await session.execute(
                    delete(ProvisionOutbox).where(ProvisionOutbox.account_id == account_id)
                )
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
        except Exception:  # keep going after a bad batch or a DB blip
            log.exception("provisioning worker batch failed")
        await asyncio.sleep(POLL_SECONDS)
