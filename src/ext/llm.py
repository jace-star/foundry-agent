"""LLM 配置模块，基于 LangChain ChatOpenAI 提供统一的 LLM 调用接口。"""

from functools import lru_cache

from langchain_openai import ChatOpenAI

from src.config import get_settings


@lru_cache
def get_llm() -> ChatOpenAI:
    """获取 LangChain ChatOpenAI 单例。"""
    settings = get_settings()
    kwargs: dict = {
        "base_url": settings.openai.base_url,
        "api_key": settings.openai.api_key,
        "model": settings.openai.model,
        "timeout": settings.openai.timeout_seconds,
    }
    if settings.openai.max_tokens is not None:
        kwargs["max_tokens"] = settings.openai.max_tokens
    return ChatOpenAI(**kwargs)
