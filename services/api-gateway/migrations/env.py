import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# migrations/env.py runs via the `alembic` console script, whose sys.path
# doesn't include this project's root the way `python -m` would - add it so
# `app.*` imports below resolve regardless of the invoking working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Alembic is run from the host (not inside the docker-compose network), same
# as pytest - see tests/conftest.py for the identical pattern. Settings()
# reads env_file=".env" relative to cwd, which only resolves when invoked
# from the repo root, so load the repo-root .env explicitly here too, then
# override postgres_host since "postgres" (the compose service name) isn't
# resolvable from the host - docker-compose publishes the port to localhost.
from dotenv import dotenv_values  # noqa: E402

_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
for _key, _value in dotenv_values(_ROOT_ENV).items():
    if _value is not None:
        os.environ.setdefault(_key, _value)
os.environ["POSTGRES_HOST"] = "localhost"

from app.core.config import get_settings  # noqa: E402
from app.db.models import Base  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# This service's schemas (auth, budget, transactions) all share one Postgres
# instance for now (see docs/architecture.md - Database strategy). Keeping
# alembic_version inside "budget" rather than "public" keeps this service's
# migration state out of the way of future services' own Alembic setups
# against the same instance.
VERSION_TABLE_SCHEMA = "budget"


def get_url() -> str:
    return get_settings().database_url.render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema=VERSION_TABLE_SCHEMA,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema=VERSION_TABLE_SCHEMA,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
