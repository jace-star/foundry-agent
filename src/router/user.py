"""用户与登录接口 — 路由直调 session，无 Service/Repository 中间层。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.auth.user import (
    create_session,
    delete_session,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from src.ext.database import get_session
from src.ext.redis import get_redis
from src.models.user import (
    LoginResponse,
    User,
    UserChangePasswordRequest,
    UserCreateRequest,
    UserLoginRequest,
    UserPublic,
    UserUpdateRequest,
    parse_uuid,
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]

router = APIRouter(tags=["users"])


# ---------------------------------------------------------------------------
# 认证
# ---------------------------------------------------------------------------


@router.post("/auth/login")
async def login(payload: UserLoginRequest, session: SessionDep):
    """用户登录。Redis session 记录 token → account 映射，返回 accessToken。"""
    user = (
        await session.exec(select(User).where(User.account == payload.account))
    ).scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误。",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用。",
        )

    redis = await get_redis()
    token = await create_session(redis, user.account)
    body = LoginResponse(
        accessToken=token,
        user=UserPublic.model_validate(user),
    )
    return JSONResponse(content=body.model_dump(mode="json"))


@router.post("/auth/logout")
async def logout(authorization: str | None = Header(None, alias="Authorization")):
    """用户登出。删除 Redis session，前端清理 access token。"""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        redis = await get_redis()
        await delete_session(redis, token)
    return JSONResponse(content={"message": "登出成功"})


# ---------------------------------------------------------------------------
# 用户 CRUD
# ---------------------------------------------------------------------------


@router.get("/user/info", response_model=UserPublic)
async def get_user_info(current_user: UserPublic = Depends(get_current_user)):
    """获取当前登录用户信息。"""
    return current_user


@router.post("/user/change-password")
async def change_password(
    payload: UserChangePasswordRequest,
    session: SessionDep,
    current_user: UserPublic = Depends(get_current_user),
):
    """当前用户自助修改密码。"""
    user = await session.get(User, current_user.id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在。",
        )
    if not verify_password(payload.old_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误。",
        )

    user.password = hash_password(payload.new_password)
    from src.models.user import _utcnow

    user.updated_at = _utcnow()
    await session.flush()
    return {"message": "密码修改成功"}


@router.post(
    "/users",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_user(payload: UserCreateRequest, session: SessionDep):
    """创建用户。"""
    user = User(
        account=payload.account,
        password=hash_password(payload.password),
        name=payload.name,
        role=payload.role,
        is_active=payload.is_active,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="账号已存在。",
        )
    await session.refresh(user)
    return UserPublic.model_validate(user)


@router.get("/users", response_model=list[UserPublic], dependencies=[Depends(require_admin)])
async def list_users(session: SessionDep):
    """查询用户列表（仅管理员）。"""
    users = (
        await session.exec(select(User).order_by(User.created_at.desc()))
    ).scalars().all()
    return [UserPublic.model_validate(u) for u in users]


@router.get("/users/{user_id}", response_model=UserPublic, dependencies=[Depends(require_admin)])
async def get_user(user_id: str, session: SessionDep):
    """查询单个用户。"""
    uid = parse_uuid(user_id)
    if uid is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在。")
    user = await session.get(User, uid)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在。")
    return UserPublic.model_validate(user)


@router.put("/users/{user_id}", response_model=UserPublic, dependencies=[Depends(require_admin)])
async def update_user(user_id: str, payload: UserUpdateRequest, session: SessionDep):
    """更新用户（仅管理员）。"""
    uid = parse_uuid(user_id)
    if uid is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在。")
    user = await session.get(User, uid)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在。")

    if payload.password is not None:
        user.password = hash_password(payload.password)

    update_data = payload.model_dump(exclude_unset=True, exclude={"password"})
    for field, value in update_data.items():
        setattr(user, field, value)

    from src.models.user import _utcnow

    user.updated_at = _utcnow()
    await session.flush()
    await session.refresh(user)
    return UserPublic.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    session: SessionDep,
    admin: UserPublic = Depends(require_admin),
):
    """删除用户（仅管理员）。不允许删除自己或最后一个管理员。"""
    uid = parse_uuid(user_id)
    if uid is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在。")

    if uid == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账号。",
        )

    user = await session.get(User, uid)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在。")

    # 检查是否为最后一个活跃管理员
    if user.role == "admin":
        admin_count = (
            await session.exec(
                select(func.count()).select_from(User).where(
                    User.role == "admin", User.is_active == True  # noqa: E712
                )
            )
        ).scalar_one()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能删除最后一个管理员账号。",
            )

    await session.delete(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
