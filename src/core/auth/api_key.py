"""API Key 哈希、加密与验证工具函数。

复用于 core/auth/user.py（认证依赖）和 router/api_key.py（管理接口）。
所有 API Key 持久化操作通过数据库完成。
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timezone
from uuid import UUID

from cryptography.fernet import Fernet
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.api_key import ApiKey


# ---------------------------------------------------------------------------
# 密钥生成
# ---------------------------------------------------------------------------


def generate_api_key() -> str:
    """生成一个新的 API Key 明文（sk- 前缀 + 随机字符串）。"""
    return f"sk-{secrets.token_urlsafe(32)}"


# ---------------------------------------------------------------------------
# 哈希
# ---------------------------------------------------------------------------


def hash_key(raw_key: str) -> str:
    """对 API Key 明文做 SHA-256 哈希。"""
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Fernet 加密 / 解密
# ---------------------------------------------------------------------------


_FERNET_KEY = "f7e2a1b3c5d6489012345678abcdef90abcde1234567890fedcba0987654321f"


def _get_fernet() -> Fernet:
    """从硬编码密钥派生 Fernet 加密密钥（32 字节 urlsafe-base64）。"""
    key_bytes = hashlib.sha256(_FERNET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt_key(plain: str) -> str:
    """使用 Fernet 加密 API Key 明文。"""
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_key(encrypted: str) -> str:
    """使用 Fernet 解密 API Key。"""
    return _get_fernet().decrypt(encrypted.encode()).decode()


# ---------------------------------------------------------------------------
# 数据库 CRUD（供 router 和 auth deps 共用）
# ---------------------------------------------------------------------------


async def read_key_record(session: AsyncSession, key_id: UUID) -> ApiKey | None:
    """按 ID 读取 API Key 记录，不存在时返回 None。"""
    return await session.get(ApiKey, key_id)


async def save_key_record(session: AsyncSession, record: ApiKey) -> None:
    """保存 API Key 记录（新增或更新）。"""
    session.add(record)


async def list_key_records(session: AsyncSession) -> list[ApiKey]:
    """列出全部 API Key 记录。"""
    result = await session.exec(select(ApiKey))
    return list(result.all())


async def delete_key_record(session: AsyncSession, key_id: UUID) -> bool:
    """物理删除 API Key 记录，返回是否删除成功。"""
    record = await session.get(ApiKey, key_id)
    if record is None:
        return False
    await session.delete(record)
    return True


# ---------------------------------------------------------------------------
# 验证（供 auth deps 复用）
# ---------------------------------------------------------------------------


async def validate_api_key(session: AsyncSession, raw_key: str) -> ApiKey | None:
    """校验 API Key 是否有效（哈希比对 + 过期检查 + 刷新 last_used_at）。

    通过 key_hash 唯一索引进行 O(1) 查找，供 core/auth/user.py 的
    get_current_user_or_api_key 复用。

    返回：
    - ApiKey 记录 → 校验通过，可从中提取 id/name 等字段用于归属绑定
    - None        → 校验失败
    """
    if not raw_key.startswith("sk-"):
        return None

    target_hash = hash_key(raw_key)
    now = datetime.now(tz=timezone.utc)

    result = await session.exec(
        select(ApiKey).where(ApiKey.key_hash == target_hash)
    )
    record = result.one_or_none()
    if record is None:
        return None
    if record.expires_at is not None and record.expires_at < now:
        return None

    # 刷新 last_used_at（失败不影响请求）
    record.last_used_at = now
    session.add(record)
    return record
