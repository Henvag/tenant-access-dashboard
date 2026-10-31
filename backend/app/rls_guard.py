"""Refuse to serve traffic as a database role that skips row-level security.

Postgres ignores every RLS policy (even FORCE ROW LEVEL SECURITY) for superusers
and roles with BYPASSRLS. Neon's default ``neondb_owner`` has BYPASSRLS, so
pointing DATABASE_URL at it silently removes tenant isolation.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import settings

logger = logging.getLogger("app.rls_guard")

_ROLE_QUERY = text(
    "SELECT current_user AS role, rolsuper OR rolbypassrls AS bypasses "
    "FROM pg_roles WHERE rolname = current_user"
)


class RlsBypassError(RuntimeError):
    pass


async def role_bypasses_rls(engine: AsyncEngine) -> tuple[str, bool]:
    async with engine.connect() as connection:
        row = (await connection.execute(_ROLE_QUERY)).one()
    return str(row.role), bool(row.bypasses)


async def ensure_rls_enforced(engine: AsyncEngine) -> None:
    """Production: fail startup on a bypassing role. Elsewhere: warn only."""
    try:
        role, bypasses = await role_bypasses_rls(engine)
    except Exception:
        if settings.is_production:
            raise
        logger.warning("could not check database role for RLS bypass", exc_info=True)
        return
    if not bypasses:
        return
    message = (
        f"database role '{role}' is a superuser or has BYPASSRLS, so tenant "
        "isolation would not apply. Point DATABASE_URL at a restricted role and "
        "put the owner connection in MIGRATION_DATABASE_URL."
    )
    if settings.is_production:
        raise RlsBypassError(message)
    logger.warning(message)
