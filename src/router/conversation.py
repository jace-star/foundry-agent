"""会话路由 — 用户侧列表/详情/删除、管理员全局查询、stop/reconnect 事件。"""

from __future__ import annotations

import json
import uuid as uuid_module
from datetime import datetime as dt, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.auth.principal import AuthPrincipal
from src.core.auth.user import get_current_user_or_api_key, require_admin
from src.core.conversation import (
    admin_list_conversations,
    delete_conversation,
    list_conversations,
    list_events,
)
from src.core.task import RunningTask, TaskManager
from src.ext.database import get_session
from src.models.api_key import ApiKey
from src.models.conversation import (
    AdminConversationDetailResponse,
    AdminConversationListResponse,
    AdminConversationSummary,
    BatchDeleteRequest,
    BatchDeleteResponse,
    Conversation,
    ConversationListResponse,
    ConversationSummary,
)
from src.models.user import User, UserPublic

router = APIRouter(tags=["conversation"])


def _conv_to_summary(conv: Conversation) -> ConversationSummary:
    return ConversationSummary(id=str(conv.id), title=conv.title or "", last_active_at=conv.last_active_at)


def _parse_date(raw: str | None) -> dt | None:
    if not raw:
        return None
    try:
        d = dt.fromisoformat(raw)
        if d.tzinfo is not None:
            d = d.astimezone(timezone.utc).replace(tzinfo=None)
        return d
    except (ValueError, TypeError):
        return None


# ── 用户侧 ──


