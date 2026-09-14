<route lang="yaml">
meta:
  title: 智能体配置
  fullPage: true
</route>

<script setup lang="ts">
import type { AgentConfig, MCPServerConfig } from "@/service";
import { ArrowLeft, Refresh } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, onMounted, provide, ref } from "vue";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import { getAgent, listMCPServers } from "@/service";

const route = useRoute();
const router = useRouter();
const agentKey = computed(() => String((route.params as { key: string }).key));

const agent = ref<AgentConfig | null>(null);
const loading = ref(false);
const availableServers = ref<MCPServerConfig[]>([]);
const hasUnsavedChanges = ref(false);

async function loadAgent() {
  loading.value = true;
  try {
    agent.value = await getAgent(agentKey.value);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载失败");
    router.replace("/agents");
  } finally {
    loading.value = false;
  }
}

async function loadServers() {
  try {
    availableServers.value = await listMCPServers();
  } catch {
    // ignore
  }
}

function handleRefresh() {
  void loadAgent();
}

onMounted(() => {
  void loadAgent();
  void loadServers();
});

provide("agentKey", agentKey);
provide("agent", agent);
provide("availableServers", availableServers);
provide("reloadAgent", loadAgent);
provide("hasUnsavedChanges", hasUnsavedChanges);

onBeforeRouteLeave(async (_to, _from, next) => {
  if (!hasUnsavedChanges.value) {
    next();
    return;
  }
  try {
    await ElMessageBox.confirm("当前有未保存的修改，确定离开吗？", "未保存的更改", {
      confirmButtonText: "离开",
      cancelButtonText: "取消",
      type: "warning",
    });
    next();
  } catch {
    next(false);
  }
});

const tabs = [
  { label: "基本信息", route: `/agents/${agentKey.value}` },
  { label: "工具服务", route: `/agents/${agentKey.value}/tools` },
  { label: "系统提示词", route: `/agents/${agentKey.value}/prompt` },
  { label: "技能", route: `/agents/${agentKey.value}/skills` },
];

async function handleBeforeTabLeave(_activeName: string, oldActiveName: string): Promise<boolean> {
  // 如果目标和当前一样，允许
  if (_activeName === oldActiveName) {
    return true;
  }
  if (hasUnsavedChanges.value) {
    try {
      await ElMessageBox.confirm("当前有未保存的修改，确定切换吗？", "未保存的更改", {
        confirmButtonText: "切换",
        cancelButtonText: "取消",
        type: "warning",
      });
    } catch {
      return false;
    }
  }
  hasUnsavedChanges.value = false;
  return true;
}

async function handleTabChange(path: string) {
  await router.push(path);
}
</script>

<template>
  <div v-loading="loading" class="h-full flex flex-col overflow-hidden px-5 pt-4 pb-4 max-md:(px-3 pt-3 pb-3)">
    <header class="flex justify-between items-center gap-3 mb-4 max-md:flex-wrap">
      <div class="flex items-center gap-3 min-w-0">
        <el-button :icon="ArrowLeft" text @click="router.push('/agents')">
          返回
        </el-button>
        <h1 class="m-0 text-xl font-600 color-#1a1a1a whitespace-nowrap overflow-hidden text-ellipsis max-md:text-base">
          {{ agent?.name || "智能体" }}
        </h1>
      </div>
      <el-button :icon="Refresh" circle @click="handleRefresh" />
    </header>

    <nav v-if="agent" class="agent-tabs">
      <el-tabs :model-value="route.path" :before-leave="handleBeforeTabLeave" @tab-change="handleTabChange">
        <el-tab-pane
          v-for="tab in tabs"
          :key="tab.route"
          :label="tab.label"
          :name="tab.route"
        />
      </el-tabs>
    </nav>

    <div v-if="agent" class="flex-1 overflow-hidden">
      <RouterView />
    </div>
  </div>
</template>

<style scoped>
.agent-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}
</style>
