<route lang="yaml">
meta:
  title: 创建智能体
</route>

<script setup lang="ts">
import type { MCPServerConfig } from "@/service";
import { ArrowLeft } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { createAgent, listMCPServers } from "@/service";

const router = useRouter();
const saving = ref(false);
const availableServers = ref<MCPServerConfig[]>([]);

const form = reactive({
  key: "",
  name: "",
  description: "",
  tool_servers: [] as string[],
});

onMounted(async () => {
  try {
    availableServers.value = await listMCPServers();
  } catch {
    // ignore
  }
});

async function handleSubmit() {
  if (!form.key.trim()) {
    ElMessage.warning("请输入标识");
    return;
  }
  if (!form.name.trim()) {
    ElMessage.warning("请输入名称");
    return;
  }
  saving.value = true;
  try {
    const agent = await createAgent({
      key: form.key.trim(),
      name: form.name.trim(),
      description: form.description.trim(),
      tool_servers: form.tool_servers,
    });
    ElMessage.success("创建成功");
    router.replace(`/agents/${agent.key}`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "创建失败");
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="h-full overflow-y-auto px-6 py-8 max-md:(px-3 py-4)">
    <header class="flex items-center gap-3 mb-6 max-w-720px mx-auto">
      <el-button :icon="ArrowLeft" text @click="router.push('/agents')">
        返回列表
      </el-button>
      <h1 class="m-0 text-xl font-600 color-#1a1a1a max-md:text-base">
        创建智能体
      </h1>
    </header>

    <el-form :model="form" label-width="100px" class="max-w-720px mx-auto">
      <el-card shadow="never" class="mb-4 rounded-xl">
        <template #header>
          <span class="font-600 text-sm color-#303133">基本信息</span>
        </template>
        <el-form-item label="标识" required>
          <el-input v-model="form.key" placeholder="智能体唯一标识，如 my-agent" maxlength="64" />
          <div class="text-xs color-#909399 mt-1">
            只允许字母、数字、下划线和连字符，创建后不可修改
          </div>
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="给智能体起个名字" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="简要描述智能体的用途" type="textarea" :rows="3" />
        </el-form-item>
      </el-card>

      <el-card shadow="never" class="mb-4 rounded-xl">
        <template #header>
          <span class="font-600 text-sm color-#303133">工具服务</span>
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

      <div class="flex justify-end gap-2 pt-2">
        <el-button @click="router.push('/agents')">
          取消
        </el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">
          创建
        </el-button>
      </div>
    </el-form>
  </div>
</template>
