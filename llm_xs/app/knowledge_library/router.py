"""知识库 REST API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from ..security import authenticate
from . import service
from .schemas import KnowledgeSearchRequest

knowledge_router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@knowledge_router.get("/status")
def knowledge_status(principal: str = Depends(authenticate)):
    return service.status().model_dump()


@knowledge_router.get("/documents")
def list_documents(
    grade: int | None = Query(None, ge=1, le=6),
    subject: str | None = Query(None),
    upload_type: str | None = Query(None),
    principal: str = Depends(authenticate),
):
    docs = service.list_documents(grade=grade, subject=subject, upload_type=upload_type)
    return {"documents": [d.model_dump() for d in docs]}


@knowledge_router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    grade: int = Form(..., ge=1, le=6),
    subject: str = Form(...),
    title: str | None = Form(None),
    upload_type: str | None = Form(None),
    principal: str = Depends(authenticate),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="空文件")
    try:
        doc = service.upload_document(
            filename=file.filename or "upload.txt",
            data=data,
            grade=grade,
            subject=subject,
            title=title,
            upload_type=upload_type,
            content_type=file.content_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"document": doc.model_dump()}


@knowledge_router.post("/upload/text")
async def upload_text(
    content: str = Form(...),
    grade: int = Form(..., ge=1, le=6),
    subject: str = Form(...),
    title: str = Form(...),
    upload_type: str = Form("txt"),
    principal: str = Depends(authenticate),
):
    data = content.encode("utf-8")
    try:
        doc = service.upload_document(
            filename=f"{title}.txt",
            data=data,
            grade=grade,
            subject=subject,
            title=title,
            upload_type=upload_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"document": doc.model_dump()}


@knowledge_router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, principal: str = Depends(authenticate)):
    if not service.get_document(doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    service.delete_document(doc_id)
    return {"status": "ok", "doc_id": doc_id}


@knowledge_router.post("/documents/{doc_id}/reindex")
def reindex_document(doc_id: str, principal: str = Depends(authenticate)):
    try:
        doc = service.index_document(doc_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"document": doc.model_dump()}


@knowledge_router.post("/rebuild")
def rebuild_index(principal: str = Depends(authenticate)):
    try:
        count = service.rebuild_all()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "ok", "index_count": count}


@knowledge_router.post("/search")
def search_knowledge(req: KnowledgeSearchRequest, principal: str = Depends(authenticate)):
    hits = service.search(
        req.query,
        grade=req.grade,
        subject=req.subject,
        top_k=req.top_k,
    )
    return {"hits": [h.model_dump() for h in hits]}
