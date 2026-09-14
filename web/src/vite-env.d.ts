/// <reference types="vite/client" />

import type { Events } from "vue";

type EventHandlers<E> = {
  [K in keyof E]?: (...args: any[]) => any
};
declare module "vue" {
  interface ComponentCustomProps extends EventHandlers<Events> {
  }
}

declare module "vue-router" {
  interface RouteMeta {
    /**
     * @description 路由标题
     */
    title?: string;
    /**
     * @description 顶栏中与标题同行的浅色说明
     */
    subtitle?: string;
    /**
     * @description 路由重定向
     */
    redirect?: string;
    /**
     * @description 是否需要登录
     * @default true
     */
    needLogin?: boolean;
    /**
     * @description 是否在菜单中显示, 默认为true
     */
    inMenu?: boolean;
    /**
     * @description 为 true 时不渲染默认布局顶栏（如全屏聊天）
     */
    hideLayoutHeader?: boolean;
  }
}
export {};
