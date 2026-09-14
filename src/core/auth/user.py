"""认证模块 — 密码、Redis Session、FastAPI 依赖。

提供：
- 密码工具: hash_password, verify_password
- Redis Session: create_session, delete_session
- FastAPI Depends: get_current_user, get_current_user_or_api_key
"""

import secrets

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.config import get_settings
from src.ext.database import get_session
from src.core.auth.principal import AuthPrincipal
from src.ext.redis import get_redis
from src.models.api_key import ApiKeySummary
from src.models.user import User, UserPublic

# ---------------------------------------------------------------------------
# 密码
# ---------------------------------------------------------------------------

_password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """对明文密码进行哈希。"""
    return _password_hasher.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与哈希值是否匹配。"""
    return _password_hasher.verify(plain, hashed)


# ---------------------------------------------------------------------------
# Redis Session
# ---------------------------------------------------------------------------

SESSION_KEY_PREFIX = "auth:session:"


def _get_session_ttl() -> int:
    return get_settings().auth.session_ttl_seconds


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


async def create_session(redis, account: str) -> str:
    """创建 Redis session，返回 token。"""
    token = _generate_token()
    key = f"{SESSION_KEY_PREFIX}{token}"
    await redis.set(key, account, ex=_get_session_ttl())
    return token


async def _get_session_account(redis, token: str) -> str | None:
    """从 Redis 读取 session 对应的 account，不存在返回 None。"""
    key = f"{SESSION_KEY_PREFIX}{token}"
    return await redis.get(key)


async def delete_session(redis, token: str) -> None:
    """删除 Redis session。"""
    key = f"{SESSION_KEY_PREFIX}{token}"
    await redis.delete(key)


async def _extend_session(redis, token: str) -> None:
    """续期 Redis session TTL。"""
    key = f"{SESSION_KEY_PREFIX}{token}"
    await redis.expire(key, _get_session_ttl())


# ---------------------------------------------------------------------------
# FastAPI 依赖
# ---------------------------------------------------------------------------

_security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    session: AsyncSession = Depends(get_session),
) -> UserPublic:
    """从 Authorization Bearer token 获取当前用户（Redis session 校验 + 滑动续期）。"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已过期。",
        )

    token = credentials.credentials
    redis = await get_redis()
    account = await _get_session_account(redis, token)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已过期。",
        )

    # 用 account 查数据库用户
    user_result = await session.exec(select(User).where(User.account == account))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已过期。",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用。",
        )

    # 每次请求滑动续期
    await _extend_session(redis, token)

    return UserPublic.model_validate(user)


async def get_current_user_or_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    api_key: str | None = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session),
) -> AuthPrincipal:
    """统一认证：优先 Redis session，其次 X-API-Key。

    返回：
    - Session 认证成功 → AuthPrincipal(type="user", user=UserPublic)
    - API Key 有效    → AuthPrincipal(type="api_key", api_key=ApiKeySummary)
    - 均失败         → 401
    """
    if credentials is not None:
        token = credentials.credentials
        redis = await get_redis()
        account = await _get_session_account(redis, token)
        if account is not None:
            user_result = await session.exec(
                select(User).where(User.account == account)
            )
            user = user_result.scalar_one_or_none()
            if user is not None and user.is_active:
                await _extend_session(redis, token)
                return AuthPrincipal(
                    type="user",
                    user=UserPublic.model_validate(user),
                )

    if api_key:
        from src.core.auth.api_key import validate_api_key

        record = await validate_api_key(session, api_key)
        if record is not None:
            return AuthPrincipal(
                type="api_key",
                api_key=ApiKeySummary(
                    id=str(record.id),
                    name=record.name,
                    expires_at=record.expires_at,
                    created_at=record.created_at,
                    last_used_at=record.last_used_at,
                ),
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录或 API Key 无效。",
    )


async def require_admin(
    current_user: UserPublic = Depends(get_current_user),
) -> UserPublic:
    """要求当前用户为管理员角色，否则返回 403。"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限。",
        )
    return current_user
