"""KP 目录：从 docs/content/*.kp.md 解析并缓存。"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from ..config import TUTORIAL_ROOT, settings
from .schemas import KnowledgePoint, UnitCatalogEntry

_GRADE_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
}


class GradeBoundaryError(ValueError):
    pass


def resolve_grade_level(grade_label: str) -> int:
    label = (grade_label or "").strip()
    for ch, num in _GRADE_MAP.items():
        if ch in label:
            return num
    m = re.search(r"(\d)", label)
    if m:
        return int(m.group(1))
    return 2


def _kp_content_dirs() -> list[Path]:
    dirs = [
        TUTORIAL_ROOT / "docs" / "content",
        settings.base_dir / "data" / "content",
    ]
    return [d for d in dirs if d.is_dir()]


def _parse_kp_file(path: Path) -> list[UnitCatalogEntry]:
    text = path.read_text(encoding="utf-8")
    fm: dict[str, str] = {}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip()
            text = parts[2]

    subject = fm.get("学科", "数学")
    grade = resolve_grade_level(fm.get("年级", "2"))
    textbook = fm.get("教材版本", "")

    units: list[UnitCatalogEntry] = []
    current: UnitCatalogEntry | None = None

    for line in text.splitlines():
        if line.startswith("# 单元："):
            if current and current.knowledge_points:
                units.append(current)
            title = line.replace("# 单元：", "").strip()
            current = UnitCatalogEntry(
                unit_id="",
                grade=grade,
                subject=subject,
                unit_title=title,
                textbook_ref=textbook,
            )
            continue
        if current is None:
            continue
        if line.startswith("unit_id:"):
            current.unit_id = line.split(":", 1)[1].strip()
        elif line.startswith("教材章节:"):
            pass
        elif line.startswith("单元说明:"):
            pass
        elif line.strip().startswith("- ") and "→" in line:
            body = line.strip()[2:]
            title_part, _, kp_id = body.partition("→")
            title = title_part.strip()
            kp_id = kp_id.strip()
            current.knowledge_points.append(
                KnowledgePoint(
                    knowledge_point_id=kp_id,
                    title=title,
                    description="",
                )
            )

    if current and current.knowledge_points:
        units.append(current)
    return [u for u in units if u.unit_id]


def _apply_catalog_override(units: dict[str, UnitCatalogEntry]) -> None:
    override = settings.memory_dir / "learning" / "catalog_override.json"
    if not override.is_file():
        return
    import json

    try:
        raw = json.loads(override.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    for row in raw if isinstance(raw, list) else []:
        try:
            entry = UnitCatalogEntry.model_validate(row)
        except Exception:
            continue
        if entry.unit_id:
            units[entry.unit_id] = entry


@lru_cache(maxsize=1)
def load_catalog() -> tuple[UnitCatalogEntry, ...]:
    units: dict[str, UnitCatalogEntry] = {}
    for d in _kp_content_dirs():
        for path in sorted(d.glob("*.kp.md")):
            for u in _parse_kp_file(path):
                units[u.unit_id] = u
    if not units:
        units.update(_default_catalog())
    _apply_catalog_override(units)
    return tuple(units.values())


def _default_catalog() -> dict[str, UnitCatalogEntry]:
    """内置兜底目录（无 kp.md 时）。"""
    kps = [
        KnowledgePoint(knowledge_point_id="kp-g2-add-carry", title="进位加法"),
        KnowledgePoint(knowledge_point_id="kp-g2-sub-borrow", title="退位减法"),
        KnowledgePoint(knowledge_point_id="kp-g2-align-digits", title="相同数位对齐"),
        KnowledgePoint(knowledge_point_id="kp-g2-word-problem-more-less", title="求比一个数多几或少几"),
    ]
    return {
        "math-g2-add-sub-100": UnitCatalogEntry(
            unit_id="math-g2-add-sub-100",
            grade=2,
            subject="数学",
            unit_title="100以内的加法和减法（二）",
            knowledge_points=kps,
        )
    }


def get_unit(unit_id: str) -> UnitCatalogEntry:
    for u in load_catalog():
        if u.unit_id == unit_id:
            return u
    raise KeyError(f"未知单元: {unit_id}")


def get_kp(kp_id: str) -> KnowledgePoint | None:
    for u in load_catalog():
        for kp in u.knowledge_points:
            if kp.knowledge_point_id == kp_id:
                return kp
    return None


def list_units(*, grade_level: int | None = None, subject: str | None = None) -> list[UnitCatalogEntry]:
    out = list(load_catalog())
    if grade_level is not None:
        out = [u for u in out if u.grade == grade_level]
    if subject:
        out = [u for u in out if u.subject == subject]
    return out


def assert_student_may_access_unit(student_grade: int, unit_id: str) -> None:
    unit = get_unit(unit_id)
    if student_grade < unit.grade:
        raise GradeBoundaryError(f"年级 {student_grade} 不可访问 {unit.unit_title}（{unit.grade} 年级）")


def reload_catalog() -> None:
    load_catalog.cache_clear()
