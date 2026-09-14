<route lang="yaml">
meta:
  title: 系统提示词
</route>

<script setup lang="ts">
import type { ComputedRef, Ref } from "vue";
import type { AgentConfig } from "@/service";
import { ElMessage } from "element-plus";
import { MdEditor } from "md-editor-v3";
import { inject, reactive, ref, watch } from "vue";
import { updateAgent } from "@/service";
import "md-editor-v3/lib/style.css";

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
  system_prompt: "",
});

watch(
  agent,
  (val) => {
    if (val) {
      form.system_prompt = val.system_prompt;
      hasChanges.value = false;
    }
  },
  { immediate: true },
);

function markChanged() {
  if (!agent.value) {
    return;
  }
  hasChanges.value = form.system_prompt !== agent.value.system_prompt;
}

watch(() => form.system_prompt, markChanged);

async function handleSave() {
  saving.value = true;
  try {
    await updateAgent(agentKey.value, { system_prompt: form.system_prompt });
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
  <el-card v-if="agent" shadow="never" class="h-full rounded-xl flex flex-col overflow-hidden">
    <template #header>
      <div class="flex justify-between items-center">
        <span class="font-600 text-sm color-#303133">系统提示词</span>
        <el-button type="primary" size="small" :loading="saving" :disabled="!hasChanges" @click="handleSave">
          保存
        </el-button>
      </div>
    </template>
    <MdEditor
      v-model="form.system_prompt"
      class="system-prompt-editor"
      :preview="true"
      :toolbars-exclude="['github', 'mermaid', 'save']"
      height="100%"
      placeholder="定义智能体的角色、能力、行为规则..."
    />
  </el-card>
</template>

<style scoped>
:deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 12px;
}

:deep(.system-prompt-editor) {
  flex: 1;
  min-height: 0;
  width: 100%;
}
</style>
