"""聊天请求/响应模型。"""

from uuid import UUID

from pydantic import BaseModel, Field


class LLMChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    agent_key: str | None = None
    stream: bool = True
    conversation_id: UUID | None = None
    stateful: bool = True
    history_limit: int = Field(default=20, ge=1, le=100)


class LLMChatResponse(BaseModel):
    content: str
    model: str
