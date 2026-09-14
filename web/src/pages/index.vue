<route lang="yaml">
meta:
  title: 首页
  fullPage: true
</route>

<script setup lang="ts">
import type { ChatFrameInstance } from "@/components/chat/chat-frame.vue";
import type { ConversationSidebarInstance } from "@/components/conversation-sidebar.vue";
import type { ChatRequestFunction, ChatStreamEvent } from "@/composables/chat-type";
import type { AgentSummary } from "@/service";
import { ElMessage } from "element-plus";
import { computed, onMounted, ref, watch } from "vue";
import ChatFrame from "@/components/chat/chat-frame.vue";
import ConversationSidebar from "@/components/conversation-sidebar.vue";
import { Chat, convertDoc, fetchConversationDetail, listAgents, setAgentHome, unsetAgentHome } from "@/service";

// Agent 选择
const agents = ref<AgentSummary[]>([]);
const selectedAgentKey = ref<string | null>(null);
const agentsLoading = ref(false);
const configReady = ref(false);
const sidebarRef = ref<ConversationSidebarInstance | null>(null);
const chatFrameRef = ref<ChatFrameInstance | null>(null);
const currentConversationId = ref<string | null>(null);
const pendingConversationId = ref<string | null>(null);
const historyHasMore = ref(false);
const historyBeforeId = ref<number | null>(null);
const historyLoading = ref(false);
const selectedAgent = computed(() => agents.value.find((agent) => agent.key === selectedAgentKey.value) ?? null);
const agentSelectPlaceholder = computed(() => {
  if (agentsLoading.value) {
    return "加载中";
  }
  return agents.value.length > 0 ? "请选择智能体" : "暂无智能体";
});

function agentInitial(agent: AgentSummary | null) {
  const name = agent?.name?.trim() || agent?.key?.trim() || "";
  return Array.from(name).at(0)?.toUpperCase() || "A";
}

watch(selectedAgentKey, async (key) => {
  if (!key) {
    configReady.value = true;
  } else {
    // agent 配置由后端加载，前端只需传递 agent_key
    configReady.value = true;
  }
  // 配置加载完成后再保存，避免初始化时覆盖
  if (configReady.value) {
    try {
      if (key) {
        await setAgentHome(key);
      } else {
        // 取消当前 home
        const prev = agents.value.find((a) => a.is_home);
        if (prev) {
          await unsetAgentHome(prev.key);
        }
      }
    } catch {
      // ignore
    }
  }
});

onMounted(async () => {
  agentsLoading.value = true;
  try {
    agents.value = await listAgents();
    const home = agents.value.find((a) => a.is_home);
    if (home) {
      selectedAgentKey.value = home.key;
    }
  } catch {
    // ignore
  } finally {
    agentsLoading.value = false;
    configReady.value = true;
  }
});

// 文档相关
const pendingDocumentMarkdown = ref("");
const pendingDocumentName = ref("");
const sessionDocumentId = ref("");

function clearPendingDoc() {
  pendingDocumentMarkdown.value = "";
  pendingDocumentName.value = "";
}

function clearSessionDocument() {
  sessionDocumentId.value = "";
}

async function handleDocChange(file: File | null) {
  if (!file) {
    clearPendingDoc();
    clearSessionDocument();
    return;
  }
  try {
    const result = await convertDoc(file);
    pendingDocumentMarkdown.value = result.markdown;
    pendingDocumentName.value = result.meta.filename || file.name;
    if (result.meta.document_id) {
      sessionDocumentId.value = result.meta.document_id;
    } else {
      clearSessionDocument();
    }
  } catch (error) {
    clearPendingDoc();
    clearSessionDocument();
    const message = error instanceof Error ? error.message : "文档转换失败";
    ElMessage.error(message);
  }
}

function buildChatPrompt(question: string) {
  if (pendingDocumentName.value && pendingDocumentMarkdown.value) {
    const prompt = [
      `用户问题：${question}`,
      `文档名称：${pendingDocumentName.value}`,
      "文档内容：",
      pendingDocumentMarkdown.value,
    ].join("\n");
    clearPendingDoc();
    return prompt;
  }

  clearPendingDoc();
  return question;
}

