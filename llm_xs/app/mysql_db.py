"""MySQL 连接池与通用查询封装（预留扩展，按需启用）。

设计目标
--------
- 与 ``app/db.py``（PostgreSQL）并列，**不混用**连接池。
- 仅配置 ``KIDS_MYSQL_*`` 时才懒加载 ``pymysql``，未配置时零开销。
- 提供 ``execute`` / ``fetch_one`` / ``fetch_all`` / ``transaction`` 供后续业务 Repository 复用。

启用示例（.env）::

    KIDS_MYSQL_URL=mysql://kid:kid@127.0.0.1:3306/kid_assistant
    # 或分项配置 KIDS_MYSQL_HOST / USER / PASSWORD / DATABASE
    KIDS_MYSQL_AUTO_INIT_SCHEMA=true   # 首次连接时执行 scripts/mysql/schema.sql
"""

from __future__ import annotations

import logging
import queue
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import unquote, urlparse

from .config import settings

logger = logging.getLogger(__name__)

_SCHEMA_PATH = settings.base_dir / "scripts" / "mysql" / "schema.sql"

_pool: "MySQLPool | None" = None
_pool_lock = threading.Lock()
_schema_initialized = False
_schema_lock = threading.Lock()


def parse_mysql_url(url: str) -> dict[str, Any]:
    """解析 ``mysql://user:pass@host:port/db?charset=utf8mb4``。"""
    raw = url.strip()
    for prefix in ("mysql+pymysql://", "mysql://"):
        if raw.startswith(prefix):
            raw = raw[len(prefix) :]
            break
    else:
        raise ValueError(f"不支持的 MySQL URL 协议：{url!r}")

    parsed = urlparse(f"//{raw}")
    if not parsed.hostname or not parsed.path or parsed.path == "/":
        raise ValueError(f"MySQL URL 缺少 host 或 database：{url!r}")

    database = parsed.path.lstrip("/")
    query = dict(
        part.split("=", 1)
        for part in (parsed.query or "").split("&")
        if "=" in part
    )
    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": database,
        "charset": query.get("charset", settings.mysql_charset),
    }


def mysql_connection_params() -> dict[str, Any] | None:
    """返回 pymysql.connect 参数字典；未配置时 ``None``。"""
    if settings.mysql_url:
        return parse_mysql_url(settings.mysql_url)
    if not settings.mysql_user or not settings.mysql_database:
        return None
    return {
        "host": settings.mysql_host,
        "port": settings.mysql_port,
        "user": settings.mysql_user,
        "password": settings.mysql_password or "",
        "database": settings.mysql_database,
        "charset": settings.mysql_charset,
    }


class MySQLPool:
    """轻量线程安全连接池（基于 ``queue.Queue`` + ``pymysql``）。"""

    def __init__(
        self,
        params: dict[str, Any],
        *,
        min_size: int,
        max_size: int,
        timeout: float,
    ) -> None:
        self._params = dict(params)
        self._max_size = max(1, max_size)
        self._timeout = timeout
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=self._max_size)
        self._created = 0
        self._lock = threading.Lock()

        for _ in range(max(0, min_size)):
            self._queue.put(self._create_connection(), block=False)

    def _create_connection(self) -> Any:
        import pymysql
        from pymysql.cursors import DictCursor

        with self._lock:
            if self._created >= self._max_size:
                raise RuntimeError("MySQL 连接池已满")
            self._created += 1

        conn = pymysql.connect(
            cursorclass=DictCursor,
            autocommit=False,
            connect_timeout=int(self._timeout),
            read_timeout=int(self._timeout),
            write_timeout=int(self._timeout),
            **self._params,
        )
        return conn

    def _acquire(self) -> Any:
        try:
            conn = self._queue.get(timeout=self._timeout)
        except queue.Empty:
            conn = self._create_connection()
        try:
            conn.ping(reconnect=True)
        except Exception:
            conn = self._create_connection()
        return conn

    def _release(self, conn: Any) -> None:
        try:
            if conn.open:
                try:
                    conn.rollback()
                except Exception:
                    pass
                self._queue.put(conn, block=False)
                return
        except Exception:
            pass
        with self._lock:
            self._created = max(0, self._created - 1)

    @contextmanager
    def connection(self) -> Iterator[Any]:
        conn = self._acquire()
        try:
            yield conn
        finally:
            self._release(conn)

    def close(self) -> None:
        while True:
            try:
                conn = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                conn.close()
            except Exception:
                pass
        with self._lock:
            self._created = 0


