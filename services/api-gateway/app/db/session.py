from collections.abc import AsyncGenerator

from app.core.config import get_settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

settings = get_settings()

# Start async database engine with pool pre-ping for every SQLAlchemy connection
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    # Open new SQLAlchemy session. One session per request pattern
    async with async_session_maker() as session:
        yield session