const chatFunction: ChatRequestFunction = (
  message: string,
  signal: AbortSignal,
  conversationId?: string | null,
): AsyncGenerator<ChatStreamEvent> => {
  const prompt = buildChatPrompt(message);

  return Chat(
    {
      message: prompt,
      agent_key: selectedAgentKey.value!,
      conversation_id: conversationId,
      stateful: true,
    },
    signal,
  );
};

function silentReplace(path: string) {
  window.history.replaceState(window.history.state, "", path);
}

function silentPush(path: string) {
  window.history.pushState(window.history.state, "", path);
}

async function loadConversationHistory(conversationId: string, beforeId?: number | null, append = false) {
  historyLoading.value = true;
  try {
    const { events, history } = await fetchConversationDetail(conversationId, 10, beforeId);
    historyHasMore.value = history.has_more;
    historyBeforeId.value = history.before_id;
    if (append) {
      chatFrameRef.value?.prependHistoryMessages(events);
      return;
    }
    chatFrameRef.value?.loadHistoryMessages(events);
  } finally {
    historyLoading.value = false;
  }
}

async function handleSelectConversation(conversationId: string) {
  if (currentConversationId.value === conversationId) {
    return;
  }
  pendingConversationId.value = null;
  currentConversationId.value = conversationId;
  silentPush(`/s/${conversationId}`);
  chatFrameRef.value?.clearMessages();
  chatFrameRef.value?.setConversationId(conversationId);
  await loadConversationHistory(conversationId);
}

function handleConversationId(conversationId: string) {
  if (currentConversationId.value === conversationId) {
    return;
  }
  currentConversationId.value = conversationId;
  pendingConversationId.value = conversationId;
  silentReplace(`/s/${conversationId}`);
}

async function handleMessageComplete(conversationId: string | null) {
  if (!conversationId) {
    return;
  }
  if (pendingConversationId.value === conversationId) {
    const committed = await sidebarRef.value?.commitPendingConversation(conversationId);
    if (committed === false) {
      await sidebarRef.value?.refresh({ silent: true });
    }
    pendingConversationId.value = null;
    return;
  }
  await sidebarRef.value?.refresh({ silent: true });
}

function handleNewChat() {
  currentConversationId.value = null;
  pendingConversationId.value = null;
  historyHasMore.value = false;
  historyBeforeId.value = null;
  chatFrameRef.value?.clearMessages();
  chatFrameRef.value?.setConversationId(null);
  silentPush("/");
  clearPendingDoc();
  clearSessionDocument();
}

async function handleLoadMoreHistory() {
  if (!currentConversationId.value || !historyHasMore.value || historyBeforeId.value == null || historyLoading.value) {
    return;
  }
  await loadConversationHistory(currentConversationId.value, historyBeforeId.value, true);
}
</script>

<template>
  <div class="chat-home">
    <ConversationSidebar
      ref="sidebarRef"
      :agent-key="selectedAgentKey"
      :active-conversation-id="currentConversationId"
      :pending-conversation-id="pendingConversationId"
      @select-conversation="handleSelectConversation"
      @new-chat="handleNewChat"
    />
    <div class="chat-main">
      <div class="chat-topbar">
        <div class="agent-picker" aria-label="请选择智能体">
          <el-select
            v-model="selectedAgentKey"
            class="agent-picker__select"
            :placeholder="agentSelectPlaceholder"
            :loading="agentsLoading"
            :disabled="agentsLoading || agents.length === 0"
            clearable
            filterable
          >
            <template #prefix>
              <span v-if="selectedAgent" class="agent-picker__avatar">
                {{ agentInitial(selectedAgent) }}
              </span>
            </template>
            <el-option
              v-for="agent in agents"
              :key="agent.key"
              :label="agent.name"
              :value="agent.key"
            >
              <div class="agent-option">
                <span class="agent-option__avatar">{{ agentInitial(agent) }}</span>
                <span class="agent-option__name">{{ agent.name }}</span>
              </div>
            </el-option>
          </el-select>
        </div>
      </div>
      <ChatFrame
        ref="chatFrameRef"
        :chat="chatFunction"
        :doc-select="handleDocChange"
        :session-document-id="sessionDocumentId"
        :on-load-more-history="handleLoadMoreHistory"
        :on-conversation-id="handleConversationId"
        :on-message-complete="handleMessageComplete"
      >
        <template #empty>
          <div class="empty-state">
            <p>AI Chat</p>
            <h1>开始对话</h1>
          </div>
        </template>
      </ChatFrame>
    </div>
  </div>
