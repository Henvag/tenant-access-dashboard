import logging

from sqlalchemy import text

from app.db import engine

logger = logging.getLogger("app.health")


async def database_reachable() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("database health check failed")
        return False
