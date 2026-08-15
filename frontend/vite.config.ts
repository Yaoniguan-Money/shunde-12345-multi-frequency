import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    // 后端 CORS allow_origins 默认只含 5173（http://127.0.0.1:5173 与 http://localhost:5173）。
    // 不能改后端，所以前端 dev server 必须跑在 5173 才能通过 CORS preflight。
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
