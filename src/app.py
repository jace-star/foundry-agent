from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from sqlalchemy import select

from src.config import BASE_DIR, get_settings
from src.constants import _check_langfuse
from src.core.auth.user import hash_password, verify_password
from src.ext.database import close_database, get_session_context, init_database
from src.handler.exception import register_exception_handlers
from src.models.user import User
from src.router import router as api_router

STATIC_DIR = BASE_DIR / "web" / "dist"


async def _ensure_admin(account: str, raw_password: str) -> None:
    """创建或同步系统管理员账号（仅密码/角色变化时才更新）。"""
    async with get_session_context() as session:
        user = (
            await session.exec(select(User).where(User.account == account))
        ).scalar_one_or_none()

        if user is None:
            user = User(
                account=account,
                password=hash_password(raw_password),
                name=account,
                role="admin",
            )
            session.add(user)
            await session.flush()
            logger.info("系统管理员账号已创建: {}", account)
        else:
            need_update = False
            if not verify_password(raw_password, user.password):
                user.password = hash_password(raw_password)
                need_update = True
            if user.role != "admin":
                user.role = "admin"
                need_update = True
            if need_update:
                await session.flush()
                logger.info("系统管理员账号已同步: {}", account)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库、同步管理员并检测外部服务连通性。"""
    await init_database()

    # 管理员种子数据
    auth = get_settings().auth
    account = auth.admin_account.strip() if auth.admin_account else ""
    password = auth.admin_password.strip() if auth.admin_password else ""
    if account and password:
        await _ensure_admin(account, password)
    else:
        logger.info("ADMIN_ACCOUNT 或 ADMIN_PASSWORD 未配置，跳过管理员账号初始化")

    _check_langfuse()
    try:
        yield
    finally:
        await close_database()


def create_app() -> FastAPI:
    app = FastAPI(title="foundry-agent", debug=True, lifespan=lifespan)

    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # 挂载自定义 OpenAPI schema（安全方案 + SSE 事件类型）
    from src.openapi import custom_openapi

    app.openapi = lambda: custom_openapi(app)

    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """托管前端构建产物（web/dist）；目录不存在时跳过（纯 API / 本地 Vite 开发）。"""
    if not STATIC_DIR.is_dir():
        logger.info("未找到前端构建产物 {}，跳过静态资源挂载", STATIC_DIR)
        return

    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    index_html = STATIC_DIR / "index.html"

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_html)

    logger.info("已挂载前端静态资源: {}", STATIC_DIR)
