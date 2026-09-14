"""Agent 运行时，预处理 + LangGraph 编排。

调用链：
  _prepare（技能选择 → Prompt 组装 → 工具过滤，Graph 外）
    → Graph: START → call_llm → (call_tool → call_llm)* → END
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Annotated, TypedDict

from loguru import logger
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from langfuse import observe, propagate_attributes

from src.ext.llm import get_llm
from src.ext.observability import get_langfuse_handler
from src.models.skill import SkillConfig
from src.utils.prompt import build_context_prompt


# ── State ──────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """Graph 执行期状态，仅保留 LLM → 工具循环所需的字段。"""
    messages: Annotated[list[BaseMessage], add_messages]
    system_prompt: str
    tools: list[BaseTool]


# ── 预处理：技能选择 → Prompt 组装 → 工具过滤 ───────────────────────────────


def _build_select_skill_tool(skills: list[SkillConfig]) -> BaseTool:
    """构建技能选择工具，供 LLM 通过 tool calling 选择技能。"""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    skill_names = [s.name for s in skills]
    skill_desc = ", ".join(f"{s.name}({s.description or '无描述'})" for s in skills)

    class SelectSkillInput(BaseModel):
        skills: list[str] = Field(
            description=f"需要激活的技能标识列表，可选值: {skill_desc}，无需激活则为空数组"
        )

    def select_skill(skills: list[str]) -> str:
        valid = set(skill_names)
        selected = [s for s in skills if s in valid]
        return f"已激活技能: {', '.join(selected) if selected else '无'}"

    tool = StructuredTool.from_function(
        func=select_skill,
        name="select_skill",
        description="选择需要激活的技能。根据用户问题判断需要哪些技能能力。",
        args_schema=SelectSkillInput,
    )
    return tool


SKILL_SELECT_SYSTEM_PROMPT = """你是一个技能路由器。根据用户的问题，判断需要激活哪些技能。

可用技能列表：
{skills_list}

