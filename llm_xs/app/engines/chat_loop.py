"""生产级对话主循环引擎（D）。

它做的事和 ``app/cli.py`` 一样——在终端里和"小博士"多轮对话，但把那个"教学版"
循环升级成"生产版"，补齐了线上长跑必须考虑的几件事：

生产级要点（本实现都覆盖了）
---------------------------
1. **会话管理**：维护 ``user_id`` / ``thread_id``，支持 ``/reset`` 开新会话、
   ``/whoami`` 查看当前身份、``/quit`` 退出。
2. **限流（令牌桶）**：防止用户/脚本疯狂刷屏把后端打爆（见 util.RateLimiter）。
3. **单条超时**：一条消息处理超过阈值就中断本轮，提示用户重试，不让界面卡死。
4. **错误自愈**：任何一条消息出错都被捕获，循环继续存活，绝不因一次异常退出。
5. **可观测**：每条消息记录耗时、是否出错的结构化日志，便于排查与统计。
6. **优雅退出**：Ctrl+C / EOF 时打印告别语并干净退出。

注意：这里用阻塞式（非流式）的 ``ask`` 以便配合"软超时"。需要打字机效果时，
可参考 ``cli.py`` 的 ``stream_answer``；流式下的超时改为"迭代时检查截止时间"。
"""

from __future__ import annotations

import time
import uuid

from ..config import settings
from .util import RateLimiter, TimeoutError_, get_logger, run_with_timeout

log = get_logger("engine.chat")


class ChatLoopEngine:
    """生产级命令行对话主循环。"""

    def __init__(
        self,
        user_id: str = "default-student",
        rate_limit_per_min: int | None = None,
        timeout_seconds: float | None = None,
    ):
        self._user_id = user_id
        self._thread_id = self._new_thread_id()
        self._limiter = RateLimiter(
            rate_limit_per_min or settings.chat_rate_limit_per_min
        )
        self._timeout = timeout_seconds or settings.chat_timeout_seconds

    @staticmethod
    def _new_thread_id() -> str:
        return f"chat-{uuid.uuid4().hex[:8]}"

    def _print_banner(self) -> None:
        print("=" * 50)
        print("  小博士 · 生产级对话循环（loop engine D）")
        print("=" * 50)
        print(f"  限流：{settings.chat_rate_limit_per_min} 条/分钟   "
              f"单条超时：{self._timeout:.0f}s")
        print("  指令：/quit 退出 · /reset 新会话 · /whoami 查看身份")
        print("=" * 50)

    def run(self) -> None:
        """启动对话主循环（阻塞，直到用户退出）。"""
        self._print_banner()
        nickname = input("先告诉我你的昵称（直接回车用默认）：").strip()
        if nickname:
            self._user_id = nickname

        while True:
            try:
                question = input("\n你：").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n小博士：下次再聊呀，拜拜！")
                return

            if not question:
                continue
            if self._handle_command(question):
                continue

            self._handle_message(question)

    def _handle_command(self, text: str) -> bool:
        """处理以 / 开头的指令；返回 True 表示已处理（本轮不再当作提问）。"""
        if text == "/quit":
            print("小博士：下次再聊呀，拜拜！")
            raise SystemExit(0)
        if text == "/reset":
            self._thread_id = self._new_thread_id()
            print(f"小博士：好的，开启新会话啦！(thread={self._thread_id})")
            return True
        if text == "/whoami":
            print(f"小博士：你是 {self._user_id}，当前会话 thread={self._thread_id}")
            return True
        return False

    def _handle_message(self, question: str) -> None:
        """处理一条普通提问：限流 -> 超时调用 Agent -> 错误自愈 -> 记录日志。"""
        # 1) 限流：取不到令牌就提示稍后再试，不把请求压给后端。
        if not self._limiter.try_acquire():
            print("小博士：你问得太快啦，休息一下下再问我好不好？🍵")
            log.warning("user=%s 触发限流", self._user_id)
            return

        start = time.monotonic()
        try:
            # 2) 软超时：包一层，避免单条消息无限期卡住界面。
            from ..agent import ask

            answer = run_with_timeout(
                lambda: ask(
                    question, user_id=self._user_id, thread_id=self._thread_id
                ),
                timeout=self._timeout,
            )
            elapsed = time.monotonic() - start
            print(f"小博士：{answer}")
            log.info("user=%s 回答完成，耗时%.2fs", self._user_id, elapsed)
        except TimeoutError_:
            # 3a) 超时自愈：提示用户，循环继续。
            print("小博士：这道题有点难，我想久了～你再问我一次好吗？⏳")
            log.error("user=%s 处理超时（>%.0fs）", self._user_id, self._timeout)
        except Exception as exc:  # noqa: BLE001
            # 3b) 任意异常自愈：绝不让循环因为一次出错而退出。
            print(f"小博士：哎呀，刚刚出了点小问题（{type(exc).__name__}），我们再试一次吧！")
            log.exception("user=%s 处理消息出错", self._user_id)
