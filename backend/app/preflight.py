"""Decides what start.sh does with the database before the server starts.

On 2 and 3 November 2026 three deploys migrated the database and then never
opened their port. Render kept the previous version, which couldn't start on the
migrated database ("Can't locate revision"), so the site went down. So:

- Nothing to migrate: say so, and start.sh starts the server straight away.
- The database is at a revision this version doesn't know: a newer version
  migrated it and was rolled back. start.sh starts without migrating, since
  migrations only add to the schema.
- Migrations are waiting: first load the app and run its startup once (database
  role check, OAuth setup). A version that can't get that far stops here, and
  the database stays as the running version needs it.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import create_async_engine

# Exit codes start.sh acts on. Anything else means the check failed.
MIGRATE = 0
DATABASE_AHEAD = 3
UP_TO_DATE = 4

BACKEND_DIR = Path(__file__).resolve().parent.parent


def script_directory() -> ScriptDirectory:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return ScriptDirectory.from_config(config)


async def database_revision(url: str) -> str | None:
    """The revision Alembic last recorded, or None for an empty database."""
    engine = create_async_engine(
        url, poolclass=pool.NullPool, connect_args={"command_timeout": 60}
    )
    try:
        async with engine.connect() as connection:
            if await connection.scalar(text("SELECT to_regclass('alembic_version')")) is None:
                return None
            return await connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        await engine.dispose()


async def start_app_once() -> None:
    from app.db import engine
    from app.main import app

    async with app.router.lifespan_context(app):
        pass
    await engine.dispose()


def decide(revision: str | None, script: ScriptDirectory) -> int:
    if revision is not None and revision in script.get_heads():
        return UP_TO_DATE
    known = {rev.revision for rev in script.walk_revisions()}
    if revision is not None and revision not in known:
        return DATABASE_AHEAD
    return MIGRATE


def log(message: str) -> None:
    print(f"preflight: {message}", file=sys.stderr, flush=True)


def main() -> int:
    from app.config import settings

    revision = asyncio.run(database_revision(settings.migrations_url))
    outcome = decide(revision, script_directory())
    if outcome == UP_TO_DATE:
        log(f"the database is at {revision}, nothing to migrate")
        return outcome
    if outcome == DATABASE_AHEAD:
        log(f"the database is at {revision}, newer than this version knows")
        return outcome

    log(f"the database is at {revision or 'no revision yet'}, checking the app starts")
    # The server runs its own webhook sender; this short-lived process must not.
    settings.webhooks_worker_enabled = False
    asyncio.run(start_app_once())
    log("the app starts, ready to migrate")
    return MIGRATE


if __name__ == "__main__":
    sys.exit(main())
