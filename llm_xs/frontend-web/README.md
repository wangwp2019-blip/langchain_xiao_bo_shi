# 小博士 React 前端（frontend-web）

React 19 + Vite + TypeScript + Tailwind CSS v4 的小学生 AI 学习助手前端，前后端分离，通过 `/api` 调用 FastAPI 后端。

## 功能

### 默认简单聊天模式（`KIDS_SIMPLE_CHAT_MODE=true`）

- 💬 **聊天**：SSE 流式 + 🎤 语音 + 🔊 朗读；Agent 自动检索知识库
- 无需 Onboarding，学生端仅显示「聊天」Tab

### 完整学习模式（后端关闭 `KIDS_SIMPLE_CHAT_MODE`）

- 🎯 智能练习（KP 学情推题 · Jarvis 闭环）
- 🌟 我的进步 / 📋 微计划 / 📇 学习卡片 / 📖 Wiki
- 🎒 首次 Onboarding（年级/单元）

### 家长模式

- 📚 **知识库**：上传 txt/pdf/docx/图片，检索预览，重建索引
- 👨‍👩‍👧 学情 / inbox / 周报 / KP 审核

### 通用

- 📝 出题练习 + 作答 + 判分
- 🌍 中文 / English · 12 套主题 · JWT 登录

详见 [../docs/JARVIS_LEARNING.md](../docs/JARVIS_LEARNING.md) · [../../docs/知识库系统设计.md](../../docs/知识库系统设计.md)

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

后端开启 JWT 或 `KIDS_API_KEYS` 时，前端经登录页获取 token，或于 `.env` 设置 `VITE_API_KEY`。

## Docker

```bash
docker build -t kid-frontend .
# 运行时需与后端容器同网络，nginx 会把 /api 反代到 http://backend:8001
```

## 目录

```
src/
├── main.tsx
├── App.tsx              应用外壳（简单/完整模式切换）
├── index.css            Tailwind v4 + 主题
├── lib/
│   ├── api.ts           聊天 / 出题 / 鉴权
│   ├── learning-api.ts  学习域 API
│   └── knowledge-api.ts 资料库 API
├── hooks/               useHealth
└── components/
    ├── ChatPanel.tsx
    ├── KnowledgeLibraryPanel.tsx
    ├── ParentDashboard.tsx
    └── …
```
