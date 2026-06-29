"""任务队列后台 Worker 引擎（A）——生产级。

适用场景
--------
当"提问"不需要立刻同步返回，而是可以排队、异步处理时（例如批量给一个班级的
学生生成学习卡片、夜间批量预生成答案、削峰填谷），就需要一个后台 Worker：
它常驻运行，不断从队列里拉任务，交给 Agent 处理，处理完把结果存起来或回调。

生产级要点（本实现都覆盖了）
---------------------------
1. **有界队列**：``maxsize`` 限制堆积量，避免内存被无限撑爆（背压）。
2. **多线程并发**：``concurrency`` 个 worker 同时处理，吞吐可调。
3. **失败重试 + 指数退避**：临时故障（如模型 API 抖动）自动重试，越退越久，
   避免"重试风暴"压垮下游。
4. **优雅停机**：收到停止信号后，不再接新任务，把"正在处理 / 已排队"的尽量做完
   （可选 drain），再退出，不丢任务、不留半截状态。
5. **结构化日志 + 结果回收**：每个任务有 id，成功/失败、耗时、重试次数都可观测。

设计为"通用引擎"：默认处理函数调用 ``agent.ask``，也可注入自定义 ``handler``，
所以它不仅能跑本项目的 Agent，理解后可直接迁移到别的后台任务系统。
"""

from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

from ..config import settings
from .util import backoff_delay, get_logger

log = get_logger("engine.worker")


@dataclass
class Task:
    """一条待处理任务。"""

    question: str
    user_id: str = "default-student"
    thread_id: str = "default-thread"
    max_retries: int = 3
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


@dataclass
class TaskResult:
    """一条任务的处理结果。"""

    task_id: str
    ok: bool
    answer: str | None = None
    error: str | None = None
    attempts: int = 0
    elapsed: float = 0.0


# 处理函数签名：给一个 Task，返回答案文本。默认实现见 _default_handler。
Handler = Callable[[Task], str]


def _default_handler(task: Task) -> str:
    """默认处理函数：调用本项目的 Agent 回答问题。"""
    from ..agent import ask

    return ask(task.question, user_id=task.user_id, thread_id=task.thread_id)


