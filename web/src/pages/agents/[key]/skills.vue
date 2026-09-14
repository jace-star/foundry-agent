<route lang="yaml">
meta:
  title: 关联技能
</route>

<script setup lang="ts">
import type { ComputedRef, Ref } from "vue";
import type { AgentConfig, SkillConfig } from "@/service";
import { Delete, Plus } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { MdEditor } from "md-editor-v3";
import { computed, inject, ref, watch } from "vue";
import { createSkill, deleteSkill, getMCPServerInfo, getSkill, listSkills, updateSkill } from "@/service";
import "md-editor-v3/lib/style.css";

const agent = inject<Ref<AgentConfig | null>>("agent")!;
const agentKey = inject<ComputedRef<string>>("agentKey")!;
const hasUnsavedChanges = inject<Ref<boolean>>("hasUnsavedChanges")!;

interface ToolOption {
  name: string;
  server: string;
  label: string;
}

const skills = ref<SkillConfig[]>([]);
const selectedName = ref("");
const loading = ref(false);
const saving = ref(false);
const addDialogVisible = ref(false);
const newSkillName = ref("");
const availableTools = ref<ToolOption[]>([]);

const selectedSkill = computed(() => skills.value.find((s) => s.name === selectedName.value) ?? null);

const editForm = ref({
  description: "",
  system_prompt: "",
  allowed_tools: "*",
});
const hasChanges = ref(false);

watch(hasChanges, (val) => {
  hasUnsavedChanges.value = val;
});

// 加载 Agent 关联的 MCP 服务的工具列表
async function loadTools() {
  const toolServers = agent.value?.tool_servers ?? [];
  if (!toolServers.length) {
    availableTools.value = [];
    return;
  }
  const tools: ToolOption[] = [];
  for (const serverName of toolServers) {
    try {
      const info = await getMCPServerInfo(serverName);
      for (const tool of info.tools) {
        tools.push({
          name: tool.name,
          server: serverName,
          label: `${serverName} / ${tool.name}`,
        });
      }
    } catch {
      // skip
    }
  }
  availableTools.value = tools;
}

watch(agent, (val) => {
  if (val) {
    void refreshSkills();
    void loadTools();
  }
}, { immediate: true });

async function refreshSkills() {
  loading.value = true;
  try {
    const summaries = await listSkills(agentKey.value);
    const full: SkillConfig[] = [];
    for (const s of summaries) {
      try {
        full.push(await getSkill(agentKey.value, s.name));
      } catch {
        // skip
      }
    }
    skills.value = full;
    if (!skills.value.some((s) => s.name === selectedName.value)) {
      selectedName.value = skills.value[0]?.name ?? "";
    }
  } catch {
    // ignore
  } finally {
    loading.value = false;
  }
}

watch(selectedSkill, (val) => {
  if (val) {
    editForm.value = {
      description: val.description,
      system_prompt: val.system_prompt,
      allowed_tools: val.allowed_tools,
    };
    hasChanges.value = false;
  }
}, { immediate: true });

function markChanged() {
  if (!selectedSkill.value) {
    return;
  }
  const orig = selectedSkill.value;
  const changed = editForm.value.description !== orig.description
    || editForm.value.system_prompt !== orig.system_prompt
    || editForm.value.allowed_tools !== orig.allowed_tools;
  hasChanges.value = changed;
}

watch(() => editForm.value.description, markChanged);
watch(() => editForm.value.system_prompt, markChanged);
watch(() => editForm.value.allowed_tools, markChanged);

async function handleSave() {
  if (!selectedSkill.value) {
    return;
  }
  saving.value = true;
  try {
    await updateSkill(agentKey.value, selectedSkill.value.name, {
      description: editForm.value.description,
      system_prompt: editForm.value.system_prompt,
      allowed_tools: editForm.value.allowed_tools,
    });
    await refreshSkills();
    hasChanges.value = false;
    ElMessage.success("已保存");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存失败");
  } finally {
    saving.value = false;
  }
}

async function handleAdd() {
  const name = newSkillName.value.trim();
  if (!name) {
    ElMessage.warning("请输入技能标识");
    return;
  }
  if (skills.value.some((s) => s.name === name)) {
    ElMessage.warning("标识已存在");
    return;
  }

  saving.value = true;
  try {
    await createSkill(agentKey.value, { name });
    addDialogVisible.value = false;
    newSkillName.value = "";
    await refreshSkills();
    selectedName.value = name;
    ElMessage.success("技能已创建");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "创建失败");
  } finally {
    saving.value = false;
  }
}

