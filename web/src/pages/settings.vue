<script setup lang="ts">
import type { ApiKeyCreateResponse, ApiKeySummary } from "@/service/modules/api-key";
import { ElMessage, ElMessageBox } from "element-plus";

import { computed, onMounted, reactive, ref } from "vue";
import { apiKeyService } from "@/service/modules/api-key";
import { userService } from "@/service/modules/user";
import { useUserStoreWithOut } from "@/store/user";

defineOptions({ name: "SettingsPage" });

const userStore = useUserStoreWithOut();
const currentUserId = computed(() => (userStore.userInfo as any)?.id as string);

// ── 标签页 ──────────────────────────────────────────────────────────────
const activeTab = ref("users");

// ── 用户管理 ────────────────────────────────────────────────────────────

interface UserRow {
  id: string;
  account: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

const users = ref<UserRow[]>([]);
const userLoading = ref(false);

const userDialogVisible = ref(false);
const userDialogTitle = ref("创建用户");
const userForm = reactive({
  id: "",
  account: "",
  password: "",
  name: "",
  role: "user",
  is_active: true,
});
const userFormMode = ref<"create" | "edit">("create");

async function loadUsers() {
  userLoading.value = true;
  try {
    const res = await userService.listUsers();
    users.value = (res as UserRow[]) ?? [];
  } finally {
    userLoading.value = false;
  }
}

function openCreateUser() {
  userFormMode.value = "create";
  userDialogTitle.value = "创建用户";
  userForm.id = "";
  userForm.account = "";
  userForm.password = "";
  userForm.name = "";
  userForm.role = "user";
  userForm.is_active = true;
  userDialogVisible.value = true;
}

function openEditUser(row: UserRow) {
  userFormMode.value = "edit";
  userDialogTitle.value = "编辑用户";
  userForm.id = row.id;
  userForm.account = row.account;
  userForm.password = "";
  userForm.name = row.name;
  userForm.role = row.role;
  userForm.is_active = row.is_active;
  userDialogVisible.value = true;
}

async function handleUserSubmit() {
  try {
    if (userFormMode.value === "create") {
      await userService.createUser({
        account: userForm.account,
        password: userForm.password,
        name: userForm.name || undefined,
        role: userForm.role,
      });
      ElMessage.success("用户创建成功");
    } else {
      const params: Record<string, any> = {};
      if (userForm.password) {
        params.password = userForm.password;
      }
      params.name = userForm.name || undefined;
      params.role = userForm.role;
      params.is_active = userForm.is_active;
      await userService.updateUser(userForm.id, params);
      ElMessage.success("用户更新成功");
    }
    userDialogVisible.value = false;
    await loadUsers();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? "操作失败");
  }
}

async function handleDeleteUser(row: UserRow) {
  if (row.id === currentUserId.value) {
    ElMessage.warning("不能删除自己");
    return;
  }
  try {
    await ElMessageBox.confirm(`确定要删除用户「${row.account}」吗？`, "确认删除", {
      confirmButtonText: "确定删除",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  try {
    await userService.deleteUser(row.id);
    ElMessage.success("用户已删除");
    await loadUsers();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? "删除失败");
  }
}

// ── API Key 管理 ────────────────────────────────────────────────────────

const EXPIRY_OPTIONS = [
  { label: "30 天", value: 30 },
  { label: "90 天", value: 90 },
  { label: "180 天", value: 180 },
  { label: "365 天", value: 365 },
  { label: "永不过期", value: 0 },
];

const apiKeys = ref<ApiKeySummary[]>([]);
const keyLoading = ref(false);
const keyDialogVisible = ref(false);
const keyDialogName = ref("");
const keyDialogExpiry = ref(0);
const keyCreating = ref(false);
const newKeyResult = ref<ApiKeyCreateResponse | null>(null);

async function loadApiKeys() {
  keyLoading.value = true;
  try {
    const res = await apiKeyService.list();
    apiKeys.value = res ?? [];
  } finally {
    keyLoading.value = false;
  }
}

function openCreateKey() {
  keyDialogName.value = "";
  keyDialogExpiry.value = 0;
  newKeyResult.value = null;
  keyCreating.value = false;
  keyDialogVisible.value = true;
}

async function handleCreateKey() {
  keyCreating.value = true;
  try {
    const days = keyDialogExpiry.value > 0 ? keyDialogExpiry.value : undefined;
    const res = await apiKeyService.create(keyDialogName.value, days);
    newKeyResult.value = res;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? "创建失败");
  } finally {
    keyCreating.value = false;
  }
}

function handleKeyDialogClose() {
  if (newKeyResult.value) {
    loadApiKeys();
  }
}

async function copyNewKey() {
  if (!newKeyResult.value?.api_key) {
    return;
  }
  try {
    await navigator.clipboard.writeText(newKeyResult.value.api_key);
    ElMessage.success("已复制到剪贴板");
  } catch {
    ElMessage.warning("复制失败，请手动复制");
  }
}

async function copyKeyFromList(row: ApiKeySummary) {
  try {
    const res = await apiKeyService.reveal(row.id);
    await navigator.clipboard.writeText(res.api_key);
    ElMessage.success("已复制到剪贴板");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? "获取失败");
  }
}

