/**
 * 带认证令牌的 fetch 封装。
 *
 * 所有需要后端鉴权的 API 请求都应通过此模块发起，
 * 会自动从 localStorage 获取 access token 附加到 Authorization header。
 */

export function getAuthToken(): string | null {
  return localStorage.getItem("app.auth.token");
}

/**
 * 发送 JSON 请求，自动附加 Bearer token。
 * 用法与原生 fetch 一致，但自动设置 Content-Type 为 application/json。
 */
export async function authFetch(
  url: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = getAuthToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "Accept": "application/json",
  };

  // 合并调用方自定义 headers
  if (init.headers) {
    const customHeaders = init.headers as Record<string, string>;
    Object.assign(headers, customHeaders);
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...init,
    headers,
  });

  // 401 未授权：清除 token 并跳转登录页
  if (response.status === 401) {
    localStorage.removeItem("app.auth.token");
    setTimeout(() => {
      window.location.replace("/login");
    }, 800);
    throw new Error("登录已过期");
  }

  return response;
}
