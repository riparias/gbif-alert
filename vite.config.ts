import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  base: "/static/vite/",
  build: {
    outDir: "static_global/vite",
    manifest: true,
    rollupOptions: {
      input: "assets/frontend/main.ts",
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/ol/")) return "vendor-openlayers";
          if (/node_modules\/d3[-/]/.test(id) || id.includes("node_modules/d3/")) return "vendor-d3";
          if (id.includes("node_modules/primevue/") || id.includes("node_modules/@primeuix/")) return "vendor-primevue";
          if (
            id.includes("node_modules/vue/") ||
            id.includes("node_modules/vue-router/") ||
            id.includes("node_modules/pinia/") ||
            id.includes("node_modules/vue-i18n/") ||
            id.includes("node_modules/@vue/")
          ) return "vendor-vue";
        },
      },
    },
  },
  server: {
    port: 5274,
    // Tells Vite what origin to use when rewriting asset URLs during dev,
    // so Django templates receive absolute URLs pointing at the dev server.
    origin: "http://localhost:5274",
  },
});
