"""Gunicorn + UvicornWorker 生产进程配置。

多 worker 下，短期/长期记忆与限流务必使用外部后端（PostgreSQL / Redis），
否则状态无法跨进程共享。worker 数由 WEB_CONCURRENCY 控制。

Prometheus 多进程：设置 PROMETHEUS_MULTIPROC_DIR 后，/api/metrics 自动聚合各 worker。
"""

import os

bind = f"0.0.0.0:{os.getenv('KIDS_API_PORT', '8001')}"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
worker_class = "uvicorn.workers.UvicornWorker"
timeout = int(os.getenv("KIDS_GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("KIDS_LOG_LEVEL", "info").lower()


def on_starting(server) -> None:
    from app.metrics import init_multiproc_dir

    init_multiproc_dir()


def child_exit(server, worker) -> None:
    from app.metrics import mark_worker_dead

    mark_worker_dead(worker.pid)
