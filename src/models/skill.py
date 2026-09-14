"""技能配置相关的数据模型。

每个技能存储在 agents/{agent_key}/skills/{skill_name}/skill.md 中。
格式：
  ---
  - name: 技能名
  - description: 描述
  - allowed_tools: *
  ---

  提示词正文
"""

from __future__ import annotations

import re

import yaml
from pydantic import BaseModel, Field, field_validator

_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
_SEP = "---"


class SkillConfig(BaseModel):
    """技能完整配置。"""

    name: str = Field(..., min_length=1, max_length=64)
    description: str = ""
    # 允许使用的工具列表，"*" 表示全部
    allowed_tools: str = "*"
    # 系统提示词（skill.md 正文）
    system_prompt: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _NAME_PATTERN.match(v):
            raise ValueError("name 只允许字母、数字、下划线和连字符")
        return v

    def to_markdown(self) -> str:
        """序列化为 skill.md 内容。"""
        frontmatter_items = [
            {"name": self.name},
            {"description": self.description},
            {"allowed_tools": self.allowed_tools},
        ]
        yaml_str = yaml.dump(frontmatter_items, allow_unicode=True, default_flow_style=False, sort_keys=False)
        body = self.system_prompt or ""
        return f"{_SEP}\n{yaml_str}{_SEP}\n\n{body}"

    @classmethod
    def from_markdown(cls, content: str) -> SkillConfig:
        """从 skill.md 内容反序列化。"""
        text = content.strip()
        if not text.startswith(_SEP):
            raise ValueError("缺少 frontmatter 分隔符")

        second = text.find(_SEP, len(_SEP))
        if second == -1:
            raise ValueError("frontmatter 未闭合")

        yaml_str = text[len(_SEP):second].strip()
        body = text[second + len(_SEP):].strip()

        raw = yaml.safe_load(yaml_str)
        meta = _parse_frontmatter_list(raw)
        meta["system_prompt"] = body
        return cls(**meta)


def _parse_frontmatter_list(raw: list | dict) -> dict:
    """解析 frontmatter，支持列表格式（- key: value）和标准字典格式。"""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, list):
        raise ValueError("无效的 frontmatter 格式")

    result: dict = {}
    for item in raw:
        if isinstance(item, dict):
            result.update(item)
    return result


class SkillCreateRequest(BaseModel):
    """创建技能时前端提交的请求体。"""

    name: str = Field(..., min_length=1, max_length=64)
    description: str = ""
    allowed_tools: str = "*"
    system_prompt: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _NAME_PATTERN.match(v):
            raise ValueError("name 只允许字母、数字、下划线和连字符")
        return v


class SkillUpdateRequest(BaseModel):
    """更新技能的请求体，所有字段可选（PATCH 语义）。"""

    description: str | None = None
    allowed_tools: str | None = None
    system_prompt: str | None = None


class SkillSummary(BaseModel):
    """技能列表展示用的精简模型，不包含 system_prompt。"""

    name: str
    description: str
    allowed_tools: str
