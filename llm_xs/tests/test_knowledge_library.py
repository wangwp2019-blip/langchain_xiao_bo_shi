"""知识库上传 API 测试。"""

from __future__ import annotations

import pytest

from app.knowledge_library import service


@pytest.fixture(autouse=True)
def _clean_library(monkeypatch, tmp_path):
    import app.config as cfg

    monkeypatch.setattr(cfg.settings, "knowledge_index_async", False)
    monkeypatch.setattr(service, "library_root", lambda: tmp_path / "knowledge_library")
    (tmp_path / "knowledge_library" / "files").mkdir(parents=True, exist_ok=True)
    service.clear_library_for_tests()
    yield
    service.clear_library_for_tests()


def test_large_upload_not_rejected_by_global_limit(client, monkeypatch):
    """知识库上传应使用 100MB 上限，而非全局 64KB。"""
    import app.config as cfg

    monkeypatch.setattr(cfg.settings, "max_body_bytes", 64 * 1024)
    monkeypatch.setattr(cfg.settings, "knowledge_max_upload_bytes", 100 * 1024 * 1024)
    monkeypatch.setattr(
        "app.knowledge_library.service.index_document",
        lambda doc_id: service._update_doc(doc_id, status="indexed", chunk_count=1),
    )

    payload = b"x" * (200 * 1024)  # 200KB
    r = client.post(
        "/api/knowledge/upload",
        data={"grade": "2", "subject": "数学", "title": "大文件"},
        files={"file": ("big.txt", payload, "text/plain")},
    )
    assert r.status_code != 413, r.text


def test_upload_text_and_list(client, monkeypatch):
    monkeypatch.setattr(
        "app.knowledge_library.service.index_document",
        lambda doc_id: service._update_doc(doc_id, status="indexed", chunk_count=2),
    )

    r = client.post(
        "/api/knowledge/upload/text",
        data={
            "content": "二年级数学：加法是把两个数合在一起。例如 3+5=8。",
            "grade": "2",
            "subject": "数学",
            "title": "加法入门",
        },
    )
    assert r.status_code == 200
    doc = r.json()["document"]
    assert doc["grade"] == 2
    assert doc["subject"] == "数学"
    assert doc["upload_type"] == "txt"

    listed = client.get("/api/knowledge/documents?grade=2&subject=数学")
    assert listed.status_code == 200
    assert len(listed.json()["documents"]) == 1


def test_upload_file_multipart(client, monkeypatch):
    monkeypatch.setattr(
        "app.knowledge_library.service.index_document",
        lambda doc_id: service._update_doc(doc_id, status="indexed", chunk_count=1),
    )

    content = b"\xe4\xba\x8c\xe5\xb9\xb4\xe7\xba\xa7\xe8\xaf\xad\xe6\x96\x87\xef\xbc\x9a\xe6\x8b\xbc\xe9\x9f\xb3\xe6\x98\xaf\xe6\x8a\x8a\xe5\xa3\xb0\xe6\xaf\x8d\xe6\x8b\xbc\xe6\x88\x90\xe5\xad\x97\xe3\x80\x82" * 2
    r = client.post(
        "/api/knowledge/upload",
        data={"grade": "2", "subject": "语文", "title": "拼音"},
        files={"file": ("pinyin.txt", content, "text/plain")},
    )
    assert r.status_code == 200
    assert r.json()["document"]["upload_type"] == "txt"


def test_delete_document(client, monkeypatch):
    monkeypatch.setattr(
        "app.knowledge_library.service.index_document",
        lambda doc_id: service._update_doc(doc_id, status="indexed", chunk_count=1),
    )

    def _noop_remove(doc_id: str) -> None:
        return None

    monkeypatch.setattr("app.rag.llamaindex_rag.remove_library_doc", _noop_remove)

    up = client.post(
        "/api/knowledge/upload/text",
        data={
            "content": "科学小知识：水是生命之源，地球表面大部分被水覆盖。",
            "grade": "3",
            "subject": "科学",
            "title": "水",
        },
    )
    doc_id = up.json()["document"]["doc_id"]

    deleted = client.delete(f"/api/knowledge/documents/{doc_id}")
    assert deleted.status_code == 200

    listed = client.get("/api/knowledge/documents")
    assert listed.json()["documents"] == []


def test_status_endpoint(client):
    r = client.get("/api/knowledge/status")
    assert r.status_code == 200
    body = r.json()
    assert "backend" in body
    assert "library_doc_count" in body


def test_search_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        "app.knowledge_library.service.search",
        lambda query, **kw: [],
    )
    r = client.post(
        "/api/knowledge/search",
        json={"query": "太阳系", "grade": 2, "top_k": 3},
    )
    assert r.status_code == 200
    assert r.json()["hits"] == []
