<script setup lang="ts">
import type { ChatProcessedMessage, FileAttachment } from "@/composables/chat-type";
import { ElButton, ElMessage } from "element-plus";
import { computed, onUnmounted, ref, watch } from "vue";
import VueJsonPretty from "vue-json-pretty";
import checkIcon from "@/assets/icon/check.svg";
import copyIcon from "@/assets/icon/copy.svg";
import downloadIcon from "@/assets/icon/download.svg";
import fileIcon from "@/assets/icon/file.svg";
import Markdown from "@/components/C-StreamMarkdown.vue";
import ChatLoading from "@/components/chat/chat-loading.vue";
import Collapse from "@/components/collapse.vue";
import { isThinkingPart, isToolPart } from "@/composables/chat-type";
import { exportDoc } from "@/service";
import "vue-json-pretty/lib/styles.css";

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

interface Props {
  chatMessage: ChatProcessedMessage;
}

const props = defineProps<Props>();

const thinkingParts = computed(() => {
  return props.chatMessage.parts.filter(isThinkingPart);
});

const toolParts = computed(() => {
  return props.chatMessage.parts.filter(isToolPart);
});

// 每个思考过程维护独立展开状态
const thinkingStates = ref<boolean[]>([]);

watch(
  thinkingParts,
  (parts) => {
    if (thinkingStates.value.length > parts.length) {
      thinkingStates.value = thinkingStates.value.slice(0, parts.length);
    }

    parts.forEach((part, index) => {
      if (thinkingStates.value[index] === undefined) {
        thinkingStates.value[index] = !(part.isCompleted ?? false);
      }

      if (part.isCompleted) {
        thinkingStates.value[index] = false;
      }
    });
  },
  { immediate: true },
);

watch(
  () => thinkingParts.value.map((part) => part.isCompleted ?? false),
  (completedStates) => {
    completedStates.forEach((isCompleted, index) => {
      if (isCompleted) {
        thinkingStates.value[index] = false;
      }
    });
  },
  { immediate: true },
);

// 根据角色获取消息内容
const userContent = computed(() => {
  if (props.chatMessage.role !== "user") {
    return "";
  }
  const textPart = props.chatMessage.parts.find((p) => p.kind === "text");
  return textPart && "content" in textPart ? textPart.content : "";
});

const userFiles = computed<FileAttachment[]>(() => {
  if (props.chatMessage.role !== "user") {
    return [];
  }
  return props.chatMessage.files || [];
});

const answerPart = computed(() =>
  props.chatMessage.parts.find((p) => p.kind === "text"),
);

const isLoading = computed(() => {
  if (props.chatMessage.status === "aborted") {
    return false;
  }
  return props.chatMessage.parts.length === 0;
});

const isAborted = computed(
  () =>
    props.chatMessage.status === "aborted"
    && props.chatMessage.parts.length === 0,
);

const isCompleted = computed(
  () => props.chatMessage.status === "completed",
);

const canDownload = computed(
  () => !!answerPart.value?.content && isCompleted.value,
);

const isExporting = ref(false);
const copied = ref(false);
let copyTimer: ReturnType<typeof setTimeout> | null = null;
const exportDocumentId = computed(
  () => props.chatMessage.documentId || "",
);

function toJsonData(value: unknown): JsonValue {
  return value as JsonValue;
}

