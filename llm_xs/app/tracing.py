"""LangSmith + OpenTelemetry 全链路追踪初始化。"""

from __future__ import annotations

import logging
import os

from .config import settings

logger = logging.getLogger(__name__)

_otel_initialized = False


def init_tracing(app=None) -> dict[str, bool]:
    """启动时配置追踪；返回各后端是否已启用。"""
    status = {"langsmith": False, "opentelemetry": False}

    if settings.enable_tracing:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        if settings.langsmith_project:
            os.environ.setdefault("LANGCHAIN_PROJECT", settings.langsmith_project)
        status["langsmith"] = True
        logger.info(
            "LangSmith 追踪已启用 project=%s",
            os.getenv("LANGCHAIN_PROJECT") or os.getenv("LANGSMITH_PROJECT", "-"),
        )

    if not settings.otel_enabled:
        return status

    global _otel_initialized
    if _otel_initialized:
        status["opentelemetry"] = True
        return status

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.warning("OpenTelemetry 依赖未安装，跳过 OTEL 初始化: %s", exc)
        return status

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": "3.0.0",
            "deployment.environment": settings.app_env,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    if app is not None:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(
                app,
                excluded_urls="health,ready,metrics",
            )
        except ImportError:
            logger.warning("opentelemetry-instrumentation-fastapi 未安装，跳过 FastAPI 自动埋点")

        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

            HTTPXClientInstrumentor().instrument()
        except ImportError:
            pass

    _otel_initialized = True
    status["opentelemetry"] = True
    logger.info("OpenTelemetry 追踪已启用 endpoint=%s", settings.otel_exporter_endpoint)
    return status


def shutdown_tracing() -> None:
    """进程退出时 flush span。"""
    if not _otel_initialized:
        return
    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
    except Exception as exc:  # noqa: BLE001
        logger.debug("OTEL shutdown: %s", exc)
