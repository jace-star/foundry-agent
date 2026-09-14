import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { userService } from "@/service/modules/user";
import pinia from "./pinia";

const ACCESS_TOKEN_KEY = "app.auth.token";

export const useUserStore = defineStore("user", () => {
  const userInfo = ref<Record<string, any> | null>(null);
  const isLoginLoading = ref(false);

  const isLogin = computed(() => !!userInfo.value);
  const isAdmin = computed(() => (userInfo.value?.role as string) === "admin");

  const getUserInfo = async () => {
    try {
      const res = await userService.getUserInfo();
      userInfo.value = (res as Record<string, any>) ?? null;
    } catch {
      userInfo.value = null;
    }
  };

  const login = async (params: { account: string; password: string }) => {
    isLoginLoading.value = true;
    try {
      const res = (await userService.login(params)) as {
        accessToken: string;
      };
      localStorage.setItem(ACCESS_TOKEN_KEY, res.accessToken);
      await getUserInfo();
      return res;
    } finally {
      isLoginLoading.value = false;
    }
  };

  const logout = async (reload = true) => {
    try {
      await userService.logout();
    } catch {
      // 忽略服务端登出失败
    } finally {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      userInfo.value = null;
      if (reload) {
        location.reload();
      }
    }
  };

  return { userInfo, isLogin, isAdmin, isLoginLoading, getUserInfo, login, logout };
});

export const useUserStoreWithOut = () => useUserStore(pinia);
