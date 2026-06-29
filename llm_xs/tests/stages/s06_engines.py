"""S6 · 循环引擎（离线，假 handler）。"""

from __future__ import annotations

import time

from app.engines import SchedulerEngine, Task, TaskWorkerEngine
from app.engines.util import RateLimiter, TimeoutError_, backoff_delay, run_with_timeout


def run() -> None:
    assert backoff_delay(0, 1.0) == 1.0
    assert backoff_delay(2, 1.0) == 4.0
    print("backoff_delay OK")

    rl = RateLimiter(rate_per_minute=60, capacity=2)
    assert rl.try_acquire() and rl.try_acquire() and not rl.try_acquire()
    print("RateLimiter OK")

    assert run_with_timeout(lambda: 42, timeout=1) == 42
    try:
        run_with_timeout(lambda: time.sleep(2), timeout=0.2)
        raise AssertionError("应超时")
    except TimeoutError_:
        print("run_with_timeout 超时 OK")

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
    r = {x.task_id: x for x in w.results()}[tid]
    assert r.ok and r.attempts == 2
    print("TaskWorkerEngine 重试 OK")

    hb = {"n": 0}

    def heartbeat() -> None:
        hb["n"] += 1

    sch = SchedulerEngine(tick=0.05)
    sch.add_job("hb", interval=0.1, func=heartbeat, run_immediately=True)
    sch.start()
    time.sleep(0.35)
    sch.stop(timeout=5)
    assert hb["n"] >= 2
    print(f"SchedulerEngine 触发 {hb['n']} 次 OK")
