"""生产级对话主循环引擎入口（loop engine D）。

与 ``run_cli.py`` 功能相同（终端里和小博士对话），但带上了生产级的
限流、单条超时、错误自愈、结构化日志与优雅退出。

用法：
    python run_chat.py
指令：/quit 退出 · /reset 新会话 · /whoami 查看身份
"""

from __future__ import annotations

from app.db import close_pool
from app.engines import ChatLoopEngine


def main() -> None:
    engine = ChatLoopEngine()
    try:
        engine.run()
    except SystemExit:
        pass
    finally:
        # 退出前关闭可能打开的数据库连接池（postgres 后端时才有意义）。
        close_pool()


if __name__ == "__main__":
    main()
