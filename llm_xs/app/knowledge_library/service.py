"""知识库上传、目录、索引编排。"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from .parser import detect_upload_type, extract_text_from_bytes, normalize_text
from .schemas import KnowledgeDocument, KnowledgeSearchHit, KnowledgeStatusResponse

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_CATALOG = "catalog.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def library_root() -> Path:
    path = settings.base_dir / "data" / "knowledge_library"
    path.mkdir(parents=True, exist_ok=True)
    (path / "files").mkdir(exist_ok=True)
    return path


def _catalog_path() -> Path:
    return library_root() / _CATALOG


def _load_catalog_raw() -> list[dict]:
    p = _catalog_path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return list(data.get("documents", []))
    except (json.JSONDecodeError, OSError):
        return []


def _save_catalog(docs: list[dict]) -> None:
    _catalog_path().write_text(
        json.dumps({"documents": docs}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_documents(
    *,
    grade: int | None = None,
    subject: str | None = None,
    upload_type: str | None = None,
) -> list[KnowledgeDocument]:
    with _lock:
        rows = _load_catalog_raw()
    out: list[KnowledgeDocument] = []
    for row in rows:
        doc = KnowledgeDocument.model_validate(row)
        if grade is not None and doc.grade != grade:
            continue
        if subject and doc.subject != subject:
            continue
        if upload_type and doc.upload_type != upload_type:
            continue
        out.append(doc)
    return sorted(out, key=lambda d: d.created_at, reverse=True)


def get_document(doc_id: str) -> KnowledgeDocument | None:
    for doc in list_documents():
        if doc.doc_id == doc_id:
            return doc
    return None


def _doc_dir(doc_id: str) -> Path:
    return library_root() / "files" / doc_id


def upload_document(
    *,
    filename: str,
    data: bytes,
    grade: int,
    subject: str,
    title: str | None = None,
    upload_type: str | None = None,
    content_type: str | None = None,
) -> KnowledgeDocument:
    if len(data) > settings.knowledge_max_upload_bytes:
        raise ValueError(
            f"文件过大（最大 {settings.knowledge_max_upload_bytes // (1024 * 1024)}MB）"
        )

    utype = upload_type or detect_upload_type(filename, content_type)
    doc_id = f"kb-{uuid.uuid4().hex[:12]}"
    ddir = _doc_dir(doc_id)
    ddir.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix or ".bin"
    (ddir / f"original{ext}").write_bytes(data)

    doc = KnowledgeDocument(
        doc_id=doc_id,
        title=title or Path(filename).stem or doc_id,
        grade=grade,
        subject=subject,
        upload_type=utype,  # type: ignore[arg-type]
        filename=filename,
        status="pending",
        char_count=0,
        created_at=_now(),
    )

    with _lock:
        rows = _load_catalog_raw()
        rows.append(doc.model_dump())
        _save_catalog(rows)

    if settings.knowledge_index_async:
        threading.Thread(
            target=_process_upload_safe,
            args=(doc_id,),
            kwargs={"filename": filename, "upload_type": utype},
            daemon=True,
        ).start()
        return doc
    return _process_upload_sync(
        doc_id, filename=filename, upload_type=utype, data=data
    )


def _process_upload_sync(
    doc_id: str,
    *,
    filename: str,
    upload_type: str,
    data: bytes,
) -> KnowledgeDocument:
    text = normalize_text(
        extract_text_from_bytes(data, filename=filename, upload_type=upload_type)
    )
    if len(text) < 20:
        raise ValueError("未能提取到足够的学习内容（至少 20 字）")
    (_doc_dir(doc_id) / "extracted.txt").write_text(text, encoding="utf-8")
    _update_doc(doc_id, char_count=len(text))
    return index_document(doc_id)


def _process_upload_safe(doc_id: str, *, filename: str, upload_type: str) -> None:
    """后台：PDF 解析 + 向量索引（避免阻塞 HTTP 连接）。"""
    try:
        ddir = _doc_dir(doc_id)
        originals = sorted(ddir.glob("original*"))
        if not originals:
            raise FileNotFoundError("缺少原始文件")
        data = originals[0].read_bytes()
        text = normalize_text(
            extract_text_from_bytes(data, filename=filename, upload_type=upload_type)
        )
        if len(text) < 20:
            raise ValueError("未能提取到足够的学习内容（至少 20 字）")
        (ddir / "extracted.txt").write_text(text, encoding="utf-8")
        _update_doc(doc_id, char_count=len(text))
        index_document(doc_id)
    except Exception as exc:
        logger.exception("后台处理 doc_id=%s 失败: %s", doc_id, exc)
        try:
            _update_doc(doc_id, status="failed", error=str(exc)[:500])
        except Exception:
            pass


def _index_doc_safe(doc_id: str) -> None:
    try:
        index_document(doc_id)
    except Exception as exc:
        logger.exception("后台索引 doc_id=%s 失败: %s", doc_id, exc)
        try:
            _update_doc(doc_id, status="failed", error=str(exc)[:500])
        except Exception:
            pass


def index_document(doc_id: str) -> KnowledgeDocument:
    doc = get_document(doc_id)
    if not doc:
        raise KeyError(doc_id)

    extracted = _doc_dir(doc_id) / "extracted.txt"
    if not extracted.is_file():
        _update_doc(doc_id, status="failed", error="缺少 extracted.txt")
        raise FileNotFoundError(extracted)

    text = extracted.read_text(encoding="utf-8")
    try:
        from ..rag.llamaindex_rag import index_library_text

        chunk_count = index_library_text(
            text,
            doc_id=doc_id,
            title=doc.title,
            grade=doc.grade,
            subject=doc.subject,
            upload_type=doc.upload_type,
            filename=doc.filename,
        )
        return _update_doc(
            doc_id,
            status="indexed",
            chunk_count=chunk_count,
            indexed_at=_now(),
            error=None,
        )
    except Exception as exc:
        return _update_doc(doc_id, status="failed", error=str(exc)[:500])


def _update_doc(doc_id: str, **fields) -> KnowledgeDocument:
    with _lock:
        rows = _load_catalog_raw()
        updated: KnowledgeDocument | None = None
        for i, row in enumerate(rows):
            if row.get("doc_id") == doc_id:
                row.update({k: v for k, v in fields.items() if v is not None})
                rows[i] = row
                updated = KnowledgeDocument.model_validate(row)
                break
        if not updated:
            raise KeyError(doc_id)
        _save_catalog(rows)
        return updated


def delete_document(doc_id: str) -> None:
    with _lock:
        rows = [r for r in _load_catalog_raw() if r.get("doc_id") != doc_id]
        _save_catalog(rows)

    ddir = _doc_dir(doc_id)
    if ddir.is_dir():
        import shutil

        shutil.rmtree(ddir, ignore_errors=True)

    try:
        from ..rag.llamaindex_rag import remove_library_doc

        remove_library_doc(doc_id)
    except Exception:
        pass


def rebuild_all() -> int:
    """全量重建：内置百科 + 全部已上传资料。"""
    from ..rag.llamaindex_rag import rebuild_all_sources

    count = rebuild_all_sources(force=True)
    docs = list_documents()
    for doc in docs:
        if (_doc_dir(doc.doc_id) / "extracted.txt").is_file():
            _update_doc(doc.doc_id, status="indexed", indexed_at=_now())
    return count


def search(
    query: str,
    *,
    grade: int | None = None,
    subject: str | None = None,
    top_k: int = 4,
) -> list[KnowledgeSearchHit]:
    from ..knowledge import retrieve

    hits = retrieve(query, top_k=top_k, grade=grade, subject=subject)
    return [
        KnowledgeSearchHit(
            text=h.get("text", ""),
            score=float(h.get("score", 0)),
            source=str(h.get("source", "")),
            grade=h.get("grade"),
            subject=h.get("subject"),
            upload_type=h.get("upload_type"),
            doc_id=h.get("doc_id"),
        )
        for h in hits
    ]


def status() -> KnowledgeStatusResponse:
    from ..rag.llamaindex_rag import check_rag_ready

    ready_info = check_rag_ready()
    docs = list_documents()
    return KnowledgeStatusResponse(
        backend=settings.vector_backend,
        rag_engine=settings.rag_engine,
        embedding_configured=settings.embedding_configured,
        index_count=int(ready_info.get("index_count", 0)),
        library_doc_count=len(docs),
        ready=bool(ready_info.get("ready")),
        milvus_uri=ready_info.get("milvus_uri"),
        collection=ready_info.get("collection"),
    )


def clear_library_for_tests() -> None:
    """测试隔离：清空 catalog 与 files。"""
    import shutil

    root = library_root()
    cat = _catalog_path()
    if cat.is_file():
        cat.unlink()
    files = root / "files"
    if files.is_dir():
        shutil.rmtree(files, ignore_errors=True)
        files.mkdir(parents=True, exist_ok=True)
