"""跨模块共享的静态常量和数据库基础配置。"""

from __future__ import annotations

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
