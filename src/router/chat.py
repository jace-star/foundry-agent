"""聊天接口 — POST /chat-messages。

支持 stateful 会话模式：自动创建/追加会话、事件持久化、后台执行。
流式响应通过 SSE 实时推送，Redis Pub/Sub 承担实时转发。
"""

from __future__ import annotations

import asyncio
import json
import uuid as uuid_module

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from loguru import logger

from src.config import get_settings
from src.core.agent import run_agent, stream_agent
from src.core.auth.principal import AuthPrincipal
from src.core.auth.user import get_current_user_or_api_key
from src.core.conversation import (
    build_history_messages,
    get_conversation,
    insert_event,
    list_events,
    touch_conversation,
)
from src.core.task import RunningTask, TaskManager
from src.ext.database import get_session_context
from src.models.conversation import Conversation
from src.models.llm import LLMChatRequest, LLMChatResponse
from src.router.agent import get_agent_config, list_agent_summaries
from src.router.mcp import get_mcp_server_config
from src.router.skill import get_skill_detail, list_skill_summaries

router = APIRouter(tags=["chat"])


@router.post("/chat-messages")
async def chat_messages(
    payload: LLMChatRequest,
    principal: AuthPrincipal = Depends(get_current_user_or_api_key),
):
    settings = get_settings()
    task_id = uuid_module.uuid4().hex

    # ── 1. 解析 agent ──
    agent_key = payload.agent_key
    if not agent_key:
        all_agents = await list_agent_summaries()
        home_agent = next((a for a in all_agents if a.is_home), None)
        agent_key = home_agent.key if home_agent else ""

    agent = None
    system_prompt = ""
    tool_server_names: list[str] = []
    if agent_key:
        agent = await get_agent_config(agent_key)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent 不存在。",
            )
        system_prompt = agent.system_prompt
        tool_server_names = agent.tool_servers

    # ── 2. 会话处理 ──
    conversation_id: uuid_module.UUID | None = None
    history_messages: list | None = None

    if payload.stateful:
        if payload.conversation_id is not None:
            # 续接已有会话
            async with get_session_context() as session:
                conv = await get_conversation(session, payload.conversation_id)
                if conv is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="会话不存在。",
                    )
                if _check_ownership(conv, principal) is False:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="无权访问此会话。",
                    )
                if conv.agent_key != agent_key:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Agent 不匹配，无法继续此会话。",
                    )
                conversation_id = conv.id
                events, _has_more, _first_id = await list_events(session, conversation_id)
                history_messages = build_history_messages(
                    events, payload.history_limit,
                )
                logger.info(
                    "续接会话 {} agent={} history_rounds={}",
                    conversation_id, agent_key, len(history_messages) // 2,
                )
        else:
            # 自动创建新会话
            async with get_session_context() as session:
                conv = Conversation(
                    agent_key=agent_key,
                    title=_truncate(payload.prompt),
                )
                if principal.type == "user":
                    conv.user_id = principal.user.id
                else:
                    conv.api_key_id = uuid_module.UUID(principal.api_key.id)
                session.add(conv)
                await session.commit()
                await session.refresh(conv)
                conversation_id = conv.id
                logger.info(
                    "自动创建会话 {} agent={}", conversation_id, agent_key,
                )

    # ── 3. 加载技能 ──
    full_skills = []
    if agent_key:
        skills = await list_skill_summaries(agent_key)
        for s in skills:
            try:
                detail = await get_skill_detail(agent_key, s.name)
                if detail:
                    full_skills.append(detail)
            except Exception:
                logger.opt(exception=True).warning(
                    "加载技能 '{}' 失败，已跳过", s.name,
                )
                continue

    # ── 4. 加载 MCP 工具 ──
    tools = await _load_mcp_tools(tool_server_names)

    # ── 5. 写入 input 事件 ──
    input_event = {
        "event": "input",
        "task_id": task_id,
        "message": payload.prompt,
        "agent_key": agent_key,
        "model": settings.openai.model,
        "conversation_id": str(conversation_id) if conversation_id else None,
    }
    if payload.stateful and conversation_id is not None:
        async with get_session_context() as session:
            await insert_event(session, conversation_id=conversation_id, event=input_event)
            await touch_conversation(session, conversation_id)
            await session.commit()

    # ── 6. 流式 / 非流式 ──
    if payload.stream:
        return StreamingResponse(
            _stream_wrapper(
                task_id, conversation_id, payload,
                system_prompt, full_skills, tools, agent_key,
                history_messages, input_event, principal,
            ),
            media_type="text/event-stream",
        )

    # 非流式
    try:
        content = await run_agent(
            system_prompt, full_skills, tools, payload.prompt,
            agent_key=agent_key, history_messages=history_messages,
            conversation_id=str(conversation_id) if conversation_id else None,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="模型调用失败",
        ) from exc

    return LLMChatResponse(content=content, model=settings.openai.model)


# ---------------------------------------------------------------------------
# 流式 SSE
# ---------------------------------------------------------------------------