</template>

<style scoped lang="less">
.chat-home {
  width: 100%; height: 100%; min-height: 0; overflow: hidden;
  display: flex;
}

.chat-main {
  flex: 1; min-width: 0; display: flex; flex-direction: column; position: relative;
  background:
    linear-gradient(135deg, rgba(17, 124, 104, 0.08), transparent 34%),
    linear-gradient(315deg, rgba(214, 95, 71, 0.1), transparent 28%),
    #fffdfa;
}

.chat-topbar {
  position: absolute;
  top: 20px;
  left: 20px;
  z-index: 10;
  width: clamp(128px, 11vw, 165px);
  max-width: calc(100% - 40px);
}

.agent-picker {
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 4px;
  border: 1px solid rgba(17, 124, 104, 0.2);
  border-radius: 14px;
  background: rgba(255, 253, 250, 0.86);
  box-shadow:
    0 16px 40px rgba(22, 32, 27, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(16px);
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    background-color 0.18s ease;
}

.agent-picker:hover {
  border-color: rgba(17, 124, 104, 0.34);
  background: rgba(255, 253, 250, 0.94);
  box-shadow:
    0 14px 34px rgba(22, 32, 27, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.82);
}

.agent-picker__select {
  flex: 1 1 auto;
  min-width: 0;
}

.agent-picker__select:deep(.el-select__wrapper) {
  min-height: 30px;
  padding: 0 8px 0 6px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: none;
  transition: background-color 0.18s ease;
}

.agent-picker__select:deep(.el-select__wrapper.is-focused) {
  box-shadow: none;
}

.agent-picker__select:deep(.el-select__wrapper:hover) {
  box-shadow: none;
  background: rgba(255, 255, 255, 0.9);
}

.agent-picker__select:deep(.el-select__placeholder) {
  color: #63706b;
  font-size: 12px;
  font-weight: 700;
}

.agent-picker__select:deep(.el-select__prefix) {
  margin-right: 4px;
}

.agent-picker__avatar,
.agent-option__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  flex: 0 0 18px;
  border-radius: 6px;
  background: #117c68;
  color: #fffdfa;
  font-size: 10px;
  font-weight: 800;
  line-height: 1;
}

.agent-picker__select:deep(.el-select__selected-item) {
  min-width: 0;
}

.agent-picker__select:deep(.el-select__selected-item span) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #26352f;
  font-size: 12px;
  font-weight: 700;
}

.agent-picker__select:deep(.el-select__wrapper.is-disabled) {
  background: rgba(255, 255, 255, 0.54);
  cursor: default;
}

.agent-picker__select:deep(.el-select__wrapper.is-disabled .el-select__placeholder) {
  color: #9aa39f;
}

.agent-option {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 7px;
}

.agent-option__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 520px) {
  .chat-topbar {
    top: 12px;
    left: 12px;
    width: min(140px, calc(100% - 24px));
    max-width: calc(100% - 24px);
  }

  .agent-picker {
    padding: 5px;
    border-radius: 12px;
  }

  .agent-picker__select {
    width: 100%;
  }
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  text-align: center;

  p {
    margin: 0 0 8px;
    color: #117c68;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h1 {
    margin: 0;
    color: #16201b;
    font-size: 32px;
    line-height: 1.12;
    font-weight: 800;
    letter-spacing: 0;
  }
}
</style>
