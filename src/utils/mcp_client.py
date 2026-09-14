"""外部 MCP 服务适配工具。

本模块只负责连接外部 MCP server，并把 MCP 原始工具定义转换成项目内部
使用的 Tool 数据结构。
"""

import traceback
from typing import Any, cast

# 使用 LangChain MCP Adapters 管理 MCP client session。
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import Connection
from mcp.types import Tool as MCPTool
from pydantic import BaseModel, Field


MAX_LIST_TOOLS_ITERATIONS = 1000


# MCP 工具元信息，供前端或调用方展示和调用工具时读取 schema。
class Tool(BaseModel):
    name: str
    title: str | None = None
    description: str | None = None
    inputSchema: dict[str, Any] = Field(default_factory=dict)
    outputSchema: dict[str, Any] | None = None


# MCP server 连接后返回的聚合信息。
class ToolServerInfo(BaseModel):
    name: str
    description: str
    type: str
    endpoint: str
    tools: list[Tool] = Field(default_factory=list)


# 外部传入的 MCP server 数组项，connection 直接使用 adapters 原生配置。
class MCPServerConfig(BaseModel):
    name: str
    connection: dict[str, Any]
    description: str = ""


async def get_server_info(servers: list[MCPServerConfig]) -> list[ToolServerInfo] | None:
    """连接外部 MCP servers，读取工具列表并包装成 ToolServerInfo 数组。"""
    try:
        # adapters 接收 dict[str, Connection]，这里由数组在边界处组装。
        # 创建 client 只保存连接配置，真正连接发生在 list_mcp_tools 的 session 中。
        mcp_client = MultiServerMCPClient(_connection_map(servers))
        infos: list[ToolServerInfo] = []
        for server in servers:
            # 获取所有工具列表
            mcp_tools = await list_mcp_tools(mcp_client, server.name)
            # 将 MCP 原始工具定义转换为前端展示模型。
            tools = [mcp_tool_to_tool(tool) for tool in mcp_tools]
            infos.append(
                ToolServerInfo(
                    name=server.name,
                    description=server.description,
                    type=_connection_transport(server.connection),
                    endpoint=_connection_endpoint(server.connection),
                    tools=tools,
                )
            )
        return infos
    except Exception:
        traceback.print_exc()
        return None


async def test_mcp_connection(servers: list[MCPServerConfig]) -> None:
    """
    测试 MCP 服务器连接
    Args:
        servers: MCP server 配置数组
    Raises:
        Exception: 如果连接失败，抛出异常
    """
    try:
        # 能成功拉到工具列表，就认为 MCP server 配置和网络连接可用。
        mcp_client = MultiServerMCPClient(_connection_map(servers))
        for server in servers:
            await list_mcp_tools(mcp_client, server.name)
    except Exception:
        traceback.print_exc()
        raise


# 辅助函数
async def list_mcp_tools(mcp_client: MultiServerMCPClient, server_name: str) -> list[MCPTool]:
    """从 MCP 原始 session 读取工具列表，保留 inputSchema 和 outputSchema。"""
    tools: list[MCPTool] = []
    cursor: str | None = None
    iterations = 0

    # MCP tools/list 支持分页，这里循环读取所有页。
    async with mcp_client.session(server_name) as session:
        while True:
            iterations += 1
            if iterations > MAX_LIST_TOOLS_ITERATIONS:
                raise RuntimeError("Reached max iterations while listing MCP tools.")

            page = await session.list_tools(cursor=cursor)
            tools.extend(page.tools)
            if not page.nextCursor:
                break
            cursor = page.nextCursor

    return tools


def mcp_tool_to_tool(mcp_tool: MCPTool) -> Tool:
    """将 MCP 原始 Tool 转换为项目内部 Tool 类型。"""
    return Tool(
        name=mcp_tool.name,
        title=mcp_tool.title,
        description=mcp_tool.description,
        inputSchema=mcp_tool.inputSchema,
        outputSchema=mcp_tool.outputSchema,
    )


def _connection_transport(connection: dict[str, Any]) -> str:
    """从 adapters 原生连接配置中读取 transport 类型。"""
    return str(connection["transport"])


def _connection_endpoint(connection: dict[str, Any]) -> str:
    """从 adapters 原生连接配置中提取可展示的 endpoint。"""
    if "url" in connection:
        return str(connection["url"])
    if "command" in connection:
        return str(connection["command"])
    return ""


def _connection_map(servers: list[MCPServerConfig]) -> dict[str, Connection]:
    """把数组配置转换成 MultiServerMCPClient 需要的连接字典。"""
    return {server.name: cast(Connection, server.connection) for server in servers}
