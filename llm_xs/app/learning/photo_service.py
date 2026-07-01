"""拍照归类 + Inbox 三档分流。"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from . import gap_service, storage
from .attempt_service import submit_freeform
from .kp_catalog import get_kp, load_catalog
from .schemas import AttemptRecord, FreeformAttemptRequest, PhotoClassifyRequest, PhotoInboxItem, PhotoTriage


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return f"inbox-{uuid.uuid4().hex[:12]}"


def _match_kp(text: str, subject: str) -> tuple[str | None, str, float]:
    text_l = text.lower()
    best_id: str | None = None
    best_title = ""
    best_score = 0.0
    keywords: dict[str, list[str]] = {
        "kp-g2-sub-borrow": ["退位", "借", "不够减"],
        "kp-g2-add-carry": ["进位", "满十", "进1"],
        "kp-g2-align-digits": ["对齐", "数位", "竖式"],
        "kp-g2-word-problem-more-less": ["比", "多几", "少几", "应用题"],
        "kp-g2-mult-meaning": ["乘法", "×", "几个相同"],
    }
    for kp_id, kws in keywords.items():
        score = sum(1 for k in kws if k in text)
        if score > best_score:
            best_score = score
            best_id = kp_id
            kp = get_kp(kp_id)
            best_title = kp.title if kp else kp_id
    # 扫描 catalog titles
    for unit in load_catalog():
        if subject and unit.subject != subject:
            continue
        for kp in unit.knowledge_points:
            if kp.title in text or kp.knowledge_point_id in text:
                return kp.knowledge_point_id, kp.title, 0.85
    if best_id and best_score > 0:
        return best_id, best_title, min(0.5 + best_score * 0.15, 0.92)
    if re.search(r"\d+\s*[+\-×x*]\s*\d+", text):
        return "kp-g2-add-no-carry", "100以内加减", 0.55
    return None, "", 0.2


def classify_photo(student_id: str, req: PhotoClassifyRequest) -> tuple[PhotoTriage, PhotoInboxItem | AttemptRecord | None]:
    kp_id, kp_title, conf = _match_kp(req.text, req.subject)

    if conf >= 0.75 and kp_id:
        attempt = submit_freeform(
            student_id,
            FreeformAttemptRequest(
                prompt=req.text[:500],
                student_answer=req.image_note or "（拍照提交）",
                subject=req.subject,
            ),
        )
        return "auto", attempt

    if conf >= 0.45 and kp_id:
        item = PhotoInboxItem(
            inbox_id=_new_id(),
            student_id=student_id,
            text=req.text[:1000],
            suggested_kp_id=kp_id,
            suggested_kp_title=kp_title,
            confidence=conf,
            triage="inbox",
            status="pending",
            created_at=_now(),
        )
        _save_inbox(item)
        return "inbox", item

    if "讲" in req.text or "怎么" in req.text:
        return "explain_only", None

    item = PhotoInboxItem(
        inbox_id=_new_id(),
        student_id=student_id,
        text=req.text[:1000],
        suggested_kp_id=kp_id,
        suggested_kp_title=kp_title or "未识别",
        confidence=conf,
        triage="inbox",
        status="pending",
        created_at=_now(),
    )
    _save_inbox(item)
    return "inbox", item


def _save_inbox(item: PhotoInboxItem) -> None:
    items = [PhotoInboxItem.model_validate(r) for r in storage.load_global_list("photo_inbox.json")]
    items.append(item)
    storage.save_global_list("photo_inbox.json", [i.model_dump() for i in items])


def list_inbox(student_id: str | None = None, status: str = "pending") -> list[PhotoInboxItem]:
    items = [PhotoInboxItem.model_validate(r) for r in storage.load_global_list("photo_inbox.json")]
    out = [i for i in items if i.status == status]
    if student_id:
        out = [i for i in out if i.student_id == student_id]
    return sorted(out, key=lambda x: x.created_at, reverse=True)


def resolve_inbox(inbox_id: str, action: str, kp_id: str | None = None) -> PhotoInboxItem:
    items_raw = storage.load_global_list("photo_inbox.json")
    items = [PhotoInboxItem.model_validate(r) for r in items_raw]
    target: PhotoInboxItem | None = None
    for i in items:
        if i.inbox_id == inbox_id:
            target = i
            break
    if not target:
        raise KeyError(f"inbox 不存在: {inbox_id}")

    if action == "ignore":
        target.status = "ignored"
    else:
        target.status = "resolved"
        target.resolved_kp_id = kp_id or target.suggested_kp_id
        if target.resolved_kp_id:
            gap_service.override_gap(target.student_id, target.resolved_kp_id, "weak", note="photo_manual")

    storage.save_global_list("photo_inbox.json", [i.model_dump() for i in items])
    return target
