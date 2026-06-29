"""引擎共用的基础工具：日志、限流、退避、超时。

这些都是"生产级"代码里反复出现的小零件，单独抽出来便于三个引擎复用，
也方便新手逐个理解。每个工具都尽量保持简单、可读、线程安全。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from ..config import settings

_LOG_CONFIGURED = False
_LOG_LOCK = threading.Lock()


def get_logger(name: str) -> logging.Logger:
    """返回带统一格式的 logger（首次调用时配置全局日志）。

    生产代码用 ``logging`` 而不是 ``print``：可以分级别（INFO/WARNING/ERROR）、
    带时间戳和线程名，方便排查"什么时候、哪个线程、发生了什么"。
    """
    global _LOG_CONFIGURED
    if not _LOG_CONFIGURED:
        with _LOG_LOCK:
            if not _LOG_CONFIGURED:
                logging.basicConfig(
                    level=getattr(logging, settings.log_level.upper(), logging.INFO),
                    format="%(asctime)s | %(levelname)-7s | %(threadName)-12s | %(name)s | %(message)s",
                    datefmt="%H:%M:%S",
                )
                _LOG_CONFIGURED = True
    return logging.getLogger(name)


class RateLimiter:
    """令牌桶限流器（线程安全）。

    原理：桶里最多装 ``capacity`` 个令牌，按 ``refill_rate`` 个/秒匀速补充。
    每处理一条请求消耗一个令牌；桶空了就说明"太快了"，需要等待或拒绝。

    令牌桶相比"每分钟计数器"的好处是**允许突发**：攒下的令牌可以一次性用掉，
    同时长期平均速率又被限制住，体验更平滑。
    """

    def __init__(self, rate_per_minute: int, capacity: int | None = None):
        # 每分钟 rate 个 -> 每秒补充 rate/60 个令牌。
        self._refill_rate = max(rate_per_minute, 1) / 60.0
        self._capacity = float(capacity if capacity is not None else max(rate_per_minute, 1))
        self._tokens = self._capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        self._last = now
        # 按流逝时间补充令牌，但不超过桶容量。
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)

    def try_acquire(self) -> bool:
        """尝试取一个令牌：成功返回 True，桶空返回 False（不阻塞）。"""
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    def acquire(self, timeout: float | None = None) -> bool:
        """阻塞取令牌：取到返回 True；超过 ``timeout`` 秒仍取不到返回 False。"""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                # 还差多少令牌、预计要等多久。
                need = 1.0 - self._tokens
                wait = need / self._refill_rate
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                wait = min(wait, remaining)
            time.sleep(max(wait, 0.01))


def backoff_delay(attempt: int, base: float, cap: float = 60.0) -> float:
    """计算指数退避时间（秒）：base * 2**attempt，封顶 cap。

    ``attempt`` 从 0 开始。指数退避能在依赖临时抖动时避免"重试风暴"，
    给下游（数据库 / 模型 API）喘息和恢复的时间。
    """
    return min(cap, base * (2 ** max(attempt, 0)))


class TimeoutError_(Exception):
    """单次调用超时。"""


def run_with_timeout(func: Callable[[], Any], timeout: float) -> Any:
    """在子线程里运行 ``func``，最多等 ``timeout`` 秒，超时抛 ``TimeoutError_``。

    说明（重要，新手必读）：Python 无法安全地"杀死"一个线程，所以这里的超时是
    **软超时**——超时后主线程不再等待并抛错，但后台那次调用其实还在继续跑完。
    它的价值在于"不让调用方被无限期卡住"。要硬隔离/可中断，需用独立进程或
    支持取消的异步框架，那是更重的方案，本教程不展开。
    """
    box: dict[str, Any] = {}
    done = threading.Event()

    def runner() -> None:
        try:
            box["result"] = func()
        except Exception as exc:  # noqa: BLE001 - 透传给调用方
            box["error"] = exc
        finally:
            done.set()

    t = threading.Thread(target=runner, name="timeout-call", daemon=True)
    t.start()
    if not done.wait(timeout):
        raise TimeoutError_(f"调用超过 {timeout} 秒未完成")
    if "error" in box:
        raise box["error"]
    return box.get("result")
