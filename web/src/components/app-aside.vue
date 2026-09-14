<script setup lang="ts">
import { Lock, SwitchButton } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { userService } from "@/service/modules/user";
import { useUserStoreWithOut } from "@/store/user";

defineOptions({
  name: "AppAside",
});

const route = useRoute();
const router = useRouter();
const userStore = useUserStoreWithOut();

async function handleLogout() {
  try {
    await ElMessageBox.confirm("确定要退出登录吗？", "提示", {
      confirmButtonText: "确定退出",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  await userStore.logout(false);
  router.replace("/login");
}

// ── 修改密码 ────────────────────────────────────────────────────────────

const passwordDialogVisible = ref(false);
const passwordChanging = ref(false);
const passwordForm = reactive({
  old_password: "",
  new_password: "",
  confirm_password: "",
});

function openPasswordDialog() {
  passwordForm.old_password = "";
  passwordForm.new_password = "";
  passwordForm.confirm_password = "";
  passwordDialogVisible.value = true;
}

async function handleChangePassword() {
  if (!passwordForm.old_password) {
    ElMessage.warning("请输入原密码");
    return;
  }
  if (!passwordForm.new_password || passwordForm.new_password.length < 6) {
    ElMessage.warning("新密码至少 6 位");
    return;
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    ElMessage.warning("两次输入的新密码不一致");
    return;
  }

  passwordChanging.value = true;
  try {
    await userService.changePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
    });
    ElMessage.success("密码修改成功");
    passwordDialogVisible.value = false;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? "修改失败");
  } finally {
    passwordChanging.value = false;
  }
}

const allMenus = [
  { path: "/", label: "首页", icon: "i-carbon-home" },
  { path: "/agents", label: "Agent", icon: "i-carbon-bot" },
  { path: "/mcp", label: "工具", icon: "i-carbon-data-vis-4" },
  { path: "/settings", label: "设置", icon: "i-carbon-settings", admin: true },
];

const menus = computed(() =>
  allMenus.filter((item) => !item.admin || userStore.isAdmin)
);

function isActive(item: { path: string }) {
  if (item.path === "/") {
    return route.path === "/";
  }
  return route.path.startsWith(item.path);
}
</script>

<template>
  <aside class="app-aside">
    <nav class="menu">
      <div class="menu-stack">
        <router-link
          v-for="item in menus"
          :key="item.path"
          :to="item.path"
          class="menu-item"
          :class="{ active: isActive(item) }"
          :title="item.label"
        >
          <span class="menu-icon" :class="item.icon" />
          <span class="menu-label">{{ item.label }}</span>
        </router-link>
      </div>
    </nav>
    <div class="aside-footer">
      <el-dropdown trigger="click" placement="top-start">
        <div class="aside-btn">
          <img src="/setting.svg" alt="" class="aside-icon">
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item :icon="Lock" @click="openPasswordDialog">
              修改密码
            </el-dropdown-item>
            <el-dropdown-item :icon="SwitchButton" @click="handleLogout">
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <!-- 修改密码对话框 -->
    <el-dialog
      v-model="passwordDialogVisible"
      title="修改密码"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-form label-position="top" @submit.prevent="handleChangePassword">
        <el-form-item label="原密码">
          <el-input
            v-model="passwordForm.old_password"
            type="password"
            show-password
            placeholder="请输入原密码"
          />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input
            v-model="passwordForm.new_password"
            type="password"
            show-password
            placeholder="至少 6 位"
            maxlength="128"
          />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input
            v-model="passwordForm.confirm_password"
            type="password"
            show-password
            placeholder="再次输入新密码"
            maxlength="128"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">
          取消
        </el-button>
        <el-button type="primary" :loading="passwordChanging" @click="handleChangePassword">
          确定
        </el-button>
      </template>
    </el-dialog>
  </aside>
</template>

<style scoped lang="less">
.app-aside {
  width: 100px;
  height: 100vh;
  flex: 0 0 100px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(22, 32, 27, 0.1);
  background: #fffdfa;
  color: #16201b;
}

.menu {
  flex: 1;
  padding: 18px 8px;
}

.menu-stack {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.menu-item {
  min-height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 8px;
  border-radius: 8px;
  color: #526159;
  font-size: 14px;
  font-weight: 650;
  text-decoration: none;
  transition: background 0.16s ease, color 0.16s ease, transform 0.16s ease;

  &:hover,
  &.active {
    background: #effaf6;
    color: #117c68;
  }
}

.menu-icon {
  flex: 0 0 auto;
  font-size: 18px;
}

.menu-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.aside-footer {
  margin-top: auto;
  padding: 8px 8px 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.aside-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 46px;
  margin: 0;
  border-radius: 8px;
  cursor: pointer;
  outline: none;
  border: none;
  background: transparent;
  transition: background 0.16s ease;

  &:hover {
    background: #effaf6;
  }

  &:focus,
  &:focus-visible {
    outline: none;
    border: none;
  }
}

.aside-footer :deep(.el-dropdown) {
  width: 100%;
  outline: none;
  border: none;
}

.aside-icon {
  width: 20px;
  height: 20px;
  opacity: 0.6;
  transition: opacity 0.16s ease;

  .aside-btn:hover & {
    opacity: 1;
  }
}
</style>
