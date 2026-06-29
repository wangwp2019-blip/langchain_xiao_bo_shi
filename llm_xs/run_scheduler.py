"""定时调度引擎入口（loop engine C）。

演示：注册两个周期任务——
1. 每 15 秒给"今天的练习题"做一次刷新（调用 Agent 出一道题）。
2. 每 5 秒打印一次心跳，证明调度器在稳定运转。

用法：
    python run_scheduler.py
按 Ctrl+C 触发优雅停机（等待在跑的任务结束）。

生产中常见任务：每天给学生推一道练习题、定时清理过期会话、周期性刷新统计等。
把 interval 调大、把 func 换成你的业务函数即可。
"""

from __future__ import annotations

import signal
import time

from app.db import close_pool
from app.engines import SchedulerEngine

_counter = {"n": 0}


def push_daily_quiz() -> None:
    """示例任务：让 Agent 出一道适合小学生的练习题。"""
    from app.agent import ask

    _counter["n"] += 1
    question = ask(
        "请出一道适合小学三年级、和今天主题相关的趣味练习题，只要题目本身。",
        user_id="scheduler",
        thread_id=f"quiz-{_counter['n']}",
    )
    print(f"\n[每日一练 #{_counter['n']}] {question[:80].strip()} …\n")


def heartbeat() -> None:
    """示例任务：心跳，证明调度器仍在运转。"""
    print(f"[心跳] {time.strftime('%H:%M:%S')} 调度器运行中 …")


def main() -> None:
    sch = SchedulerEngine()
    sch.add_job("heartbeat", interval=5, func=heartbeat, run_immediately=True)
    sch.add_job("daily-quiz", interval=15, func=push_daily_quiz, run_immediately=True)

    def _graceful(*_):
        print("\n[信号] 开始优雅停机 …")
        sch.stop(timeout=30)
        close_pool()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _graceful)
    try:
        signal.signal(signal.SIGTERM, _graceful)
    except (AttributeError, ValueError):
        pass

    sch.start()
    print("调度引擎已启动，按 Ctrl+C 退出。")

    # 主线程保持存活，让后台调度线程持续工作。
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _graceful()


if __name__ == "__main__":
    main()
