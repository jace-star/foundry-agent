"""API Key 相关数据模型。

API Key 是全局服务凭证，供外部程序调用 Agent API。
持有有效 API Key 即可访问大部分接口（除用户管理和 API Key 管理外）。
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """返回 naive UTC 时间，与数据库 TIMESTAMP WITHOUT TIME ZONE 列匹配。"""
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# ORM 模型（数据库表）
# ---------------------------------------------------------------------------


class ApiKey(SQLModel, table=True):
    """api_keys 表 ORM 模型。"""

    __tablename__ = "api_keys"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # 可读名称，方便管理员识别
    name: str = Field(default="", max_length=128)
    # SHA-256 哈希，用于验证（唯一索引，O(1) 查找）
    key_hash: str = Field(max_length=64, unique=True, index=True)
    # Fernet 加密后的完整 key，用于管理员后续复制
    encrypted_key: str = Field(default="", sa_type=Text)
    # 过期时间，None 表示永不过期
    expires_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    last_used_at: datetime | None = Field(default=None)


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class ApiKeyCreateRequest(BaseModel):
    """创建 API Key 请求。"""

    name: str = Field(default="", max_length=128)
    # 过期天数：null/0 表示永不过期，正整数表示 N 天后过期
    expires_in_days: int | None = Field(default=None, ge=0)


class ApiKeyCreateResponse(BaseModel):
    """创建 API Key 响应，明文 key 仅创建时返回。"""

    api_key: str
    id: str
    name: str
    expires_at: datetime | None = None


class ApiKeyRevealResponse(BaseModel):
    """获取完整 API Key 的响应。"""

    api_key: str
    id: str
    name: str


class ApiKeyTestResponse(BaseModel):
    """API Key 测试结果。"""

    valid: bool
    reason: str = ""
    name: str = ""
    expires_at: datetime | None = None


class ApiKeySummary(BaseModel):
    """API Key 列表展示项（不含 key_hash 和 encrypted_key）。"""

    id: str
    name: str
    expires_at: datetime | None = None
    created_at: datetime
    last_used_at: datetime | None = None
