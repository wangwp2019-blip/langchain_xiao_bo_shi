"""安全 / 鉴权层：JWT + API Key 双模式鉴权 + 防越权（IDOR）身份派生。

鉴权优先级：
1. JWT（KIDS_JWT_SECRET 配置后启用，验证认证服务签发的 token）
2. 静态 API Key（KIDS_API_KEYS，向后兼容）
3. 开放模式（两者均未配置时，按 IP 识别）
"""

from __future__ import annotations

import hashlib
import hmac
import re

from fastapi import Header, HTTPException, Request

from .audit import auth_failure, auth_success
from .config import settings

try:
    import jwt as _jwt  # PyJWT
except ImportError:  # 未装 PyJWT 时 JWT 鉴权不可用，但不影响 API Key 模式
    _jwt = None

_ANON = "anon"
_SUB_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")


def _configured_keys() -> list[str]:
    raw = settings.api_keys or ""
    return [k.strip() for k in raw.split(",") if k.strip()]


def _fingerprint(principal: str) -> str:
    return hashlib.sha256(principal.encode("utf-8")).hexdigest()[:12]


def _verify_jwt(token: str) -> str | None:
    """验证 JWT 并返回 principal（``jwt:<user_id>``），失败返回 None。"""
    if _jwt is None or not settings.jwt_secret:
        return None
    try:
        payload = _jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        # fastapi-fullauth 的 sub 字段是用户 ID（字符串化的 UUID）
        sub = str(payload.get("sub", "")).strip()
        if not sub:
            return None
        return f"jwt:{sub}"
    except Exception:
        return None


def extract_presented_key(
    authorization: str | None = None,
    x_api_key: str | None = None,
) -> str | None:
    """从请求头提取 API Key（Bearer / X-API-Key）。"""
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    if x_api_key:
        return x_api_key.strip() or None
    return None


def resolve_client_ip(request: Request) -> str:
    """解析真实客户端 IP（信任 Nginx X-Forwarded-For 时需配置 KIDS_TRUSTED_PROXY_HOPS）。"""
    hops = settings.trusted_proxy_hops
    if hops > 0:
        xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if xff:
            parts = [p.strip() for p in xff.split(",") if p.strip()]
            if parts:
                idx = max(0, len(parts) - hops)
                return parts[idx]
    return request.client.host if request.client else _ANON


def compare_secret(presented: str | None, expected: str | None) -> bool:
    if not expected or presented is None:
        return False
    return hmac.compare_digest(presented, expected)


def client_id_from_request(request: Request) -> str:
    """限流维度：JWT/API Key 用户用身份指纹，开放模式用 IP + UA 前缀。"""
    presented = extract_presented_key(
        request.headers.get("authorization"),
        request.headers.get("x-api-key"),
    )
    if presented:
        # 优先 JWT
        jwt_principal = _verify_jwt(presented)
        if jwt_principal:
            return jwt_principal
        # 再试静态 API Key
        keys = _configured_keys()
        if keys:
            for key in keys:
                if hmac.compare_digest(presented, key):
                    return f"uid:{_fingerprint(presented)}"
    host = resolve_client_ip(request)
    ua = (request.headers.get("user-agent") or "")[:32]
    return f"ip:{host}:{hashlib.sha256(ua.encode()).hexdigest()[:8]}"


def sanitize_sub_id(value: str | None, *, field: str = "sub") -> str:
    """校验 user_id / thread_id / sub：长度与字符集，防 IDOR 注入。"""
    sub = (value or "default").strip() or "default"
    if not _SUB_ID_PATTERN.fullmatch(sub):
        raise HTTPException(
            status_code=400,
            detail=f"{field} 只能包含字母数字、点、下划线、连字符，最长 64 字符",
        )
    return sub


def authenticate(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> str:
    """FastAPI 依赖：校验 JWT / API Key 并返回 principal。

    鉴权优先级：JWT → 静态 API Key → 开放模式（均未配置时）。
    """
    rid = request.headers.get("X-Request-ID") or "-"
    client = resolve_client_ip(request)
    keys = _configured_keys()
    has_jwt = _jwt is not None and bool(settings.jwt_secret)

    # 都没配置 → 开放 / 生产模式拦截
    if not keys and not has_jwt:
        if settings.auth_required:
            auth_failure("missing_key_production", client=client, request_id=rid)
            raise HTTPException(
                status_code=503,
                detail="服务未正确配置鉴权（生产模式需要 KIDS_API_KEYS 或 KIDS_JWT_SECRET）",
            )
        return f"ip:{client}"

    presented = extract_presented_key(authorization, x_api_key)
    if not presented:
        auth_failure("missing_key", client=client, request_id=rid)
        raise HTTPException(
            status_code=401,
            detail="缺少认证凭证（JWT 或 API Key）",
            headers={"WWW-Authenticate": 'Bearer realm="kid-assistant"'},
        )

    # 1) 优先尝试 JWT
    if has_jwt:
        principal = _verify_jwt(presented)
        if principal:
            auth_success(principal=principal, request_id=rid)
            return principal

    # 2) 再尝试静态 API Key
    if keys:
        for key in keys:
            if hmac.compare_digest(presented, key):
                principal = f"uid:{_fingerprint(presented)}"
                auth_success(principal=principal, request_id=rid)
                return principal

    auth_failure("invalid_key", client=client, request_id=rid)
    raise HTTPException(
        status_code=401,
        detail="认证凭证无效",
        headers={"WWW-Authenticate": 'Bearer realm="kid-assistant"'},
    )


def derive_user_id(principal: str, requested: str | None) -> str:
    """从鉴权身份派生 user_id 命名空间（防 IDOR）。"""
    sub = sanitize_sub_id(requested, field="user_id")
    base = _fingerprint(principal)
    return f"{base}:{sub}"


def derive_thread_id(principal: str, requested: str | None) -> str:
    """从鉴权身份派生 thread_id 作用域（防 IDOR）。"""
    sub = sanitize_sub_id(requested, field="thread_id")
    base = _fingerprint(principal)
    return f"{base}:{sub}"


def verify_ingest_token(
    request: Request,
    x_ingest_token: str | None = Header(default=None, alias="X-Ingest-Token"),
) -> None:
    """灌库专用鉴权：生产环境必须配置 KIDS_INGEST_TOKEN。"""
    expected = settings.ingest_token
    if not expected:
        if settings.is_production:
            raise HTTPException(
                status_code=503,
                detail="生产环境未配置 KIDS_INGEST_TOKEN，禁止在线灌库",
            )
        return
    presented = (x_ingest_token or "").strip()
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        presented = presented or auth[7:].strip()
    if not compare_secret(presented, expected):
        raise HTTPException(status_code=403, detail="灌库 Token 无效")
