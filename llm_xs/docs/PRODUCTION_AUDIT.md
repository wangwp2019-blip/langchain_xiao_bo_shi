# 生产上线三轮审计与修复记录

> 本文档记录对 `llm_xs` 的三轮「扫描 → 列缺口 → 代码修复」过程，便于上线 checklist 与后续迭代。

---

## 第一轮：安全与数据完整性（P0）

### 扫描结论（上线前缺口）

| 类别 | 问题 | 风险 |
|------|------|------|
| 鉴权 | 默认开放 API，无 Key 即可访问全部端点 | 公网裸奔 |
| 判分 | 客户端提交 `questions+answers`，可自建全对题目 | 作弊 / 数据不可信 |
| 出题 | 响应含标准答案 `quiz` | 前端可直接看答案 |
| 灌库 | `/api/ingest` 任意 Key 可触发全量重建 | DoS / 成本 |
| 多 Worker | file/sqlite 记忆 + 进程内限流 | 状态分裂 |

### 已实施修复

- **`KIDS_ENV=production` / `KIDS_REQUIRE_AUTH=true`**：生产门禁，未配 `KIDS_API_KEYS` 时鉴权依赖返回 503（`app/security.py`）
- **`settings.validate_production()`**：启动时检查多 Worker + 记忆后端 + Redis（`app/config.py` + `app/api.py` lifespan）
- **出题会话 `app/services/quiz_session.py`**：`POST /api/quiz` 仅返回 `session_id + public`；判分必须 `session_id`
- **`KIDS_INGEST_TOKEN` + `X-Ingest-Token`**：灌库与业务 API Key 分离（`app/security.py::verify_ingest_token`）
- **输入长度** `ChatRequest.question` max 2000（`app/api.py`）

---

## 第二轮：1：网络、限流与审计（P1）

### 扫描结论

| 类别 | 问题 | 风险 |
|------|------|------|
| 反代 | 未解析 `X-Forwarded-For`，限流/审计 IP 失真 | 误限流 / 无法追溯 |
| 限流 | Redis 故障 fail-open | 高峰失去保护 |
| 限流 | 本地桶无上限 | 内存膨胀 |
| 审计 | MySQL 表已建但未写入 | 无法追责 / 报表 |
| 工具 | 联网搜索结果未净化 | 儿童安全风险 |
| 记忆 | `save_student_profile` 绕过治理 | 策略不一致 |
| 健康检查 | `/api/health` 暴露过多内部信息 | 信息枚举 |
| Metrics | Token 非恒定时间比较 | 低危时序攻击 |

### 已实施修复

- **`KIDS_TRUSTED_PROXY_HOPS`** + `resolve_client_ip()`（`app/security.py`）
- **`KIDS_RATELIMIT_FAIL_OPEN`**（默认 true；生产建议 false）+ **`KIDS_RATELIMIT_MAX_CLIENTS`**
- **`app/audit_persist.py`**：chat / quiz 可选写 MySQL（`KIDS_MYSQL_AUDIT_ENABLED`）
- **联网工具输出**经 `sanitize_output`（`app/tools.py`）
- **`memory_admin.save_profile`** 统一资料写入（`app/tools.py`）
- **`KIDS_HEALTH_PUBLIC_DETAIL`**：公网 health 最小化（`app/api.py`）
- **Metrics** 使用 `compare_secret` 恒定时间比较
- **Nginx** SSE 路径补充 `X-Forwarded-*`（`deploy/nginx.conf`）
- **统一日志** `app/logging_setup.py` + `run_api.py`

---

## 第三轮：前端、测试与仍待完成项（P1–P2）

### 扫描结论（修复后仍缺）

| 优先级 | 仍缺能力 | 建议 |
|--------|----------|------|
| P1 | TLS 终结 | Nginx 443 + 证书 或云 LB |
| P1 | 完整 Compose 栈 | `--profile full` 启用 postgres+redis+mysql+frontend |
| P1 | 公网前端 Key | `VITE_API_KEY` 会进 bundle；应 BFF / 同域 Cookie |
| P1 | 会话存储 Redis | 多实例 quiz_session 需 Redis 共享 |
| P2 | 异步 API | 阻塞 LLM 占满 worker |
| P2 | 儿童隐私合规 | 家长同意、导出/删除 SLA |
| P2 | 备份 runbook | Postgres/Milvus/MySQL 备份脚本 |
| P2 | 前端 e2e | Playwright 冒烟 |
| P2 | CI 安全扫描 | pip-audit / bandit |

### 已实施修复

