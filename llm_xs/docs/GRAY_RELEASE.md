# 小博士 · 灰度上线清单

完成 **TLS、密钥校验、Cron 备份、Prometheus 告警** 后即可进入灰度。Playwright E2E 与 Prometheus 多进程指标已在仓库内就绪，可按需启用。

---

## 1. 上线前 Checklist

| 项 | 说明 | 命令/文件 |
|----|------|-----------|
| 强密钥 | 复制模板并填写随机值 | `.env.prod.example` → `.env.prod` |
| 密钥校验 | 启动前检查占位符/弱口令 | `bash scripts/check-production-secrets.sh .env.prod` |
| TLS | 自签（内网）或 Let's Encrypt | `scripts/tls/generate-self-signed.sh <域名>` |
| 生产 overlay | 鉴权、Postgres/Redis/MySQL | `docker-compose.prod.yml` |
| 监控 | Prometheus + Grafana + 告警 | `--profile monitoring` |
| 定时备份 | PG/MySQL/Milvus + retention | `--profile cron` 或宿主机 crontab |
| E2E 冒烟 | API 闭环 | `cd e2e && npm ci && npm run test:api` |

---

## 2. 灰度启动（推荐命令）

```bash
cd llm_xs

# 1) 环境
cp .env.prod.example .env.prod
# 编辑 .env.prod：KIDS_API_KEYS、POSTGRES_PASSWORD、KIDS_CORS_ORIGINS 等

# 2) 校验
bash scripts/check-production-secrets.sh .env.prod

# 3) TLS（公网/HTTPS 必选）
bash scripts/tls/generate-self-signed.sh your-domain.example.com
# 证书输出至 deploy/certs/fullchain.pem + privkey.pem

# 4) 启动
docker compose --env-file .env.prod \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tls.yml \
  --profile full --profile frontend --profile monitoring --profile cron \
  up -d --build
```

访问：

- **HTTPS 入口**：`https://<域名>/`（nginx 443）
- **Grafana**：`https://<域名>/grafana` 或 `:3000`（视反代配置）
- **Prometheus**：`:9090`（建议内网/VPN）
- **Alertmanager**：`:9093`

---

## 3. TLS

- 配置：`deploy/nginx.prod.conf` + `docker-compose.tls.yml`
- 证书挂载：`TLS_CERT_DIR`（默认 `./deploy/certs`）→ 容器 `/etc/letsencrypt`
- HTTP 80 自动 301 到 HTTPS
- Backend 启用 HSTS：`KIDS_HSTS_MAX_AGE=31536000`

Let's Encrypt 示例：将 `live/<domain>/fullchain.pem` 软链或复制到 `deploy/certs/`。

---

## 4. 密钥与安全

`scripts/check-production-secrets.sh` 校验：

- `KIDS_API_KEYS`、`KIDS_INGEST_TOKEN`、`KIDS_RETENTION_SWEEP_TOKEN`
- `KIDS_CORS_ORIGINS`（禁止 `*`）
- `KIDS_METRICS_TOKEN`
- `POSTGRES_PASSWORD` 非默认 `kid`

生产 overlay（`docker-compose.prod.yml`）额外开启：

- `KIDS_REQUIRE_AUTH=true`
- `KIDS_REQUIRE_PARENT_CONSENT=true`
- JSON 日志、限流 fail-closed、Postgres/Redis/MySQL

---

## 5. Cron 备份

**Sidecar（推荐）**：`backup-cron` 服务，每日 UTC 03:00 执行。

```bash
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml \
  --profile cron up -d backup-cron
```

备份内容（`scripts/cron/backup-all.sh`）：

1. Postgres `pg_dump`
2. MySQL `mysqldump`
3. Milvus 元数据（volume 快照需宿主机 `scripts/backup/milvus.sh`）
4. `POST /api/privacy/retention/sweep`（`X-Retention-Token`）
5. 删除 14 天前的备份文件

**宿主机 Cron**（无 sidecar 时）：

