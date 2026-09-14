<script lang="tsx">
import type { PropType } from "vue";
import type { ChatRequestFunction, ChatStreamEvent, FileAttachment } from "@/composables/chat-type";
import {
  computed,
  defineComponent,
  onUnmounted,
  ref,
  renderSlot,
} from "vue";
import AutoScrollbar from "@/components/auto-scrollbar.vue";
import ChatInput from "@/components/chat/chat-input.vue";
import { useChat } from "@/composables/chat";
import Dialogue from "./chat-dialogue.vue";

// 定义 ChatFrame 实例接口
export interface ChatFrameInstance {
  sendMessage: (message: string) => Promise<void>;
  conversationId: import("vue").ComputedRef<string | null>;
  clearMessages: () => void;
  setConversationId: (id: string | null) => void;
  loadHistoryMessages: (events: ChatStreamEvent[]) => void;
  prependHistoryMessages: (events: ChatStreamEvent[]) => void;
}

export default defineComponent({
  name: "ChatFrame",
  props: {
    chat: {
      type: Function as PropType<ChatRequestFunction>,
      required: true,
    },
    docSelect: {
      type: Function as PropType<(file: File | null) => Promise<void> | void>,
      default: undefined,
    },
    contentClass: {
      type: [String, Array] as PropType<string | string[]>,
      default: "",
    },
    onMessageComplete: {
      type: Function as PropType<(conversationId: string | null) => void>,
      default: undefined,
    },
    onConversationId: {
      type: Function as PropType<(conversationId: string) => void>,
      default: undefined,
    },
    onLoadMoreHistory: {
      type: Function as PropType<() => void | Promise<void>>,
      default: undefined,
    },
    // 当前会话正在使用的文档 id，下载导出时要带着它。
    sessionDocumentId: {
      type: String as PropType<string>,
      default: "",
    },
  },
  setup(props, { slots, expose }) {
    const isAutoScroll = ref(true);
    const inputValue = ref("");
    const selectedReport = ref<FileAttachment | null>(null);
    const isDocUploading = ref(false);

    const {
      messages,
      conversationId,
      isLoading,
      sendMessage,
      abort,
      clearMessages,
      setConversationId,
      loadHistoryMessages,
      prependHistoryMessages,
    } = useChat(props.chat, {
      onBefore() {
        isAutoScroll.value = true;
      },
      onConversationId(conversationId) {
        props.onConversationId?.(conversationId);
      },
      onComplete() {
        props.onMessageComplete?.(conversationId.value);
      },
    });

    expose({
      sendMessage,
      conversationId,
      clearMessages,
      setConversationId,
      loadHistoryMessages,
      prependHistoryMessages,
    });

    const handleReachTop = async () => {
      await props.onLoadMoreHistory?.();
    };

    // 处理发送消息
    const handleSend = (message: string) => {
      sendMessage(
        message,
        selectedReport.value ? [selectedReport.value] : undefined,
        props.sessionDocumentId || null,
      );
      selectedReport.value = null;
    };

    const handleDocChange = async (file: File | null) => {
      selectedReport.value = file
        ? {
            id: `${file.name}-${file.lastModified}-${file.size}`,
            name: file.name,
            size: file.size,
          }
        : null;
      if (file) {
        isDocUploading.value = true;
        try {
          await props.docSelect?.(file);
        } finally {
          isDocUploading.value = false;
        }
      } else {
        await props.docSelect?.(file);
      }
    };

    // 处理停止聊天
    const chatInputStop = async (): Promise<boolean> => {
      if (!isLoading.value) {
        return true;
      }

      // 使用 Element Plus 的 ElMessageBox
      const { ElMessageBox } = await import("element-plus");

      try {
        await ElMessageBox.confirm("你确定要终止当前回答吗？", "警告", {
          confirmButtonText: "确定",
          cancelButtonText: "取消",
          type: "warning",
        });
        abort();
        return true;
      } catch {
        return !isLoading.value;
      }
    };

    // 计算是否显示消息列表
    const hasMessages = computed(() => messages.value.length > 0);

    onUnmounted(() => abort());

    return () => (
      <>
        <div class="flex flex-col h-full w-full box-border">
          <div class="flex-1 min-h-0 flex flex-col">
            {!hasMessages.value && <div class="w-full flex-1 min-h-0">{renderSlot(slots, "empty")}</div>}
            {hasMessages.value && (
              <AutoScrollbar
                v-model:auto={isAutoScroll.value}
                class="w-full flex-1 px-6 py-4"
                onReachTop={handleReachTop}
                contentClass={
                  typeof props.contentClass === "string"
                    ? props.contentClass
                    : (props.contentClass as string[]).join(" ")
                }
              >
                {messages.value.map((message, index) => (
                  <div key={`message-${index}`} class="chat-message-block">
                    <Dialogue
                      chatMessage={message}
                    />
                  </div>
                ))}
              </AutoScrollbar>
            )}
          </div>
          <ChatInput
            modelValue={inputValue.value}
            stopState={!isLoading.value}
            docUploading={isDocUploading.value}
            class="w-full box-border px-6 pb-6 flex-shrink-0"
            onUpdate:modelValue={(value: string) => {
              inputValue.value = value;
            }}
            onSend={handleSend}
            onDoc-change={handleDocChange}
            onStop={chatInputStop}
          >
            {{
              model: () => renderSlot(slots, "model"),
            }}
          </ChatInput>
        </div>
      </>
    );
  },
});
</script>
