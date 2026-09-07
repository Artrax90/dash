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
        # Optimized connection pooling for high concurrency (thousands of agents)
        opts.update({
            "pool_size": 20,
            "max_overflow": 15,
            "pool_pre_ping": True,
            "pool_recycle": 1800,
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
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

