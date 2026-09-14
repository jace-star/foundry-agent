<script setup lang="ts">
import type { ConversationSummary } from "@/service/modules/conversation";
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, ref, watch } from "vue";
import { deleteConversationById, fetchConversations } from "@/service/modules/conversation";

export interface ConversationSidebarInstance {
  commitPendingConversation: (conversationId: string) => Promise<boolean>;
  refresh: (options?: { silent?: boolean }) => Promise<void>;
}

defineOptions({ name: "ConversationSidebar" });

const props = withDefaults(
  defineProps<{
    agentKey?: string | null;
    activeConversationId?: string | null;
    pendingConversationId?: string | null;
  }>(),
  { agentKey: null, activeConversationId: null, pendingConversationId: null },
);
const emit = defineEmits<{
  newChat: [];
  selectConversation: [conversationId: string];
}>();
const conversations = ref<ConversationSummary[]>([]);
const isLoading = ref(false);
const hasMore = ref(false);
const currentPage = ref(1);
const pageSize = 50;
const collapsed = ref(false);
const listRef = ref<HTMLElement | null>(null);
const closedGroups = ref<Set<string>>(new Set());

const agentKey = computed(() => props.agentKey || "");
watch(agentKey, () => refresh(), { immediate: true });

async function refresh(options: { silent?: boolean } = {}) {
  currentPage.value = 1;
  if (!options.silent) {
    isLoading.value = true;
  }
  try {
    const res = await fetchConversations({
      agent_key: agentKey.value || "default",
      page: 1,
      page_size: pageSize,
    });
    if (options.silent) {
      conversations.value.splice(0, conversations.value.length, ...res.items);
    } else {
      conversations.value = res.items;
    }
    hasMore.value = currentPage.value * pageSize < res.total;
  } catch (e) {
    console.error("加载会话列表失败:", e);
  } finally {
    if (!options.silent) {
      isLoading.value = false;
    }
  }
}

async function commitPendingConversation(conversationId: string) {
  try {
    const res = await fetchConversations({
      agent_key: agentKey.value || "default",
      page: 1,
      page_size: pageSize,
    });
    const item = res.items.find((conversation) => conversation.id === conversationId);
    if (!item) {
      return false;
    }

    const index = conversations.value.findIndex((conversation) => conversation.id === conversationId);
    if (index !== -1) {
      conversations.value.splice(index, 1);
    }
    conversations.value.unshift(item);
    hasMore.value = currentPage.value * pageSize < res.total;
    return true;
  } catch (e) {
    console.error("更新会话标题失败:", e);
    return false;
  }
}

defineExpose<ConversationSidebarInstance>({
  commitPendingConversation,
  refresh,
});

const activeConvId = computed(() => props.activeConversationId || null);
const visibleConversations = computed(() => {
  const pendingId = props.pendingConversationId;
  const items = conversations.value.slice();

  if (!pendingId) {
    return items;
  }

  const pendingItem: ConversationSummary = {
    id: pendingId,
    title: "新对话",
    last_active_at: new Date().toISOString(),
  };
  const index = items.findIndex((item) => item.id === pendingId);
  const item = index === -1
    ? pendingItem
    : { ...items.splice(index, 1)[0], title: pendingItem.title };
  items.unshift(item);
  return items;
});

function toggleCollapse() {
  collapsed.value = !collapsed.value;
}
function toggleGroup(label: string) {
  if (closedGroups.value.has(label)) {
    closedGroups.value.delete(label);
  } else {
    closedGroups.value.add(label);
  }
}

function selectConv(item: ConversationSummary) {
  const currentId = activeConvId.value;
  if (currentId === item.id) {
    return;
  }
  emit("selectConversation", item.id);
}
function handleNewChat() {
  if (!activeConvId.value) {
    return;
  }
  emit("newChat");
}

