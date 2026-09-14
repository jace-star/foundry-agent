<route lang="yaml">
meta:
  layout: empty
</route>

<script setup lang="ts">
import { Lock, User } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useUserStore } from "@/store/user";

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();

const formRef = ref();
const loading = ref(false);

const formData = reactive({
  account: "",
  password: "",
});

const rules = {
  account: [{ required: true, message: "请输入账号", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
};

function getErrorMessage(error: unknown): string {
  if (error && typeof error === "object" && "response" in error) {
    const axiosError = error as { response?: { data?: { detail?: string }; status?: number } };
    if (axiosError.response?.data?.detail) {
      return axiosError.response.data.detail;
    }
    if (axiosError.response?.status === 401) {
      return "账号或密码错误";
    }
  }
  if (error instanceof Error) {
    return error.message || "登录失败，请稍后重试";
  }
  return "登录失败，请检查网络连接";
}

async function handleLogin() {
  try {
    await formRef.value?.validate();
  } catch {
    return;
  }

  loading.value = true;

  try {
    await userStore.login({
      account: formData.account,
      password: formData.password,
    });
    const redirect = (route.query.redirect as string) || "/";
    await router.replace(redirect);
    ElMessage.success("登录成功");
  } catch (error: unknown) {
    localStorage.removeItem("app.auth.token");
    ElMessage.error(getErrorMessage(error));
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <main class="login-card">
      <h1 class="login-title">
        登录
      </h1>

      <el-form
        ref="formRef"
        :model="formData"
        :rules="rules"
        class="login-form"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="account">
          <el-input
            v-model="formData.account"
            placeholder="请输入账号"
            size="large"
            autocomplete="off"
            :prefix-icon="User"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="formData.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
            autocomplete="current-password"
            :prefix-icon="Lock"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          :loading="loading"
          class="login-btn"
          @click="handleLogin"
        >
          {{ loading ? "登录中..." : "登 录" }}
        </el-button>
      </el-form>
    </main>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  box-sizing: border-box;
  background: #f6f7f4;
  color: #16201b;
  font-family: "Avenir Next", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.login-card {
  width: min(360px, 100%);
  padding: 34px 32px 30px;
  box-sizing: border-box;
  border: 1px solid rgba(22, 32, 27, 0.1);
  border-radius: 8px;
  background: #ffffff;
  box-shadow:
    0 18px 48px rgba(22, 32, 27, 0.08),
    0 1px 2px rgba(22, 32, 27, 0.04);
}

.login-title {
  margin: 0 0 22px;
  color: #16201b;
  font-size: 24px;
  line-height: 1.2;
  font-weight: 800;
  letter-spacing: 0;
  text-align: center;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.login-form :deep(.el-input__wrapper) {
  min-height: 44px;
  padding: 0 12px;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 0 0 1px rgba(22, 32, 27, 0.13) inset;
  transition:
    box-shadow 0.18s ease,
    background-color 0.18s ease;
}

.login-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px rgba(22, 32, 27, 0.22) inset;
}

.login-form :deep(.el-input.is-focus .el-input__wrapper) {
  box-shadow: 0 0 0 1px #8c9892 inset;
}

.login-form :deep(.el-input__inner) {
  color: #16201b;
  font-weight: 600;
}

.login-form :deep(.el-input__inner::placeholder) {
  color: #8a948f;
  font-weight: 500;
}

.login-form :deep(.el-input__prefix) {
  color: #75817b;
}

.login-btn {
  width: 100%;
  height: 44px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.08em;
  background: #117c68;
  border: none;
  box-shadow: none;
  transition:
    background-color 0.18s ease,
    transform 0.12s ease;
}

.login-btn:hover {
  background: #0e6d5c;
}

.login-btn:active {
  transform: translateY(1px);
}

.login-btn :deep(.el-button__text) {
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 760px) {
  .login-page {
    padding: 16px;
  }

  .login-card {
    padding: 28px 22px 24px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-btn,
  .login-form :deep(.el-input__wrapper) {
    transition: none;
  }
}
</style>