请分析用户问题，调用 select_skill 工具选择需要激活的技能。"""


async def _do_select_skills(
    skills: list[SkillConfig], user_msg: BaseMessage, context: str,
) -> list[str]:
    """LLM 通过 tool calling 选择需要激活的技能，返回技能名列表。"""
    if not skills:
        return []

    skills_desc = "\n".join(
        f"- {s.name}: {s.description or '无描述'}"
        for s in skills
    )
    system_msg = SKILL_SELECT_SYSTEM_PROMPT.format(skills_list=skills_desc)
    system_msg = f"{system_msg}\n\n{context}"

    select_tool = _build_select_skill_tool(skills)
    llm = get_llm().bind_tools([select_tool], tool_choice="required")

    try:
        response = await llm.ainvoke([
            SystemMessage(content=system_msg),
            user_msg,
        ])
        if response.tool_calls:
            for tc in response.tool_calls:
                if tc["name"] == "select_skill":
                    selected = tc["args"].get("skills", [])
                    valid_names = {s.name for s in skills}
                    active = [n for n in selected if n in valid_names]
                    logger.info("技能选择结果: {}", active if active else "无")
                    return active
    except Exception:
        logger.opt(exception=True).warning("技能选择调用失败，回退为空技能列表")

    return []


def _do_build_prompt(
    agent_prompt: str,
    skills: list[SkillConfig],
    active_names: list[str],
    context: str,
) -> str:
    """组装最终 system prompt：agent prompt + 激活的技能 prompt + 上下文。"""
    parts: list[str] = []

    if agent_prompt:
        parts.append(agent_prompt)

    skills_map = {s.name: s for s in skills}
    for name in active_names:
        skill = skills_map.get(name)
        if skill and skill.system_prompt:
            parts.append(skill.system_prompt)

    if context:
        parts.append(context)

    return "\n\n".join(parts)


def _do_filter_tools(
    all_tools: list[BaseTool],
    skills: list[SkillConfig],
    active_names: list[str],
) -> list[BaseTool]:
    """根据激活技能的 allowed_tools 过滤可用工具。"""
    if not all_tools:
        return []

    skills_map = {s.name: s for s in skills}
    allowed_set: set[str] | None = None

    for name in active_names:
        skill = skills_map.get(name)
        if not skill:
            continue
        allowed = skill.allowed_tools or "*"
        if allowed == "*":
            return all_tools  # 全部工具
        tool_names = {t.strip() for t in allowed.split(",") if t.strip()}
        if allowed_set is None:
            allowed_set = tool_names
        else:
            allowed_set |= tool_names

    if allowed_set is None:
        return []

    if not allowed_set:
        logger.warning(
            "激活技能的工具白名单为空（skills={}），LLM 将无工具可用",
            active_names,
        )

    return [t for t in all_tools if t.name in allowed_set]


async def _prepare(
    agent_prompt: str,
    skills: list[SkillConfig],
    tools: list[BaseTool],
    user_msg: BaseMessage,
) -> tuple[str, list[BaseTool], list[str]]:
    """预处理管道：技能选择 → Prompt 组装 → 工具过滤。

    在 Graph 之外执行，返回 (system_prompt, filtered_tools, active_skill_names)。
    """
    context = build_context_prompt()
    active_names = await _do_select_skills(skills, user_msg, context)
    system_prompt = _do_build_prompt(agent_prompt, skills, active_names, context)
    filtered_tools = _do_filter_tools(tools, skills, active_names)
    return system_prompt, filtered_tools, active_names


# ── LLM 调用 ──────────────────────────────────────────────────────────────────

# LLM 调用重试配置
_LLM_MAX_RETRIES = 3
_LLM_RETRY_BASE_DELAY = 1.0  # 秒

# 最多允许 LLM 发起的工具调用轮数；达到后强制进入最终文本回复
_MAX_TOOL_ROUNDS = 3


def _is_retryable(exc: Exception) -> bool:
    """判断 LLM 调用异常是否可重试。4xx（除 429）为不可重试错误。"""
    status = (
        getattr(exc, "status_code", None)
        or getattr(exc, "http_status", None)
    )
    if isinstance(status, int) and 400 <= status < 500 and status != 429:
        return False
    return True


async def call_llm(state: AgentState) -> dict:
    """用组装好的 prompt 和工具调用 LLM，失败时自动重试（指数退避）。"""
    llm = get_llm()
    tools = state["tools"]
    tool_rounds = sum(
        1
        for msg in state["messages"]
        if isinstance(msg, AIMessage) and msg.tool_calls
    )
    max_tool_rounds_reached = tool_rounds >= _MAX_TOOL_ROUNDS
    if tools and not max_tool_rounds_reached:
        llm_with_tools = llm.bind_tools(tools)
    else:
        if tools and max_tool_rounds_reached:
            logger.info("工具调用已达到 {} 轮，本轮不再绑定工具，强制文本回复", _MAX_TOOL_ROUNDS)
        llm_with_tools = llm

    # 构建消息
    messages: list[BaseMessage] = []
    if state["system_prompt"]:
        messages.append(SystemMessage(content=state["system_prompt"]))
    messages.extend(state["messages"])

    last_exc: Exception | None = None
    for attempt in range(1, _LLM_MAX_RETRIES + 1):
        try:
            response = await llm_with_tools.ainvoke(messages)
            return {"messages": [response]}
        except Exception as exc:
            if not _is_retryable(exc):
                raise
            last_exc = exc
            if attempt < _LLM_MAX_RETRIES:
                delay = _LLM_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "LLM 调用失败 (第 {}/{} 次)，{} 秒后重试: {}",
                    attempt, _LLM_MAX_RETRIES, delay, exc,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "LLM 调用失败，已达最大重试次数 {}: {}", _LLM_MAX_RETRIES, exc,
                )

    raise last_exc  # type: ignore[misc]


# ── 路由逻辑 ──────────────────────────────────────────────────────────────────

def should_call_tool(state: AgentState) -> str:
    """判断 LLM 是否请求调用工具。"""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "call_tool"
    return END


# ── 工具执行 ──────────────────────────────────────────────────────────────────

async def call_tool(state: AgentState) -> dict:
    """执行 LLM 请求的工具调用。"""
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    # 构建工具名 → 工具实例的映射
    tools_map = {t.name: t for t in state["tools"]}

    # 执行所有工具调用
    results = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool = tools_map.get(tool_name)
        if tool is None:
            logger.warning("工具 '{}' 不在可用工具列表中（可用: {}）", tool_name, list(tools_map.keys()))
            results.append(
                ToolMessage(content=f"工具 {tool_name} 不存在", tool_call_id=tool_call["id"], name=tool_name)
            )
            continue
        try:
            output = await tool.ainvoke(tool_call["args"])
            results.append(ToolMessage(content=str(output), tool_call_id=tool_call["id"], name=tool_name))
        except Exception as e:
            logger.opt(exception=True).warning(
                "工具 '{}' 执行失败, args={}: {}",
                tool_name, tool_call.get("args", {}), e,
            )
            results.append(ToolMessage(content=f"工具执行失败: {e}", tool_call_id=tool_call["id"], name=tool_name))

    return {"messages": results}


# ── 构建 Graph ────────────────────────────────────────────────────────────────

@lru_cache
def build_agent_graph() -> CompiledStateGraph:
    """构建 LangGraph agent 图，仅处理 LLM ↔ 工具的循环。"""
    graph = StateGraph(AgentState)

    graph.add_node("call_llm", call_llm)
    graph.add_node("call_tool", call_tool)

    graph.add_edge(START, "call_llm")
    graph.add_conditional_edges("call_llm", should_call_tool, {
        "call_tool": "call_tool",
        END: END,
    })
    graph.add_edge("call_tool", "call_llm")

    return graph.compile()


# ── 内容提取 ──────────────────────────────────────────────────────────────────

def _extract_text(content: str | list[dict] | None) -> str:
    """从消息 content 中安全提取纯文本。

    LangChain 消息的 content 可能是:
      - str: 纯文本模型
      - list[dict]: 多模态模型（如 GPT-4V），每项为 {"type": "text", "text": "..."} 或 {"type": "image_url", ...}
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


