from typing import Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from backend.app.core.config import settings

def is_postgres_url(url: str) -> bool:
    """Return True if the database URL points to a PostgreSQL database."""
    if not url:
        return False
    u = url.lower()
    return u.startswith("postgresql") or u.startswith("postgres")

def get_engine_options(database_url: str) -> Dict[str, Any]:
    """Return database engine options tailored for SQLite or PostgreSQL."""
    opts: Dict[str, Any] = {
        "echo": False,
        "future": True,
    }
    if is_postgres_url(database_url):
        # Enterprise high-concurrency connection pooling (thousands of agents & dashboards)
        opts.update({
            "pool_size": 30,
            "max_overflow": 20,
            "pool_timeout": 15,
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_reset_on_return": "rollback",
        })
    return opts

engine = create_async_engine(
    settings.DATABASE_URL,
    **get_engine_options(settings.DATABASE_URL)
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Alias for backwards compatibility
SessionLocal = AsyncSessionLocal

Base = declarative_base()

async def get_db():
    session = AsyncSessionLocal()
    try:
        yield session
        if session.in_transaction():
            await session.commit()
    except BaseException:
        if session.in_transaction():
            await session.rollback()
        raise
    finally:
        await session.close()


