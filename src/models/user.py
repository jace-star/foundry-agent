"""用户与登录相关的数据模型。

User 同时是 SQLModel ORM 模型和 Pydantic 模型 —— 无需 Entity / Record 双份定义。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, field_validator
from sqlalchemy import Text
from sqlmodel import Field, SQLModel


_ACCOUNT_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


# ---------------------------------------------------------------------------
# 公共工具函数（供 router 和 auth 模块共用）
# ---------------------------------------------------------------------------


def parse_uuid(raw: str | UUID) -> UUID | None:
    """把路由中的字符串 ID 解析为 UUID，非法值返回 None。"""
    if isinstance(raw, UUID):
        return raw
    try:
        return UUID(raw)
    except (ValueError, AttributeError):
        return None


def _utcnow() -> datetime:
    """返回 naive UTC 时间，与数据库 TIMESTAMP WITHOUT TIME ZONE 列匹配。"""
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# 持久化 + 公共模型（继承复用）
# ---------------------------------------------------------------------------


class UserBase(SQLModel):
    """用户基础字段，User 和 UserPublic 共用。"""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    account: str = Field(max_length=64, unique=True)
    name: str = Field(default="", max_length=128)
    role: str = Field(default="user", max_length=64)
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class User(UserBase, table=True):
    """users 表 ORM 模型。password 存的是 Service 层 hash 后的值。"""

    __tablename__ = "users"
    password: str = Field(sa_type=Text)


class UserPublic(UserBase):
    """对外返回的用户信息，不含密码。"""

    pass


# ---------------------------------------------------------------------------
# API 请求 / 响应模型
# ---------------------------------------------------------------------------


class UserCreateRequest(BaseModel):
    """创建用户请求。"""

    account: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    name: str = Field(default="", max_length=128)
    role: str = Field(default="user", max_length=64)
    is_active: bool = True

    @field_validator("account")
    @classmethod
    def validate_account(cls, value: str) -> str:
        if not _ACCOUNT_PATTERN.match(value):
            raise ValueError("account 只允许字母、数字、下划线和连字符")
        return value


class UserUpdateRequest(BaseModel):
    """更新用户请求。"""

    password: str | None = Field(default=None, min_length=6, max_length=128)
    name: str | None = Field(default=None, max_length=128)
    role: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None


class UserLoginRequest(BaseModel):
    """登录请求。"""

    account: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    """登录成功响应数据（refreshToken 通过 httpOnly cookie 下发，不出现在 body 中）。"""

    accessToken: str
    tokenType: str = "Bearer"
    user: UserPublic


class UserChangePasswordRequest(BaseModel):
    """当前用户自助修改密码。"""

    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)
