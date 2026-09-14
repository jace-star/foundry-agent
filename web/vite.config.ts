import path from "node:path";
import { fileURLToPath } from "node:url";
import vue from "@vitejs/plugin-vue";
import jsx from "@vitejs/plugin-vue-jsx";
import UnoCSS from "unocss/vite";
import { defineConfig, loadEnv } from "vite";
import layouts from "vite-plugin-vue-layouts";
import router from "vue-router/vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, fileURLToPath(new URL(".", import.meta.url)), "");

  return {
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
          target: env.VITE_DOC_API_BASE_URL || "http://localhost:9110",
          changeOrigin: true,
        },
        "/config": {
          target: env.VITE_DOC_API_BASE_URL || "http://localhost:9110",
          changeOrigin: true,
        },
        "/agent/v1": {
          target: env.VITE_DOC_API_BASE_URL || "http://localhost:9110",
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
  };
});