- **React 前端**适配 `session_id` 判分流（`frontend-web/`）
- **测试** `tests/test_production_hardening.py` 覆盖会话防作弊、ingest Token、生产鉴权门禁
- **文档** 本文件 + README 环境变量表更新

---

## 生产上线最小 Checklist

```env
KIDS_ENV=production
KIDS_REQUIRE_AUTH=true
KIDS_API_KEYS=your-secret-key
KIDS_INGEST_TOKEN=your-ingest-token
KIDS_TRUSTED_PROXY_HOPS=1
KIDS_RATELIMIT_FAIL_OPEN=false
KIDS_REDIS_URL=redis://redis:6379/0
KIDS_POSTGRES_URL=postgresql://...
KIDS_SHORT_TERM_BACKEND=postgres
KIDS_MEMORY_BACKEND=postgres
KIDS_MYSQL_URL=mysql://...
KIDS_MYSQL_AUTO_INIT_SCHEMA=true
KIDS_HEALTH_PUBLIC_DETAIL=false
KIDS_LOG_FORMAT=json
WEB_CONCURRENCY=2
```

```bash
docker compose --profile full up -d
python run_mysql_init.py
python run_ingest.py --force   # 或带 X-Ingest-Token 调 /api/ingest
python -m pytest tests/ -m "not integration" -v
```

---

## 第四轮：多实例与运维（P1）

### 扫描结论

| 类别 | 问题 |
|------|------|
| 会话 | quiz_session 仅进程内内存，多 Worker 判分会话丢失 |
| 限流 | `KIDS_CHAT_RATE_LIMIT_PER_MIN` 未在 API 生效 |
| 合规 | 无数据导出 API |
| 运维 | 无 DB 备份脚本 / TLS 模板 |
| CI | 无依赖漏洞扫描 |

### 已实施修复

- **Redis 出题会话** `app/services/quiz_session_store.py`（配 `KIDS_REDIS_URL` 自动启用）
- **聊天专用限流** `/api/chat` + `/api/chat/stream` 使用 `get_chat_limiter()`
- **`GET /api/privacy/export`**：记忆 + MySQL 审计数据导出
- **`scripts/backup/`** postgres / mysql 备份脚本
- **`deploy/nginx.tls.conf.example`** TLS 终结模板
- **CI `pip-audit`** 依赖安全审计（continue-on-error）

---

## 第五轮：仍建议在上线前完成（运维 / 架构）

| 优先级 | 项 | 说明 |
|--------|-----|------|
| P1 | 公网 TLS | 使用 `nginx.tls.conf.example` + Let's Encrypt |
| P1 | 前端 Key | 生产勿暴露 `VITE_API_KEY`，用 Nginx 反代 + 服务端 Session |
| P1 | Compose full | `docker compose --profile full up -d` |
| P2 | API 异步化 | LLM 路由改 async + executor |
| P2 | Playwright e2e | 前端 SSE / 出题流程 |
| P2 | 家长同意流程 | 产品层合规，非纯后端 |

---

## 第六轮：功能就绪度总览

| 模块 | 状态 | 说明 |
|------|------|------|
| 离线问答/出题/判分 | ✅ | 无 Key 可跑 |
| LangGraph Agent | ✅ | 需 LLM Key |
| RAG LlamaIndex/Milvus | ✅ | 需 Embedding |
| 安全护栏 | ✅ | 三级 + 输出净化 |
| API 鉴权 | ✅ | API Key + JWT |
| 判分防作弊 | ✅ | session_id |
| 限流 | ✅ | 本地/Redis + chat 分轨 |
| 记忆治理 | ✅ | 去重/TTL/清除 |
| MySQL 审计 | ✅ | 可选落库 |
| 隐私导出 | ✅ | `/api/privacy/export` |
| 多 Worker | ⚠️ | 需 postgres+redis |
| TLS | 📄 | 模板已提供 |
| 儿童隐私合规 | ✅ | consent + export + delete + retention sweep |
| API 异步化 | ✅ | chat/stream/study-card/quiz/grade |
| 全链路追踪 | ✅ | LangSmith + OTEL（镜像已装 OTEL 包） |
| Milvus 备份 | ✅ | `run_milvus_backup.py` |

---

## 第七轮：部署默认值与信息泄露（P0）

### 扫描结论

| 类别 | 问题 | 风险 |
|------|------|------|
| Compose | 默认 `WEB_CONCURRENCY=2` 但未启 postgres/redis | 多 Worker 状态分裂 |
| Health | `health_public_detail=false` 且已开鉴权时仍返回完整 payload | 内部信息枚举 |
| UI | `GET /` 内嵌页无鉴权，绕过 JWT/ConsentGate | 公网旁路 |
| 门禁 | `validate_production()` 仅在 `auth_required` 时检查 | 生产误配不告警 |
| Docker | HEALTHCHECK 打 `/api/ready`，MySQL 未就绪时重启循环 | 容器不稳定 |