async def _stream_wrapper(
    task_id: str,
    conversation_id: uuid_module.UUID | None,
    payload: LLMChatRequest,
    system_prompt: str,
    skills: list,
    tools: list,
    agent_key: str,
    history_messages: list | None,
    input_event: dict,
    principal: AuthPrincipal,
):
    """SSE 流式响应：yield input 事件 → 启动后台 Agent → 订阅 Redis → 转发事件。"""
    is_stateful = payload.stateful and conversation_id is not None

    yield f"data: {json.dumps(input_event, ensure_ascii=False)}\n\n"

    owner_id = (
        principal.user.id
        if principal.type == "user"
        else uuid_module.UUID(principal.api_key.id)
    )
    agent_task = await TaskManager.create(
        RunningTask(
            task_id=task_id,
            conversation_id=conversation_id,
            owner_type=principal.type,
            owner_id=owner_id,
        ),
        _run_agent_background(
            task_id, conversation_id, system_prompt, skills, tools,
            payload.prompt, agent_key, history_messages, is_stateful,
        ),
    )

    from src.ext.redis import get_redis as _get_redis

    try:
        redis = await _get_redis()
        channel = TaskManager.channel(task_id)
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            data_str = message["data"]
            yield f"data: {data_str}\n\n"

            try:
                evt = json.loads(data_str)
                if evt.get("event") in ("message_end", "error", "interrupted"):
                    break
            except json.JSONDecodeError:
                pass

    except asyncio.CancelledError:
        logger.info("客户端断开: task_id={}", task_id)
    except Exception:
        logger.opt(exception=True).error("SSE 流转发出错: task_id={}", task_id)
    finally:
        try:
            await pubsub.unsubscribe(channel)
        except Exception:
            pass
        try:
            await agent_task
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 后台 Agent 执行
# ---------------------------------------------------------------------------


async def _run_agent_background(
    task_id: str,
    conversation_id: uuid_module.UUID | None,
    system_prompt: str,
    skills: list,
    tools: list,
    user_message: str,
    agent_key: str,
    history_messages: list | None,
    is_stateful: bool,
) -> None:
    """后台执行 Agent。message chunk 先拼接，结束时再落库。"""
    accumulated_text = ""

    async def _save(event: dict):
        """写入 DB。"""
        if not is_stateful or conversation_id is None:
            return
        try:
            async with get_session_context() as session:
                await insert_event(session, conversation_id=conversation_id, event=dict(event))
                await session.commit()
        except Exception:
            logger.opt(exception=True).warning("事件持久化失败: task_id={}", task_id)

    async def _flush_message() -> None:
        nonlocal accumulated_text
        if not accumulated_text:
            return
        await _save({"event": "message", "content": accumulated_text})
        accumulated_text = ""

    try:
        async for event in stream_agent(
            system_prompt, skills, tools, user_message,
            agent_key=agent_key,
            history_messages=history_messages,
            conversation_id=str(conversation_id) if conversation_id else None,
        ):
            etype = event.get("event", "")
            if etype == "message":
                chunk = event.get("content")
                if chunk is not None:
                    accumulated_text += chunk
                await TaskManager.publish_event(task_id, event)
                continue

            if etype == "message_start":
                accumulated_text = ""
                await _save(event)
                await TaskManager.publish_event(task_id, event)
                continue

            if etype == "message_end":
                await _flush_message()
                await _save(event)
                await TaskManager.publish_event(task_id, event)
                continue

            await _save(event)
            await TaskManager.publish_event(task_id, event)

    except asyncio.CancelledError:
        logger.info("Agent 任务被取消: task_id={}", task_id)
        await _flush_message()
        event = {"event": "interrupted", "status": "stopped"}
        await _save(event)
        await TaskManager.publish_event(task_id, event)
    except Exception:
        logger.opt(exception=True).error("Agent 执行失败: task_id={}", task_id)
        await _flush_message()
        event = {"event": "error", "detail": "Agent 执行异常", "status": "failed"}
        await _save(event)
        await TaskManager.publish_event(task_id, event)


# ---------------------------------------------------------------------------
# 内部
# ---------------------------------------------------------------------------


def _check_ownership(conv: Conversation, principal: AuthPrincipal) -> bool:
    if principal.type == "user":
        return conv.user_id == principal.user.id
    elif principal.type == "api_key":
        return conv.api_key_id is not None and str(conv.api_key_id) == principal.api_key.id
    return False


def _truncate(text: str, max_len: int = 50) -> str:
    stripped = text.strip()
    if len(stripped) > max_len:
        return stripped[:max_len] + "..."
    return stripped


async def _load_mcp_tools(tool_servers: list[str]) -> list:
    if not tool_servers:
        return []

    from langchain_mcp_adapters.client import MultiServerMCPClient
    from src.utils.mcp_client import MCPServerConfig, _connection_map

    try:
        servers = []
        for name in tool_servers:
            server = await get_mcp_server_config(name)
            if not server:
                logger.warning("Agent 引用的 MCP server '{}' 不存在，已跳过", name)
                continue
            servers.append(MCPServerConfig(
                name=server.name,
                connection=server.connection,
                description=server.description,
            ))
    except Exception:
        logger.opt(exception=True).warning("读取 MCP server 配置失败，LLM 将无 MCP 工具可用")
        return []

    if not servers:
        return []

    try:
        client = MultiServerMCPClient(_connection_map(servers))
        return client.get_tools()
    except Exception:
        logger.opt(exception=True).warning("加载 MCP 工具失败，LLM 将无 MCP 工具可用")
        return []
