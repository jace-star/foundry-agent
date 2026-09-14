"""自定义 OpenAPI Schema 增强。

为 /openapi.json 补充：
  1. 安全方案：BearerAuth (JWT) + ApiKeyAuth (X-API-Key)
  2. SSE 流式事件类型定义
  3. 聊天端点的 security 标注
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

# ── SSE 事件 Schema ──────────────────────────────────────────────────────────

SSE_EVENT_SCHEMAS = {
    "SSEMessageStartEvent": {
        "type": "object",
        "properties": {
            "event": {"type": "string", "enum": ["message_start"]},
            "conversation_id": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "会话 ID",
            },
        },
        "required": ["event"],
    },
    "SSEMessageEvent": {
        "type": "object",
        "properties": {
            "event": {"type": "string", "enum": ["message"]},
            "content": {"type": "string", "description": "增量文本"},
        },
        "required": ["event"],
    },
    "SSEToolStartEvent": {
        "type": "object",
        "properties": {
            "event": {"type": "string", "enum": ["tool_start"]},
            "name": {"type": "string", "description": "工具名称"},
            "input": {"description": "工具输入参数"},
        },
        "required": ["event"],
    },
    "SSEToolEndEvent": {
        "type": "object",
        "properties": {
            "event": {"type": "string", "enum": ["tool_end"]},
            "name": {"type": "string", "description": "工具名称"},
            "output": {"description": "工具输出"},
        },
        "required": ["event"],
    },
    "SSEMessageEndEvent": {
        "type": "object",
        "properties": {
            "event": {"type": "string", "enum": ["message_end"]},
            "conversation_id": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
            },
        },
        "required": ["event"],
    },
    "SSEErrorEvent": {
        "type": "object",
        "properties": {
            "event": {"type": "string", "enum": ["error"]},
            "detail": {"type": "string", "description": "错误详情"},
        },
        "required": ["event"],
    },
    "SSEEvent": {
        "description": "SSE 流式事件联合类型",
        "anyOf": [
            {"$ref": "#/components/schemas/SSEMessageStartEvent"},
            {"$ref": "#/components/schemas/SSEMessageEvent"},
            {"$ref": "#/components/schemas/SSEToolStartEvent"},
            {"$ref": "#/components/schemas/SSEToolEndEvent"},
            {"$ref": "#/components/schemas/SSEMessageEndEvent"},
            {"$ref": "#/components/schemas/SSEErrorEvent"},
        ],
    },
}


def custom_openapi(app: FastAPI) -> dict:
    """生成增强后的 OpenAPI schema。"""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=getattr(app, "version", "0.1.0"),
        description=getattr(app, "description", ""),
        routes=app.routes,
    )

    # 1. 注册安全方案
    if "securitySchemes" not in openapi_schema.setdefault("components", {}):
        openapi_schema["components"]["securitySchemes"] = {}

    openapi_schema["components"]["securitySchemes"].update({
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "用户登录后的 access token",
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "全局 API Key，供外部程序调用",
        },
    })

    # 2. 注册 SSE 事件 schemas
    openapi_schema["components"]["schemas"].update(SSE_EVENT_SCHEMAS)

    # 3. 为聊天端点标注 security（任一认证方式即可）
    for path, path_item in openapi_schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if operation.get("operationId") == "chat_messages_chat_messages_post":
                operation["security"] = [
                    {"BearerAuth": []},
                    {"ApiKeyAuth": []},
                ]
                # 标注流式响应的内容类型
                if "200" in operation.get("responses", {}):
                    for status_code, response in operation["responses"].items():
                        if status_code.startswith("2"):
                            content = response.get("content", {})
                            if "text/event-stream" not in content:
                                # 保留已有 JSON 响应，追加 SSE 描述
                                pass

    app.openapi_schema = openapi_schema
    return openapi_schema