async function handleDelete(name: string) {
  try {
    await ElMessageBox.confirm(`删除技能「${name}」？`, "删除技能", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }

  try {
    await deleteSkill(agentKey.value, name);
    if (selectedName.value === name) {
      selectedName.value = "";
    }
    await refreshSkills();
    ElMessage.success("技能已删除");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "删除失败");
  }
}

function openAddDialog() {
  newSkillName.value = "";
  addDialogVisible.value = true;
}
</script>

<template>
  <div class="skills-container">
    <div class="skills-layout">
      <!-- 左侧技能列表 -->
      <div v-loading="loading" class="skills-sidebar">
        <div class="skills-sidebar-header">
          <span class="font-600 text-xs color-#303133">技能列表</span>
          <el-button text type="primary" size="small" :icon="Plus" @click="openAddDialog" />
        </div>
        <div class="skills-name-list">
          <div
            v-for="skill in skills"
            :key="skill.name"
            class="skill-name-item"
            :class="{ active: skill.name === selectedName }"
            @click="selectedName = skill.name"
          >
            <span class="skill-name-text">{{ skill.name }}</span>
            <el-button
              text
              type="danger"
              size="small"
              :icon="Delete"
              @click.stop="handleDelete(skill.name)"
            />
          </div>
          <el-empty v-if="!skills.length && !loading" description="暂无技能" :image-size="48" />
        </div>
      </div>

      <!-- 右侧编辑区 -->
      <div class="skills-editor">
        <el-empty v-if="!selectedSkill" description="选择左侧技能进行编辑" :image-size="64" />
        <el-card v-else shadow="never" class="h-full rounded-xl flex flex-col overflow-hidden">
          <template #header>
            <div class="flex justify-between items-center">
              <span class="font-600 text-sm color-#303133">{{ selectedName }}</span>
              <el-button type="primary" size="small" :loading="saving" :disabled="!hasChanges" @click="handleSave">
                保存
              </el-button>
            </div>
          </template>
          <el-form label-position="top" class="flex flex-col flex-1 overflow-hidden">
            <el-form-item>
              <el-input v-model="editForm.description" placeholder="描述该技能的用途，用于 LLM 判断是否激活" type="textarea" :rows="2" />
            </el-form-item>
            <el-form-item>
              <el-select
                v-model="editForm.allowed_tools"
                class="w-full"
                clearable
                placeholder="选择允许使用的工具"
              >
                <el-option label="全部工具" value="*" />
                <el-option
                  v-for="tool in availableTools"
                  :key="tool.name"
                  :label="tool.label"
                  :value="tool.name"
                />
              </el-select>
            </el-form-item>
            <el-form-item class="flex-1 overflow-hidden prompt-item">
              <MdEditor
                v-model="editForm.system_prompt"
                :preview="true"
                :toolbars-exclude="['github', 'mermaid', 'save']"
                style="height: 100%"
                placeholder="技能激活后注入的提示词"
              />
            </el-form-item>
          </el-form>
        </el-card>
      </div>
    </div>

    <!-- 新增弹窗 -->
    <el-dialog v-model="addDialogVisible" width="400px" title="新增技能" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="标识" required>
          <el-input v-model="newSkillName" placeholder="如 translate" maxlength="64" />
          <div class="text-xs color-#909399 mt-1">
            只允许字母、数字、下划线和连字符
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">
          取消
        </el-button>
        <el-button type="primary" :loading="saving" @click="handleAdd">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="less">
.skills-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.skills-layout {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 12px;
}

.skills-sidebar {
  width: 146px;
  flex: 0 0 146px;
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(22, 32, 27, 0.12);
  border-radius: 8px;
  background: #fffdfa;
  overflow: hidden;
}

.skills-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(22, 32, 27, 0.08);
}

.skills-name-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

.skill-name-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.16s ease;
}

.skill-name-item:hover {
  background: #effaf6;
}

.skill-name-item.active {
  background: #effaf6;
  box-shadow: inset 3px 0 0 #117c68;
}

.skill-name-text {
  font-size: 14px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.skills-editor {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

:deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 12px;
}

:deep(.skills-editor .el-form-item) {
  margin-bottom: 8px;
}

.prompt-item {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  margin-bottom: 0;
}

:deep(.prompt-item .el-form-item__content) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

:deep(.prompt-item .md-editor-footer) {
  align-items: center;
  line-height: 1;
}

:deep(.prompt-item .md-editor-footer-item) {
  line-height: 1;
}
</style>
