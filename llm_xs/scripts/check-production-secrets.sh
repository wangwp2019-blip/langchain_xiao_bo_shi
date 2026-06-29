#!/usr/bin/env bash
# 生产/灰度启动前校验：弱口令、必填项、TLS 证书
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${1:-.env.prod}"
FAIL=0

warn() { echo "[WARN] $*"; }
err()  { echo "[ERROR] $*"; FAIL=1; }
ok()   { echo "[OK]   $*"; }

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  ok "已加载 $ENV_FILE"
else
  warn "未找到 $ENV_FILE，仅检查环境变量与文件"
fi

check_nonempty() {
  local name="$1" val="${!1:-}"
  if [[ -z "$val" ]]; then
    err "$name 未设置"
  elif [[ "$val" == *"replace-"* ]] || [[ "$val" == "change-me"* ]]; then
    err "$name 仍为占位符: $val"
  else
    ok "$name 已配置"
  fi
}

for var in KIDS_API_KEYS KIDS_INGEST_TOKEN KIDS_RETENTION_SWEEP_TOKEN \
           KIDS_CORS_ORIGINS KIDS_METRICS_TOKEN; do
  check_nonempty "$var"
done

if [[ "${POSTGRES_PASSWORD:-kid}" == "kid" ]] || [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
  err "POSTGRES_PASSWORD 仍为默认值 kid 或未设置"
else
  ok "POSTGRES_PASSWORD 已自定义"
fi

if [[ "${MYSQL_PASSWORD:-kid}" == "kid" ]]; then
  warn "MYSQL_PASSWORD 仍为 kid（若启用 MySQL 请修改）"
fi

if [[ "${KIDS_CORS_ORIGINS:-}" == "*" ]]; then
  err "KIDS_CORS_ORIGINS 不能为 *"
fi

CERT_DIR="${TLS_CERT_DIR:-./deploy/certs}"
if [[ -f "$CERT_DIR/fullchain.pem" ]] && [[ -f "$CERT_DIR/privkey.pem" ]]; then
  ok "TLS 证书存在: $CERT_DIR"
else
  warn "TLS 证书未找到（HTTP 灰度可跳过；公网需 ./scripts/tls/generate-self-signed.sh）"
fi

if [[ $FAIL -ne 0 ]]; then
  echo ""
  echo "校验失败。请复制 .env.prod.example -> .env.prod 并填写强随机值。"
  exit 1
fi

echo ""
echo "密钥校验通过，可执行灰度部署。"
