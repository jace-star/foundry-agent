"""数据库 engine、Alembic 迁移与会话管理（PostgreSQL / MySQL 异步驱动）。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from src.config import BASE_DIR, get_settings
from src.constants import make_sqlalchemy_url


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_database() -> AsyncEngine:
    """初始化数据库 engine、执行连接检测并运行 Alembic 迁移。"""
    global _engine, _session_factory
    if _engine is not None:
        logger.info("数据库 engine 已存在，跳过初始化")
        return _engine

    database = get_settings().database
    database_url = make_sqlalchemy_url(database.url)
    logger.info("正在连接数据库...")
    try:
        _engine = create_async_engine(database_url, pool_pre_ping=True)
        _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("数据库连接成功，engine 已创建")
        await _run_migrations(_engine)
    except Exception as exc:
        logger.error("数据库初始化失败: {}", exc)
        if _engine is not None:
            await _engine.dispose()
        _engine = None
        _session_factory = None
        raise
    return _engine


async def close_database() -> None:
    """关闭数据库 engine。"""
    global _engine, _session_factory
    if _engine is None:
        return
    logger.info("正在关闭数据库 engine...")
    await _engine.dispose()
    _engine = None
    _session_factory = None
    logger.info("数据库 engine 已关闭")


async def get_database_engine() -> AsyncEngine:
    """获取数据库 engine，未初始化时按需初始化。"""
    if _engine is None:
        return await init_database()
    return _engine


@asynccontextmanager
async def get_session_context() -> AsyncIterator[AsyncSession]:
    """创建一个事务边界的异步会话（供 lifespan 等非请求上下文使用）。"""
    if _session_factory is None:
        raise RuntimeError("数据库尚未初始化")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI `Depends` 使用的请求级会话生成器。

    用法:
        SessionDep = Annotated[AsyncSession, Depends(get_session)]
    """
    if _session_factory is None:
        raise RuntimeError("数据库尚未初始化")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# 内部：Alembic 迁移
# ---------------------------------------------------------------------------


async def _run_migrations(engine: AsyncEngine) -> None:
    """通过 async engine 执行 Alembic 迁移。"""
    alembic_ini = Path(BASE_DIR) / "alembic.ini"
    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(Path(BASE_DIR) / "src" / "migrations"))

    logger.info("正在执行数据库迁移: alembic upgrade head")
    async with engine.begin() as conn:
        await conn.run_sync(_do_upgrade, config)
    logger.info("数据库迁移已完成")


def _do_upgrade(connection, config: Config) -> None:
    """同步回调：将 connection 注入 alembic config 后执行 upgrade。"""
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
