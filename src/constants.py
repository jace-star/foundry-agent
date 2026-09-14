"""跨模块共享的静态常量和数据库基础配置。"""

from __future__ import annotations

from loguru import logger
from sqlalchemy.engine import make_url

# ---------------------------------------------------------------------------
# SQLAlchemy URL 驱动映射（应用侧统一使用异步驱动）
# ---------------------------------------------------------------------------

ASYNC_DRIVER_MAP: dict[str, str] = {
    "postgresql": "postgresql+asyncpg",
    "postgres": "postgresql+asyncpg",
    "mysql": "mysql+asyncmy",
    "mariadb": "mysql+asyncmy",
}


def make_sqlalchemy_url(database_url: str) -> str:
    """将数据库 URL 改写为对应的异步 SQLAlchemy driver。

    支持 PostgreSQL（asyncpg）和 MySQL（asyncmy）；已带异步驱动名的 URL 原样返回。
    """
    url = make_url(database_url)
    mapped = ASYNC_DRIVER_MAP.get(url.drivername)
    if mapped is not None:
        url = url.set(drivername=mapped)
    return url.render_as_string(hide_password=False)


# ---------------------------------------------------------------------------
# Langfuse 连通性检测
# ---------------------------------------------------------------------------


def _check_langfuse() -> None:
    """检测 Langfuse 追踪是否可用，并输出诊断日志。"""
    from src.ext.observability import get_langfuse_client, is_tracing_enabled

    if not is_tracing_enabled():
        logger.info("Langfuse 追踪未配置 (LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY 为空)，已禁用")
        return

    client = get_langfuse_client()
    if client is None:
        logger.warning("Langfuse 客户端初始化失败，追踪已禁用")
        return

    from src.config import get_settings

    try:
        health = client.api.health.health()
        logger.info(
            "Langfuse 已连接: {}, 版本 {}",
            get_settings().langfuse.host,
            health.version,
        )
    except Exception as exc:
        logger.warning(
            "Langfuse 连接失败 ({}): {} — 追踪将降级为 no-op",
            get_settings().langfuse.host,
            exc,
        )