class TaskWorkerEngine:
    """任务队列后台 Worker 引擎。

    典型用法::

        engine = TaskWorkerEngine()
        engine.start()
        engine.submit(Task(question="太阳系有几大行星？"))
        ...
        engine.stop(drain=True)        # 优雅停机：把队列里剩余任务做完
        for r in engine.results():     # 取回所有结果
            print(r)
    """

    def __init__(
        self,
        concurrency: int | None = None,
        max_queue: int | None = None,
        retry_base_delay: float | None = None,
        handler: Handler | None = None,
        on_result: Callable[[TaskResult], None] | None = None,
    ):
        self._concurrency = concurrency or settings.worker_concurrency
        self._queue: "queue.Queue[Task | None]" = queue.Queue(
            maxsize=max_queue or settings.worker_max_queue
        )
        self._retry_base_delay = (
            retry_base_delay
            if retry_base_delay is not None
            else settings.worker_retry_base_delay
        )
        self._handler = handler or _default_handler
        self._on_result = on_result

        self._threads: list[threading.Thread] = []
        self._stopping = threading.Event()  # 置位后 worker 不再领新任务
        self._results: list[TaskResult] = []
        self._results_lock = threading.Lock()
        self._started = False

    # ---------------- 对外接口 ----------------

    def start(self) -> None:
        """启动 worker 线程池。"""
        if self._started:
            return
        self._started = True
        self._stopping.clear()
        for i in range(self._concurrency):
            t = threading.Thread(
                target=self._worker_loop, name=f"worker-{i}", daemon=True
            )
            t.start()
            self._threads.append(t)
        log.info("Worker 引擎已启动，并发数=%d", self._concurrency)

    def submit(self, task: Task, block: bool = True, timeout: float | None = None) -> str:
        """提交一个任务，返回 task_id。

        队列满时：``block=True`` 则最多等待 ``timeout`` 秒（背压），
        否则立刻抛出 ``queue.Full``。
        """
        if self._stopping.is_set():
            raise RuntimeError("引擎正在停机，拒绝新任务")
        self._queue.put(task, block=block, timeout=timeout)
        log.debug("已入队 task=%s（队列长度≈%d）", task.id, self._queue.qsize())
        return task.id

    def stop(self, drain: bool = True, timeout: float | None = None) -> None:
        """优雅停机。

        - ``drain=True``：先把队列里**已排队**的任务处理完，再退出。
        - ``drain=False``：尽快退出，丢弃未开始的排队任务（已在处理的仍会做完）。
        """
        if not self._started:
            return
        log.info("收到停机信号，drain=%s …", drain)

        if drain:
            self._queue.join()  # 阻塞直到队列中所有任务都被标记完成

        # 通知所有 worker 退出：置停止位 + 投放 None 哨兵唤醒阻塞中的 get()。
        self._stopping.set()
        for _ in self._threads:
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass

        for t in self._threads:
            t.join(timeout=timeout)
        self._threads.clear()
        self._started = False
        log.info("Worker 引擎已停止，累计结果 %d 条", len(self._results))

    def results(self) -> list[TaskResult]:
        """返回已完成任务的结果快照。"""
        with self._results_lock:
            return list(self._results)

    def is_running(self) -> bool:
        """健康检查：是否已启动且至少有一个 worker 线程存活。

        供运行时监护 Harness（Supervisor）巡检用——若返回 False，说明引擎
        异常退出，监护器可据此重启它。
        """
        return self._started and any(t.is_alive() for t in self._threads)

    # ---------------- 内部逻辑 ----------------

    def _worker_loop(self) -> None:
        """单个 worker 的主循环：取任务 -> 处理（带重试）-> 记录结果。"""
        while True:
            try:
                task = self._queue.get(timeout=0.5)
            except queue.Empty:
                # 没任务时：若已停机就退出，否则继续等。
                if self._stopping.is_set():
                    return
                continue

            if task is None:  # 哨兵：要求退出
                self._queue.task_done()
                return

            try:
                result = self._process_with_retry(task)
                self._record(result)
            finally:
                # 无论成功失败都要 task_done，否则 stop(drain=True) 的 join() 永不返回。
                self._queue.task_done()

    def _process_with_retry(self, task: Task) -> TaskResult:
        """处理单个任务，失败按指数退避重试，直到成功或用尽次数。"""
        start = time.monotonic()
        last_error = ""
        for attempt in range(task.max_retries + 1):
            # 停机时不再发起新的重试，尽快收尾。
            if attempt > 0 and self._stopping.is_set():
                break
            try:
                answer = self._handler(task)
                elapsed = time.monotonic() - start
                log.info(
                    "task=%s 成功（第%d次尝试，耗时%.2fs）", task.id, attempt + 1, elapsed
                )
                return TaskResult(
                    task_id=task.id,
                    ok=True,
                    answer=answer,
                    attempts=attempt + 1,
                    elapsed=elapsed,
                )
            except Exception as exc:  # noqa: BLE001 - 引擎要兜住一切异常，保证不崩
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < task.max_retries:
                    delay = backoff_delay(attempt, self._retry_base_delay)
                    log.warning(
                        "task=%s 第%d次失败：%s；%.1fs 后重试",
                        task.id, attempt + 1, last_error, delay,
                    )
                    # 退避期间也要能被停机打断，避免停机时还在长睡。
                    if self._stopping.wait(delay):
                        break
                else:
                    log.error("task=%s 重试耗尽，最终失败：%s", task.id, last_error)

        return TaskResult(
            task_id=task.id,
            ok=False,
            error=last_error or "未知错误",
            attempts=task.max_retries + 1,
            elapsed=time.monotonic() - start,
        )

    def _record(self, result: TaskResult) -> None:
        with self._results_lock:
            self._results.append(result)
        if self._on_result is not None:
            try:
                self._on_result(result)
            except Exception:  # noqa: BLE001 - 回调出错不影响引擎
                log.exception("on_result 回调出错")
