import ElementPlus from "element-plus";
import { enableKatex } from "markstream-vue";
import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";
import pinia from "./store/pinia";
import "element-plus/dist/index.css";
import "uno.css";
import "katex/dist/katex.min.css";

// markstream-vue 公式渲染（peer: katex）
enableKatex();

function bootstrap() {
  const app = createApp(App);

  app.use(pinia);
  app.use(router);
  app.use(ElementPlus);

  app.mount("#app");
}

bootstrap();
