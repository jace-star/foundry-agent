export interface ChatStreamEvent {
  event: string;
  task_id?: string;
  message?: string;
  content?: string;
  agent_key?: string;
  name?: string;
  input?: unknown;
  output?: unknown;
  skills?: string[];
  status?: string;
  detail?: string;
  conversation_id?: string;
  model?: string;
  done?: boolean;
  has_more?: boolean;
  before_id?: number | null;
}

export interface FileAttachment {
  id: string;
  name: string;
  size: number;
}

export interface TextPart {
  kind: "text";
  content: string;
}

export interface ThinkingPart {
  kind: "reasoning";
  content: string;
  isCompleted?: boolean;
}

export interface ToolPart {
  kind: "tool";
  name: string;
  input: unknown;
  output: unknown;
  done: boolean;
}

export type ChatProcessedPart = TextPart | ThinkingPart | ToolPart;

export function isThinkingPart(part: ChatProcessedPart): part is ThinkingPart {
  return part.kind === "reasoning";
}

export function isToolPart(part: ChatProcessedPart): part is ToolPart {
  return part.kind === "tool";
}

export interface ChatProcessedMessage {
  role: "user" | "assistant";
  timestamp?: string;
  parts: ChatProcessedPart[];
  status?: "streaming" | "completed" | "aborted";
  files?: FileAttachment[];
  documentId?: string | null;
}

export interface ChatRequestFunction {
  (
    message: string,
    signal: AbortSignal,
    conversationId?: string | null
  ): AsyncGenerator<ChatStreamEvent> | Promise<AsyncGenerator<ChatStreamEvent>>;
}
