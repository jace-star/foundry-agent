from functools import lru_cache

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
from loguru import logger

from src.config import get_settings


@lru_cache
def get_langfuse_client() -> Langfuse | None:
    """Create a Langfuse client when tracing credentials are configured."""
    settings = get_settings().langfuse
    if not settings.public_key or not settings.secret_key:
        return None

    try:
        return Langfuse(
            public_key=settings.public_key,
            secret_key=settings.secret_key,
            host=settings.host,
        )
    except Exception as exc:
        logger.warning("Langfuse client initialization failed: {}", exc)
        return None


def is_tracing_enabled() -> bool:
    return get_langfuse_client() is not None


def get_langfuse_handler() -> LangfuseCallbackHandler | None:
    """获取 Langfuse LangChain CallbackHandler，用于注入 LangGraph config["callbacks"]。

    CallbackHandler 自动追踪所有 LLM 调用和工具执行，在 @observe() 装饰器
    创建的根 trace 下生成子 span。凭据未配置时返回 None（零开销）。
    """
    if not is_tracing_enabled():
        return None

    try:
        return LangfuseCallbackHandler()
    except Exception as exc:
        logger.warning("创建 Langfuse CallbackHandler 失败: {}", exc)
        return None
