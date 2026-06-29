"""Prometheus 告警规则文件完整性（不启动 Prometheus）。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALERTS = ROOT / "deploy" / "prometheus" / "alerts.yml"
ENTRYPOINT = ROOT / "deploy" / "prometheus" / "entrypoint.sh"
ALERTMANAGER = ROOT / "deploy" / "prometheus" / "alertmanager.yml"

CORE_ALERTS = (
    "KidHighErrorRate",
    "KidHighRateLimit",
    "KidAuditWriteFailures",
    "KidBackendDown",
    "KidHighLatencyP95",
)


def test_alerts_yml_contains_core_rules():
    text = ALERTS.read_text(encoding="utf-8")
    for name in CORE_ALERTS:
        assert name in text, f"missing alert rule: {name}"


def test_prometheus_entrypoint_wires_alertmanager():
    text = ENTRYPOINT.read_text(encoding="utf-8")
    assert "alertmanagers:" in text
    assert "rule_files:" in text
    assert "alerts.yml" in text


def test_alertmanager_config_exists():
    text = ALERTMANAGER.read_text(encoding="utf-8")
    assert "receivers:" in text
    assert "route:" in text


def test_alertmanager_entrypoint_supports_webhooks():
    path = ROOT / "deploy" / "prometheus" / "alertmanager-entrypoint.sh"
    text = path.read_text(encoding="utf-8")
    assert "ALERTMANAGER_WEBHOOK_URL" in text
    assert "ALERTMANAGER_SLACK_WEBHOOK" in text
    assert "webhook_configs" in text
