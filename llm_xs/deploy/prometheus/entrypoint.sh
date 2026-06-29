#!/bin/sh
# 根据环境变量生成 Prometheus 抓取配置并启动
set -eu

TOKEN="${KIDS_METRICS_TOKEN:-}"
TARGET="${KIDS_METRICS_TARGET:-backend:8001}"
ENV_LABEL="${KIDS_ENV:-production}"

mkdir -p /etc/prometheus

ALERTMANAGER="${ALERTMANAGER_TARGET:-alertmanager:9093}"

cat > /etc/prometheus/prometheus.yml <<EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: kid-assistant
    env: ${ENV_LABEL}

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['${ALERTMANAGER}']

rule_files:
  - /etc/prometheus/alerts.yml

scrape_configs:
  - job_name: kid-assistant-backend
    metrics_path: /api/metrics
    scheme: http
    static_configs:
      - targets: ['${TARGET}']
        labels:
          service: kid-assistant
EOF

if [ -n "$TOKEN" ]; then
  cat >> /etc/prometheus/prometheus.yml <<EOF
    http_headers:
      X-Metrics-Token:
        values: ['${TOKEN}']
EOF
fi

exec /bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --web.enable-lifecycle \
  "$@"
