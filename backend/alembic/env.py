import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.models import AuditEvent, Tenant, User  # noqa: F401 — register metadata
from app.models.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Migrations need the table owner; the app itself runs as a restricted role.
config.set_main_option("sqlalchemy.url", settings.migrations_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


# asyncpg waits forever by default, for a query and for the server to close the
# connection. On deploy that turns a stuck lock or a connection Neon never closes
# into a container that hangs until Render gives up (15 minutes), with the old
# version unable to start on the migrated database. These limits make it fail
# fast instead, so start.sh can retry.
MIGRATION_CONNECT_ARGS = {
    # Seconds for any one statement, and for closing the connection.
    "command_timeout": 120,
    # Give up waiting for a lock that the running app or another session holds.
    "server_settings": {"lock_timeout": "30s"},
}


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=MIGRATION_CONNECT_ARGS,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
