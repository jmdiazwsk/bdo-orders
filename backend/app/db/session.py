#C:\bdo-orders-platform\backend\app\db\session.py
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.settings import settings

class Base(DeclarativeBase):
    pass

engine = create_async_engine(
    settings.database_url, echo=False, future=True, pool_pre_ping=True
)
AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, autoflush=False, autocommit=False, class_=AsyncSession
)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

def get_async_session_maker():
    return AsyncSessionLocal