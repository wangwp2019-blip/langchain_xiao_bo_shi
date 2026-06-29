#!/usr/bin/env bash
# Milvus 数据卷备份（docker compose --profile milvus / full 环境）
# 用法: ./scripts/backup/milvus.sh [输出路径.tar.gz]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

OUT="${1:-./backups/milvus_$(date +%Y%m%d_%H%M%S).tar.gz}"
mkdir -p "$(dirname "$OUT")"

# compose 项目名 + volume 名（默认 llm_xs_milvusdata，可通过 KIDS_MILVUS_VOLUME 覆盖）
VOLUME="${KIDS_MILVUS_VOLUME:-llm_xs_milvusdata}"

echo "[milvus-backup] 打包 volume: $VOLUME -> $OUT"
docker run --rm \
  -v "${VOLUME}:/data:ro" \
  -v "$(dirname "$(realpath "$OUT")"):/backup" \
  alpine:3.20 \
  tar czf "/backup/$(basename "$OUT")" -C /data .

echo "[milvus-backup] 导出集合元数据..."
python scripts/backup/milvus_export.py --out "$(dirname "$OUT")/milvus_meta_$(date +%Y%m%d_%H%M%S).json" || true

echo "[milvus-backup] 完成: $OUT"
