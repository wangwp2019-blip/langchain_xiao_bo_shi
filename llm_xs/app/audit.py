"""安全审计日志（鉴权 / 护栏 / 记忆合规）。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from .config import settings

logger = logging.getLogger("kid.audit")


def _emit(event: str, **fields: Any) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    if settings.log_format.lower() == "json":
        logger.info(json.dumps(payload, ensure_ascii=False))
    else:
        logger.info("%s %s", event, payload)


def auth_failure(reason: str, *, client: str, request_id: str) -> None:
    _emit("auth_failure", reason=reason, client=client, request_id=request_id)


def auth_success(*, principal: str, request_id: str) -> None:
    _emit("auth_success", principal=principal, request_id=request_id)


def rate_limited(*, client: str, request_id: str, retry_after: int) -> None:
    _emit("rate_limited", client=client, request_id=request_id, retry_after=retry_after)


def safety_triggered(
    action: str,
    *,
    matched: str | None,
    request_id: str,
    principal: str,
) -> None:
    _emit(
        "safety_triggered",
        action=action,
        matched=matched,
        request_id=request_id,
        principal=principal,
    )


def memory_access(
    operation: str,
    *,
    user_id: str,
    principal: str,
    request_id: str,
    detail: str | None = None,
) -> None:
    _emit(
        "memory_access",
        operation=operation,
        user_id=user_id,
        principal=principal,
        request_id=request_id,
        detail=detail,
    )
