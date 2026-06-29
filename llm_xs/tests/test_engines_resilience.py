"""S6 · 循环引擎与弹性重试。"""

from __future__ import annotations

import time

import pytest

from app.engines import SchedulerEngine, Task, TaskWorkerEngine
from app.engines.util import RateLimiter, TimeoutError_, backoff_delay, run_with_timeout
from app.resilience import invoke_with_retry


def test_backoff_delay():
    assert backoff_delay(0, 1.0) == 1.0
    assert backoff_delay(2, 1.0) == 4.0


def test_rate_limiter():
    rl = RateLimiter(rate_per_minute=60, capacity=2)
    assert rl.try_acquire()
    assert rl.try_acquire()
    assert not rl.try_acquire()


def test_run_with_timeout_success():
    assert run_with_timeout(lambda: 42, timeout=1) == 42


def test_run_with_timeout_raises():
    with pytest.raises(TimeoutError_):
        run_with_timeout(lambda: time.sleep(2), timeout=0.2)


def test_invoke_with_retry_recovers():
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectionError("模拟网络失败")
        return "ok"

    result = invoke_with_retry(
        flaky,
        max_retries=2,
        base_delay=0.01,
        retry_on=(ConnectionError,),
    )
    assert result == "ok"
    assert calls["n"] == 2


def test_task_worker_retry():
    calls: dict[str, int] = {}

    def flaky(task: Task) -> str:
        calls[task.id] = calls.get(task.id, 0) + 1
        if calls[task.id] < 2:
            raise RuntimeError("模拟失败")
        return "ok"

    w = TaskWorkerEngine(concurrency=2, retry_base_delay=0.02, handler=flaky)
    w.start()
    tid = w.submit(Task(question="q", max_retries=2))
    w.stop(drain=True, timeout=10)
    results = {x.task_id: x for x in w.results()}
    assert results[tid].ok
    assert results[tid].attempts >= 2


def test_scheduler_engine():
    hb = {"n": 0}

    def heartbeat() -> None:
        hb["n"] += 1

    sch = SchedulerEngine(tick=0.05)
    sch.add_job("hb", interval=0.1, func=heartbeat, run_immediately=True)
    sch.start()
    time.sleep(0.35)
    sch.stop(timeout=5)
    assert hb["n"] >= 2
