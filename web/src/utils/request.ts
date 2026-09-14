import axios from "axios";
import { ElMessage } from "element-plus";

const instance = axios.create({
  baseURL: "/agent/v1",
  timeout: 10000,
});

// ── 请求拦截器：注入 token ─────────────────────────────────────────────

instance.interceptors.request.use((config) => {
  const token = localStorage.getItem("app.auth.token");
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── 响应拦截器：401 跳登录 + 错误提示 ──────────────────────────────────

instance.interceptors.response.use(
  (response) => response,
  (error) => {
    let errorMessage = "请求失败，请稍后重试";

    if (error.response) {
      const { data, status } = error.response;

      if (data?.detail) {
        errorMessage = typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail);
      } else if (data?.message) {
        errorMessage = typeof data.message === "string"
          ? data.message
          : JSON.stringify(data.message);
      }

      if (status === 401) {
        const isLoginRequest = error.config?.url?.includes("/auth/login");
        if (!isLoginRequest) {
          localStorage.removeItem("app.auth.token");
          ElMessage.warning("登录已过期，请重新登录");
          setTimeout(() => {
            window.location.replace("/login");
          }, 800);
          return Promise.reject(error);
        }
      }
    } else if (error.request) {
      errorMessage = "网络错误，请检查网络连接";
    }

    if (!error.config?.silent) {
      ElMessage.error(errorMessage);
    }

    return Promise.reject(error);
  },
);

export const request = {
  get<T = any>(url: string, config?: Record<string, any>) {
    return instance.get<T>(url, config).then((res) => res.data);
  },
  post<T = any>(url: string, data?: any, config?: Record<string, any>) {
    return instance.post<T>(url, data, config).then((res) => res.data);
  },
  put<T = any>(url: string, data?: any, config?: Record<string, any>) {
    return instance.put<T>(url, data, config).then((res) => res.data);
  },
  delete<T = any>(url: string, config?: Record<string, any>) {
    return instance.delete<T>(url, config).then((res) => res.data);
  },
};