@router.get("/conversations")
async def list_user_conversations(
    agent_key: str = Query(..., min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    days: int | None = Query(default=None, ge=1),
    principal: AuthPrincipal = Depends(get_current_user_or_api_key),
    session: AsyncSession = Depends(get_session),
) -> ConversationListResponse:
    user_id = principal.user.id if principal.type == "user" else None
    api_key_id = (
        uuid_module.UUID(principal.api_key.id)
        if principal.type == "api_key"
        else None
    )
    items, total = await list_conversations(
        session,
        user_id=user_id,
        api_key_id=api_key_id,
        agent_key=agent_key,
        page=page,
        page_size=page_size,
        days=days,
    )
    return ConversationListResponse(
        items=[_conv_to_summary(c) for c in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/conversations/{conv_id}")
async def get_user_conversation_detail(
    conv_id: str,
    rounds: int = Query(default=10, ge=1, le=100),
    before_id: int | None = Query(default=None),
    principal: AuthPrincipal = Depends(get_current_user_or_api_key),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    conv = await _get_and_check(session, conv_id, principal)
    events, has_more, first_id = await list_events(
        session, conv.id, rounds=rounds, before_id=before_id,
    )

    async def _stream_events():
        for event in events:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield (
            "data: "
            + json.dumps(
                {
                    "event": "history",
                    "has_more": has_more,
                    "before_id": first_id,
                },
                ensure_ascii=False,
            )
            + "\n\n"
        )

    return StreamingResponse(_stream_events(), media_type="text/event-stream")


@router.delete("/conversations/{conv_id}")
async def delete_user_conversation(
    conv_id: str,
    principal: AuthPrincipal = Depends(get_current_user_or_api_key),
    session: AsyncSession = Depends(get_session),
):
    conv = await _get_and_check(session, conv_id, principal)
    await delete_conversation(session, conv.id)
    await session.commit()
    return {"detail": "ok"}


@router.post("/conversations/batch-delete")
async def batch_delete_conversations(
    body: BatchDeleteRequest,
    principal: AuthPrincipal = Depends(get_current_user_or_api_key),
    session: AsyncSession = Depends(get_session),
) -> BatchDeleteResponse:
    if not body.ids or len(body.ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ids 不能为空且最多 100 个。",
        )

    deleted, not_found, forbidden = [], [], []
    for raw_id in body.ids:
        try:
            uid = uuid_module.UUID(raw_id)
        except (ValueError, AttributeError):
            not_found.append(raw_id)
            continue

        conv = await session.get(Conversation, uid)
        if conv is None:
            not_found.append(raw_id)
            continue
        if not _check_ownership(conv, principal):
            forbidden.append(raw_id)
            continue

        await delete_conversation(session, uid)
        deleted.append(raw_id)

    await session.commit()
    return BatchDeleteResponse(
        deleted=deleted, not_found=not_found, forbidden=forbidden,
    )


# ── 管理员侧 ──


@router.get("/admin/conversations")
async def admin_list_conversations_endpoint(
    user_id: str | None = Query(default=None),
    api_key_id: str | None = Query(default=None),
    agent_key: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: UserPublic = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminConversationListResponse:
    uid = uuid_module.UUID(user_id) if user_id else None
    akid = uuid_module.UUID(api_key_id) if api_key_id else None

    items, total = await admin_list_conversations(
        session,
        user_id=uid,
        api_key_id=akid,
        agent_key=agent_key,
        keyword=keyword,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        page=page,
        page_size=page_size,
    )

    cache: dict[str, dict] = {}
    summaries = []
    for conv in items:
        owner = await _resolve_owner(session, conv, cache)
        summaries.append(AdminConversationSummary(
            id=str(conv.id),
            title=conv.title or "",
            agent_key=conv.agent_key,
            owner=owner,
            created_at=conv.created_at,
            last_active_at=conv.last_active_at,
        ))

    return AdminConversationListResponse(
        items=summaries, total=total, page=page, page_size=page_size,
    )


@router.get("/admin/conversations/{conv_id}")
async def admin_get_conversation_detail(
    conv_id: str,
    _admin: UserPublic = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminConversationDetailResponse:
    uid = _parse_uuid(conv_id)
    conv = await session.get(Conversation, uid)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在。")

    owner = await _resolve_owner(session, conv, {})
    events, has_more, first_id = await list_events(session, conv.id, rounds=200)
    events = [
        *events,
        {
            "event": "history",
            "has_more": has_more,
            "before_id": first_id,
        },
    ]

    return AdminConversationDetailResponse(
        id=str(conv.id),
        title=conv.title or "",
        agent_key=conv.agent_key,
        owner=owner,
        events=events,
        created_at=conv.created_at,
        last_active_at=conv.last_active_at,
    )


# ── 任务控制 ──


@router.get("/chat-messages/{task_id}/events")
async def reconnect_task_events(
    task_id: str,
    principal: AuthPrincipal = Depends(get_current_user_or_api_key),
):
    meta = TaskManager.get_meta(task_id)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在或已完成。",
        )
    if not _check_task_ownership(meta, principal):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问。")

    async def _reconnect():
        from src.ext.redis import get_redis as _get_redis

        redis = await _get_redis()
        channel = TaskManager.channel(task_id)
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                yield f"data: {message['data']}\n\n"
                try:
                    evt = json.loads(message["data"])
                    if evt.get("event") in ("message_end", "error", "interrupted"):
                        break
                except json.JSONDecodeError:
                    pass
        finally:
            await pubsub.unsubscribe(channel)

    return StreamingResponse(_reconnect(), media_type="text/event-stream")


@router.post("/chat-messages/{task_id}/stop")
async def stop_task(
    task_id: str,
    principal: AuthPrincipal = Depends(get_current_user_or_api_key),
):
    meta = TaskManager.get_meta(task_id)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在或已完成。",
        )
    if not _check_task_ownership(meta, principal):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作。")

    cancelled = await TaskManager.cancel(task_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在或已完成。",
        )
    return {"detail": "ok"}


# ── 内部辅助 ──


async def _get_and_check(
    session: AsyncSession,
    conv_id: str,
    principal: AuthPrincipal,
) -> Conversation:
    uid = _parse_uuid(conv_id)
    conv = await session.get(Conversation, uid)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在。")
    if not _check_ownership(conv, principal):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此会话。")
    return conv


def _check_ownership(conv: Conversation, principal: AuthPrincipal) -> bool:
    if principal.type == "user":
        return conv.user_id == principal.user.id
    elif principal.type == "api_key":
        return conv.api_key_id is not None and str(conv.api_key_id) == principal.api_key.id
    return False


def _parse_uuid(raw: str) -> uuid_module.UUID:
    try:
        return uuid_module.UUID(raw)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="无效的 ID 格式。")


def _check_task_ownership(meta: RunningTask, principal: AuthPrincipal) -> bool:
    if principal.type != meta.owner_type:
        return False
    if principal.type == "user":
        return meta.owner_id == principal.user.id
    if principal.type == "api_key":
        return meta.owner_id == uuid_module.UUID(principal.api_key.id)
    return False


async def _resolve_owner(
    session: AsyncSession,
    conv: Conversation,
    cache: dict[str, dict],
) -> dict:
    if conv.user_id is not None:
        uid_str = str(conv.user_id)
        if uid_str in cache:
            return cache[uid_str]
        user = await session.get(User, conv.user_id)
        result = {"type": "user", "id": uid_str, "name": user.name if user else "", "account": user.account if user else ""}
        cache[uid_str] = result
        return result

    if conv.api_key_id is not None:
        akid_str = str(conv.api_key_id)
        if akid_str in cache:
            return cache[akid_str]
        ak = await session.get(ApiKey, conv.api_key_id)
        result = {"type": "api_key", "id": akid_str, "name": ak.name if ak else ""}
        cache[akid_str] = result
        return result

    return {"type": "unknown", "id": "", "name": ""}
