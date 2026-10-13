# Vue Router 配置方案

> 基于 Vite + Vue 3 + Vue Router 4

---

## 目录结构

```
src/router/
├── index.ts              # 路由主文件（创建、导出）
└── guards/
    ├── index.ts         # Guard 入口（注册所有 guard）
    ├── setup.ts         # 系统初始化守卫（未初始化时跳转 /setup）
    ├── auth.ts          # 登录状态守卫（未登录跳转 /login）
    ├── redirect.ts      # 动态重定向守卫（处理 meta.redirect）
    └── progress.ts      # 页面进度条（NProgress）
```

---

## 1. 路由主文件 `src/router/index.ts`

```typescript
import { setupLayouts } from "virtual:generated-layouts";
import { createRouter, createWebHistory } from "vue-router";
import { routes } from "vue-router/auto-routes";
import { setupRouterGuard } from "./guards";

const router = createRouter({
  history: createWebHistory(),
  routes: setupLayouts([...routes]),
});

setupRouterGuard(router);

export default router;
```

---

## 2. Guard 统一注册 `src/router/guards/index.ts`

```typescript
import type { Router } from "vue-router";
import { useAuthGuard } from "./auth";
import { useProgressGuard } from "./progress";
import { useRedirectGuard } from "./redirect";
import { useSetupGuard } from "./setup";

// setup guard 要优先执行（未 setup 时需要在登录前拦截并跳转）
const guards = [useSetupGuard, useRedirectGuard, useAuthGuard, useProgressGuard];

export function setupRouterGuard(router: Router) {
  for (const guard of guards) {
    guard(router);
  }
}
```

---

## 3. Guard 实现

### `setup.ts` — 系统初始化守卫

```typescript
import type { Router } from "vue-router";
import { useSystemStoreWithOut } from "@/store/system";

export function useSetupGuard(router: Router) {
  const systemStore = useSystemStoreWithOut();

  router.beforeEach(async (to) => {
    if (to.path.startsWith("/setup")) {
      return true;
    }
    const initialized = await systemStore.isInitialized();
    if (!initialized) {
      return {
        path: "/setup",
        query: { redirect: to.fullPath },
      };
    }
    return true;
  });
}
```

> 用于首次使用前的初始化引导流程，未完成初始化时强制跳转 `/setup`。

### `auth.ts` — 登录状态守卫

```typescript
import type { Router } from "vue-router";
import { useUserStoreWithOut } from "@/store/user";

export function useAuthGuard(router: Router) {
  router.beforeEach(async (to) => {
    const userStore = useUserStoreWithOut();
    const isLogin = await userStore.checkLogin();

    if (to.path !== "/login" && !isLogin && to.meta.needLogin !== false) {
      return {
        path: "/login",
        query: { redirect: to.fullPath },
      };
    }
    return true;
  });
}
```

> 未登录时重定向到登录页，登录后携带 redirect 参数跳转回原页面。

### `redirect.ts` — 动态重定向守卫

```typescript
import type { Router } from "vue-router";

export function useRedirectGuard(router: Router) {
  router.beforeEach(async (to) => {
    const redirect = to.meta.redirect?.replace(/:(\w+)/g, (_, p1: string) => {
      const value = to.params[p1 as keyof typeof to.params];
      if (value === undefined) {
        return "";
      }
      return value;
    });

    if (redirect === to.path) {
      return true;
    }

    if (redirect) {
      return redirect;
    }

    return true;
  });
}
```

> 支持 `redirect: /chat/:tab` 这种带参数的动态重定向，自动替换 URL 参数。

### `progress.ts` — 页面进度条

```typescript
import type { Router } from "vue-router";
import NProgress from "nprogress";

NProgress.configure({
  showSpinner: false,
});

export function useProgressGuard(router: Router) {
  router.beforeEach((to, from) => {
    if (to.path !== from.path) {
      NProgress.start();
    }
    return true;
  });

  router.afterEach(() => {
    NProgress.done();
  });
}
```

