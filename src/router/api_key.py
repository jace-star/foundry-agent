"""API Key 管理接口 — 核心逻辑集中在 core/auth/api_key.py。"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from loguru import logger
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.auth.user import get_current_user
from src.core.auth.api_key import (
    decrypt_key,
    delete_key_record,
    encrypt_key,
    generate_api_key,
    hash_key,
    list_key_records,
    read_key_record,
    save_key_record,
)
from src.ext.database import get_session
from src.models.api_key import (
    ApiKey,
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyRevealResponse,
    ApiKeySummary,
    ApiKeyTestResponse,
)

router = APIRouter(
    prefix="/api-keys",
    tags=["api-keys"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    payload: ApiKeyCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """创建新的 API Key，返回明文 key。到期时间根据 expires_in_days 计算。"""
    key_id = uuid4()
    plain = generate_api_key()
    key_hash_value = hash_key(plain)
    now = datetime.now(tz=timezone.utc)

    expires_at: datetime | None = None
    if payload.expires_in_days and payload.expires_in_days > 0:
        expires_at = now + timedelta(days=payload.expires_in_days)

    record = ApiKey(
        id=key_id,
        name=payload.name,
        key_hash=key_hash_value,
        encrypted_key=encrypt_key(plain),
        expires_at=expires_at,
        created_at=now.replace(tzinfo=None),
    )
    await save_key_record(session, record)

    data = ApiKeyCreateResponse(
        api_key=plain,
        id=str(record.id),
        name=payload.name,
        expires_at=expires_at,
    )
    logger.info("API Key '{}' ({}) 已创建", data.name or data.id, data.id)
    return data


@router.get("", response_model=list[ApiKeySummary])
async def list_api_keys(
    session: AsyncSession = Depends(get_session),
):
    """列出所有 API Key（含掩码预览，不含完整明文）。"""
    records = await list_key_records(session)
    records.sort(key=lambda r: r.created_at, reverse=True)
    return [
        ApiKeySummary(
            id=str(r.id),
            name=r.name,
            expires_at=r.expires_at,
            created_at=r.created_at,
            last_used_at=r.last_used_at,
        )
        for r in records
    ]


@router.get("/{key_id}/reveal", response_model=ApiKeyRevealResponse)
async def reveal_api_key(
    key_id: str,
    session: AsyncSession = Depends(get_session),
):
    """获取完整 API Key 明文（管理员操作）。"""
    kid = _parse_key_id(key_id)
    record = await read_key_record(session, kid)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key 不存在。",
        )
    if not record.encrypted_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key 不存在。",
        )
    plain = decrypt_key(record.encrypted_key)
    return ApiKeyRevealResponse(api_key=plain, id=str(record.id), name=record.name)


@router.get("/{key_id}/test", response_model=ApiKeyTestResponse)
async def test_api_key(
    key_id: str,
    session: AsyncSession = Depends(get_session),
):
    """测试 API Key 当前是否可用。"""
    kid = _parse_key_id(key_id)
    record = await read_key_record(session, kid)
    if record is None:
        return ApiKeyTestResponse(valid=False, reason="API Key 不存在")

    now = datetime.now(tz=timezone.utc)
    if record.expires_at is not None and record.expires_at < now:
        return ApiKeyTestResponse(
            valid=False, reason="API Key 已过期",
            name=record.name, expires_at=record.expires_at,
        )

    return ApiKeyTestResponse(
        valid=True, reason="API Key 有效，可正常使用",
        name=record.name, expires_at=record.expires_at,
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: str,
    session: AsyncSession = Depends(get_session),
):
    """删除 API Key 记录。"""
    kid = _parse_key_id(key_id)
    deleted = await delete_key_record(session, kid)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key 不存在。",
        )
    logger.info("API Key '{}' 已删除", key_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _parse_key_id(raw: str) -> UUID:
    """将路由中的字符串 ID 解析为 UUID，非法值抛 404。"""
    try:
        return UUID(raw)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key 不存在。",
        )
