"""单元 Wiki（从 KP 目录 + 可选 markdown 片段）。"""

from __future__ import annotations

from . import storage
from .kp_catalog import get_kp, get_unit, list_units


def explain_kp_wiki(kp_id: str) -> str:
    kp = get_kp(kp_id)
    if not kp:
        return f"暂无「{kp_id}」的 Wiki 资料。"
    extra = _custom_wiki(kp_id)
    body = kp.description or "这是本单元的重要知识点。"
    if extra:
        return f"【{kp.title}】\n{body}\n\n补充：{extra}"
    return f"【{kp.title}】\n{body}"


def explain_unit_wiki(unit_id: str) -> str:
    try:
        unit = get_unit(unit_id)
    except KeyError:
        return "未找到该单元 Wiki。"
    lines = [f"《{unit.unit_title}》", f"教材：{unit.textbook_ref or '校内教材'}"]
    for kp in unit.knowledge_points[:8]:
        lines.append(f"- {kp.title}（{kp.knowledge_point_id}）")
    return "\n".join(lines)


def _custom_wiki(kp_id: str) -> str:
    data = storage.get_student_singleton("_wiki.json", "_global") or {}
    return str(data.get(kp_id, ""))


def upsert_wiki(kp_id: str, content: str) -> None:
    data = storage.get_student_singleton("_wiki.json", "_global") or {}
    data[kp_id] = content
    storage.upsert_student_singleton("_wiki.json", "_global", data)


def search_wiki(query: str, grade: int | None = None) -> list[dict]:
    from ..config import settings

    if not settings.knowledge_scope_filter:
        grade = None
    hits: list[dict] = []
    for unit in list_units(grade_level=grade):
        for kp in unit.knowledge_points:
            if query in kp.title or query in kp.knowledge_point_id:
                hits.append(
                    {
                        "unit_id": unit.unit_id,
                        "knowledge_point_id": kp.knowledge_point_id,
                        "title": kp.title,
                        "snippet": explain_kp_wiki(kp.knowledge_point_id)[:200],
                    }
                )
    return hits[:10]
