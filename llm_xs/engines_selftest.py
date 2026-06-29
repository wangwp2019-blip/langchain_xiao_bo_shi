"""引擎离线自测：用假处理函数验证引擎机制，不调用真实 API。"""

from __future__ import annotations

import time


def section(t: str) -> None:
    print("\n" + "=" * 52 + "\n" + t + "\n" + "=" * 52)


def main() -> None:
    from app.engines import SchedulerEngine, Task, TaskWorkerEngine
    from app.engines.util import RateLimiter, backoff_delay, run_with_timeout, TimeoutError_

    section("[1] util：退避 / 限流 / 软超时")
    assert backoff_delay(0, 1.0) == 1.0
    assert backoff_delay(1, 1.0) == 2.0
    assert backoff_delay(2, 1.0) == 4.0
    assert backoff_delay(100, 1.0, cap=60) == 60.0
    print("backoff_delay OK:", [backoff_delay(i, 1.0) for i in range(4)])

    rl = RateLimiter(rate_per_minute=60, capacity=2)
    got = [rl.try_acquire() for _ in range(4)]
    print("RateLimiter 容量2，连取4次:", got)
    assert got[:2] == [True, True] and got[2] is False

    assert run_with_timeout(lambda: 42, timeout=1) == 42
    try:
        run_with_timeout(lambda: time.sleep(2), timeout=0.3)
        raise AssertionError("应当超时")
    except TimeoutError_:
        print("run_with_timeout 超时分支 OK")

    section("[2] TaskWorkerEngine：并发 + 重试 + 优雅停机")
    calls: dict[str, int] = {}

    def flaky_handler(task: Task) -> str:
        # 前两次失败，第三次成功，用来验证重试 + 退避。
        calls[task.id] = calls.get(task.id, 0) + 1
        if calls[task.id] < 3:
            raise RuntimeError(f"模拟第{calls[task.id]}次失败")
        return f"答案:{task.question}"

    engine = TaskWorkerEngine(
        concurrency=3, retry_base_delay=0.05, handler=flaky_handler
    )
    engine.start()
    ids = [engine.submit(Task(question=f"q{i}", max_retries=3)) for i in range(5)]
    engine.stop(drain=True, timeout=10)
    results = {r.task_id: r for r in engine.results()}
    print(f"提交{len(ids)}个，完成{len(results)}个")
    assert len(results) == 5
    for tid in ids:
        r = results[tid]
        assert r.ok, f"{tid} 应当最终成功"
        assert r.attempts == 3, f"{tid} 应当尝试3次，实际{r.attempts}"
    print("全部任务重试3次后成功 OK，示例:", results[ids[0]])

    section("[3] TaskWorkerEngine：重试耗尽 -> 失败结果")
    def always_fail(task: Task) -> str:
        raise ValueError("永远失败")

    e2 = TaskWorkerEngine(concurrency=1, retry_base_delay=0.01, handler=always_fail)
    e2.start()
    e2.submit(Task(question="boom", max_retries=2))
    e2.stop(drain=True, timeout=10)
    r = e2.results()[0]
    print("失败结果:", r)
    assert r.ok is False and r.attempts == 3 and "永远失败" in (r.error or "")
    print("重试耗尽分支 OK")

    section("[4] SchedulerEngine：周期触发 + 错误隔离 + 防重叠")
    hb = {"n": 0}
    err = {"n": 0}

    def heartbeat() -> None:
        hb["n"] += 1

    def boom() -> None:
        err["n"] += 1
        raise RuntimeError("任务内部错误（应被隔离）")

    sch = SchedulerEngine(tick=0.05)
    sch.add_job("hb", interval=0.1, func=heartbeat, run_immediately=True)
    sch.add_job("boom", interval=0.1, func=boom, run_immediately=True)
    sch.start()
    time.sleep(0.65)
    sch.stop(timeout=5)
    print(f"心跳触发 {hb['n']} 次，报错任务触发 {err['n']} 次（均被隔离）")
    assert hb["n"] >= 3, "心跳应被多次触发"
    assert err["n"] >= 3, "报错任务也应被多次触发且不影响调度器"
    print("调度器错误隔离 OK（报错任务没有拖垮调度循环）")

    section("[5] db.close_pool：未配置 postgres 时空跑不报错")
    from app.db import close_pool

    close_pool()  # 没创建过池，应安静返回
    print("close_pool 幂等空跑 OK")

    print("\n>>> 引擎离线自测全部通过（未调用任何外部 API）。")


if __name__ == "__main__":
    main()
