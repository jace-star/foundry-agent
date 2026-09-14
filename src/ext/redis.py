"""Redis 客户端单例（基于 redis.asyncio 异步驱动）。"""

from __future__ import annotations

import redis.asyncio as aioredis
from loguru import logger

from src.config import get_settings


_client: aioredis.Redis | None = None


async def init_redis() -> aioredis.Redis:
    """初始化 Redis 连接并执行连通性检测。"""
    global _client
    if _client is not None:
        logger.info("Redis 客户端已存在，跳过初始化")
        return _client

    redis_settings = get_settings().redis
    logger.info("正在连接 Redis: {}:{}", redis_settings.host, redis_settings.port)
    try:
        _client = aioredis.Redis(
            host=redis_settings.host,
            port=redis_settings.port,
            db=redis_settings.db,
            decode_responses=True,
        )
        await _client.ping()
        logger.info("Redis 连接成功")
    except Exception as exc:
        logger.error("Redis 初始化失败: {}", exc)
        if _client is not None:
            await _client.aclose()
        _client = None
        raise
    return _client


async def close_redis() -> None:
    """关闭 Redis 连接。"""
    global _client
    if _client is None:
        return
    logger.info("正在关闭 Redis 连接...")
    await _client.aclose()
    _client = None
    logger.info("Redis 连接已关闭")


async def get_redis() -> aioredis.Redis:
    """获取 Redis 客户端，未初始化时按需初始化。"""
    if _client is None:
        return await init_redis()
    return _client
