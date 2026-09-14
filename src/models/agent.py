"""Agent 配置相关的数据模型。"""

import re
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator

# key 只允许字母、数字、下划线、连字符
_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class AgentConfig(BaseModel):
    """Agent 完整配置。

    config.json 中存储除 system_prompt 外的所有字段。
    system_prompt 单独存储在 prompt.md 中。
    """

    # 唯一标识，由服务端生成（uuid4 hex）
    id: str
    # 业务标识，作为 agents/ 下的目录名，全局唯一
    key: str = Field(..., min_length=1, max_length=64)
    # Agent 名称
    name: str = Field(..., min_length=1, max_length=128)
    # 可选描述
    description: str = ""
    # 系统提示词，存储在 prompt.md 中
    system_prompt: str = ""
    # 关联的 MCP server 名称列表，引用已有 MCPServerConfig.name
    tool_servers: list[str] = Field(default_factory=list)
    # 是否为首页默认智能体
    is_home: bool = False
    # 时间戳，ISO 8601 格式字符串
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        if not _KEY_PATTERN.match(v):
            raise ValueError("key 只允许字母、数字、下划线和连字符")
        return v


class AgentCreateRequest(BaseModel):
    """创建 Agent 时前端提交的请求体，不含 id 和时间戳。"""

    key: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    system_prompt: str = ""
    tool_servers: list[str] = Field(default_factory=list)

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        if not _KEY_PATTERN.match(v):
            raise ValueError("key 只允许字母、数字、下划线和连字符")
        return v


class AgentUpdateRequest(BaseModel):
    """更新 Agent 的请求体，所有字段可选（PATCH 语义）。key 不可修改。"""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    system_prompt: str | None = None
    tool_servers: list[str] | None = None


class AgentSummary(BaseModel):
    """Agent 列表展示用的精简模型，不包含 system_prompt（可能很长）。"""

    id: str
    key: str
    name: str
    description: str
    tool_servers: list[str]
    is_home: bool
    created_at: datetime
    updated_at: datetime
