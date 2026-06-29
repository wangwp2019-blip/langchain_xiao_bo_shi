#!/usr/bin/env bash
# MySQL 备份（docker compose --profile mysql 环境）
set -euo pipefail
OUT="${1:-./backups/mysql_$(date +%Y%m%d_%H%M%S).sql.gz}"
mkdir -p "$(dirname "$OUT")"
docker compose exec -T mysql mysqldump -ukid -pkid kid_assistant | gzip > "$OUT"
echo "备份完成: $OUT"
