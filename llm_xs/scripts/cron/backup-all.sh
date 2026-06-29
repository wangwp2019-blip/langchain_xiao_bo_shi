#!/usr/bin/env bash
# 全量备份 + 数据留存清理（Cron / 手动）
# BACKUP_MODE=network  容器内直连 postgres/mysql/backend（backup-cron sidecar）
# BACKUP_MODE=compose  宿主机 docker compose exec（默认）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_MODE="${BACKUP_MODE:-compose}"
TS="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

log() { echo "[$(date -Iseconds 2>/dev/null || date)] $*"; }

log "=== 开始备份 $TS (mode=$BACKUP_MODE) ==="

backup_postgres() {
  local out="$BACKUP_DIR/postgres_${TS}.sql.gz"
  if [[ "$BACKUP_MODE" == "network" ]]; then
    PGPASSWORD="${POSTGRES_PASSWORD:-kid}" pg_dump \
      -h "${POSTGRES_HOST:-postgres}" -U "${POSTGRES_USER:-kid}" \
      "${POSTGRES_DB:-kid_assistant}" | gzip > "$out"
  elif docker compose ps postgres 2>/dev/null | grep -q "running"; then
    docker compose exec -T postgres pg_dump -U kid kid_assistant | gzip > "$out"
  else
    log "跳过 Postgres（未运行）"
    return 0
  fi
  log "Postgres: $out"
}

backup_mysql() {
  local out="$BACKUP_DIR/mysql_${TS}.sql.gz"
  if [[ "$BACKUP_MODE" == "network" ]]; then
    mysqldump -h "${MYSQL_HOST:-mysql}" -u"${MYSQL_USER:-kid}" \
      -p"${MYSQL_PASSWORD:-kid}" "${MYSQL_DATABASE:-kid_assistant}" | gzip > "$out"
  elif docker compose ps mysql 2>/dev/null | grep -q "running"; then
    docker compose exec -T mysql mysqldump -ukid -p"${MYSQL_PASSWORD:-kid}" kid_assistant | gzip > "$out"
  else
    log "跳过 MySQL（未运行）"
    return 0
  fi
  log "MySQL: $out"
}

backup_milvus() {
  if [[ "$BACKUP_MODE" == "network" ]]; then
    log "跳过 Milvus（network 模式请在宿主机运行 scripts/backup/milvus.sh）"
    return 0
  fi
  if docker compose ps milvus 2>/dev/null | grep -q "running"; then
    bash scripts/backup/milvus.sh "$BACKUP_DIR/milvus_${TS}.tar.gz" || log "Milvus volume 备份失败（可忽略）"
  else
    python run_milvus_backup.py --meta-only --out-dir "$BACKUP_DIR" 2>/dev/null || true
  fi
}

run_retention_sweep() {
  local token="${KIDS_RETENTION_SWEEP_TOKEN:-}"
  [[ -n "$token" ]] || { log "跳过 retention sweep（无 token）"; return 0; }
  local base
  if [[ "$BACKUP_MODE" == "network" ]]; then
    base="http://${BACKEND_HOST:-backend}:${KIDS_API_PORT:-8001}"
  elif docker compose ps backend 2>/dev/null | grep -q "running"; then
    base="http://127.0.0.1:${KIDS_API_PORT:-8001}"
  else
    log "跳过 retention sweep（backend 未运行）"
    return 0
  fi
  log "执行数据留存 sweep..."
  curl -sf -X POST "${base}/api/privacy/retention/sweep" \
    -H "X-Retention-Token: ${token}" || log "retention sweep 失败（检查 token/backend）"
}

backup_postgres || log "Postgres 备份失败"
backup_mysql || log "MySQL 备份失败"
backup_milvus || true
run_retention_sweep || true

find "$BACKUP_DIR" -type f -mtime +14 -delete 2>/dev/null || true

log "=== 备份完成 ==="
