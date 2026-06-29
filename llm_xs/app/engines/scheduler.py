"""定时调度引擎（C）——生产级。

适用场景
--------
需要"周期性"做某件事：每天早上给学生推送一道练习题、每隔几分钟把某些统计
刷新一次、定期清理过期数据等。这类需求就要一个调度器（scheduler）。

生产级要点（本实现都覆盖了）
---------------------------
1. **后台线程驱动**：一个调度线程负责"看表"，到点就触发，不阻塞主程序。
2. **错误隔离**：某个任务抛异常**绝不能**拖垮调度器或影响其它任务，
   异常被捕获并记录，下个周期照常继续。
3. **执行与计时分离**：任务实际运行交给线程池，长任务不会卡住"看表"线程，
   也就不会让别的任务被一起拖晚。
4. **防重叠（overlap guard）**：同一个任务上一轮还没跑完时，本轮不再重复触发，
   避免任务堆叠把系统压垮。
5. **优雅停机**：停机时不再触发新任务，并等待在跑的任务结束。

说明：这是一个"固定间隔（interval）"调度器，足够覆盖绝大多数教学/小型场景。
若需要真正的 crontab 表达式（如"每周一 8:00"），生产上一般直接用 APScheduler，
原理与本实现一致，只是把"下次时间"的计算换成 cron 解析。
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

from .util import get_logger

log = get_logger("engine.scheduler")


@dataclass
class Job:
    """一个周期性任务。"""

    name: str
    interval: float  # 触发间隔（秒）
    func: Callable[[], None]
    run_immediately: bool = False  # 注册后是否立刻先跑一次
    next_run: float = 0.0  # 下次触发的单调时钟时间（内部维护）
    running: bool = field(default=False)  # 防重叠标记（内部维护）


class SchedulerEngine:
    """固定间隔定时调度引擎。

    典型用法::

        sch = SchedulerEngine()
        sch.add_job("daily-quiz", interval=86400, func=push_daily_quiz, run_immediately=True)
        sch.start()
        ...
        sch.stop()
    """

    def __init__(self, max_workers: int = 4, tick: float = 0.5):
        self._jobs: list[Job] = []
        self._jobs_lock = threading.Lock()
        self._stop = threading.Event()
        self._tick = tick  # "看表"的精度：每 tick 秒检查一次有没有到点的任务
        self._thread: threading.Thread | None = None
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="job"
        )

    def add_job(
        self,
        name: str,
        interval: float,
        func: Callable[[], None],
        run_immediately: bool = False,
    ) -> None:
        """注册一个周期任务。``interval`` 单位为秒。"""
        if interval <= 0:
            raise ValueError("interval 必须为正数")
        now = time.monotonic()
        job = Job(
            name=name,
            interval=interval,
            func=func,
            run_immediately=run_immediately,
            next_run=now if run_immediately else now + interval,
        )
        with self._jobs_lock:
            self._jobs.append(job)
        log.info("已注册任务 '%s'，间隔 %gs，立即执行=%s", name, interval, run_immediately)

    def start(self) -> None:
        """启动调度线程。"""
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="scheduler", daemon=True
        )
        self._thread.start()
        log.info("调度引擎已启动（tick=%.2fs）", self._tick)

    def is_alive(self) -> bool:
        """健康检查：调度线程是否存活（供监护 Harness 巡检用）。"""
        return self._thread is not None and self._thread.is_alive()

    def stop(self, timeout: float | None = 10.0) -> None:
        """优雅停机：停止触发新任务，等待在跑的任务结束。"""
        if self._thread is None:
            return
        log.info("收到停机信号 …")
        self._stop.set()
        self._thread.join(timeout=timeout)
        self._thread = None
        # 关闭线程池并等待已提交的任务结束（生产环境希望任务跑完再退）。
        self._executor.shutdown(wait=True, cancel_futures=False)
        log.info("调度引擎已停止")

    def _loop(self) -> None:
        """调度主循环：周期性扫描所有任务，到点的就丢给线程池执行。"""
        while not self._stop.is_set():
            now = time.monotonic()
            with self._jobs_lock:
                due = [
                    j for j in self._jobs if now >= j.next_run and not j.running
                ]
            for job in due:
                job.running = True
                job.next_run = now + job.interval  # 先排下一次，保证节奏稳定
                self._executor.submit(self._run_job, job)
            # 用 wait 而非 sleep：停机信号能立刻打断等待，停机更跟手。
            self._stop.wait(self._tick)

    def _run_job(self, job: Job) -> None:
        """在线程池里实际运行一个任务，吞掉异常以隔离错误。"""
        start = time.monotonic()
        try:
            log.info("触发任务 '%s'", job.name)
            job.func()
            log.info("任务 '%s' 完成，耗时 %.2fs", job.name, time.monotonic() - start)
        except Exception:  # noqa: BLE001 - 错误隔离：绝不让单个任务搞垮调度器
            log.exception("任务 '%s' 执行出错（已隔离，不影响其它任务）", job.name)
        finally:
            job.running = False
