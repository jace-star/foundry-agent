"""应用路由聚合入口。"""

from fastapi import APIRouter

from src.router.agent import router as agent_router
from src.router.api_key import router as api_key_router
from src.router.chat import router as chat_router
from src.router.conversation import router as conversation_router
from src.router.mcp import router as mcp_server_router
from src.router.skill import router as skill_router
from src.router.user import router as user_router

router = APIRouter(prefix="/agent/v1")
router.include_router(agent_router)
router.include_router(api_key_router)
router.include_router(chat_router)
router.include_router(conversation_router)
router.include_router(mcp_server_router)
router.include_router(skill_router)
router.include_router(user_router)
