/**
 * Chat 接口类型定义
 */

// ─────────────────────────────────────────────────────────────────────────────
// 请求类型
// ─────────────────────────────────────────────────────────────────────────────

export interface ChatRequestInput {
  message: string;
  agent_key: string;
  conversation_id?: string | null;
  stateful?: boolean;
}
