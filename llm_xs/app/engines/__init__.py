"""循环引擎（loop engines）合集。

本包提供三种"循环引擎"的生产级实现，覆盖三类常见的后台运行形态：

- ``task_worker``：任务队列后台 Worker 引擎（A）。
  常驻进程，不断从队列拉取"学生提问任务"，多线程并发跑 Agent，
  失败自动重试 + 指数退避，支持优雅停机。

- ``scheduler``：定时调度引擎（C）。
  按固定间隔周期性触发任务（如每天给学生推一道练习题），
  任务错误相互隔离、不会拖垮调度器，支持优雅停机。

- ``chat_loop``：生产级对话主循环引擎（D）。
  把命令行对话循环升级为生产级：会话管理、单条超时、令牌桶限流、
  错误自愈（出错不退出）、结构化日志、Ctrl+C 优雅退出。

三者共享 ``util`` 里的日志、限流器、退避、超时等基础工具。
"""

from __future__ import annotations

from .chat_loop import ChatLoopEngine
from .scheduler import Job, SchedulerEngine
from .task_worker import Task, TaskResult, TaskWorkerEngine

__all__ = [
    "ChatLoopEngine",
    "Job",
    "SchedulerEngine",
    "Task",
    "TaskResult",
    "TaskWorkerEngine",
]
