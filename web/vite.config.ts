import path from "node:path";
import vue from "@vitejs/plugin-vue";
import jsx from "@vitejs/plugin-vue-jsx";
import UnoCSS from "unocss/vite";
import { defineConfig } from "vite";
import layouts from "vite-plugin-vue-layouts";
import router from "vue-router/vite";

const backendTarget = "http://localhost:9110";

export default defineConfig({
  base: "/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/doc": {
        target: backendTarget,
        changeOrigin: true,
      },
      "/config": {
        target: backendTarget,
        changeOrigin: true,
      },
      "/agent/v1": {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    extensions: [".js", ".ts", ".jsx", ".tsx", ".json", ".vue"],
  },
  plugins: [
    vue({
      include: [/\.vue$/, /\.tsx$/],
    }),
    jsx(),
    router({
      routesFolder: "src/pages",
      routeBlockLang: "yaml",
      exclude: ["**/_components/**"],
      dts: "typed-router.d.ts",
    }),
    layouts(),
    UnoCSS(),
  ],
});
