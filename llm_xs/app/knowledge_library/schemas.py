"""知识库上传元数据模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

UploadType = Literal["txt", "pdf", "image", "document", "other"]
DocStatus = Literal["pending", "indexed", "failed"]


class KnowledgeDocument(BaseModel):
    doc_id: str
    title: str
    grade: int = Field(ge=1, le=6)
    subject: str
    upload_type: UploadType
    filename: str
    status: DocStatus = "pending"
    chunk_count: int = 0
    char_count: int = 0
    error: str | None = None
    created_at: str
    indexed_at: str | None = None


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    grade: int | None = Field(None, ge=1, le=6)
    subject: str | None = None
    top_k: int = Field(default=4, ge=1, le=20)


class KnowledgeSearchHit(BaseModel):
    text: str
    score: float
    source: str = ""
    grade: int | None = None
    subject: str | None = None
    upload_type: str | None = None
    doc_id: str | None = None


class KnowledgeStatusResponse(BaseModel):
    backend: str
    rag_engine: str
    embedding_configured: bool
    index_count: int
    library_doc_count: int
    ready: bool
    milvus_uri: str | None = None
    collection: str | None = None
