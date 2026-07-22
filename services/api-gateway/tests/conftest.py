import os
import tempfile
from pathlib import Path

from dotenv import dotenv_values

# Must run before any `app.*` import - app.db.session reads Settings() at
# import time. Tests run on the host, not inside the docker-compose network,
# so we load the same credentials the app containers use from the repo-root
# .env, then override just the host: "postgres" (the compose service name)
# doesn't resolve here, but docker-compose publishes the port to localhost.
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
for _key, _value in dotenv_values(_ROOT_ENV).items():
    if _value is not None:
        os.environ.setdefault(_key, _value)
os.environ["POSTGRES_HOST"] = "localhost"

# Same host-vs-container gap as POSTGRES_HOST above: STATEMENT_UPLOAD_DIR is an
# absolute container path (e.g. "/app/files"), which on the host resolves to a
# nonsense location (e.g. the current drive's root on Windows). Point it at a
# real temp dir instead.
os.environ["STATEMENT_UPLOAD_DIR"] = str(
    Path(tempfile.gettempdir()) / "envelo-statement-uploads-test"
)

import pytest_asyncio  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402


@pytest_asyncio.fixture
async def db_session():
    """One test = one DB transaction, rolled back at the end.

    A fresh engine per test (rather than the app's module-level singleton)
    avoids binding a long-lived connection pool to one test's event loop and
    then reusing it from another - pytest-asyncio gives each test function its
    own loop by default.

    Repo functions call db.commit() themselves; join_transaction_mode=
    "create_savepoint" makes those commits release a SAVEPOINT instead of the
    real outer transaction, so nothing written during a test is ever persisted
    against the shared dev database.
    """
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as connection:
        await connection.begin()
        session_factory = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        session = session_factory()
        try:
            yield session
        finally:
            await session.close()
            await connection.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
