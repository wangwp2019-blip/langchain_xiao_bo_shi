# 小博士 React 前端（frontend-web）

React 19 + Vite + TypeScript + Tailwind CSS v4 的小学生 AI 学习助手前端，前后端分离，通过 `/api` 调用 [FastAPI 后端](../)。

## 功能

- 💬 问答（SSE 流式 + 🎤 语音 + 📷 拍照识题 + 🔊 朗读）
- 🎯 智能练习（KP 学情推题 · Jarvis 闭环）
- 📝 出题练习 + 作答 + 判分
- 🌟 我的进步（T4 鼓励性进度视图）
- 📋 20 分钟微计划
- 📇 学习卡片
- 👨‍👩‍👧 家长模式（学情 / inbox / 周报）
- 🎒 首次 Onboarding（年级/单元）
- 🌍 中文 / English · 12 套主题 · JWT 登录

详见 [../docs/JARVIS_LEARNING.md](../docs/JARVIS_LEARNING.md)

## 本地开发

```bash
cd frontend-web
npm install
cp .env.example .env        # 按需配置 VITE_BACKEND / VITE_API_KEY
npm run dev                  # http://localhost:5173
```

> 需先启动后端：在上级目录 `python run_api.py`（默认 8001）。
> `vite.config.ts` 已把 `/api` 反代到 `VITE_BACKEND`（默认 `http://127.0.0.1:8001`），无 CORS 烦恼。

## 构建

```bash
npm run build      # 产物在 dist/
npm run preview    # 本地预览构建产物
```

## 鉴权

后端开启 `KIDS_API_KEYS` 时，在 `.env` 设置 `VITE_API_KEY=<key>`，
`src/lib/api.ts` 会自动在请求头附带 `X-API-Key`。

## Docker

```bash
docker build -t kid-frontend .
# 运行时需与后端容器同网络，nginx 会把 /api 反代到 http://backend:8001
```

## 目录

```
src/
├── main.tsx              入口
├── App.tsx              应用外壳（侧边栏 + 页签）
├── index.css           Tailwind v4 + 主题 CSS 变量
├── lib/                api 客户端 / 类型 / 文案(i18n)
├── hooks/              useHealth 健康探测
└── components/         Sidebar / ChatPanel / QuizPanel
```