```cron
0 3 * * * cd /path/to/llm_xs && BACKUP_MODE=compose bash scripts/cron/backup-all.sh >> /var/log/kid-backup.log 2>&1
```

日志：`docker compose logs -f backup-cron` 或 `/var/log/kid-backup.log`。

---

## 6. 监控与告警

### Prometheus 多进程

- Dockerfile 已设 `PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc`
- `gunicorn_conf.py` 在 master 启动时清空目录，worker 退出时 `mark_process_dead`
- `WEB_CONCURRENCY>1` 时 `/api/metrics` 自动聚合各 worker

### 告警规则

`deploy/prometheus/alerts.yml`：

| 告警 | 条件 |
|------|------|
| KidHighErrorRate | 5xx 占比 > 5%（5m） |
| KidHighRateLimit | 10m 内 429 > 50 |
| KidAuditWriteFailures | 审计写入失败 |
| KidBackendDown | metrics 抓取失败 |
| KidHighLatencyP95 | P95 > 10s |

Alertmanager：Compose 启动时由 `deploy/prometheus/alertmanager-entrypoint.sh` 根据环境变量生成配置：

| 变量 | 说明 |
|------|------|
| `ALERTMANAGER_WEBHOOK_URL` | 通用 Webhook（钉钉/飞书/自建网关，Prometheus JSON） |
| `ALERTMANAGER_SLACK_WEBHOOK` | Slack Incoming Webhook |
| `KIDS_ENV` | 告警标签中的环境名 |

未配置时仅 Web UI（`:9093`）。静态示例见 `deploy/prometheus/alertmanager.yml.example`。

---

## 7.1 备份恢复

```bash
# 备份（cron profile 或手动）
bash scripts/cron/backup-all.sh

# 校验备份文件（不写入数据库）
bash scripts/backup/restore-all.sh verify ./backups/postgres_YYYYMMDD.sql.gz

# 恢复（需 postgres/mysql 容器已运行）
bash scripts/backup/restore-all.sh postgres ./backups/postgres_YYYYMMDD.sql.gz
bash scripts/backup/restore-all.sh mysql   ./backups/mysql_YYYYMMDD.sql.gz
```

---

## 7.2 真 token 流式 SSE

`/api/chat/stream` 默认启用原生流式（`KIDS_CHAT_STREAM_NATIVE=true`）：在线 LLM 通过 LangGraph `astream` 逐 chunk 推送；离线或失败时降级为一次性输出。设为 `false` 可恢复「先算完再 12 字符分块」的旧行为。

---

## 8. Playwright E2E

```bash
# 终端 1：本地后端（开放模式或带 Key）
cd llm_xs && uvicorn app.api:app --port 8001

# 终端 2
cd e2e
npm ci
npx playwright install chromium
E2E_API_KEY=your-key npm run test:api    # 生产模式需 Key
E2E_UI_URL=http://127.0.0.1:5173 npm run test:ui   # UI 全流程（mock JWT + 出题判分）
```

CI 可在 backend job 后增加 e2e job，对 `127.0.0.1:8001` 跑 API 冒烟。

---

## 8. 灰度观察期建议

1. **第 1–3 天**：内测用户 ≤ 50，盯 Grafana 5xx/429/P95
2. **告警**：确认 Alertmanager 能收到 KidHighErrorRate / KidBackendDown
3. **备份**：手动触发一次 `bash scripts/cron/backup-all.sh`，验证恢复路径
4. **合规**：家长同意弹窗、数据导出/删除 API 抽测
5. **扩容**：P95 持续 > 5s 时考虑 `WEB_CONCURRENCY` 或 LLM 配额

---

## 9. 已知后续项（非灰度阻塞）

- 前端 JWT 与 `llm_xs_auth` 联调（hash 回跳写 `kid_user`）
- `PyJWT` 进生产镜像、`auth` 服务进 Compose
- UI E2E 覆盖登录/consent 全流程
- `postJSON()` 增加 `resp.ok` 检查

详见 [PRODUCTION_AUDIT.md](./PRODUCTION_AUDIT.md)。