# ── 对外接口 ──────────────────────────────────────────────────────────────────

async def _build_initial_state(
    agent_prompt: str,
    skills: list[SkillConfig],
    tools: list[BaseTool],
    user_message: str,
    history_messages: list[BaseMessage] | None = None,
) -> tuple[AgentState, list[str]]:
    """构建 Graph 初始 state。返回 (state, active_skill_names)。

    history_messages 为历史 LangChain 消息列表，会拼接到当前用户输入之前，
    使 LLM 能感知上一轮对话上下文。
    """
    user_msg = HumanMessage(content=user_message)
    system_prompt, filtered_tools, active_names = await _prepare(
        agent_prompt, skills, tools, user_msg,
    )
    messages: list[BaseMessage] = []
    if history_messages:
        messages.extend(history_messages)
    messages.append(user_msg)

    state: AgentState = {
        "messages": messages,
        "system_prompt": system_prompt,
        "tools": filtered_tools,
    }
    return state, active_names


@observe(name="agent-hub", capture_input=True, capture_output=True)
async def run_agent(
    system_prompt: str,
    skills: list[SkillConfig],
    tools: list[BaseTool],
    user_message: str,
    agent_key: str = "",
    history_messages: list[BaseMessage] | None = None,
    conversation_id: str | None = None,
) -> str:
    """运行 agent，返回最终回复文本。"""
    with propagate_attributes(
        metadata={
            "agent_key": agent_key,
            "skills": ",".join(s.name for s in skills),
        },
        tags=["agent", agent_key] if agent_key else ["agent"],
    ):
        state, _active_names = await _build_initial_state(
            system_prompt, skills, tools, user_message,
            history_messages=history_messages,
        )

        graph = build_agent_graph()

        # Langfuse CallbackHandler 自动追踪 LLM 调用和工具执行
        handler = get_langfuse_handler()
        config = {"callbacks": [handler]} if handler else {}

        result = await graph.ainvoke(state, config=config)

        # 提取最后一条 AI 消息
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                return msg.content

        return ""


@observe(name="agent-hub", capture_input=True, capture_output=True)
async def stream_agent(
    system_prompt: str,
    skills: list[SkillConfig],
    tools: list[BaseTool],
    user_message: str,
    agent_key: str = "",
    history_messages: list[BaseMessage] | None = None,
    event_callback=None,
    conversation_id: str | None = None,
):
    """流式运行 agent，yield 每个事件。

    预处理阶段手动 emit 技能选择事件，Graph 阶段通过 messages 通道流式输出。

    event_callback 为可选异步回调 async def(event: dict)，用于持久化每个 SSE 事件。
    """
    async def _emit(event: dict):
        """发布事件到回调（持久化）并 yield 给上游。"""
        if event_callback:
            try:
                await event_callback(event)
            except Exception:
                logger.opt(exception=True).warning("event_callback 执行失败")
        return event

    with propagate_attributes(
        metadata={
            "agent_key": agent_key,
            "skills": ",".join(s.name for s in skills),
        },
        tags=["agent", agent_key] if agent_key else ["agent"],
    ):
        msg_start: dict = {"event": "message_start"}
        if conversation_id:
            msg_start["conversation_id"] = conversation_id
        yield await _emit(msg_start)

        # ── 预处理：技能选择（仅在有技能时才 emit 事件） ──
        if skills:
            yield await _emit({
                "event": "tool_start",
                "name": "select_skill",
                "input": {"question": user_message},
            })

        state, active_names = await _build_initial_state(
            system_prompt, skills, tools, user_message,
            history_messages=history_messages,
        )

        if skills:
            yield await _emit({
                "event": "tool_end",
                "name": "select_skill",
                "output": {"skills": active_names},
            })

        # ── Graph 阶段：LLM ↔ 工具循环 ──

        graph = build_agent_graph()
        handler = get_langfuse_handler()
        config = {"callbacks": [handler]} if handler else {}

        # 跟踪已 emit 的 tool_start，避免 tool_call chunk 重复触发
        emitted_tool_starts: set[str] = set()

        async for mode, data in graph.astream(
            state, stream_mode=["messages", "updates"], config=config,
        ):
            if mode == "messages":
                msg, _metadata = data
                if not isinstance(msg, AIMessageChunk):
                    continue

                text = _extract_text(msg.content)
                if text:
                    yield await _emit({"event": "message", "content": text})

                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        tc_id = tc.get("id", "")
                        if tc.get("name") and tc_id and tc_id not in emitted_tool_starts:
                            emitted_tool_starts.add(tc_id)
                            yield await _emit({
                                "event": "tool_start",
                                "name": tc["name"],
                                "input": tc.get("args", {}),
                            })

            elif mode == "updates":
                tool_update = data.get("call_tool") if isinstance(data, dict) else None
                if not isinstance(tool_update, dict):
                    continue

                for msg in tool_update.get("messages", []):
                    if isinstance(msg, ToolMessage):
                        yield await _emit({
                            "event": "tool_end",
                            "name": msg.name,
                            "output": msg.content,
                        })

        yield await _emit({"event": "message_end"})
