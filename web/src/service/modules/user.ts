import { request } from "@/utils/request";

export const userService = {
  login(params: { account: string; password: string }) {
    return request.post("/auth/login", {
      account: params.account,
      password: params.password,
    });
  },

  logout() {
    return request.post("/auth/logout");
  },

  getUserInfo() {
    return request.get("/user/info");
  },

  changePassword(params: { old_password: string; new_password: string }) {
    return request.post("/user/change-password", params);
  },

  // ── 用户管理（管理员） ──────────────────────────────────────────────

  listUsers() {
    return request.get("/users");
  },

  createUser(params: {
    account: string;
    password: string;
    name?: string;
    role?: string;
  }) {
    return request.post("/users", params);
  },

  updateUser(userId: string, params: {
    password?: string;
    name?: string;
    role?: string;
    is_active?: boolean;
  }) {
    return request.put(`/users/${userId}`, params);
  },

  deleteUser(userId: string) {
    return request.delete(`/users/${userId}`);
  },
};
