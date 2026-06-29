#!/usr/bin/env bash
# Postgres 备份（docker compose --profile full 环境）
set -euo pipefail
OUT="${1:-./backups/postgres_$(date +%Y%m%d_%H%M%S).sql.gz}"
mkdir -p "$(dirname "$OUT")"
docker compose exec -T postgres pg_dump -U kid kid_assistant | gzip > "$OUT"
echo "备份完成: $OUT"
