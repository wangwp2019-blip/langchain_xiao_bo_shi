#!/usr/bin/env bash
# 生成自签 TLS 证书（开发/内网灰度），输出到 deploy/certs/
set -euo pipefail

DOMAIN="${1:-localhost}"
OUT_DIR="$(cd "$(dirname "$0")/../.." && pwd)/deploy/certs"
DAYS="${2:-365}"

mkdir -p "$OUT_DIR"
openssl req -x509 -nodes -days "$DAYS" -newkey rsa:2048 \
  -keyout "$OUT_DIR/privkey.pem" \
  -out "$OUT_DIR/fullchain.pem" \
  -subj "/CN=${DOMAIN}/O=KidAssistant/C=CN"

echo "已生成: $OUT_DIR/fullchain.pem"
echo "       $OUT_DIR/privkey.pem"
echo "启动: TLS_CERT_DIR=./deploy/certs docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d nginx"
