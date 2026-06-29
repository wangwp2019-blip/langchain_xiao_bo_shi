#!/usr/bin/env bash
# 从备份文件恢复 Postgres / MySQL（需对应 Compose 服务已运行）
#
# 用法:
#   bash scripts/backup/restore-all.sh postgres ./backups/postgres_20250630.sql.gz
#   bash scripts/backup/restore-all.sh mysql   ./backups/mysql_20250630.sql.gz
#   bash scripts/backup/restore-all.sh verify  ./backups/postgres_20250630.sql.gz
#
# verify 模式：仅检查 gzip 完整性 + SQL 头，不写入数据库
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

TARGET="${1:-}"
FILE="${2:-}"
BACKUP_MODE="${BACKUP_MODE:-compose}"

usage() {
  echo "用法: $0 {postgres|mysql|verify} <backup-file>"
  exit 1
}

[[ -n "$TARGET" && -n "$FILE" ]] || usage
[[ -f "$FILE" ]] || { echo "[ERROR] 文件不存在: $FILE"; exit 1; }

log() { echo "[$(date -Iseconds 2>/dev/null || date)] $*"; }

verify_backup() {
  log "校验备份: $FILE"
  gzip -t "$FILE"
  log "gzip 完整性 OK"
  if [[ "$FILE" == *postgres* ]] || gunzip -c "$FILE" | head -5 | grep -qi "postgres"; then
    gunzip -c "$FILE" | head -20 | grep -qi "PostgreSQL" && log "检测到 PostgreSQL dump 头"
  fi
  if [[ "$FILE" == *mysql* ]] || gunzip -c "$FILE" | head -5 | grep -qi "mysql"; then
    gunzip -c "$FILE" | head -20 | grep -qi "MySQL" && log "检测到 MySQL dump 头"
  fi
  log "verify 完成（未写入数据库）"
}

restore_postgres() {
  log "恢复 Postgres ← $FILE"
  if [[ "$BACKUP_MODE" == "network" ]]; then
    gunzip -c "$FILE" | PGPASSWORD="${POSTGRES_PASSWORD:-kid}" psql \
      -h "${POSTGRES_HOST:-postgres}" -U "${POSTGRES_USER:-kid}" -d "${POSTGRES_DB:-kid_assistant}"
  else
    docker compose ps postgres 2>/dev/null | grep -q running || {
      echo "[ERROR] postgres 未运行"; exit 1;
    }
    gunzip -c "$FILE" | docker compose exec -T postgres psql -U kid -d kid_assistant
  fi
  log "Postgres 恢复完成"
}

restore_mysql() {
  log "恢复 MySQL ← $FILE"
  if [[ "$BACKUP_MODE" == "network" ]]; then
    gunzip -c "$FILE" | mysql -h "${MYSQL_HOST:-mysql}" -u"${MYSQL_USER:-kid}" \
      -p"${MYSQL_PASSWORD:-kid}" "${MYSQL_DATABASE:-kid_assistant}"
  else
    docker compose ps mysql 2>/dev/null | grep -q running || {
      echo "[ERROR] mysql 未运行"; exit 1;
    }
    gunzip -c "$FILE" | docker compose exec -T mysql mysql -ukid -p"${MYSQL_PASSWORD:-kid}" kid_assistant
  fi
  log "MySQL 恢复完成"
}

case "$TARGET" in
  verify)   verify_backup ;;
  postgres) restore_postgres ;;
  mysql)    restore_mysql ;;
  *)        usage ;;
esac