---

## 4. 路由元信息类型扩展 `src/vite-env.d.ts`

```typescript
declare module "vue-router" {
  interface RouteMeta {
    /** 路由标题 */
    title?: string;
    /** 顶栏中与标题同行的浅色说明 */
    subtitle?: string;
    /** 路由重定向 */
    redirect?: string;
    /** 是否需要登录，默认 true */
    needLogin?: boolean;
    /** 是否在菜单中显示，默认为 true */
    inMenu?: boolean;
    /** 为 true 时不渲染默认布局顶栏（如全屏聊天） */
    hideLayoutHeader?: boolean;
  }
}
```

---

## 5. Vite 配置 `vite.config.ts`

```typescript
import type { Plugin } from "vite";
import path from "node:path";
import vue from "@vitejs/plugin-vue";
import unocss from "unocss/vite";
import { defineConfig } from "vite";
import layouts from "vite-plugin-vue-layouts";
import router from "vue-router/vite";

export default defineConfig(() => {
  return {
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
      extensions: [".js", ".ts", ".jsx", ".tsx", ".json", ".vue"],
    },
    plugins: [
      vue(),
      unocss(),
      router({
        routesFolder: "src/pages",
        routeBlockLang: "yaml",
        exclude: ["**/_components/**"],
        dts: "typed-router.d.ts",
      }),
      layouts(),
    ],
  };
});
```

---

## 6. 页面路由声明示例

在 Vue 组件内部通过 `<route lang="yaml">` 声明路由元信息，无需手动编写路由表。

```vue
<!-- src/pages/index.vue — 根路径重定向 -->
<route lang="yaml">
meta:
  redirect: /chat
</route>

<!-- src/pages/login/index.vue — 空布局（无侧边栏/顶栏） -->
<route lang="yaml">
meta:
  layout: empty
</route>

<!-- src/pages/chat.vue — 全屏聊天页 -->
<route lang="yaml">
meta:
  isMenu: true
  title: 聊天
  hideLayoutHeader: true
</route>
```

### 目录结构约定

```
src/pages/
├── index.vue              → /
├── login/
│   └── index.vue          → /login
├── chat.vue               → /chat
├── agents/
│   ├── index.vue          → /agents
│   ├── create.vue         → /agents/create
│   └── detail/
│       └── [name].vue     → /agents/detail/:name
├── settings/
│   ├── index.vue          → /settings
│   └── [tab].vue          → /settings/:tab
└── _components/           # 不生成路由（被 exclude 排除）
```

---

## 7. 安装依赖

```bash
pnpm add vue-router nprogress
pnpm add -D vite-plugin-vue-layouts
```

---

## 8. 布局文件 `src/layouts/default.vue`

由 `vite-plugin-vue-layouts` 自动根据 `meta.layout` 选择布局文件。默认布局示例：

```vue
<script lang="tsx">
import { computed, defineComponent } from "vue";
import { RouterView, useRoute } from "vue-router";
import AppAside from "@/components/app-aside.vue";
import AppHeader from "@/components/app-header.vue";

export default defineComponent({
  name: "DefaultLayout",
  setup() {
    const route = useRoute();
    const hideLayoutHeader = computed(() => route.meta.hideLayoutHeader === true);

    return () => (
      <div class="box-border flex h-full min-h-0 w-full gap-3 md:gap-4 p-3 sm:p-4 md:p-5">
        <AppAside class="h-full min-h-0 shrink-0 overflow-hidden" />
        <main class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[20px] sm:rounded-[22px] border border-white/70 bg-white/85 shadow-[var(--shadow-card)] backdrop-blur-xl backdrop-saturate-150">
          {!hideLayoutHeader.value ? <AppHeader /> : null}
          <div class="min-h-0 flex-1 overflow-hidden">
            <RouterView />
          </div>
        </main>
      </div>
    );
  },
});
</script>
```
