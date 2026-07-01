# Jarvis 学习域（学生 Jarvis-v2 落地）

基于 `学生Jarvis-v2/` 与 `docs/` 需求，在 **llm_xs** 技术栈上实现的小学学习闭环。

## 后端 `app/learning/`

| 模块 | 能力 |
|------|------|
| `kp_catalog.py` | 从 `docs/content/*.kp.md` 加载 KP 目录 |
| `gap_service.py` | 学情 GapMap（knowledge_point_id 主轴） |
| `attempt_service.py` | 题库题 / freeform 真实题提交 |
| `photo_service.py` | 拍照归类 + inbox 三档分流 |
| `plan_service.py` | 20 分钟微计划 + 家长周报 |
| `learning_tools.py` | LangGraph Agent 工具 + AnswerGate 注入 |

## API 一览

**学生端** `/api/learning/*`

- `POST /onboarding` · `GET /profile` · `GET /gaps` · `GET /progress`
- `POST /attempts` · `POST /attempts/freeform`
- `POST /questions/suggest` · `GET /questions/{id}`
- `POST /plan` · `POST /photo/classify` · `GET /photo/inbox`
- `POST /vision/understand` · `POST /tts`

**家长端** `/api/parent/*`

- `GET /students/{id}/profile` · `GET /report` · `PATCH /gaps/{kp_id}`

**内容** `/api/kp/catalog`

## 前端 Tab

| Tab | 组件 |
|-----|------|
| 问答 | `ChatPanel`（语音/拍照/朗读） |
| 智能练习 | `LearningQuizPanel`（KP 推题） |
| 出题练习 | `QuizPanel`（原规则引擎） |
| 我的进步 | `ProgressPanel`（T4 鼓励视图） |
| 微计划 | `StudyPlanPanel` |
| 学习卡片 | `StudyCardPanel` |
| 家长模式 | `ParentDashboard`（学情/inbox/周报） |

## 启动

```bash
cd llm_xs
uvicorn app.api:app --port 8001 --reload

cd frontend-web && npm run dev
```

首次进入会弹出 **Onboarding**（年级/单元），之后学情写入 `data/memory/learning/*.json`。

## 测试

```bash
python -m pytest tests/test_learning.py -v
```
