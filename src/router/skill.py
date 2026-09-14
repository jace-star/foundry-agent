"""Agent 技能管理接口 — 直调 OpenDAL，无 Repository/Service 中间层。

路由嵌套在 /agents/{agent_key}/skills 下，技能归属于特定 Agent。
同时导出可复用的读取函数，供 chat.py 等路由使用。
"""

from __future__ import annotations

import asyncio
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.core.auth.user import get_current_user
from src.ext.storage import get_storage_operator
from src.models.skill import (
    SkillConfig,
    SkillCreateRequest,
    SkillSummary,
    SkillUpdateRequest,
)

AGENTS_PREFIX = "agents/"

router = APIRouter(
    prefix="/agents/{agent_key}/skills",
    tags=["skills"],
    dependencies=[Depends(get_current_user)],
)

_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# 共享的 OpenDAL 读写函数（chat.py 等路由复用）
# ---------------------------------------------------------------------------


def _skills_prefix(agent_key: str) -> str:
    return f"{AGENTS_PREFIX}{quote(agent_key, safe='')}/skills/"


def _skill_path(agent_key: str, skill_name: str) -> str:
    return f"{_skills_prefix(agent_key)}{quote(skill_name, safe='')}/skill.md"


async def _read_skill(agent_key: str, skill_name: str) -> SkillConfig | None:
    """读取技能 Markdown，不存在或解析失败时返回 None。"""
    op = get_storage_operator()
    path = _skill_path(agent_key, skill_name)
    try:
        data = await asyncio.to_thread(op.read, path)
        return SkillConfig.from_markdown(data.decode("utf-8"))
    except Exception:
        return None


async def _write_skill(agent_key: str, skill: SkillConfig) -> None:
    """将技能配置序列化为 Markdown 后写入对象存储。"""
    op = get_storage_operator()
    content = skill.to_markdown().encode("utf-8")
    await asyncio.to_thread(
        op.write, _skill_path(agent_key, skill.name), content, content_type="text/markdown"
    )


async def _delete_skill_file(agent_key: str, skill_name: str) -> None:
    """删除指定技能文件。"""
    op = get_storage_operator()
    await asyncio.to_thread(op.delete, _skill_path(agent_key, skill_name))


async def _list_skill_names(agent_key: str) -> list[str]:
    """列出 Agent 下所有技能目录名。"""
    op = get_storage_operator()
    prefix = _skills_prefix(agent_key)
    entries = await asyncio.to_thread(lambda: list(op.list(prefix)))
    names: list[str] = []
    for entry in entries:
        path = entry.path
        if not path.endswith("/"):
            continue
        rel = path[len(prefix):]
        name = rel.rstrip("/")
        if name:
            names.append(name)
    return names


# ── 复用的公开读取接口 ──────────────────────────────────────────────────────


async def get_skill_detail(agent_key: str, skill_name: str) -> SkillConfig | None:
    """获取指定技能详情，供 chat.py 等路由复用。"""
    return await _read_skill(agent_key, skill_name)


async def list_skill_summaries(agent_key: str) -> list[SkillSummary]:
    """列出 Agent 下所有技能摘要，供 chat.py 等路由复用。"""
    names = await _list_skill_names(agent_key)
    summaries: list[SkillSummary] = []
    for name in names:
        skill = await _read_skill(agent_key, name)
        if skill:
            summaries.append(SkillSummary(
                name=skill.name,
                description=skill.description,
                allowed_tools=skill.allowed_tools,
            ))
    return summaries


# ---------------------------------------------------------------------------
# 路由处理函数
# ---------------------------------------------------------------------------


@router.post("", response_model=SkillConfig, status_code=status.HTTP_201_CREATED)
async def create_skill(agent_key: str, payload: SkillCreateRequest):
    """为指定 Agent 创建技能。"""
    async with _lock:
        existing = await _read_skill(agent_key, payload.name)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="技能标识已存在。",
            )

        skill = SkillConfig(
            name=payload.name,
            description=payload.description,
            allowed_tools=payload.allowed_tools,
            system_prompt=payload.system_prompt,
        )
        await _write_skill(agent_key, skill)
        return skill


@router.get("", response_model=list[SkillSummary])
async def list_skills(agent_key: str):
    """查询指定 Agent 的所有技能列表。"""
    return await list_skill_summaries(agent_key)


@router.get("/{skill_name}", response_model=SkillConfig)
async def get_skill(agent_key: str, skill_name: str):
    """获取指定 Agent 下的单个技能详情。"""
    skill = await _read_skill(agent_key, skill_name)
    if skill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="技能不存在。",
        )
    return skill


@router.put("/{skill_name}", response_model=SkillConfig)
async def update_skill(agent_key: str, skill_name: str, payload: SkillUpdateRequest):
    """更新指定 Agent 下的技能配置。"""
    async with _lock:
        skill = await _read_skill(agent_key, skill_name)
        if skill is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="技能不存在。",
            )

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(skill, field, value)

        await _write_skill(agent_key, skill)
        return skill


@router.delete("/{skill_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(agent_key: str, skill_name: str):
    """删除指定 Agent 下的技能。"""
    op = get_storage_operator()
    if not await asyncio.to_thread(op.exists, _skill_path(agent_key, skill_name)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="技能不存在。",
        )
    await _delete_skill_file(agent_key, skill_name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
