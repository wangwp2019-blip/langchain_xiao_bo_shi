"""Prometheus 指标（prometheus_client + Gunicorn 多进程聚合）。"""

from __future__ import annotations

import os
import time

_START = time.time()
_multiproc_dir: str | None = None

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Histogram,
        Gauge,
        generate_latest,
        multiprocess,
    )

    _HAS_PROM = True
except ImportError:  # pragma: no cover - 生产镜像必装
    _HAS_PROM = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"

if _HAS_PROM:
    REQUESTS = Counter(
        "kid_requests_total",
        "Total HTTP requests",
        ["path", "status", "method"],
    )
    DURATION = Histogram(
        "kid_request_duration_seconds",
        "Request latency in seconds",
        ["path"],
        buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")),
    )
    AUDIT_FAILURES = Counter(
        "kid_audit_write_failures_total",
        "MySQL audit write failures",
    )
    UPTIME = Gauge("kid_uptime_seconds", "Process uptime in seconds")
    WORKERS = Gauge("kid_gunicorn_workers", "Configured Gunicorn worker count")


def init_multiproc_dir() -> str | None:
    """Gunicorn master 启动前清空 multiproc 目录（prometheus_client 要求）。"""
    global _multiproc_dir
    d = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not d:
        return None
    os.makedirs(d, exist_ok=True)
    for name in os.listdir(d):
        path = os.path.join(d, name)
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass
    _multiproc_dir = d
    return d


def mark_worker_dead(pid: int) -> None:
    if _HAS_PROM and os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        multiprocess.mark_process_dead(pid)


def record_request(path: str, status: int, duration: float, *, method: str = "GET") -> None:
    if not _HAS_PROM:
        return
    REQUESTS.labels(path=path, status=str(status), method=method).inc()
    DURATION.labels(path=path).observe(duration)


def record_audit_failure() -> None:
    if _HAS_PROM:
        AUDIT_FAILURES.inc()


def _registry():
    if _HAS_PROM and os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return registry
    from prometheus_client import REGISTRY

    return REGISTRY


def render() -> str:
    if not _HAS_PROM:
        return (
            "# HELP kid_uptime_seconds Process uptime.\n"
            "# TYPE kid_uptime_seconds gauge\n"
            f"kid_uptime_seconds {time.time() - _START:.1f}\n"
        )
    UPTIME.set(time.time() - _START)
    workers = int(os.environ.get("WEB_CONCURRENCY", "1") or "1")
    WORKERS.set(workers)
    return generate_latest(_registry()).decode("utf-8")


def content_type() -> str:
    return CONTENT_TYPE_LATEST if _HAS_PROM else "text/plain; version=0.0.4"