const testingKeyId = ref<string | null>(null);

async function handleTestKey(row: ApiKeySummary) {
  testingKeyId.value = row.id;
  try {
    const data = await apiKeyService.test(row.id);
    if (data.valid) {
      ElMessage.success(data.reason);
    } else {
      ElMessage.warning(data.reason);
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? "测试失败");
  } finally {
    testingKeyId.value = null;
  }
}

async function handleDeleteKey(row: ApiKeySummary) {
  try {
    await ElMessageBox.confirm(
      `确定要删除 API Key「${row.name || "(未命名)"}」吗？此操作不可撤销。`,
      "确认删除",
      { confirmButtonText: "确定删除", cancelButtonText: "取消", type: "warning" },
    );
  } catch {
    return;
  }
  try {
    await apiKeyService.delete(row.id);
    ElMessage.success("API Key 已删除");
    await loadApiKeys();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? "删除失败");
  }
}

function formatTime(iso: string | null) {
  if (!iso) {
    return "从未使用";
  }
  return new Date(iso).toLocaleString();
}

onMounted(() => {
  loadUsers();
  loadApiKeys();
});
</script>

<template>
  <div class="settings-page">
    <h1 class="page-title">
      设置
    </h1>

    <el-tabs v-model="activeTab" class="settings-tabs">
      <!-- ═══════════════════════════════════════════════════════════ 用户管理 -->
      <el-tab-pane label="用户管理" name="users">
        <div class="tab-toolbar">
          <el-button type="primary" @click="openCreateUser">
            创建用户
          </el-button>
        </div>

        <el-table v-loading="userLoading" :data="users" stripe>
          <el-table-column prop="account" label="账号" min-width="120" />
          <el-table-column prop="name" label="姓名" min-width="100" />
          <el-table-column prop="role" label="角色" width="90">
            <template #default="{ row }">
              <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
                {{ row.role }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="is_active" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
                {{ row.is_active ? "启用" : "禁用" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="updated_at" label="更新时间" min-width="160">
            <template #default="{ row }">
              {{ formatTime(row.updated_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click="openEditUser(row)">
                编辑
              </el-button>
              <el-button text type="danger" size="small" @click="handleDeleteUser(row)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ═══════════════════════════════════════════════════════════ API Key -->
      <el-tab-pane label="API Key" name="apikeys">
        <div class="tab-toolbar">
          <el-button type="primary" @click="openCreateKey">
            创建 API Key
          </el-button>
        </div>

        <el-table v-loading="keyLoading" :data="apiKeys" stripe>
          <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.name || '(未命名)' }}
            </template>
          </el-table-column>
          <el-table-column label="密钥" width="160">
            <template #default="{ row }">
              <div class="key-cell">
                <code class="key-preview">sk-...</code>
                <el-button
                  text
                  type="primary"
                  size="small"
                  @click="copyKeyFromList(row)"
                >
                  复制
                </el-button>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="过期时间" width="100">
            <template #default="{ row }">
              <template v-if="row.expires_at">
                <el-tag
                  :type="new Date(row.expires_at).getTime() < Date.now() ? 'danger' : 'warning'"
                  size="small"
                >
                  {{ formatTime(row.expires_at) }}
                </el-tag>
              </template>
              <span v-else class="text-muted">永不过期</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" min-width="140">
            <template #default="{ row }">
              {{ formatTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="last_used_at" label="最后使用" min-width="140">
            <template #default="{ row }">
              {{ formatTime(row.last_used_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button
                text
                type="primary"
                size="small"
                :loading="testingKeyId === row.id"
                @click="handleTestKey(row)"
              >
                测试
              </el-button>
              <el-button
                text
                type="danger"
                size="small"
                @click="handleDeleteKey(row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- ── 用户表单对话框 ──────────────────────────────────────────────── -->
    <el-dialog
      v-model="userDialogVisible"
      :title="userDialogTitle"
      width="460px"
      :close-on-click-modal="false"
    >
      <el-form
        label-position="top"
        @submit.prevent="handleUserSubmit"
      >
        <el-form-item label="账号" required>
          <el-input
            v-model="userForm.account"
            :disabled="userFormMode === 'edit'"
            placeholder="字母、数字、下划线、连字符"
            maxlength="64"
          />
        </el-form-item>
        <el-form-item :label="userFormMode === 'create' ? '密码' : '新密码（留空不修改）'">
          <el-input
            v-model="userForm.password"
            type="password"
            show-password
            placeholder="至少 6 位"
            maxlength="128"
          />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="userForm.name" placeholder="可选" maxlength="128" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.role">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="userFormMode === 'edit'" label="启用">
          <el-switch v-model="userForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialogVisible = false">
          取消
        </el-button>
        <el-button type="primary" @click="handleUserSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- ── API Key 创建对话框 ──────────────────────────────────────────── -->
    <el-dialog
      v-model="keyDialogVisible"
      title="创建 API Key"
      width="500px"
      :close-on-click-modal="false"
      @closed="handleKeyDialogClose"
    >
      <!-- 未创建：输入名称和过期时间 -->
      <div v-if="!newKeyResult">
        <el-form label-position="top" @submit.prevent="handleCreateKey">
          <el-form-item label="名称（可选）">
            <el-input
              v-model="keyDialogName"
              placeholder="便于记忆的名称，如 CI Pipeline"
              maxlength="128"
            />
          </el-form-item>
          <el-form-item label="过期时间">
            <el-select v-model="keyDialogExpiry" style="width: 100%">
              <el-option
                v-for="opt in EXPIRY_OPTIONS"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-form>
      </div>

      <!-- 已创建：展示 key -->
      <div v-else>
        <el-alert
          type="success"
          :closable="false"
          show-icon
          title="API Key 创建成功！请复制并妥善保存。"
          style="margin-bottom: 16px"
        />
        <div class="key-result">
          <el-input
            :model-value="newKeyResult.api_key"
            readonly
            size="large"
          />
          <el-button
            type="primary"
            style="margin-top: 12px; width: 100%"
            @click="copyNewKey"
          >
            复制到剪贴板
          </el-button>
        </div>
      </div>

      <template #footer>
        <template v-if="!newKeyResult">
          <el-button @click="keyDialogVisible = false">
            取消
          </el-button>
          <el-button
            type="primary"
            :loading="keyCreating"
            @click="handleCreateKey"
          >
            创建
          </el-button>
        </template>
        <el-button v-else type="primary" @click="keyDialogVisible = false">
          我已保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="less">
.settings-page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px 32px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #16201b;
  margin: 0 0 20px;
}

.settings-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 16px;
  }
}

.tab-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.key-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.key-preview {
  font-size: 13px;
  color: #16201b;
}

.text-muted {
  color: #909399;
  font-size: 13px;
}

.key-result {
  text-align: center;

  :deep(.el-input__inner) {
    font-family: monospace;
    text-align: center;
    letter-spacing: 1px;
  }
}
</style>