### 已实施修复

- **`docker-compose.yml`** 默认 `WEB_CONCURRENCY=1`
- **`docker-compose.prod.yml`** 生产 overlay（postgres/redis/consent/鉴权/env 必填）
- **`/api/health`** 仅看 `health_public_detail`，与鉴权解耦
- **`embedded_ui_allowed`** 生产默认 404 内嵌 UI（`KIDS_EMBEDDED_UI=true` 可开）
- **`validate_production()`** 扩展：CORS、JWT/API Key、consent、redis、postgres memory、sweep token、proxy hops
- **`Dockerfile`** HEALTHCHECK 改 `/api/health`（liveness）
- **`tests/test_production_audit_rounds.py`**

---

## 第八轮：Moderation / 审计 / CI（P1）

### 扫描结论

| 类别 | 问题 |
|------|------|
| Moderation | API 故障 fail-open 放行 |
| 审计 | MySQL 写入失败无指标 |
| Metrics | Gunicorn 多进程指标不可聚合 |
| CI | pip-audit continue-on-error |
| OTEL | docker 镜像未装 OTEL 包 |
| 文档 | README 判分示例仍为旧 API |

### 已实施修复

- **`KIDS_MODERATION_FAIL_OPEN`**（生产门禁建议 false）
- **`kid_audit_write_failures_total`** + **`kid_worker_info`** 指标
- **CI** pip-audit 失败即红 + **bandit** 静态扫描
- **requirements.docker.txt** 启用 OTEL 依赖
- **README** session_id 判分示例

---

## 第九轮：收尾与仍待运维项（P1–P2）

### 扫描结论（修复后仍缺）

| 优先级 | 仍缺 | 说明 |
|--------|------|------|
| P1 | 公网 TLS | 使用 `deploy/nginx.tls.conf.example` + 证书 |
| P1 | 弱口令 | Compose 默认 kid/kid，生产必须用 secrets |
| P1 | Prometheus 多 Worker | 需 multiprocess 或单 worker 抓 metrics |
| P2 | 真 token SSE | 当前仍护栏后分块 |
| P2 | Playwright E2E | 前端登录→consent→chat 冒烟 |
| P2 | MySQL 集成测试 | testcontainers 或 CI compose job |
| P2 | 备份 restore 验证 | 仅有 dump 脚本 |

### 已实施修复

- **`/api/quiz`、`/api/grade`** 改 `async def`
- **`privacy.py`** 政策版本与 `KIDS_CONSENT_POLICY_VERSION` 动态同步
- **`credentials_auth_enabled`** 支持仅 JWT 生产部署

### 仍待运维（非代码）

- TLS 证书与 HSTS（`KIDS_HSTS_MAX_AGE`）
- Cron：`POST /api/privacy/retention/sweep` + Milvus/PG 备份
- 法务：隐私政策文案与 SLA

---

## 生产上线最小 Checklist（更新）

```env
KIDS_ENV=production
KIDS_REQUIRE_AUTH=true
KIDS_API_KEYS=...          # 或 KIDS_JWT_SECRET=...
KIDS_INGEST_TOKEN=...
KIDS_RETENTION_SWEEP_TOKEN=...
KIDS_CORS_ORIGINS=https://your-domain.example.com
KIDS_TRUSTED_PROXY_HOPS=1
KIDS_RATELIMIT_FAIL_OPEN=false
KIDS_REQUIRE_PARENT_CONSENT=true
KIDS_REDIS_URL=redis://...
KIDS_POSTGRES_URL=postgresql://...
KIDS_SHORT_TERM_BACKEND=postgres
KIDS_MEMORY_BACKEND=postgres
KIDS_QUIZ_SESSION_BACKEND=redis
KIDS_MYSQL_URL=mysql://...
KIDS_HEALTH_PUBLIC_DETAIL=false
KIDS_LOG_FORMAT=json
KIDS_MODERATION_FAIL_OPEN=false   # 若启用 Moderation
WEB_CONCURRENCY=2
```

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile full up -d
python run_mysql_init.py
python run_ingest.py --force
python run_milvus_backup.py --meta-only
python -m pytest tests/ -m "not integration" -v
```

---

# 离线全量（CI 同款）
python -m pytest tests/ -m "not integration" -v

# 含 LLM 集成
python -m pytest tests/ -m integration -v
```
