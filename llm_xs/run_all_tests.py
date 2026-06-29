"""分阶段测试统一入口。

用法：
    python run_all_tests.py                 # S0–S7 离线
    python run_all_tests.py --api         # S0–S8 含端到端
    python run_all_tests.py --stage S4
    python run_all_tests.py --from S1 --to S3
"""

from __future__ import annotations

import argparse
import sys

from tests.runner import run_stages


def main() -> None:
    parser = argparse.ArgumentParser(description="小博士 LangGraph 版 · 分阶段测试")
    parser.add_argument("--api", action="store_true", help="包含 S8 端到端（消耗 LLM API）")
    parser.add_argument("--stage", type=str, help="只运行指定阶段，如 S4")
    parser.add_argument("--from", dest="from_code", type=str, help="起始阶段，如 S2")
    parser.add_argument("--to", dest="to_code", type=str, help="结束阶段，如 S6")
    args = parser.parse_args()

    code = run_stages(
        with_api=args.api,
        only=args.stage,
        from_code=args.from_code,
        to_code=args.to_code,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
