"""后台任务管理器。

职责：
- 管理同进程 asyncio.Task 生命周期
- Redis Pub/Sub 发布实时 SSE 事件
- 支持 stop / 重连

MVP 限制：仅保证同进程后台执行，服务重启/多 worker 时任务可能丢失。
"""

from __future__ import annotations

import asyncio
import json
from typing import Literal
from uuid import UUID

from loguru import logger
from pydantic import BaseModel

from src.ext.redis import get_redis

# Redis channel 前缀
CHANNEL_PREFIX = "agent:task:"


class RunningTask(BaseModel):
    """运行中任务的元信息。"""

    task_id: str
    conversation_id: UUID | None
    owner_type: Literal["user", "api_key"]
    owner_id: UUID


class TaskManager:
    """同进程后台任务生命周期管理器。"""

    _tasks: dict[str, asyncio.Task] = {}
    _meta: dict[str, RunningTask] = {}

    @classmethod
    def channel(cls, task_id: str) -> str:
        """返回指定 task 的 Redis Pub/Sub channel 名称。"""
        return f"{CHANNEL_PREFIX}{task_id}"

    @classmethod
    async def create(cls, meta: RunningTask, coro) -> asyncio.Task:
        """创建并启动后台任务。"""
        task = asyncio.create_task(coro)
        cls._tasks[meta.task_id] = task
        cls._meta[meta.task_id] = meta
        task.add_done_callback(lambda _task: cls.remove(meta.task_id))
        logger.info("后台任务已创建: task_id={}, conv={}", meta.task_id, meta.conversation_id)
        return task

    @classmethod
    async def cancel(cls, task_id: str) -> bool:
        """取消指定任务，返回是否成功。"""
        task = cls._tasks.get(task_id)
        if task is None:
            return False
        task.cancel()
        logger.info("后台任务已取消: task_id={}", task_id)
        return True

    @classmethod
    def get(cls, task_id: str) -> asyncio.Task | None:
        """获取指定任务。"""
        return cls._tasks.get(task_id)

    @classmethod
    def get_meta(cls, task_id: str) -> RunningTask | None:
        """获取任务元信息。"""
        return cls._meta.get(task_id)

    @classmethod
    def remove(cls, task_id: str) -> None:
        """清理已完成/已取消的任务记录。"""
        cls._tasks.pop(task_id, None)
        cls._meta.pop(task_id, None)

    @classmethod
    async def publish_event(cls, task_id: str, event: dict) -> None:
        """向 Redis Pub/Sub 发布一个实时事件。"""
        try:
            redis = await get_redis()
            channel = cls.channel(task_id)
            payload = json.dumps(event, ensure_ascii=False)
            await redis.publish(channel, payload)
        except Exception:
            logger.opt(exception=True).warning(
                "Redis Pub/Sub 发布失败: task_id={}", task_id
            )
