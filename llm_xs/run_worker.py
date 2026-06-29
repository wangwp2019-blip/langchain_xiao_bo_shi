"""任务队列后台 Worker 引擎入口（loop engine A）。

演示：往队列里投放几道"学生提问"，多线程后台并发处理，
失败自动重试，最后优雅停机并打印结果汇总。

用法：
    python run_worker.py

生产中，``submit`` 的来源通常是消息队列（Redis/RabbitMQ/Kafka）或 HTTP 接口，
这里用几条示例任务代替，便于直接观察引擎行为。按 Ctrl+C 可随时优雅停机。
"""

from __future__ import annotations

import signal

from app.db import close_pool
from app.engines import Task, TaskResult, TaskWorkerEngine


def main() -> None:
    def on_result(r: TaskResult) -> None:
        flag = "✅" if r.ok else "❌"
        head = (r.answer or r.error or "")[:60].replace("\n", " ")
        print(f"  {flag} task={r.task_id} 尝试{r.attempts}次 耗时{r.elapsed:.2f}s | {head}")

    engine = TaskWorkerEngine(on_result=on_result)

    # 捕获 Ctrl+C / kill，触发优雅停机（drain：把已排队任务做完）。
    def _graceful(*_):
        print("\n[信号] 开始优雅停机 …")
        engine.stop(drain=True, timeout=30)
        close_pool()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _graceful)
    try:
        signal.signal(signal.SIGTERM, _graceful)
    except (AttributeError, ValueError):
        pass  # Windows 上 SIGTERM 支持有限，忽略即可

    engine.start()

    demo_tasks = [
        "太阳系有几大行星？",
        "帮我算一下 (25 + 17) * 3",
        "今天星期几？",
        "长方形的面积怎么算？",
        "过马路要注意什么？",
    ]
    print(f"[投放] 共 {len(demo_tasks)} 个任务入队 …")
    for q in demo_tasks:
        engine.submit(Task(question=q, user_id="worker-demo"))

    # 等队列处理完后优雅停机（drain=True 会先把剩余任务做完）。
    engine.stop(drain=True, timeout=60)
    close_pool()

    results = engine.results()
    ok = sum(1 for r in results if r.ok)
    print(f"\n[汇总] 成功 {ok}/{len(results)} 个任务。")


if __name__ == "__main__":
    main()
