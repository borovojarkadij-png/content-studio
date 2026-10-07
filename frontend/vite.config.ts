import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    watch: {
      usePolling: process.env.NEWSFLOW_WATCH_POLLING === "true",
    },
    proxy: {
      "/api": {
        target:
          process.env.NEWSFLOW_API_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
