"""共享的 PostgreSQL 连接池（生产级基础设施）。

为什么需要连接池？
------------------
建立一条数据库连接（TCP 握手 + 认证 + 初始化）是相对昂贵的操作，
如果每次读写记忆都新建一条连接、用完就丢，会带来两个严重问题：

1. **慢**：每个请求都付一次建连成本，高并发时延迟飙升。
2. **会打爆数据库**：连接数无上限增长，PostgreSQL 默认 max_connections
   只有 100 左右，连接泄漏很快就会把数据库连满，整个服务雪崩。

连接池（``psycopg_pool.ConnectionPool``）解决这两个问题：
- 预先建立并复用一批连接（``min_size`` ~ ``max_size``）。
- 借出/归还，连接数有上限，借不到时最多等 ``pool_timeout`` 秒。

短期记忆（checkpointer）和长期记忆（store）共用**同一个**连接池，
统一管理生命周期：进程启动时打开，进程退出时优雅关闭。

注意：本模块对外暴露 ``get_pool()`` / ``close_pool()``，是线程安全的单例。
"""

from __future__ import annotations

from threading import Lock
from typing import TYPE_CHECKING

from .config import settings

if TYPE_CHECKING:  # 仅用于类型提示，运行时不强制依赖 psycopg_pool
    from psycopg_pool import ConnectionPool

# 模块级单例 + 锁：保证多线程下连接池只被创建一次（双重检查锁定）。
_pool: "ConnectionPool | None" = None
_pool_lock = Lock()


def get_pool() -> "ConnectionPool":
    """返回全局唯一的 PostgreSQL 连接池（懒加载 + 线程安全单例）。

    第一次调用时按配置创建并打开连接池；后续调用直接复用。
    """
    global _pool
    # 第一次检查（无锁，快路径）：绝大多数调用都走到这里直接返回。
    if _pool is not None:
        return _pool

    with _pool_lock:
        # 第二次检查（持锁）：防止多个线程同时穿过第一次检查、重复创建池。
        if _pool is not None:
            return _pool

        if not settings.postgres_url:
            raise RuntimeError(
                "使用 postgres 后端需要配置 KIDS_POSTGRES_URL（或 KIDS_DB_URL）。"
            )

        # 延迟导入：只有真正用到 postgres 时才要求安装这些可选依赖。
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        # LangGraph 的 PostgresSaver / PostgresStore 对连接有三点硬性要求：
        # - autocommit=True：它自己管理事务，连接必须是自动提交模式。
        # - prepare_threshold=0：禁用预编译语句缓存（配合连接池更稳定）。
        # - row_factory=dict_row：以字典而非元组返回行，便于按列名取值。
        connection_kwargs = {
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        }

        pool = ConnectionPool(
            conninfo=settings.postgres_url,
            min_size=settings.pg_pool_min_size,
            max_size=settings.pg_pool_max_size,
            timeout=settings.pg_pool_timeout,
            kwargs=connection_kwargs,
            open=False,  # 先构造，下面显式 open()，避免构造期副作用
        )
        pool.open(wait=True)  # 阻塞直到至少 min_size 条连接就绪，启动即可用
        _pool = pool
        return _pool


def close_pool() -> None:
    """优雅关闭连接池（进程退出 / FastAPI 停机时调用）。

    关闭后会等待借出的连接归还并断开所有底层连接，释放数据库资源。
    幂等：未创建或已关闭时调用不会报错。
    """
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None
