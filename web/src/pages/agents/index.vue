<route lang="yaml">
meta:
  title: 智能体
  fullPage: true
</route>

<script setup lang="ts">
import type { AgentSummary } from "@/service";
import { Delete, Plus, Refresh } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { deleteAgent, listAgents } from "@/service";

const router = useRouter();
const agents = ref<AgentSummary[]>([]);
const loading = ref(false);
const deleting = ref("");

onMounted(() => {
  void refresh();
});

async function refresh() {
  loading.value = true;
  try {
    agents.value = await listAgents();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载失败");
  } finally {
    loading.value = false;
  }
}

function goCreate() {
  router.push("/agents/create");
}

function goDetail(key: string) {
  router.push(`/agents/${key}`);
}

async function handleDelete(key: string, name: string) {
  try {
    await ElMessageBox.confirm(`确定删除「${name}」？`, "删除智能体", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  deleting.value = key;
  try {
    await deleteAgent(key);
    await refresh();
    ElMessage.success("已删除");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "删除失败");
  } finally {
    deleting.value = "";
  }
}

function formatTime(ts: string) {
  return ts ? new Date(ts).toLocaleString("zh-CN") : "-";
}
</script>

<template>
  <div class="h-full overflow-y-auto px-6 py-8">
    <header class="flex items-center justify-between mb-7">
      <h1 class="m-0 text-2xl font-700 color-#1a1a1a">
        智能体
      </h1>
      <div class="flex gap-2">
        <el-button :icon="Refresh" circle :loading="loading" @click="refresh" />
        <el-button type="primary" :icon="Plus" @click="goCreate">
          创建智能体
        </el-button>
      </div>
    </header>

    <div v-loading="loading" class="grid gap-4" style="grid-template-columns: repeat(auto-fill, minmax(260px, 1fr))">
      <article
        v-for="agent in agents"
        :key="agent.key"
        class="relative p-5 bg-white border border-#e8e8e8 rounded-xl cursor-pointer transition-all hover:border-#c0c4cc hover:shadow-lg agent-card"
        @click="goDetail(agent.key)"
      >
        <div class="flex justify-between items-start mb-3">
          <div class="flex gap-3 min-w-0 flex-1">
            <div class="w-10 h-10 rounded-lg bg-gradient-to-br from-#117c68 to-#409eff text-white text-lg font-700 flex items-center justify-center shrink-0">
              {{ agent.name.charAt(0) }}
            </div>
            <div class="min-w-0 flex-1">
              <h3 class="m-0 mb-0.5 text-sm font-600 color-#303133">
                {{ agent.name }}
              </h3>
              <span class="inline-block text-xs color-#909399 font-mono">{{ agent.key }}</span>
            </div>
          </div>
          <el-button
            class="opacity-0 transition-opacity shrink-0"
            text
            type="danger"
            size="small"
            :icon="Delete"
            :loading="deleting === agent.key"
            @click.stop="handleDelete(agent.key, agent.name)"
          />
        </div>
        <div class="flex justify-between items-end">
          <div class="flex flex-wrap gap-1">
            <el-tag
              v-for="s in agent.tool_servers"
              :key="s"
              size="small"
              type="info"
              disable-transitions
            >
              {{ s }}
            </el-tag>
          </div>
          <span class="text-11px color-#c0c4cc shrink-0">{{ formatTime(agent.updated_at) }}</span>
        </div>
      </article>

      <article
        class="flex flex-col items-center justify-center gap-2 min-h-160px color-#909399 border-dashed rounded-xl cursor-pointer transition-all hover:color-#409eff hover:border-#409eff p-5 bg-white border border-#e8e8e8"
        @click="goCreate"
      >
        <el-icon :size="32">
          <Plus />
        </el-icon>
        <span>创建智能体</span>
      </article>
    </div>
  </div>
</template>

<style scoped>
.agent-card:hover .el-button {
  opacity: 1;
}
</style>
