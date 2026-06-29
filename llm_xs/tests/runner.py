"""分阶段测试套件。

阶段一览
--------
S0  配置与导入        离线   环境变量、模块导入、路径
S1  RAG 基础设施      离线   切分、本地向量库、关键词检索
S2  记忆系统          离线   长期记忆落盘、短期 checkpointer、连接池
S3  工具层            离线   calculator、日期、工具装配
S4  Agent 图结构      离线   LangGraph StateGraph / 旧版 create_agent
S5  RAG 在线链路      离线*  keyword 建索引 + 检索 + 图节点（*不需 LLM）
S6  循环引擎          离线   Worker / Scheduler / util
S7  HTTP API          离线   /api/health（TestClient，不调 LLM）
S8  端到端集成        需 API 完整 Agent 冒烟（LLM + 可选 Embedding）

运行
----
    python run_all_tests.py              # S0–S7（默认，不耗 API）
    python run_all_tests.py --api        # S0–S8 全部
    python run_all_tests.py --stage S4   # 只跑某一阶段
    python run_all_tests.py --from S2 --to S6
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .stages import (
    run_s00_config,
    run_s01_rag,
    run_s02_memory,
    run_s03_tools,
    run_s04_graph,
    run_s05_rag_online,
    run_s06_engines,
    run_s07_api,
    run_s08_integration,
)


@dataclass(frozen=True)
class Stage:
    code: str
    title: str
    run: Callable[[], None]
    requires_api: bool = False


STAGES: list[Stage] = [
    Stage("S0", "配置与导入", run_s00_config),
    Stage("S1", "RAG 基础设施", run_s01_rag),
    Stage("S2", "记忆系统", run_s02_memory),
    Stage("S3", "工具层", run_s03_tools),
    Stage("S4", "LangGraph 图结构", run_s04_graph),
    Stage("S5", "RAG 在线链路", run_s05_rag_online),
    Stage("S6", "循环引擎", run_s06_engines),
    Stage("S7", "HTTP API", run_s07_api),
    Stage("S8", "端到端集成", run_s08_integration, requires_api=True),
]

STAGE_MAP = {s.code.upper(): s for s in STAGES}


def section(title: str) -> None:
    print("\n" + "=" * 56 + f"\n{title}\n" + "=" * 56)


def run_stages(
    *,
    with_api: bool = False,
    only: str | None = None,
    from_code: str | None = None,
    to_code: str | None = None,
) -> int:
    """执行选定阶段，返回失败阶段数。"""
    if only:
        key = only.upper()
        if key not in STAGE_MAP:
            print(f"[错误] 未知阶段 {only!r}，可选: {', '.join(STAGE_MAP)}")
            return 1
        selected = [STAGE_MAP[key]]
    else:
        start = from_code.upper() if from_code else "S0"
        end = to_code.upper() if to_code else "S8"
        if start not in STAGE_MAP or end not in STAGE_MAP:
            print("[错误] --from / --to 阶段代码无效")
            return 1
        start_i = next(i for i, s in enumerate(STAGES) if s.code == start)
        end_i = next(i for i, s in enumerate(STAGES) if s.code == end)
        if start_i > end_i:
            print("[错误] --from 不能晚于 --to")
            return 1
        selected = STAGES[start_i : end_i + 1]

    failed = 0
    passed = 0
    skipped = 0

    print("小博士 LangGraph 版 · 分阶段测试")
    print(f"模式: {'含 API (S0–S8)' if with_api else '离线 (S0–S7，跳过 S8)'}")

    for stage in selected:
        if stage.requires_api and not with_api:
            print(f"\n⏭  跳过 {stage.code} {stage.title}（需加 --api）")
            skipped += 1
            continue
        section(f"{stage.code} · {stage.title}")
        try:
            stage.run()
            print(f"\n✅ {stage.code} 通过")
            passed += 1
        except Exception as exc:
            print(f"\n❌ {stage.code} 失败: {type(exc).__name__}: {exc}")
            failed += 1

    print("\n" + "=" * 56)
    print(f"汇总: 通过 {passed} | 失败 {failed} | 跳过 {skipped}")
    if failed == 0:
        print(">>> 所选阶段全部通过！")
    return failed
