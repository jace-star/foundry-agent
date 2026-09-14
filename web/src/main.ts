import ElementPlus from "element-plus";
import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";
import pinia from "./store/pinia";
import "element-plus/dist/index.css";
import "uno.css";

function bootstrap() {
  const app = createApp(App);

  app.use(pinia);
  app.use(router);
  app.use(ElementPlus);

  app.mount("#app");
}

bootstrap();
