/**
 * AI Chat Composable — 对话状态管理
 * 核心职责：管理 messages、isLoading、sendMessage、abort、历史事件回放。
 */

import type { Ref } from "vue";
import type {
  ChatProcessedMessage,
  ChatRequestFunction,
  ChatStreamEvent,
  FileAttachment,
  TextPart,
  ThinkingPart,
  ToolPart,
} from "./chat-type";

import { computed, reactive, ref, shallowRef } from "vue";

export async function* readSseJsonEvents<T = unknown>(
  response: Response,
): AsyncGenerator<T> {
  if (!response.body) {
    throw new Error("数据异常");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) {
        continue;
      }

      const jsonStr = trimmed.slice(5).trim();
      if (!jsonStr) {
        continue;
      }

      try {
        yield JSON.parse(jsonStr) as T;
      } catch (e) {
        if (e instanceof SyntaxError) {
          console.warn("解析 SSE 事件失败:", jsonStr);
        } else {
          throw e;
        }
      }
    }
  }
}

export interface UseChatOptions {
  onError?: (error: Error) => void;
  onConversationId?: (conversationId: string) => void;
  onComplete?: () => void;
  onUpdate?: () => Promise<void>;
  onBefore?: () => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// useAssistantMessage — 基于后端原始事件构建 parts
// ─────────────────────────────────────────────────────────────────────────────

export interface UseAssistantMessageReturn {
  assistantMessage: ChatProcessedMessage;
  isThinking: Ref<boolean>;
  appendEvent: (event: ChatStreamEvent) => void;
  markCompleted: () => void;
}

export function useAssistantMessage(): UseAssistantMessageReturn {
  const assistantMessage = reactive<ChatProcessedMessage>({
    role: "assistant",
    parts: [],
    status: "streaming",
  });

  let currentReasoningPart: ThinkingPart | null = null;
  let textPart: TextPart | null = null;

  const isThinking = ref(false);

  const createReasoningPart = () => {
    assistantMessage.parts.push({
      kind: "reasoning",
      content: "",
      isCompleted: false,
    } as ThinkingPart);
    currentReasoningPart = assistantMessage.parts.at(-1) as ThinkingPart;
    return currentReasoningPart;
  };

  const getCurrentReasoningPart = () => {
    if (!currentReasoningPart || currentReasoningPart.isCompleted) {
      return createReasoningPart();
    }

    return currentReasoningPart;
  };

  const completeCurrentReasoningPart = () => {
    if (currentReasoningPart) {
      currentReasoningPart.content = currentReasoningPart.content.trimEnd();
      currentReasoningPart.isCompleted = true;
      currentReasoningPart = null;
    }
    isThinking.value = false;
  };

  const getTextPart = () => {
    if (!textPart) {
      assistantMessage.parts.push({
        kind: "text",
        content: "",
      } as TextPart);
      textPart = assistantMessage.parts.at(-1) as TextPart;
    }

    return textPart;
  };

  const appendEvent = (event: ChatStreamEvent) => {
    switch (event.event) {
      case "message":
        completeCurrentReasoningPart();
        if (event.content) {
          getTextPart().content += event.content;
        }
        break;

      case "message_start":
        break;

      case "reasoning":
        if (event.content) {
          getCurrentReasoningPart().content += event.content;
          isThinking.value = true;
        }
        if (event.done) {
          completeCurrentReasoningPart();
        }
        break;

      case "tool_start":
        completeCurrentReasoningPart();
        assistantMessage.parts.push({
          kind: "tool",
          name: event.name || "",
          input: event.input,
          output: null,
          done: false,
        } as ToolPart);
        break;

      case "tool_end": {
        const lastTool = [...assistantMessage.parts].reverse().find(
          (p) => p.kind === "tool" && !(p as ToolPart).done,
        ) as ToolPart | undefined;
        if (lastTool) {
          lastTool.output = event.output;
          lastTool.done = true;
        }
        break;
      }

      case "error":
      case "interrupted":
        assistantMessage.status = "aborted";
        break;

      case "message_end":
        assistantMessage.status = "completed";
        completeCurrentReasoningPart();
        break;

      case "input":
        break;
    }
  };

  const markCompleted = () => {
    if (assistantMessage.status !== "aborted") {
      assistantMessage.status = "completed";
      completeCurrentReasoningPart();
    }
  };

  return {
    assistantMessage,
    isThinking,
    appendEvent,
    markCompleted,
  };
}

export function useChat(
  chat: ChatRequestFunction,
  options: UseChatOptions = {}
) {
  const messages = ref<ChatProcessedMessage[]>([]);
  const isLoading = ref(false);
  const controller = shallowRef<AbortController | null>(null);

  let conversationId: string | null = null;

  const sendMessage = async (
    content: string,
    files?: FileAttachment[],
    documentId?: string | null,
  ) => {
    if (!content.trim() || isLoading.value) {
      return;
    }
    options.onBefore?.();
    let conversationIdNotified = false;
    let interrupted = false;

    messages.value.push({
      role: "user",
      parts: [{ kind: "text", content } as TextPart],
      files: files && files.length > 0 ? files : undefined,
    });

    const { assistantMessage, appendEvent, markCompleted } = useAssistantMessage();
    assistantMessage.documentId = documentId ?? null;
    messages.value.push(assistantMessage);

    options.onUpdate?.();

    isLoading.value = true;

    try {
      if (controller.value) {
        controller.value.abort();
      }

      controller.value = new AbortController();

      const currentConversationId = conversationId;
      const response = await chat(
        content,
        controller.value.signal,
        currentConversationId
      );

      for await (const event of response) {
        if (event.event === "input" && event.conversation_id) {
          conversationId = event.conversation_id;
          if (!conversationIdNotified) {
            conversationIdNotified = true;
            options.onConversationId?.(event.conversation_id);
          }
        }

        appendEvent(event);

        if (event.event === "error") {
          throw new Error(event.detail || "服务异常");
        }
        if (event.event === "interrupted") {
          interrupted = true;
          break;
        }

        options.onUpdate?.();
      }

      if (!interrupted) {
        markCompleted();
        options.onComplete?.();
      }
    } catch (error) {
      if (error instanceof Error && error.name !== "AbortError") {
        console.error("聊天请求出错:", error);
        options.onError?.(error);
      }
    } finally {
      isLoading.value = false;
      controller.value = null;
      await options.onUpdate?.();
    }
  };

  const abort = async () => {
    if (controller.value) {
      controller.value.abort();
      if (messages.value.length > 0) {
        const lastMessage = messages.value.at(-1)!;
        lastMessage.status = "aborted";
      }
      isLoading.value = false;
    }
  };

  function clearMessages() {
    messages.value = [];
    conversationId = null;
  }

  function setConversationId(id: string | null) {
    conversationId = id;
  }

  function buildHistoryMessages(events: ChatStreamEvent[]) {
    const historyMessages: ChatProcessedMessage[] = [];
    let assistant = null as ReturnType<typeof useAssistantMessage> | null;

    const ensureAssistant = () => {
      if (!assistant) {
        assistant = useAssistantMessage();
        historyMessages.push(assistant.assistantMessage);
      }
      return assistant;
    };

    for (const event of events) {
      if (event.event === "input") {
        historyMessages.push({
          role: "user",
          parts: [{ kind: "text", content: event.message || "" }],
          status: "completed",
        });
        assistant = null;
        continue;
      }

      if (event.event === "message_start") {
        ensureAssistant();
        continue;
      }

      if (
        event.event === "message"
        || event.event === "tool_start"
        || event.event === "tool_end"
      ) {
        ensureAssistant().appendEvent(event);
        continue;
      }

      if (event.event === "message_end") {
        ensureAssistant().appendEvent(event);
        assistant = null;
        continue;
      }

      if (event.event === "error" || event.event === "interrupted") {
        ensureAssistant().appendEvent(event);
        assistant = null;
      }
    }

    return historyMessages;
  }

  function loadHistoryMessages(events: ChatStreamEvent[]) {
    messages.value = buildHistoryMessages(events);
  }

  function prependHistoryMessages(events: ChatStreamEvent[]) {
    messages.value = [
      ...buildHistoryMessages(events),
      ...messages.value,
    ];
  }

  return {
    messages,
    conversationId: computed(() => conversationId),
    isLoading,
    sendMessage,
    abort,
    clearMessages,
    setConversationId,
    loadHistoryMessages,
    prependHistoryMessages,
  };
}
