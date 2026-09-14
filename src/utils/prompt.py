"""通用提示词服务 - 为 LLM 提供统一的系统提示词构建。

使用方式：
    from src.utils.prompt import build_context_prompt

    context = build_context_prompt()
    # "当前时间: 2026-06-17 08:00:00 UTC\n语言: 简体中文"

扩展方式:
    添加新的 _xxx_context() 函数，并在 build_context_prompt 中调用。
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")


def current_time_context() -> str:
    """当前时间"""
    now = datetime.now(UTC).astimezone(SHANGHAI)
    return (
        f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"
    )


def language_context() -> str:
    """默认语言。"""
    return "语言: 简体中文"


def build_context_prompt() -> str:
    """组装所有上下文信息为一段文本。"""
    parts = [current_time_context(), language_context()]
    return "\n".join(parts)
