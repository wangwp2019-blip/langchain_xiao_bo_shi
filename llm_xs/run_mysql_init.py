"""MySQL 离线建表入口。

用法：
    python run_mysql_init.py              # 应用 scripts/mysql/schema.sql
    python run_mysql_init.py --ping       # 仅连通性探针
"""

from __future__ import annotations

import argparse
import json
import sys

from app.config import settings
from app.mysql_db import check_mysql_ready, close_mysql_pool, init_schema, ping_mysql


def main() -> int:
    parser = argparse.ArgumentParser(description="MySQL 建表 / 探针")
    parser.add_argument("--ping", action="store_true", help="仅 SELECT 1 探针")
    parser.add_argument(
        "--schema",
        default=None,
        help="自定义 schema.sql 路径（默认 scripts/mysql/schema.sql）",
    )
    args = parser.parse_args()

    if not settings.mysql_configured:
        print("[错误] 未配置 MySQL。请设置 KIDS_MYSQL_URL 或 KIDS_MYSQL_USER + KIDS_MYSQL_DATABASE。", file=sys.stderr)
        return 1

    print(f"MySQL 目标：{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}")

    try:
        if args.ping:
            ok = ping_mysql()
            print("探针结果：", "OK" if ok else "FAIL")
            return 0 if ok else 2

        init_schema(args.schema)
        status = check_mysql_ready()
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status.get("ready") else 2
    finally:
        close_mysql_pool()


if __name__ == "__main__":
    raise SystemExit(main())
