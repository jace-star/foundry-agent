import type { Router } from "vue-router";
import { useUserStoreWithOut } from "@/store/user";

const AUTH_ENABLED = import.meta.env.VITE_AUTH_ENABLED === "true";

export function useAuthGuard(router: Router) {
  router.beforeEach(async (to) => {
    if (!AUTH_ENABLED) {
      return true;
    }

    const userStore = useUserStoreWithOut();

    // 页面刷新后恢复用户状态
    if (!userStore.userInfo && localStorage.getItem("app.auth.token")) {
      await userStore.getUserInfo();
    }

    const isLogin = userStore.isLogin;

    if (to.path === "/login" && isLogin) {
      return { path: (to.query.redirect as string) || "/" };
    }

    if (to.path !== "/login" && !isLogin && to.meta.needLogin !== false) {
      return {
        path: "/login",
        query: { redirect: to.fullPath },
      };
    }
    return true;
  });
}