async function handleDelete(id: string, title: string) {
  try {
    await ElMessageBox.confirm(`确定要删除「${title || "未命名"}」吗？`, "删除", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  try {
    await deleteConversationById(id);
    conversations.value = conversations.value.filter((item) => item.id !== id);
    ElMessage.success("已删除");
  } catch {
    ElMessage.error("删除失败");
  }
}

async function handleScroll() {
  const el = listRef.value;
  if (!el || !hasMore.value || isLoading.value) {
    return;
  }
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 60) {
    if (isLoading.value) {
      return;
    }
    isLoading.value = true;
    try {
      const next = currentPage.value + 1;
      const res = await fetchConversations({
        agent_key: agentKey.value || "default",
        page: next,
        page_size: pageSize,
      });
      conversations.value.push(...res.items);
      currentPage.value = next;
      hasMore.value = currentPage.value * pageSize < res.total;
    } catch (e) {
      console.error("加载更多失败:", e);
    } finally {
      isLoading.value = false;
    }
  }
}

// ── 客户端时间分组 ────────────────────────────────────

const NOW = Date.now();
const DAY_MS = 86400_000;

interface Group {
  label: string;
  match: (ts: number) => boolean;
}

const groups: Group[] = [
  { label: "今天", match: (t) => t > NOW - DAY_MS },
  { label: "昨天", match: (t) => t > NOW - 2 * DAY_MS && t <= NOW - DAY_MS },
  { label: "3天内", match: (t) => t > NOW - 3 * DAY_MS && t <= NOW - 2 * DAY_MS },
  { label: "7天内", match: (t) => t > NOW - 7 * DAY_MS && t <= NOW - 3 * DAY_MS },
  { label: "30天内", match: (t) => t > NOW - 30 * DAY_MS && t <= NOW - 7 * DAY_MS },
  { label: "更早", match: (t) => t <= NOW - 30 * DAY_MS },
];

const grouped = computed(() => {
  const result: { label: string; items: ConversationSummary[] }[] = [];
  for (const g of groups) {
    const items = visibleConversations.value.filter((c) => {
      const ts = new Date(c.last_active_at).getTime();
      return g.match(ts);
    });
    if (items.length > 0) {
      result.push({ label: g.label, items });
    }
  }
  return result;
});

function fmtTitle(t: string) {
  return t || "未命名会话";
}
</script>

<template>
  <aside class="conv-sidebar" :class="{ collapsed }">
    <button class="cs-toggle" :title="collapsed ? '展开' : '折叠'" @click="toggleCollapse">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path v-if="!collapsed" d="M10 4L6 8l4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        <path v-else d="M6 4l4 4-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
      </svg>
    </button>

    <div v-show="!collapsed" class="cs-body">
      <button class="cs-new-btn" :class="{ active: activeConvId === null }" @click="handleNewChat">
        <span>+</span> 新会话
      </button>

      <div ref="listRef" class="cs-list" @scroll="handleScroll">
        <div v-if="isLoading" class="cs-hint">
          加载中...
        </div>
        <div v-else-if="grouped.length === 0" class="cs-hint">
          暂无记录
        </div>

        <template v-for="g in grouped" :key="g.label">
          <div class="cs-group-header" @click="toggleGroup(g.label)">
            <span>{{ g.label }}</span>
            <svg
              width="12" height="12" viewBox="0 0 12 12" fill="none"
              :class="{ rotated: !closedGroups.has(g.label) }"
            ><path d="M4 2.5L8 6l-4 3.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" /></svg>
          </div>
          <div v-show="!closedGroups.has(g.label)">
            <div
              v-for="item in g.items" :key="item.id"
              class="cs-item" :class="{ active: item.id === activeConvId }"
              @click="selectConv(item)"
            >
              <span class="cs-title">{{ fmtTitle(item.title) }}</span>
              <button class="cs-del" title="删除" @click.stop="handleDelete(item.id, item.title)">
                <svg width="14" height="14" viewBox="0 0 14 14"><path d="M4 4.5L10 9.5M10 4.5L4 9.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" /></svg>
              </button>
            </div>
          </div>
        </template>
      </div>
    </div>

    <div v-if="collapsed" class="cs-collapsed-icons">
      <button class="cs-new-btn icon-only" :class="{ active: activeConvId === null }" title="新会话" @click="handleNewChat">
        +
      </button>
    </div>
  </aside>
</template>

<style scoped lang="less">
.conv-sidebar {
  --w: 260px; width: var(--w); flex: 0 0 var(--w);
  background: #fafbfc; border-right: 1px solid #e8ecf0;
  display: flex; flex-direction: column; position: relative;
  transition: width .2s, flex-basis .2s;
  &.collapsed { --w: 48px; }
}
.cs-toggle {
  position: absolute; top: 12px; right: -14px; z-index: 2;
  width: 24px; height: 24px; border-radius: 12px;
  border: 1px solid #dce1e6; background: #fff; color: #64748b;
  display: flex; align-items: center; justify-content: center; cursor: pointer;
  &:hover { background: #f1f5f9; color: #334155; }
}
.cs-body { display: flex; flex-direction: column; height: 100%; padding: 16px 12px 12px; overflow: hidden; }
.cs-new-btn {
  display: flex; align-items: center; justify-content: center; gap: 4px;
  padding: 8px 0; margin-bottom: 12px;
  border: 1px solid #117c68; border-radius: 8px;
  background: #fff; color: #117c68; font-size: 13px; font-weight: 600; cursor: pointer;
  transition: all .15s;
  &:hover { background: #e0f5ed; }
  &.active { background: #e0f5ed; box-shadow: inset 0 0 0 1px rgba(17,124,104,.18); }
  &.icon-only { width: 32px; height: 32px; margin: 8px auto; padding: 0; font-size: 18px; }
}
.cs-list { flex: 1; overflow-y: auto; }
.cs-hint { font-size: 12px; color: #94a3b8; text-align: center; padding: 24px 0; }

.cs-group-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 8px 4px; font-size: 11px; font-weight: 650; color: #8ba398;
  cursor: pointer; user-select: none;
  svg { transition: transform .15s; }
  svg.rotated { transform: rotate(90deg); }
}
.cs-item {
  display: flex; align-items: center; padding: 7px 10px; border-radius: 8px;
  cursor: pointer; transition: background .1s; gap: 6px;
  &:hover { background: #f1f5f9; }
  &.active { background: #e0f5ed; .cs-title { color: #117c68; font-weight: 600; } }
}
.cs-title {
  flex: 1; font-size: 13px; color: #334155;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.cs-del {
  opacity: 0; flex: 0 0 auto; width: 24px; height: 24px;
  border: none; background: transparent; color: #94a3b8; cursor: pointer; border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  transition: opacity .1s, color .1s;
  &:hover { color: #e53e3e; background: #fde8e8; }
}
.cs-item:hover .cs-del { opacity: 1; }
.cs-collapsed-icons {
  display: flex; flex-direction: column; align-items: center; padding-top: 52px; gap: 12px;
}
</style>
