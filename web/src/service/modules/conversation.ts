/**
 * 会话 REST API Service — 对接 Agent 后端 /agent/v1/conversations
 */

import type { ChatStreamEvent } from "@/composables/chat-type";
import { readSseJsonEvents } from "@/composables/chat";
import { authFetch } from "@/utils/auth-fetch";
import { request } from "@/utils/request";

// ─────────────────────────────────────────────────────────────────────────────
// 类型
// ─────────────────────────────────────────────────────────────────────────────

export interface ConversationSummary {
  id: string;
  title: string;
  last_active_at: string; // ISO datetime
}

export interface ConversationListResponse {
  items: ConversationSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface ConversationEvent extends ChatStreamEvent {}

export interface ConversationHistoryMeta {
  has_more: boolean;
  before_id: number | null;
}

export interface ConversationDetailResponse {
  events: ConversationEvent[];
  history: ConversationHistoryMeta;
}

export interface BatchDeleteResponse {
  deleted: string[];
  not_found: string[];
  forbidden: string[];
}

// ─────────────────────────────────────────────────────────────────────────────
// API
// ─────────────────────────────────────────────────────────────────────────────

export interface FetchConversationsParams {
  agent_key: string;
  page?: number;
  page_size?: number;
}

/** 获取会话列表（全部，前端按 last_active_at 分组） */
export function fetchConversations(
  params: FetchConversationsParams,
): Promise<ConversationListResponse> {
  const qs = new URLSearchParams();
  qs.set("agent_key", params.agent_key);
  if (params.page != null) {
    qs.set("page", String(params.page));
  }
  if (params.page_size != null) {
    qs.set("page_size", String(params.page_size));
  }
  return request.get(`/conversations?${qs.toString()}`);
}

/** 获取会话详情（按轮次分页，默认最近 10 轮完整对话） */
export async function fetchConversationDetail(
  conversationId: string,
  rounds = 10,
  beforeId?: number | null,
): Promise<ConversationDetailResponse> {
  const qs = new URLSearchParams();
  qs.set("rounds", String(rounds));
  if (beforeId != null) {
    qs.set("before_id", String(beforeId));
  }

  const response = await authFetch(`/agent/v1/conversations/${conversationId}?${qs.toString()}`, {
    headers: {
      Accept: "text/event-stream",
    },
  });

  const events: ConversationEvent[] = [];
  let history: ConversationHistoryMeta = {
    has_more: false,
    before_id: null,
  };

  for await (const event of readSseJsonEvents<ChatStreamEvent>(response)) {
    if (event.event === "history") {
      history = {
        has_more: Boolean(event.has_more),
        before_id: event.before_id ?? null,
      };
      continue;
    }
    events.push(event);
  }
  return { events, history };
}

/** 删除会话 */
export function deleteConversationById(conversationId: string): Promise<{ detail: string }> {
  return request.delete(`/conversations/${conversationId}`);
}

/** 批量删除 */
export function batchDeleteConversations(ids: string[]): Promise<BatchDeleteResponse> {
  return request.post("/conversations/batch-delete", { ids });
}
