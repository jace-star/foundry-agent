/**
 * Chat 接口 - SSE 请求函数。
 * 将当前后端 /agent/v1/chat-messages 响应解析为原始事件流。
 */

import type { ChatRequestInput } from "./chat.types";
import type { ChatStreamEvent } from "@/composables/chat-type";
import { readSseJsonEvents } from "@/composables/chat";
import { getAuthToken } from "@/utils/auth-fetch";

/**
 * SSE 事件流生成器
 * 向当前后端 /agent/v1/chat-messages POST 请求，逐行解析 SSE data: 前缀的 JSON。
 */
export async function* Chat(
  body: ChatRequestInput,
  signal: AbortSignal
): AsyncGenerator<ChatStreamEvent> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "Accept": "text/event-stream",
  };
  const token = getAuthToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const reqBody: Record<string, unknown> = {
    prompt: body.message,
    agent_key: body.agent_key,
    stream: true,
    stateful: body.stateful ?? true,
  };
  if (body.conversation_id) {
    reqBody.conversation_id = body.conversation_id;
  }

  const response = await fetch("/agent/v1/chat-messages", {
    method: "POST",
    headers,
    body: JSON.stringify(reqBody),
    signal,
  });

  // 401 未授权：清除 token 并跳转登录页
  if (response.status === 401) {
    localStorage.removeItem("app.auth.token");
    setTimeout(() => {
      window.location.replace("/login");
    }, 800);
    throw new Error("登录已过期");
  }

  try {
    for await (const event of readSseJsonEvents<ChatStreamEvent>(response)) {
      yield event;
    }
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw error;
    }
    console.error("聊天请求失败:", error);
    throw error;
  }
}