async function handleCopy() {
  const content = answerPart.value?.content?.trim();
  if (!content) {
    return;
  }

  // markdown 中 \n\n 是段落分隔，复制时合并为单换行避免粘贴后多出空行
  const normalized = content.replace(/\n{2,}/g, "\n");

  try {
    await navigator.clipboard.writeText(normalized);
    copied.value = true;
    if (copyTimer) {
      clearTimeout(copyTimer);
    }
    copyTimer = setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch {
    ElMessage.error("复制失败");
  }
}

async function handleDownload() {
  const content = answerPart.value?.content?.trim();
  if (!content || isExporting.value) {
    return;
  }

  isExporting.value = true;
  try {
    const { blob, filename } = await exportDoc(
      content,
      exportDocumentId.value || undefined,
    );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    const message = error instanceof Error ? error.message : "文档导出失败";
    ElMessage.error(message);
  } finally {
    isExporting.value = false;
  }
}

onUnmounted(() => {
  if (copyTimer) {
    clearTimeout(copyTimer);
  }
});
</script>

<template>
  <div class="mb-6 px-4">
    <!-- 用户消息 -->
    <div
      v-if="chatMessage.role === 'user' && (userContent || userFiles.length > 0)"
      class="mb-4 flex flex-col items-end"
    >
      <div v-if="userFiles.length > 0" class="mb-2 flex max-w-3xl flex-wrap gap-2">
        <div
          v-for="file in userFiles"
          :key="file.id"
          class="inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs shadow-sm"
          style="background: #eef; border-color: #ccf; color: #55f"
        >
          <img :src="fileIcon" alt="file" class="h-3.5 w-3.5">
          <span
            class="max-w-44 truncate"
            :title="file.name"
          >
            {{ file.name }}
          </span>
        </div>
      </div>
      <div
        v-if="userContent"
        class="max-w-3xl rounded-2xl rounded-tr-sm py-3 px-5 shadow-md text-slate-800"
        style="background-color: #fafafa"
      >
        <div class="whitespace-pre-wrap">
          {{ userContent }}
        </div>
      </div>
    </div>

    <!-- 助手消息 -->
    <template v-if="chatMessage.role === 'assistant'">
      <!-- 思考过程 -->
      <template v-if="thinkingParts.length > 0">
        <Collapse
          v-for="(part, index) in thinkingParts"
          v-show="part.content"
          :key="`thinking-${index}`"
          v-model="thinkingStates[index]"
          :title="part.isCompleted ? '思考结束' : '思考中'"
          class="bg-blue-50 w-full mb-4 rounded-xl py-3 px-4 border border-blue-200 shadow-sm"
        >
          <Markdown :text="part.content" :loading="false" />
        </Collapse>
      </template>

      <!-- 工具调用 -->
      <template v-if="toolParts.length > 0">
        <Collapse
          v-for="(part, index) in toolParts"
          :key="`tool-${index}`"
          :model-value="false"
          :title="part.done ? part.name : `${part.name} 执行中`"
          :title-icon="part.name === 'select_skill' && part.done ? '/tool.svg' : ''"
          :title-loading="part.name === 'select_skill' && !part.done"
          class="tool-call"
        >
          <div v-if="part.input" class="tool-call__section">
            <div class="tool-call__label">
              参数
            </div>
            <div class="tool-call__json">
              <VueJsonPretty :data="toJsonData(part.input)" :deep="0" :show-length="true" />
            </div>
          </div>
          <div v-if="part.done && part.output !== null" class="tool-call__section">
            <div class="tool-call__label">
              结果
            </div>
            <div class="tool-call__json">
              <VueJsonPretty :data="toJsonData(part.output)" :deep="0" :show-length="true" />
            </div>
          </div>
          <div v-else-if="!part.done" class="tool-call__pending">
            执行中...
          </div>
        </Collapse>
      </template>

      <!-- 回答内容 -->
      <div v-if="answerPart && answerPart.content">
        <div class="bg-white rounded-2xl px-3 py-2 mb-1 shadow-sm border border-slate-200">
          <Markdown :text="answerPart.content" :loading="false" />
        </div>
        <div class="mb-4 px-1 flex items-center gap-0">
          <ElButton
            text
            :title="copied ? '已复制' : '复制'"
            :style="copied ? { color: '#67c23a', padding: '4px' } : { color: '#909399', padding: '4px' }"
            @click="handleCopy"
          >
            <img
              :src="copied ? checkIcon : copyIcon"
              alt=""
              class="h-4 w-4"
            >
          </ElButton>
          <ElButton
            v-if="canDownload"
            text
            title="导出 docx"
            :loading="isExporting"
            style="color: #909399; padding: 4px"
            @click="handleDownload"
          >
            <img :src="downloadIcon" alt="" class="h-4 w-4">
          </ElButton>
        </div>
      </div>
    </template>

    <!-- 加载状态 -->
    <ChatLoading v-if="isLoading" />

    <!-- 中止提示 -->
    <div
      v-if="isAborted"
      class="my-4 text-slate-500 text-sm bg-slate-100 rounded-lg py-2 px-4 inline-block"
    >
      回答已结束
    </div>
  </div>
</template>

<style scoped lang="less">
.tool-call {
  width: 100%;
  margin-bottom: 10px;
  padding: 2px 8px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fafafa;
  box-sizing: border-box;
}

.tool-call:deep(button) {
  min-height: 30px;
  padding: 4px 0;
  font-size: 12px;
  line-height: 18px;
  font-weight: 600;
  color: #4b5563;
}

.tool-call:deep(button span:first-child) {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-call:deep(button img) {
  width: 14px;
  height: 14px;
  opacity: 0.62;
}

.tool-call:deep(.mt-3) {
  margin-top: 4px;
}

.tool-call__section + .tool-call__section {
  margin-top: 8px;
}

.tool-call__label {
  margin-bottom: 4px;
  color: #8a9099;
  font-size: 11px;
  line-height: 16px;
  font-weight: 600;
}

.tool-call__json {
  max-height: 220px;
  overflow: auto;
  border-radius: 6px;
  background: #f4f6f8;
  padding: 6px 8px;
}

.tool-call__json:deep(.vjs-tree) {
  font-size: 12px;
  line-height: 1.55;
}

.tool-call__pending {
  padding: 2px 0 6px;
  color: #8a9099;
  font-size: 12px;
}
</style>
