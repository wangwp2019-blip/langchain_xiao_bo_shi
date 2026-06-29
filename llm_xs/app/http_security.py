"""HTTP 安全中间件：请求体限制 + 安全响应头。"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response

from .config import settings


async def read_body_with_limit(request: Request, max_bytes: int) -> bytes | None:
    """读取并限制请求体大小；超限返回 None（调用方应返回 413）。"""
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > max_bytes:
        return None

    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > max_bytes:
            return None

    # 将 body 重新注入，供下游路由读取
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive  # noqa: SLF001
    return body


def apply_security_headers(response: Response, *, path: str, rid: str) -> None:
    """生产级安全响应头（API + 静态页）。"""
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    elif path == "/":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"
        )

    if settings.hsts_max_age > 0:
        response.headers["Strict-Transport-Security"] = (
            f"max-age={settings.hsts_max_age}; includeSubDomains"
        )
