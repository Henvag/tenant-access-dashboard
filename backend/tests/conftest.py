import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TEST_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/access_dashboard_test"

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)

APP_ROLE = "app_test"
APP_PASSWORD = "app_test"


def _admin_url() -> str:
    return os.environ["DATABASE_URL"]


def _app_url(admin_url: str) -> str:
    url = make_url(admin_url)
    return url.set(username=APP_ROLE, password=APP_PASSWORD).render_as_string(
        hide_password=False
    )


async def _prepare_database() -> None:
    subprocess.check_call(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": _admin_url()},
    )
    admin_engine = create_async_engine(_admin_url(), pool_pre_ping=True, poolclass=NullPool)
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    f"""
                    DO $$
                    BEGIN
                      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                        CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_PASSWORD}'
                          NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS;
                      END IF;
                    END
                    $$;
                    """
                )
            )
            await connection.execute(
                text(
                    f"ALTER ROLE {APP_ROLE} WITH LOGIN PASSWORD '{APP_PASSWORD}' "
                    "NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS"
                )
            )
            db_name = make_url(_admin_url()).database
            await connection.execute(text(f"GRANT CONNECT ON DATABASE {db_name} TO {APP_ROLE}"))
            await connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
            await connection.execute(
                text(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"
                )
            )
            await connection.execute(text(f"GRANT USAGE ON TYPE user_role TO {APP_ROLE}"))
            await connection.execute(
                text(f"GRANT USAGE ON TYPE identity_provider TO {APP_ROLE}")
            )
            await connection.execute(
                text(f"GRANT USAGE ON TYPE audit_event_type TO {APP_ROLE}")
            )
            await connection.execute(
                text(f"GRANT USAGE ON TYPE oauth_access_policy TO {APP_ROLE}")
            )
            await connection.execute(text(f"GRANT USAGE ON TYPE tenant_plan TO {APP_ROLE}"))
    finally:
        await admin_engine.dispose()


@pytest.fixture(scope="session")
def prepared_database() -> None:
    admin_engine = create_async_engine(_admin_url(), pool_pre_ping=True, poolclass=NullPool)

    async def _ping() -> None:
        async with admin_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        await admin_engine.dispose()

    try:
        asyncio.run(_ping())
    except Exception as exc:
        pytest.skip(f"Postgres is not available for RLS tests: {exc}")

    try:
        asyncio.run(_prepare_database())
    except Exception as exc:
        pytest.skip(f"Could not prepare test database: {exc}")


@pytest.fixture
async def app_engine(prepared_database: None) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(_app_url(_admin_url()), pool_pre_ping=True, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def app_session_factory(app_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(app_engine, expire_on_commit=False, class_=AsyncSession)
