"""知识库文件解析测试。"""

from __future__ import annotations

import pytest

from app.knowledge_library.parser import _extract_pdf_pypdf, _pdf_text_ok, extract_text_from_bytes


def test_pdf_text_ok():
    assert _pdf_text_ok("一二三四五六七八九十" * 2)
    assert not _pdf_text_ok("short")


def test_extract_pdf_minimal():
    # minimal valid PDF with text stream
    pdf = b"""%PDF-1.4
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj
4 0 obj<< /Length 44 >>stream
BT /F1 12 Tf 72 720 Td (Hello PDF text layer) Tj ET
endstream
endobj
5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000240 00000 n 
0000000333 00000 n 
trailer<< /Size 6 /Root 1 0 R >>
startxref
411
%%EOF
"""
    text = _extract_pdf_pypdf(pdf)
    assert "Hello PDF" in text or len(text) >= 10


def test_extract_txt():
    data = "二年级语文：识字与写字练习内容。".encode("utf-8")
    out = extract_text_from_bytes(data, filename="a.txt", upload_type="txt")
    assert "二年级" in out
