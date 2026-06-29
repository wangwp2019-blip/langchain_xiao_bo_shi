"""S7 · HTTP API（离线，TestClient 不调 LLM）。"""

from __future__ import annotations


def run() -> None:
    from fastapi.testclient import TestClient

    from app.api import app

    client = TestClient(app)

    r = client.get("/api/health")
    assert r.status_code == 200, r.text
    data = r.json()
    print("health:", data)
    assert data["status"] == "ok"
    assert "vector_backend" in data
    assert "memory_backend" in data

    r2 = client.get("/")
    assert r2.status_code == 200
    assert "小博士" in r2.text
    print("GET / 聊天页 OK")

    # ingest：强制 keyword 避免 Embedding
    from app.config import settings
    from app.vector_store import get_vector_store

    settings.vector_backend = "keyword"
    get_vector_store.cache_clear()
    r3 = client.post("/api/ingest")
    assert r3.status_code == 200, r3.text
    body = r3.json()
    print("POST /api/ingest:", body)
    assert body.get("status") == "ok"
    assert body.get("index_count", 0) > 0
    get_vector_store.cache_clear()
