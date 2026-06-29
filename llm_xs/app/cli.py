"""命令行交互入口：在终端里和"小博士"对话（流式打字机效果）。

支持指令：
- ``/quit``  退出
- ``/reset`` 开启新会话（清空当前对话短期记忆，长期记忆仍保留）
"""

from __future__ import annotations

import uuid

from .agent import stream_answer
from .config import settings
from .vector_store import get_vector_store


def _print_banner() -> None:
    print("=" * 46)
    print("  小博士 - 小学生 AI 学习伙伴（命令行版）")
    print("=" * 46)
    print("  我可以陪你学：语文 · 数学 · 科学 · 安全 · 健康")
    print("  指令：/quit 退出，/reset 开启新会话")
    print("=" * 46)


def main() -> None:
    _print_banner()

    try:
        count = get_vector_store().count()
    except Exception:  # noqa: BLE001
        count = 0
    if count == 0:
        print("\n[提示] 知识库索引为空，建议先运行：python run_ingest.py\n")

    user_id = input("先告诉我你的昵称（直接回车用默认）：").strip() or "default-student"
    thread_id = f"cli-{uuid.uuid4().hex[:8]}"

    while True:
        try:
            question = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n小博士：下次再聊呀，拜拜！")
            break

        if not question:
            continue
        if question == "/quit":
            print("小博士：下次再聊呀，拜拜！")
            break
        if question == "/reset":
            thread_id = f"cli-{uuid.uuid4().hex[:8]}"
            print("小博士：好的，我们重新开始一段新对话吧！")
            continue

        print("小博士：", end="", flush=True)
        try:
            for token in stream_answer(question, user_id=user_id, thread_id=thread_id):
                print(token, end="", flush=True)
            print()
        except Exception as exc:  # noqa: BLE001
            print(f"\n[出错了] {exc}")


if __name__ == "__main__":
    main()
