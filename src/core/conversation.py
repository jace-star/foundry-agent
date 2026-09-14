"""会话事件服务 — 事件追加、历史查询、LLM 上下文构建。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.conversation import Conversation, ConversationEvent


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# 事件写入
# ---------------------------------------------------------------------------


async def insert_event(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    event: dict,
) -> None:
    """INSERT 一行事件到 conversation_events（纯追加）。"""
    row = ConversationEvent(
        conversation_id=conversation_id,
        event=event,
    )
    session.add(row)


async def touch_conversation(session: AsyncSession, conversation_id: UUID) -> None:
    """更新会话的 last_active_at。"""
    conv = await session.get(Conversation, conversation_id)
    if conv is not None:
        conv.last_active_at = _utcnow()
        session.add(conv)


# ---------------------------------------------------------------------------
# 会话读取
# ---------------------------------------------------------------------------


async def get_conversation(session: AsyncSession, conversation_id: UUID) -> Conversation | None:
    return await session.get(Conversation, conversation_id)


async def list_conversations(
    session: AsyncSession,
    *,
    user_id: UUID | None = None,
    api_key_id: UUID | None = None,
    agent_key: str,
    page: int = 1,
    page_size: int = 20,
    days: int | None = None,
) -> tuple[list[Conversation], int]:
    """分页列出当前用户/API Key 的会话，按 agent_key 和时间范围过滤。"""
    base = select(Conversation)
    count_base = select(Conversation)

    if user_id is not None:
        base = base.where(Conversation.user_id == user_id)
        count_base = count_base.where(Conversation.user_id == user_id)
    elif api_key_id is not None:
        base = base.where(Conversation.api_key_id == api_key_id)
        count_base = count_base.where(Conversation.api_key_id == api_key_id)

    base = base.where(Conversation.agent_key == agent_key)

    if days is not None:
        since = _utcnow() - timedelta(days=days)
        base = base.where(Conversation.last_active_at >= since)
        count_base = count_base.where(Conversation.last_active_at >= since)

    # 计数
    count_result = await session.exec(count_base)
    total = len(count_result.all())

    # 分页 + 排序
    query = (
        base
        .order_by(Conversation.last_active_at.desc(), Conversation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.exec(query)
    items = list(result.all())

    return items, total


async def list_events(
    session: AsyncSession,
    conversation_id: UUID,
    *,
    rounds: int = 10,
    before_id: int | None = None,
) -> tuple[list[dict], bool, int | None]:
    """按 task_id 分组，返回最近 N 轮完整对话。

    每轮 = 一个 input 事件 + 同 task_id 的后续事件。
    返回 (events_asc, has_more, first_id)：
    - events_asc: 最近 N 轮的所有事件，按 id ASC
    - has_more: 是否还有更早的轮次
    - first_id: 本轮次最小事件 id，作为下次 before_id 游标；None 表示无更多
    """
    # 1. 从后往前找出最近 N 个 input 事件
    base = select(ConversationEvent).where(
        ConversationEvent.conversation_id == conversation_id
    )
    if before_id is not None:
        base = base.where(ConversationEvent.id < before_id)

    # 查出所有 input 事件 id（DESC），取前 rounds+1 个来判断 has_more
    input_query = (
        base.where(
            or_(
                ConversationEvent.event["event"].astext == "input",
                ConversationEvent.event["type"].astext == "input",
            )
        )
        .order_by(ConversationEvent.id.desc())
        .limit(rounds + 1)
    )
    input_result = await session.exec(input_query)
    input_rows = list(input_result.all())

    if not input_rows:
        return [], False, None

    has_more = len(input_rows) > rounds
    target_inputs = input_rows[:rounds]  # 最近 N 个 input（DESC）

    # 最老 input 的 id（从最老 input 往后取所有事件）
    oldest_input_id = target_inputs[-1].id

    # 2. 取出这 N 轮的所有事件：从 oldest_input_id 到 newest_input_id（含）
    #    以及同 task_id 的后续事件（id > newest_input_id 但 task_id 相同）
    all_query = (
        select(ConversationEvent)
        .where(
            ConversationEvent.conversation_id == conversation_id,
            ConversationEvent.id >= oldest_input_id,
        )
        .order_by(ConversationEvent.id.asc())
    )
    all_result = await session.exec(all_query)
    all_rows = list(all_result.all())

    events = [row.event for row in all_rows]
    first_id = oldest_input_id
    return events, has_more, first_id


# ---------------------------------------------------------------------------
# 管理员全局查询
# ---------------------------------------------------------------------------


async def admin_list_conversations(
    session: AsyncSession,
    *,
    user_id: UUID | None = None,
    api_key_id: UUID | None = None,
    agent_key: str | None = None,
    keyword: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Conversation], int]:
    """管理员跨用户/API Key 查询会话列表。"""
    base = select(Conversation)
    count_base = select(Conversation)

    if user_id is not None:
        base = base.where(Conversation.user_id == user_id)
        count_base = count_base.where(Conversation.user_id == user_id)
    if api_key_id is not None:
        base = base.where(Conversation.api_key_id == api_key_id)
        count_base = count_base.where(Conversation.api_key_id == api_key_id)
    if agent_key is not None:
        base = base.where(Conversation.agent_key == agent_key)
        count_base = count_base.where(Conversation.agent_key == agent_key)
    if start_date is not None:
        base = base.where(Conversation.created_at >= start_date)
        count_base = count_base.where(Conversation.created_at >= start_date)
    if end_date is not None:
        base = base.where(Conversation.created_at <= end_date)
        count_base = count_base.where(Conversation.created_at <= end_date)
    if keyword:
        # 标题模糊搜索
        base = base.where(Conversation.title.ilike(f"%{keyword}%"))
        count_base = count_base.where(Conversation.title.ilike(f"%{keyword}%"))

    # 计数
    count_result = await session.exec(count_base)
    total = len(count_result.all())

    query = (
        base
        .order_by(Conversation.last_active_at.desc(), Conversation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.exec(query)
    items = list(result.all())

    return items, total


# ---------------------------------------------------------------------------
# 删除
# ---------------------------------------------------------------------------


async def delete_conversation(session: AsyncSession, conversation_id: UUID) -> bool:
    """删除会话（级联删除事件），返回是否删除成功。"""
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        return False
    await session.delete(conv)
    return True


# ---------------------------------------------------------------------------
# LLM 历史上下文构建
# ---------------------------------------------------------------------------

# 默认注入模型上下文的最近轮数
DEFAULT_HISTORY_LIMIT = 20


def build_history_messages(
    events: list[dict],
    history_limit: int = DEFAULT_HISTORY_LIMIT,
) -> list:
    """从事件流构建 LangChain 历史消息。"""
    rounds: list[dict] = []
    current_round: dict | None = None

    for evt in events:
        etype = evt.get("event") or evt.get("type", "")
        if etype == "input":
            current_round = {"input": evt, "ai_text": ""}
            rounds.append(current_round)
        elif etype == "message" and current_round:
            current_round["ai_text"] += evt.get("content", "")

    recent = rounds[-history_limit:] if len(rounds) > history_limit else rounds

    messages: list = []
    for rnd in recent:
        messages.append(HumanMessage(content=rnd["input"].get("message", "")))
        if rnd["ai_text"]:
            messages.append(AIMessage(content=rnd["ai_text"]))

    return messages
