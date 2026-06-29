import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// 开发期把 /api 反代到 FastAPI 后端（默认 8001），避免 CORS。
// 后端地址可用环境变量 VITE_BACKEND 覆盖。
const backend = process.env.VITE_BACKEND || "http://127.0.0.1:8001";
// 认证服务（默认 8002）
const authBackend = process.env.VITE_AUTH_BACKEND || "http://127.0.0.1:8002";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/auth-api": {
        target: authBackend,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/auth-api/, "/api/v1/auth"),
      },
      "/api": {
        target: backend,
        changeOrigin: true,
      },
    },
  },
});
