# Pinia 配置方案

> 基于 Vite + Vue 3 + Pinia + @vueuse/core

---

## 目录结构

```
src/store/
├── pinia.ts          # Pinia 实例创建与导出
├── user.ts           # 用户状态（登录/登出/用户信息）
└── system.ts         # 系统状态（初始化状态/系统能力）
```

---

## 1. Pinia 实例 `src/store/pinia.ts`

```typescript
import { createPinia } from "pinia";

export const pinia = createPinia();

export default pinia;
```

> 在 `main.ts` 中引入挂载：
> ```typescript
> import pinia from "@/store/pinia";
> app.use(pinia);
> ```

---

## 2. 用户状态 `src/store/user.ts`

使用 **Composition API 风格**（`defineStore` + 函数式写法），搭配 `@vueuse/core` 的 `useAsyncState` 管理异步状态。

```typescript
import { useAsyncState } from "@vueuse/core";
import { defineStore } from "pinia";
import { computed } from "vue";

import { userService } from "@/service/modules/user";
import pinia from "./pinia";
import { useSystemStore } from "./system";

export const useUserStore = defineStore("user", () => {
  const systemStore = useSystemStore();

  // 异步获取用户信息，immediate: false 延迟手动触发
  const {
    state: userInfo,
    execute: getUserInfo,
    isLoading: isLoginLoading,
  } = useAsyncState(async () => {
    try {
      const res = await userService.getUserInfo();
      const data = res ? (res.data as Record<string, any>) : null;
      return data;
    } catch (error) {
      console.error(error);
      return null;
    }
  }, null, { immediate: false });

  const userName = computed(() => (userInfo.value?.name as string) ?? "");
  const isLogin = computed(() => !!userInfo.value);

  // 检查是否已登录（优先取缓存）
  const checkLogin = async () => {
    const initialized = await systemStore.isInitialized();
    if (!initialized) {
      return false;
    }
    const cachedUserInfo = userInfo?.value;
    if (cachedUserInfo) {
      return true;
    }
    const result = await getUserInfo();
    return !!result;
  };

  const logout = async (reload = true) => {
    await userService.logout();
    localStorage.removeItem("app.auth.token");
    if (reload) {
      location.reload();
    }
  };

  const login = async (params: { username: string; password: string }) => {
    const res = await userService.login(params);
    localStorage.setItem("app.auth.token", res.data.accessToken);
    if (res) {
      await getUserInfo();
    }
    return res;
  };

  return {
    userInfo,
    userName,
    isLogin,
    isLoginLoading,
    getUserInfo,
    checkLogin,
    logout,
    login,
  };
});

// 供路由守卫等场景使用（无需在 setup 中调用）
export const useUserStoreWithOut = () => useUserStore(pinia);
```

---

## 3. 系统状态 `src/store/system.ts`

使用 `@vueuse/core` 的 `computedAsync` 管理 Promise 异步状态，优雅地处理加载中/错误/默认值的场景。

```typescript
import { computedAsync } from "@vueuse/core";
import { defineStore } from "pinia";

import { ref } from "vue";

import { systemService } from "@/service/modules/system";
import pinia from "./pinia";

export const useSystemStore = defineStore("system", () => {
  const initialized = ref(false);
  // 预加载系统能力
  const ready = systemService.getCapabilities().then(({ data }) => data);

  // 异步计算属性，默认值兜底
  const capabilities = computedAsync(() => ready, {
    chat: false,
    embedding: false,
    textToSpeech: false,
    speechToText: false,
    mcpServers: false,
    initialized: false,
  });

  const isInitialized = async () => {
    const caps = await ready;
    return caps.initialized || initialized.value;
  };

  const markInitialized = () => {
    initialized.value = true;
  };

  return {
    capabilities,
    isInitialized,
    markInitialized
  };
});

export const useSystemStoreWithOut = () => useSystemStore(pinia);
```

---

## 4. Store 两种用法对比

### 组件内用法（推荐）

```typescript
import { useUserStore } from "@/store/user";

const userStore = useUserStore();
console.log(userStore.userName);    // 直接访问 state
console.log(userStore.isLogin);    // computed
userStore.login({ username, password });
userStore.logout();
```

### 组件外用法（如路由守卫、工具函数）

```typescript
import { useUserStoreWithOut } from "@/store/user";
import { useSystemStoreWithOut } from "@/store/system";

const userStore = useUserStoreWithOut();
const systemStore = useSystemStoreWithOut();
```

> **原理**：`useStore(pinia)` 传入 pinia 实例，绕过 setup 上下文在组件外获取 store。

---

## 5. Service 层（配合 Pinia 使用）

Pinia store 中不直接调用 API，而是通过 service 层封装：

```
src/service/
├── index.ts
└── modules/
    ├── user.ts
    └── system.ts
```

### `src/service/modules/user.ts` 示例

```typescript
import { request } from "@/utils/request";

export const userService = {
  login(params: { username: string; password: string }) {
    return request.post("/auth/login", params);
  },

  logout() {
    return request.post("/auth/logout");
  },

  getUserInfo() {
    return request.get("/user/info");
  },
};
```

### `src/service/modules/system.ts` 示例

```typescript
import { request } from "@/utils/request";

export const systemService = {
  getCapabilities() {
    return request.get("/system/capabilities");
  },
};
```

---

## 6. 与 Pinia 配合的核心工具

### `@vueuse/core` — 异步状态

| 工具 | 用途 |
|---|---|
| `useAsyncState` | 通用异步状态管理，自动处理 loading/error |
| `computedAsync` | 异步 computed，带默认值兜底 |
| `useLocalStorage` | 持久化本地存储（token 等） |

### Pinia Store 设计模式

```
1. 用 defineStore + Composition API 风格（setup 函数）
2. 异步操作用 useAsyncState / computedAsync
3. computed 直接从 state 派生（如 userName, isLogin）
4. 返回同步/异步方法供外部调用（如 login, logout, checkLogin）
5. WithOut 工厂函数支持组件外调用
```

---

## 7. 安装依赖

```bash
pnpm add pinia @vueuse/core
```

---

## 8. 完整 `main.ts` 接入示例

```typescript
import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import pinia from "./store/pinia";

const app = createApp(App);

app.use(router);
app.use(pinia);

app.mount("#app");
```
