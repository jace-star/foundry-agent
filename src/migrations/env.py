from __future__ import annotations

import asyncio
from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))

from sqlmodel import SQLModel  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.constants import make_sqlalchemy_url  # noqa: E402
from src.models.user import User  # noqa: E402, F401 — 注册模型到 SQLModel.metadata
from src.models.api_key import ApiKey  # noqa: E402, F401 — 注册模型到 SQLModel.metadata
from src.models.conversation import Conversation, ConversationEvent  # noqa: E402, F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _database_url() -> str:
    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url and "agent:agent@localhost" not in configured_url:
        return make_sqlalchemy_url(configured_url)
    return make_sqlalchemy_url(get_settings().database.url)


def run_migrations_offline() -> None:
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """优先使用 database.py 通过 config.attributes 传入的 connection，
    否则自行创建异步引擎（支持直接运行 alembic 命令）。"""
    connection = config.attributes.get("connection")
    if connection is not None:
        do_run_migrations(connection)
        return

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async def _async_main() -> None:
        async with connectable.connect() as conn:
            await conn.run_sync(do_run_migrations)
        await connectable.dispose()

    asyncio.run(_async_main())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
