import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  base: "/static/vite/",
  build: {
    outDir: "static_global/vite",
    manifest: true,
    rollupOptions: {
      input: "assets/new-frontend/main.ts",
    },
  },
  server: {
    port: 5274,
    // Tells Vite what origin to use when rewriting asset URLs during dev,
    // so Django templates receive absolute URLs pointing at the dev server.
    origin: "http://localhost:5274",
  },
});
