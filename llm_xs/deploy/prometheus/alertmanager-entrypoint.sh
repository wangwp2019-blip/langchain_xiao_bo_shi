#!/bin/sh
# 根据环境变量生成 Alertmanager 配置并启动
set -eu

WEBHOOK_URL="${ALERTMANAGER_WEBHOOK_URL:-}"
SLACK_URL="${ALERTMANAGER_SLACK_WEBHOOK:-}"
ENV_LABEL="${KIDS_ENV:-production}"

mkdir -p /etc/alertmanager

cat > /etc/alertmanager/alertmanager.yml <<EOF
global:
  resolve_timeout: 5m

route:
  receiver: default
  group_by: [alertname, service, env]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: critical
      repeat_interval: 1h

receivers:
  - name: default
EOF

# 通用 Webhook（钉钉/飞书/自建告警网关等，Prometheus 标准 JSON 格式）
if [ -n "$WEBHOOK_URL" ]; then
  cat >> /etc/alertmanager/alertmanager.yml <<EOF
    webhook_configs:
      - url: '${WEBHOOK_URL}'
        send_resolved: true
EOF
else
  cat >> /etc/alertmanager/alertmanager.yml <<'EOF'
    # 未配置 ALERTMANAGER_WEBHOOK_URL，仅 Web UI（:9093）
EOF
fi

cat >> /etc/alertmanager/alertmanager.yml <<EOF

  - name: critical
EOF

if [ -n "$WEBHOOK_URL" ]; then
  cat >> /etc/alertmanager/alertmanager.yml <<EOF
    webhook_configs:
      - url: '${WEBHOOK_URL}'
        send_resolved: true
EOF
fi

if [ -n "$SLACK_URL" ]; then
  cat >> /etc/alertmanager/alertmanager.yml <<EOF
    slack_configs:
      - api_url: '${SLACK_URL}'
        channel: '#kid-alerts'
        send_resolved: true
        title: '[{{ .Status | toUpper }}] {{ .CommonLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }} — {{ .Annotations.description }}{{ end }}'
EOF
fi

cat >> /etc/alertmanager/alertmanager.yml <<EOF

inhibit_rules:
  - source_matchers: [severity="critical"]
    target_matchers: [severity="warning"]
    equal: [alertname, service]
EOF

exec /bin/alertmanager \
  --config.file=/etc/alertmanager/alertmanager.yml \
  --storage.path=/alertmanager \
  "$@"
