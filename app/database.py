from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

settings = get_settings()

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    future=True,
    echo=False,
    pool_pre_ping=True,       # 自动检测断开的连接
    pool_size=10,
    max_overflow=20,
)

Base = declarative_base()

async_session = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：提供异步数据库会话。"""
    async with async_session() as session:
        yield session


# 别名，兼容 documents.py / chat.py 里的 Depends(get_db)
get_db = get_async_session


async def init_db() -> None:
    """启动时建表（开发用；生产建议改用 Alembic）。"""
    # 必须先 import models，让 Base.metadata 感知到所有表
    import app.models.user      # noqa: F401
    import app.models.document  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """关闭引擎，释放连接池。"""
    await engine.dispose()
