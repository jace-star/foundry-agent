<route lang="yaml">
meta:
  title: 工具服务
</route>

<script setup lang="ts">
import type { ComputedRef, Ref } from "vue";
import type { AgentConfig, MCPServerConfig } from "@/service";
import { ElMessage } from "element-plus";
import { inject, reactive, ref, watch } from "vue";
import { updateAgent } from "@/service";

const agent = inject<Ref<AgentConfig | null>>("agent")!;
const agentKey = inject<ComputedRef<string>>("agentKey")!;
const availableServers = inject<Ref<MCPServerConfig[]>>("availableServers")!;
const reloadAgent = inject<() => Promise<void>>("reloadAgent")!;
const hasUnsavedChanges = inject<Ref<boolean>>("hasUnsavedChanges")!;

const saving = ref(false);
const hasChanges = ref(false);

watch(hasChanges, (val) => {
  hasUnsavedChanges.value = val;
});

const form = reactive({
  tool_servers: [] as string[],
});

watch(
  agent,
  (val) => {
    if (val) {
      form.tool_servers = [...val.tool_servers];
      hasChanges.value = false;
    }
  },
  { immediate: true },
);

function markChanged() {
  if (!agent.value) {
    return;
  }
  hasChanges.value = JSON.stringify(form.tool_servers) !== JSON.stringify(agent.value.tool_servers);
}

watch(() => form.tool_servers, markChanged, { deep: true });

async function handleSave() {
  saving.value = true;
  try {
    await updateAgent(agentKey.value, { tool_servers: form.tool_servers });
    await reloadAgent();
    hasChanges.value = false;
    ElMessage.success("已保存");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存失败");
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <el-form v-if="agent" :model="form" label-width="100px">
    <el-card shadow="never" class="mb-4 rounded-xl">
      <template #header>
        <div class="flex justify-between items-center">
          <span class="font-600 text-sm color-#303133">工具服务</span>
          <el-button type="primary" size="small" :loading="saving" :disabled="!hasChanges" @click="handleSave">
            保存
          </el-button>
        </div>
      </template>
      <el-form-item label="关联服务">
        <el-select
          v-model="form.tool_servers"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="选择要关联的 MCP 工具服务"
          class="w-full"
        >
          <el-option
            v-for="server in availableServers"
            :key="server.name"
            :label="server.name"
            :value="server.name"
          />
        </el-select>
        <div class="text-xs color-#909399 mt-1">
          关联后智能体可以调用这些服务提供的工具
        </div>
      </el-form-item>
    </el-card>
  </el-form>
</template>