def get_mysql_pool() -> MySQLPool:
    """懒加载 MySQL 连接池（线程安全单例）。"""
    global _pool
    if _pool is not None:
        return _pool

    with _pool_lock:
        if _pool is not None:
            return _pool

        params = mysql_connection_params()
        if not params:
            raise RuntimeError(
                "MySQL 未配置。请设置 KIDS_MYSQL_URL 或 KIDS_MYSQL_USER + KIDS_MYSQL_DATABASE。"
            )

        pool = MySQLPool(
            params,
            min_size=settings.mysql_pool_min_size,
            max_size=settings.mysql_pool_max_size,
            timeout=settings.mysql_pool_timeout,
        )
        _maybe_init_schema(pool)
        _pool = pool
        logger.info(
            "MySQL 连接池已就绪 host=%s db=%s pool=%d~%d",
            params.get("host"),
            params.get("database"),
            settings.mysql_pool_min_size,
            settings.mysql_pool_max_size,
        )
        return _pool


def _maybe_init_schema(pool: MySQLPool) -> None:
    global _schema_initialized
    if _schema_initialized or not settings.mysql_auto_init_schema:
        return
    if not _SCHEMA_PATH.exists():
        logger.warning("MySQL 自动建表已开启，但未找到 schema 文件：%s", _SCHEMA_PATH)
        return

    with _schema_lock:
        if _schema_initialized:
            return
        init_schema(_SCHEMA_PATH, pool=pool)
        _schema_initialized = True


def init_schema(schema_path: str | Path | None = None, *, pool: MySQLPool | None = None) -> None:
    """执行 ``schema.sql``（幂等：脚本内使用 IF NOT EXISTS）。"""
    path = Path(schema_path or _SCHEMA_PATH)
    if not path.exists():
        raise FileNotFoundError(f"MySQL schema 文件不存在：{path}")

    sql_text = path.read_text(encoding="utf-8")
    statements = [s.strip() for s in sql_text.split(";") if s.strip()]
    target = pool or get_mysql_pool()

    with target.connection() as conn:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
        conn.commit()
    logger.info("MySQL schema 已应用：%s（%d 条语句）", path, len(statements))


def close_mysql_pool() -> None:
    """优雅关闭 MySQL 连接池（FastAPI 停机 / 测试 teardown）。"""
    global _pool, _schema_initialized
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None
        _schema_initialized = False


@contextmanager
def mysql_connection() -> Iterator[Any]:
    """便捷上下文：``with mysql_connection() as conn: ...``"""
    with get_mysql_pool().connection() as conn:
        yield conn


def execute(sql: str, params: tuple | dict | None = None) -> int:
    """执行写操作，返回 ``cursor.rowcount``。"""
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            affected = cur.rowcount
        conn.commit()
        return affected


def fetch_one(sql: str, params: tuple | dict | None = None) -> dict[str, Any] | None:
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        return row


def fetch_all(sql: str, params: tuple | dict | None = None) -> list[dict[str, Any]]:
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        conn.commit()
        return list(rows or [])


@contextmanager
def transaction() -> Iterator[Any]:
    """显式事务：成功 commit，异常 rollback。"""
    with mysql_connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def ping_mysql() -> bool:
    """连通性探针（SELECT 1）。"""
    row = fetch_one("SELECT 1 AS ok")
    return bool(row and row.get("ok") == 1)


def check_mysql_ready() -> dict[str, Any]:
    """health / ready 探针用。"""
    params = mysql_connection_params()
    if not params:
        return {"configured": False, "ready": False}

    result: dict[str, Any] = {
        "configured": True,
        "ready": False,
        "host": params.get("host"),
        "database": params.get("database"),
        "auto_init_schema": settings.mysql_auto_init_schema,
    }
    try:
        get_mysql_pool()
        result["ready"] = ping_mysql()
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
    return result
