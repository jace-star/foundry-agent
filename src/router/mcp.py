"""MCP server 接入管理接口 — 直调 OpenDAL，无 Repository/Service 中间层。

同时导出可复用的读取函数，供 chat.py / agent.py 等路由使用。
"""

from __future__ import annotations

import asyncio
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.core.auth.user import get_current_user
from src.ext.storage import get_storage_operator
from src.utils.mcp_client import (
    MCPServerConfig,
    ToolServerInfo,
    get_server_info,
    test_mcp_connection,
)

MCP_SERVER_CONFIG_PREFIX = "mcp/servers/"

router = APIRouter(
    prefix="/mcp/servers",
    tags=["mcp"],
    dependencies=[Depends(get_current_user)],
)

_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# 共享的 OpenDAL 读写函数（chat.py / agent.py 等路由复用）
# ---------------------------------------------------------------------------


def _server_config_path(name: str) -> str:
    return f"{MCP_SERVER_CONFIG_PREFIX}{quote(name, safe='')}.json"


async def _read_mcp_server(name: str) -> MCPServerConfig | None:
    """按名称读取 MCP server 配置，不存在返回 None。"""
    op = get_storage_operator()
    path = _server_config_path(name)
    if not await asyncio.to_thread(op.exists, path):
        return None
    data = await asyncio.to_thread(op.read, path)
    return MCPServerConfig.model_validate_json(data.decode("utf-8"))


async def _save_mcp_server(server: MCPServerConfig) -> MCPServerConfig:
    """保存 MCP server 配置。"""
    op = get_storage_operator()
    data = server.model_dump_json().encode("utf-8")
    await asyncio.to_thread(op.write, _server_config_path(server.name), data, content_type="application/json")
    return server


async def _delete_mcp_server_file(name: str) -> None:
    """删除 MCP server 配置。"""
    op = get_storage_operator()
    await asyncio.to_thread(op.delete, _server_config_path(name))


# ── 复用的公开读取接口 ──────────────────────────────────────────────────────


async def get_mcp_server_config(name: str) -> MCPServerConfig | None:
    """获取 MCP server 配置，供 chat.py 等路由复用。"""
    return await _read_mcp_server(name)


async def list_mcp_server_configs() -> list[MCPServerConfig]:
    """列出所有 MCP server 配置，供 agent.py / chat.py 等路由复用。"""
    op = get_storage_operator()
    entries = await asyncio.to_thread(lambda: list(op.list(MCP_SERVER_CONFIG_PREFIX)))
    servers: list[MCPServerConfig] = []
    for entry in entries:
        path = entry.path
        if not path.endswith(".json"):
            continue
        try:
            data = await asyncio.to_thread(op.read, path)
            servers.append(MCPServerConfig.model_validate_json(data.decode("utf-8")))
        except Exception:
            continue
    return servers


# ---------------------------------------------------------------------------
# 路由处理函数
# ---------------------------------------------------------------------------


@router.post("", response_model=MCPServerConfig, status_code=status.HTTP_201_CREATED)
async def add_mcp_server(payload: MCPServerConfig):
    """新增外部 MCP server，并校验连接。"""
    async with _lock:
        if await asyncio.to_thread(get_storage_operator().exists, _server_config_path(payload.name)):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="MCP server 已存在。",
            )

    try:
        await test_mcp_connection([payload])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="MCP server 连接失败。",
        ) from exc

    async with _lock:
        if await asyncio.to_thread(get_storage_operator().exists, _server_config_path(payload.name)):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="MCP server 已存在。",
            )
        return await _save_mcp_server(payload)


@router.get("", response_model=list[MCPServerConfig])
async def list_mcp_servers():
    """查询已接入的 MCP server 配置。"""
    return await list_mcp_server_configs()


@router.get("/{name}", response_model=ToolServerInfo)
async def get_mcp_server(name: str):
    """查询单个 MCP server 的工具信息。"""
    server = await _read_mcp_server(name)
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server 不存在。",
        )

    infos = await get_server_info([server])
    if not infos:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="无法读取 MCP server 工具信息。",
        )
    return infos[0]


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_server(name: str):
    """删除已接入的 MCP server。"""
    if not await asyncio.to_thread(get_storage_operator().exists, _server_config_path(name)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server 不存在。",
        )
    await _delete_mcp_server_file(name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
