<route lang="yaml">
meta:
  title: 基本信息
</route>

<script setup lang="ts">
import type { ComputedRef, Ref } from "vue";
import type { AgentConfig } from "@/service";
import { ElMessage } from "element-plus";
import { inject, reactive, ref, watch } from "vue";
import { updateAgent } from "@/service";

const agent = inject<Ref<AgentConfig | null>>("agent")!;
const agentKey = inject<ComputedRef<string>>("agentKey")!;
const reloadAgent = inject<() => Promise<void>>("reloadAgent")!;
const hasUnsavedChanges = inject<Ref<boolean>>("hasUnsavedChanges")!;

const saving = ref(false);
const hasChanges = ref(false);

watch(hasChanges, (val) => {
  hasUnsavedChanges.value = val;
});

const form = reactive({
  name: "",
  description: "",
});

watch(
  agent,
  (val) => {
    if (val) {
      form.name = val.name;
      form.description = val.description;
      hasChanges.value = false;
    }
  },
  { immediate: true },
);

function markChanged() {
  if (!agent.value) {
    return;
  }
  hasChanges.value = form.name !== agent.value.name || form.description !== agent.value.description;
}

watch(() => [form.name, form.description], markChanged, { deep: true });

async function handleSave() {
  if (!form.name.trim()) {
    ElMessage.warning("请输入名称");
    return;
  }
  saving.value = true;
  try {
    await updateAgent(agentKey.value, {
      name: form.name.trim(),
      description: form.description.trim(),
    });
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
          <span class="font-600 text-sm color-#303133">基本信息</span>
          <el-button type="primary" size="small" :loading="saving" :disabled="!hasChanges" @click="handleSave">
            保存
          </el-button>
        </div>
      </template>
      <el-form-item label="标识">
        <el-input :model-value="agent.key" disabled />
      </el-form-item>
      <el-form-item label="名称" required>
        <el-input v-model="form.name" maxlength="128" show-word-limit />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="3" placeholder="简要描述智能体的用途" />
      </el-form-item>
      <el-form-item label="创建时间">
        <el-input :model-value="new Date(agent.created_at).toLocaleString('zh-CN')" disabled />
      </el-form-item>
      <el-form-item label="修改时间">
        <el-input :model-value="new Date(agent.updated_at).toLocaleString('zh-CN')" disabled />
      </el-form-item>
    </el-card>
  </el-form>
</template>
