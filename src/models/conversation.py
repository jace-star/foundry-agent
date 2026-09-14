"""会话与事件 ORM 模型。

Conversation  — 会话元数据（归属、标题、agent_key）
ConversationEvent — 事件流（每行一个事件，纯追加）
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import JSON, Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """返回 naive UTC 时间，与数据库 TIMESTAMP(6) WITHOUT TIME ZONE 列匹配。"""
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Conversation 会话表
# ---------------------------------------------------------------------------


class Conversation(SQLModel, table=True):
    """会话元数据表。"""

    __tablename__ = "conversations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    api_key_id: UUID | None = Field(default=None, foreign_key="api_keys.id", index=True)
    title: str = Field(default="", max_length=256)
    agent_key: str = Field(default="", max_length=64, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    last_active_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# ConversationEvent 事件表
# ---------------------------------------------------------------------------


class ConversationEvent(SQLModel, table=True):
    """事件流表 — 每行一个事件，纯追加写入。"""

    __tablename__ = "conversation_events"

    id: int = Field(default=None, primary_key=True)
    conversation_id: UUID = Field(
        default=None, foreign_key="conversations.id", index=True
    )
    event: dict = Field(
        default_factory=dict,
        # JSON 可移植；PostgreSQL 上优先使用 JSONB
        sa_column=Column(JSON().with_variant(JSONB(), "postgresql")),
    )
    created_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# API 请求 / 响应模型
# ---------------------------------------------------------------------------


class ConversationSummary(BaseModel):
    """会话列表项。"""

    id: str
    title: str
    last_active_at: datetime


class ConversationListResponse(BaseModel):
    """会话分页列表响应。"""

    items: list[ConversationSummary]
    total: int
    page: int
    page_size: int


class BatchDeleteRequest(BaseModel):
    """批量删除请求。"""

    ids: list[str]


class BatchDeleteResponse(BaseModel):
    """批量删除响应。"""

    deleted: list[str]
    not_found: list[str]
    forbidden: list[str]


class AdminConversationSummary(BaseModel):
    """管理员会话列表项（含归属信息）。"""

    id: str
    title: str
    agent_key: str
    owner: dict  # {"type": "user"|"api_key", "id": "...", "name": "..."}
    created_at: datetime
    last_active_at: datetime


class AdminConversationListResponse(BaseModel):
    """管理员会话分页列表响应。"""

    items: list[AdminConversationSummary]
    total: int
    page: int
    page_size: int


class AdminConversationDetailResponse(BaseModel):
    """管理员会话详情响应。"""

    id: str
    title: str
    agent_key: str
    owner: dict
    events: list[dict]
    created_at: datetime
    last_active_at: datetime
