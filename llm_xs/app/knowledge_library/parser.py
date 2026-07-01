"""从 txt / pdf / 图片等提取纯文本。"""

from __future__ import annotations

import re
from pathlib import Path

from ..config import settings


def detect_upload_type(filename: str, content_type: str | None = None) -> str:
    ext = Path(filename).suffix.lower()
    if ext in (".txt", ".md", ".markdown"):
        return "txt"
    if ext == ".pdf":
        return "pdf"
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
        return "image"
    if ext in (".doc", ".docx", ".ppt", ".pptx"):
        return "document"
    if content_type:
        if "pdf" in content_type:
            return "pdf"
        if "text" in content_type:
            return "txt"
        if "image" in content_type:
            return "image"
    return "other"


def extract_text_from_bytes(
    data: bytes,
    *,
    filename: str,
    upload_type: str,
) -> str:
    if upload_type == "txt" or upload_type == "other":
        for enc in ("utf-8", "gbk", "utf-16"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="ignore")

    if upload_type == "pdf":
        return _extract_pdf(data, filename=filename)

    if upload_type == "image":
        return _extract_image(data, filename)

    if upload_type == "document":
        return _extract_document(data, filename)

    return data.decode("utf-8", errors="ignore")


def _extract_pdf(data: bytes, *, filename: str = "upload.pdf") -> str:
    errors: list[str] = []

    text = _extract_pdf_pymupdf(data)
    if _pdf_text_ok(text):
        return text
    if text:
        errors.append("pymupdf 文本过短")

    text = _extract_pdf_pypdf(data)
    if _pdf_text_ok(text):
        return text
    if text:
        errors.append("pypdf 文本过短")

    if settings.llm_configured:
        try:
            ocr_text = _extract_pdf_llm_ocr(data, filename=filename)
            if _pdf_text_ok(ocr_text):
                return ocr_text
            errors.append("LLM OCR 结果过短")
        except Exception as exc:
            errors.append(f"LLM OCR 失败：{exc}")

    hint = "；".join(errors) if errors else "可能是扫描版 PDF"
    raise RuntimeError(
        f"PDF 未能提取到有效文本（{hint}）。"
        "可尝试：1) 导出为 txt 再上传；"
        "2) 安装 pymupdf（pip install pymupdf）；"
        "3) 配置 LLM 多模态以自动 OCR 扫描版 PDF。"
    )


def _pdf_text_ok(text: str | None, min_len: int = 20) -> bool:
    return bool(text and len(text.strip()) >= min_len)


def _extract_pdf_pypdf(data: bytes) -> str:
    try:
        from io import BytesIO

        from pypdf import PdfReader
    except ImportError:
        return ""

    reader = PdfReader(BytesIO(data))
    if getattr(reader, "is_encrypted", False):
        try:
            reader.decrypt("")
        except Exception:
            pass
    parts: list[str] = []
    for page in reader.pages:
        t = ""
        try:
            t = page.extract_text(extraction_mode="layout") or ""
        except TypeError:
            t = page.extract_text() or ""
        except Exception:
            t = page.extract_text() or ""
        if t.strip():
            parts.append(t.strip())
    return "\n\n".join(parts)


def _extract_pdf_pymupdf(data: bytes) -> str:
    try:
        import fitz
    except ImportError:
        return ""

    doc = fitz.open(stream=data, filetype="pdf")
    parts: list[str] = []
    try:
        for page in doc:
            t = page.get_text("text") or ""
            if not t.strip():
                blocks = page.get_text("blocks") or []
                t = "\n".join(
                    b[4] for b in blocks if len(b) > 4 and isinstance(b[4], str)
                )
            if t.strip():
                parts.append(t.strip())
    finally:
        doc.close()
    return "\n\n".join(parts)


def _extract_pdf_llm_ocr(data: bytes, *, filename: str, max_pages: int | None = None) -> str:
    """扫描版 PDF：逐页渲染为图片后 LLM OCR。"""
    import logging

    import fitz

    logger = logging.getLogger(__name__)
    limit = max_pages if max_pages is not None else settings.knowledge_pdf_ocr_max_pages
    doc = fitz.open(stream=data, filetype="pdf")
    parts: list[str] = []
    try:
        total = min(len(doc), max(1, limit))
        if len(doc) > total:
            logger.info("PDF 共 %d 页，LLM OCR 前 %d 页", len(doc), total)
        for i in range(total):
            page = doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            img_bytes = pix.tobytes("png")
            page_name = f"{Path(filename).stem}-p{i + 1}.png"
            parts.append(_extract_image_llm(img_bytes, page_name))
    finally:
        doc.close()
    return "\n\n".join(p for p in parts if p.strip())

def _extract_image(data: bytes, filename: str) -> str:
    """图片 OCR：在线 LLM 多模态或离线提示。"""
    if settings.llm_configured:
        try:
            return _extract_image_llm(data, filename)
        except Exception:
            pass
    raise RuntimeError(
        "图片资料需配置 LLM 多模态能力，或请先 OCR 成 txt 再上传。"
    )


def _extract_image_llm(data: bytes, filename: str) -> str:
    import base64

    from langchain.chat_models import init_chat_model

    ext = Path(filename).suffix.lower().lstrip(".") or "png"
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "gif": "gif"}.get(
        ext, ext
    )
    b64 = base64.b64encode(data).decode("ascii")
    model = init_chat_model(
        settings.llm_model,
        model_provider=settings.llm_provider,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )
    msg = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "请完整 OCR 识别这张学习资料图片中的文字，保留题目与段落结构，只输出识别文字。",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/{mime};base64,{b64}"},
                },
            ],
        }
    ]
    resp = model.invoke(msg)
    text = resp.content if hasattr(resp, "content") else str(resp)
    text = str(text).strip()
    if len(text) < 10:
        raise RuntimeError("图片 OCR 结果过短")
    return text


def _extract_document(data: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".docx":
        try:
            from docx import Document
            from io import BytesIO

            doc = Document(BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            raise RuntimeError("Word 解析需要 python-docx：pip install python-docx")
    raise RuntimeError(f"暂不支持该文档格式 {ext}，请转为 txt 或 pdf 上传")


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
