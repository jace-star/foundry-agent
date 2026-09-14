import { request } from "@/utils/request";

export interface ApiKeySummary {
  id: string;
  name: string;
  expires_at: string | null;
  created_at: string;
  last_used_at: string | null;
}

export interface ApiKeyCreateResponse {
  api_key: string;
  id: string;
  name: string;
  expires_at: string | null;
}

export interface ApiKeyRevealResponse {
  api_key: string;
  id: string;
  name: string;
}

export interface ApiKeyTestResponse {
  valid: boolean;
  reason: string;
  name: string;
  expires_at: string | null;
}

export const apiKeyService = {
  list() {
    return request.get<ApiKeySummary[]>("/api-keys");
  },

  create(name: string, expiresInDays?: number) {
    return request.post<ApiKeyCreateResponse>("/api-keys", {
      name,
      expires_in_days: expiresInDays || null,
    });
  },

  /** 获取完整 API Key 明文 */
  reveal(keyId: string) {
    return request.get<ApiKeyRevealResponse>(`/api-keys/${keyId}/reveal`);
  },

  /** 测试 API Key 当前是否可用 */
  test(keyId: string) {
    return request.get<ApiKeyTestResponse>(`/api-keys/${keyId}/test`);
  },

  delete(keyId: string) {
    return request.delete<null>(`/api-keys/${keyId}`);
  },
};
