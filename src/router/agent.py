"""Agent 配置管理接口 — 直调 OpenDAL，无 Repository/Service 中间层。

同时导出可复用的读取函数，供 chat.py 等路由使用。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.core.auth.user import get_current_user
from src.ext.storage import get_storage_operator
from src.models.agent import (
    AgentConfig,
    AgentCreateRequest,
    AgentSummary,
    AgentUpdateRequest,
)

AGENTS_PREFIX = "agents/"

router = APIRouter(
    prefix="/agents",
    tags=["agents"],
    dependencies=[Depends(get_current_user)],
)

_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# 共享的 OpenDAL 读写函数（chat.py 等路由复用）
# ---------------------------------------------------------------------------


def _agent_dir(agent_key: str) -> str:
    return f"{AGENTS_PREFIX}{quote(agent_key, safe='')}/"


def _config_path(agent_key: str) -> str:
    return f"{_agent_dir(agent_key)}config.json"


def _prompt_path(agent_key: str) -> str:
    return f"{_agent_dir(agent_key)}prompt.md"


async def _read_config(agent_key: str) -> AgentConfig | None:
    """读取 Agent config.json，不存在返回 None。"""
    op = get_storage_operator()
    if not await asyncio.to_thread(op.exists, _config_path(agent_key)):
        return None
    data = await asyncio.to_thread(op.read, _config_path(agent_key))
    return AgentConfig.model_validate_json(data.decode("utf-8"))


async def _read_prompt(agent_key: str) -> str:
    """读取 Agent prompt.md，不存在返回空字符串。"""
    op = get_storage_operator()
    try:
        data = await asyncio.to_thread(op.read, _prompt_path(agent_key))
        return data.decode("utf-8")
    except Exception:
        return ""


async def _list_configs() -> list[AgentConfig]:
    """列出所有 Agent 的 config.json。"""
    op = get_storage_operator()
    entries = await asyncio.to_thread(lambda: list(op.list(AGENTS_PREFIX)))
    agents: list[AgentConfig] = []
    for entry in entries:
        path = entry.path
        if not path.endswith("/"):
            continue
        config_path_str = f"{path}config.json"
        try:
            data = await asyncio.to_thread(op.read, config_path_str)
            agents.append(AgentConfig.model_validate_json(data.decode("utf-8")))
        except Exception:
            continue
    return agents


async def _save_config(agent: AgentConfig) -> None:
    """保存 Agent config.json（不含 system_prompt）。"""
    op = get_storage_operator()
    data = agent.model_dump_json(exclude={"system_prompt"}).encode("utf-8")
    await asyncio.to_thread(op.write, _config_path(agent.key), data, content_type="application/json")


async def _save_prompt(agent_key: str, prompt: str) -> None:
    """保存 Agent prompt.md。"""
    op = get_storage_operator()
    data = prompt.encode("utf-8")
    await asyncio.to_thread(op.write, _prompt_path(agent_key), data, content_type="text/markdown")


# ── 复用的公开读取接口 ──────────────────────────────────────────────────────


async def get_agent_config(agent_key: str) -> AgentConfig | None:
    """获取 Agent 完整配置（config + prompt），供 chat.py 等路由复用。"""
    config = await _read_config(agent_key)
    if config is None:
        return None
    config.system_prompt = await _read_prompt(agent_key)
    return config


async def list_agent_summaries() -> list[AgentSummary]:
    """列出所有 Agent 摘要，供 chat.py 查找首页 Agent 等复用。"""
    agents = await _list_configs()
    return [
        AgentSummary(
            id=a.id, key=a.key, name=a.name, description=a.description,
            tool_servers=a.tool_servers, is_home=a.is_home,
            created_at=a.created_at, updated_at=a.updated_at,
        )
        for a in agents
    ]


# ---------------------------------------------------------------------------
# MCP server 校验
# ---------------------------------------------------------------------------


async def _validate_tool_servers(tool_servers: list[str]) -> None:
    """校验 Agent 引用的 MCP server 是否存在。"""
    if not tool_servers:
        return
    from src.router.mcp import list_mcp_server_configs

    available = await list_mcp_server_configs()
    names = {s.name for s in available}
    for name in tool_servers:
        if name not in names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"MCP server '{name}' 不存在",
            )


# ---------------------------------------------------------------------------
# 路由处理函数
# ---------------------------------------------------------------------------


@router.post("", response_model=AgentConfig, status_code=status.HTTP_201_CREATED)
async def create_agent(payload: AgentCreateRequest):
    """创建新的 Agent 配置。"""
    await _validate_tool_servers(payload.tool_servers)

    async with _lock:
        existing = await _list_configs()
        for agent in existing:
            if agent.key == payload.key:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Agent 标识已存在。",
                )

        now = datetime.now(tz=timezone.utc)
        agent = AgentConfig(
            id=uuid4().hex,
            key=payload.key,
            name=payload.name,
            description=payload.description,
            tool_servers=payload.tool_servers,
            created_at=now,
            updated_at=now,
        )
        await _save_config(agent)
        prompt = payload.system_prompt or ""
        await _save_prompt(agent.key, prompt)
        agent.system_prompt = prompt
        return agent


@router.get("", response_model=list[AgentSummary])
async def list_agents():
    """查询所有 Agent 配置列表。"""
    return await list_agent_summaries()


@router.get("/{agent_key}", response_model=AgentConfig)
async def get_agent(agent_key: str):
    """获取单个 Agent 完整配置。"""
    config = await get_agent_config(agent_key)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent 不存在。",
        )
    return config


@router.put("/{agent_key}", response_model=AgentConfig)
async def update_agent(agent_key: str, payload: AgentUpdateRequest):
    """更新 Agent 配置。"""
    async with _lock:
        agent = await _read_config(agent_key)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent 不存在。",
            )

        if payload.tool_servers is not None:
            await _validate_tool_servers(payload.tool_servers)

        update_data = payload.model_dump(exclude_unset=True, exclude={"system_prompt"})
        for field, value in update_data.items():
            setattr(agent, field, value)
        agent.updated_at = datetime.now(tz=timezone.utc)
        await _save_config(agent)

        if payload.system_prompt is not None:
            await _save_prompt(agent_key, payload.system_prompt)

        agent.system_prompt = await _read_prompt(agent_key)
        return agent


@router.delete("/{agent_key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_key: str):
    """删除 Agent 配置。"""
    op = get_storage_operator()
    if not await asyncio.to_thread(op.exists, _config_path(agent_key)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent 不存在。",
        )

    for path in [_config_path(agent_key), _prompt_path(agent_key)]:
        try:
            await asyncio.to_thread(op.delete, path)
        except Exception:
            pass
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{agent_key}/home", status_code=status.HTTP_204_NO_CONTENT)
async def set_home_agent(agent_key: str):
    """将指定 Agent 设为首页默认。"""
    async with _lock:
        agents = await _list_configs()
        found = False
        for agent in agents:
            if agent.key == agent_key:
                agent.is_home = True
                found = True
            elif agent.is_home:
                agent.is_home = False
            await _save_config(agent)

        if not found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent 不存在。",
            )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{agent_key}/home", status_code=status.HTTP_204_NO_CONTENT)
async def unset_home_agent(agent_key: str):
    """取消指定 Agent 的首页默认。"""
    async with _lock:
        agent = await _read_config(agent_key)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent 不存在。",
            )
        if agent.is_home:
            agent.is_home = False
            await _save_config(agent)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
