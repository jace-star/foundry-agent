# 代码分层方案：最简架构，去 Repository + 去 Service

更新时间：2026-06-24

## 目标

参考 FastAPI 官方教程（[SQL Databases](https://fastapi.tiangolo.com/tutorial/sql-databases/)）和 [full-stack-fastapi-template](https://github.com/tiangolo/full-stack-fastapi-template) 的做法：

- 路由直接拿注入的 `AsyncSession` 写数据库操作
- 不复用的逻辑不单独抽层
- 复用的工具函数放 `core/`，认证依赖放 `core/deps.py`

社区真实情况：FastAPI 作者、Prefect（18k ⭐）、Dify（70k ⭐）、Netflix Dispatch（5k ⭐）都不写 Repository，也不为单次调用写独立 Service 类。

## 核心原则

> **只对真正复用的逻辑做抽取，单次调用的逻辑直接写在路由里。**

| 场景 | 放哪里 |
| --- | --- |
| 路由专属的 CRUD（一个路由用一次） | 直接写在路由函数里 |
| 登录验证（一个路由用一次） | 直接写在路由函数里 |
| JWT token 解析 + 用户查询（多个路由共用） | 抽成 FastAPI `Depends` → `core/deps.py` |
| JWT 生成/验证（认证流程共用） | 抽成工具函数 → `core/security.py` |
| 密码 hash/verify（多处调用） | 抽成工具函数 → `core/security.py` |
| 管理员种子数据（lifespan 一次性调用） | 内联在 `app.py` lifespan 中 |

## 目标分层

```text
router（HTTP + DB 操作 + 业务逻辑）
  ├── 复用逻辑 → core/deps.py（FastAPI Depends）/ core/security.py（纯工具函数）
  └── 不复用的逻辑 → 直接写在路由函数里
        ↓
      ext（基础设施：AsyncSession、OpenDAL operator）
```

| 层 / 位置 | 职责 |
| --- | --- |
| `router` | HTTP 处理 + 数据库操作 + 业务逻辑 |
| `core` | 复用的认证依赖（deps）和工具函数（security） |
| `ext` | 基础设施客户端（async engine、async session、OpenDAL operator） |

不再有独立的 `service/` 层和 `repository/` 层。

## 改造后目录结构

对齐官方 `full-stack-fastapi-template` 的布局，`core/` 内按逻辑分区用目录划分：

```text
src/
├── core/
│   ├── security/
│   │   ├── password.py   ← hash_password, verify_password
│   │   └── jwt.py        ← create_access_token, decode_token
│   └── auth/
│       └── deps.py       ← get_current_user, get_current_user_or_api_key
├── ext/                  ← 基础设施（不知道业务）
│   ├── database.py       ← async engine + get_session()
│   ├── storage.py        ← OpenDAL operator 工厂
│   ├── llm.py
│   └── observability.py
├── router/               ← 路由 + 业务逻辑（直接写 DB / OpenDAL）
│   ├── user.py           ← 用户 CRUD + 登录（直调 session）
│   ├── agent.py
│   ├── api_key.py
│   ├── chat.py
│   ├── mcp.py
│   └── skill.py
├── models/               ← SQLModel / Pydantic 模型
│   ├── user.py
│   └── ...
├── config.py
└── app.py                ← lifespan 内联 seed_admin 逻辑
```

每个目录职责单一、可独立扩展：

| 目录 | 职责 | 未来可能增加 |
|------|------|-------------|
| `core/security/` | 密码学工具（hash、JWT） | token 刷新、API Key 生成 |
| `core/auth/` | FastAPI 认证依赖 | 权限校验、角色守卫 |
| `ext/` | 基础设施客户端 | 消息队列、缓存 |
| `router/` | HTTP 路由 + 业务逻辑 | 新业务模块 |

对比官方模板：

| 官方 | 本项目 |
|------|--------|
| `app/core/security.py` | `src/core/security/`（拆成 password + jwt） |
| `app/api/deps.py` | `src/core/auth/deps.py` |
| `app/api/routes/users.py` | `src/router/user.py` |
| `app/core/db.py` | `src/ext/database.py` |
| `app/models.py` | `src/models/` |

`src/service/` 和 `src/repository/` 目录删除。

## AsyncSession 注入模式

和官方教程一模一样：

```python
# src/ext/database.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

async def get_session() -> AsyncIterator[AsyncSession]:
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

# src/router/user.py
from typing import Annotated
from fastapi import Depends
SessionDep = Annotated[AsyncSession, Depends(get_session)]

@router.post("/users", response_model=ApiResponse[UserPublic])
async def create_user(payload: UserCreateRequest, session: SessionDep):
    user = User(
        account=payload.account,
        password=hash_password(payload.password),
        name=payload.name,
        role=payload.role,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="账号已存在")
    return ApiResponse(data=UserPublic.model_validate(user), message="创建成功")
```

## 复用逻辑放在 core/

### core/security/password.py — 密码 hash

```python
from pwdlib import PasswordHash

_password_hasher = PasswordHash.recommended()

def hash_password(password: str) -> str: ...
def verify_password(plain: str, hashed: str) -> bool: ...
```

### core/security/jwt.py — JWT 生成/解析

```python
import jwt

def create_access_token(user: UserBase) -> str: ...
def decode_token(token: str) -> dict | None: ...
```

### core/auth/deps.py — FastAPI 认证依赖

```python
"""复用的认证依赖，被多个路由引用。"""
from fastapi import Depends, HTTPException
from src.core.security.jwt import decode_token
from src.ext.database import get_session

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    session: AsyncSession = Depends(get_session),
) -> UserPublic: ...

async def get_current_user_or_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    api_key: str | None = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session),
) -> UserPublic | None: ...
```

## 管理员初始化（内联在 app.py）

不单独抽文件，逻辑直接写在 lifespan 里：

```python
# src/app.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
    # 管理员种子数据
    auth = get_settings().auth
    if auth.admin_account and auth.admin_password:
        async with get_session_context() as session:
            await _ensure_admin(session, auth.admin_account, auth.admin_password)
    yield
    await close_database()
```

## 强制边界规则

1. 只有 `src/ext/database.py` 创建 `AsyncEngine` 和 `async_sessionmaker`。
2. 只有 `src/ext/storage.py` 调用 OpenDAL 创建 operator。
3. `AsyncSession` 通过 `Depends(get_session)` 注入路由。
4. 不复用的 CRUD/业务逻辑直接写在路由函数里。
5. 被多处调用的逻辑抽成函数，放在 `src/core/` 下。
6. 一次性启动逻辑内联在 `app.py` lifespan 中，不单独建文件。

## 具体改造顺序

### Phase 1：database.py 切 AsyncSession ✅（已完成）

- `create_engine` → `create_async_engine`，驱动切 `asyncpg`
- `database_session()` → `get_session()` 异步生成器
- Alembic 迁移通过 `run_sync` 桥接

### Phase 2：用户相关代码重构

目标：去掉 `UserService` 和 `UserRepository`，路由直调 session。

改动：
- 新增 `src/core/security/password.py` — hash_password、verify_password
- 新增 `src/core/security/jwt.py` — create_access_token、decode_token
- 新增 `src/core/auth/deps.py` — get_current_user、get_current_user_or_api_key
- `src/router/user.py` — 路由内联 CRUD + 登录逻辑，直调 session
- `src/app.py` — lifespan 内联 seed_admin 逻辑
- 删除 `src/service/user_service.py`
- 删除 `src/repository/user_repository.py`
- 更新 `src/repository/__init__.py`
- 更新所有路由中 `get_current_user` / `get_current_user_or_api_key` 的 import 路径

### Phase 3：Agent / Skill / API Key / MCP 去 Repository

目标：这些路由直接拿 OpenDAL operator 做文件读写。

改动：
- 路由内联持久化逻辑，不经过 Repository
- 删除对应的 service 和 repository 文件

### Phase 4：清理

删除 `src/service/` 和 `src/repository/` 目录。

## 依赖变更

```text
# pyproject.toml
"asyncpg>=0.30.0",        # 替换 psycopg[binary]
```

## 不建议做的事

- 不引入 Service 层（不复用的逻辑不值得抽）
- 不引入 Repository 层
- 不引入泛型基类
- 不引入 Unit of Work / Protocol
- 不为一次性启动逻辑单独建文件
- 不改现有接口路径和前端契约
