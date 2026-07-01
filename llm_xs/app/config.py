"""集中配置模块（LangGraph 原生版）。

与旧项目共用同一套环境变量前缀 ``KIDS_*``，便于从旧项目迁移时只改代码路径、
不必重配 Key。默认 API 端口改为 **8001**，避免与旧项目 ``8000`` 冲突。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent  # chapter11-实战-小学生智能助手-langgraph/
TUTORIAL_ROOT = BASE_DIR.parent  # langchain1.2_tutorial/

load_dotenv(dotenv_path=TUTORIAL_ROOT / ".env", override=False)
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

if (os.getenv("KIDS_ENABLE_TRACING", "false") or "").lower() not in ("1", "true", "yes"):
    os.environ["LANGSMITH_TRACING"] = "false"


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


@dataclass
class Settings:
    """项目运行所需的全部配置。"""

    llm_model: str = _env("KIDS_LLM_MODEL", "glm-5.2")
    llm_provider: str = _env("KIDS_LLM_PROVIDER", "openai")
    llm_api_key: str | None = _env("KIDS_LLM_API_KEY", _env("CLOSEAI_API_KEY"))
    llm_base_url: str | None = _env("KIDS_LLM_BASE_URL", _env("CLOSEAI_BASE_URL"))
    structured_llm_model: str | None = _env("KIDS_STRUCTURED_LLM_MODEL")

    embed_model: str = _env("KIDS_EMBED_MODEL", "Pro/BAAI/bge-m3")
    embed_dim: int = int(_env("KIDS_EMBED_DIM", "1024"))
    embed_api_key: str | None = _env("KIDS_EMBED_API_KEY", _env("SILICONFLOW_API_KEY"))
    embed_base_url: str | None = _env("KIDS_EMBED_BASE_URL", _env("SILICONFLOW_BASE_URL"))

    tavily_api_key: str | None = _env("TAVILY_API_KEY")
    google_api_key: str | None = _env("GOOGLE_API_KEY")
    google_cse_id: str | None = _env("GOOGLE_CSE_ID")
    web_search_max_results: int = int(_env("KIDS_WEB_MAX_RESULTS", "3"))

    vector_backend: str = _env("KIDS_VECTOR_BACKEND", "local")
    force_reingest: str | None = _env("KIDS_FORCE_REINGEST")
    milvus_uri: str = _env("KIDS_MILVUS_URI", "http://localhost:19530")
    milvus_db: str = _env("KIDS_MILVUS_DB", "kids_rag")
    milvus_collection: str = _env("KIDS_MILVUS_COLLECTION", "kids_docs")

    memory_backend: str = _env("KIDS_MEMORY_BACKEND", "file")
    short_term_backend: str = _env("KIDS_SHORT_TERM_BACKEND", "memory")
    sqlite_checkpoint_path: Path = BASE_DIR / "data" / "checkpoints.db"
    postgres_url: str | None = _env("KIDS_POSTGRES_URL", _env("KIDS_DB_URL"))

    pg_pool_min_size: int = int(_env("KIDS_PG_POOL_MIN_SIZE", "1"))
    pg_pool_max_size: int = int(_env("KIDS_PG_POOL_MAX_SIZE", "10"))
    pg_pool_timeout: float = float(_env("KIDS_PG_POOL_TIMEOUT", "30"))

    # ---------- MySQL（预留业务库，与 Postgres 记忆库并列）----------
    mysql_url: str | None = _env("KIDS_MYSQL_URL")
    mysql_host: str = _env("KIDS_MYSQL_HOST", "127.0.0.1") or "127.0.0.1"
    mysql_port: int = int(_env("KIDS_MYSQL_PORT", "3306"))
    mysql_user: str | None = _env("KIDS_MYSQL_USER")
    mysql_password: str | None = _env("KIDS_MYSQL_PASSWORD")
    mysql_database: str | None = _env("KIDS_MYSQL_DATABASE", "kid_assistant")
    mysql_charset: str = _env("KIDS_MYSQL_CHARSET", "utf8mb4") or "utf8mb4"
    mysql_pool_min_size: int = int(_env("KIDS_MYSQL_POOL_MIN_SIZE", "1"))
    mysql_pool_max_size: int = int(_env("KIDS_MYSQL_POOL_MAX_SIZE", "10"))
    mysql_pool_timeout: float = float(_env("KIDS_MYSQL_POOL_TIMEOUT", "30"))
    mysql_auto_init_schema: bool = (
        _env("KIDS_MYSQL_AUTO_INIT_SCHEMA", "false") or ""
    ).lower() in ("1", "true", "yes")

    worker_concurrency: int = int(_env("KIDS_WORKER_CONCURRENCY", "2"))
    worker_max_queue: int = int(_env("KIDS_WORKER_MAX_QUEUE", "1000"))
    worker_max_retries: int = int(_env("KIDS_WORKER_MAX_RETRIES", "3"))
    worker_retry_base_delay: float = float(_env("KIDS_WORKER_RETRY_BASE_DELAY", "1.0"))

    chat_rate_limit_per_min: int = int(_env("KIDS_CHAT_RATE_LIMIT_PER_MIN", "30"))
    chat_timeout_seconds: float = float(_env("KIDS_CHAT_TIMEOUT_SECONDS", "60"))
    # True=SSE 逐 token 推送（在线 LLM）；False=先跑完再分块（兼容旧行为）
    chat_stream_native: bool = (
        _env("KIDS_CHAT_STREAM_NATIVE", "true") or "true"
    ).lower() in ("1", "true", "yes")
    # 每用户每日在线大模型调用上限（0=不限制）；防恶意刷量爆账单
    llm_daily_quota_per_user: int = int(_env("KIDS_LLM_DAILY_QUOTA_PER_USER", "0"))
    llm_max_retries: int = int(_env("KIDS_LLM_MAX_RETRIES", "2"))
    llm_retry_base_delay: float = float(_env("KIDS_LLM_RETRY_BASE_DELAY", "1.0"))
    llm_retry_max_delay: float = float(_env("KIDS_LLM_RETRY_MAX_DELAY", "30.0"))

    # ---------- OpenAI Moderation（可选）----------
    moderation_enabled: bool = (_env("KIDS_MODERATION_ENABLED", "false") or "").lower() in (
        "1",
        "true",
        "yes",
    )
    moderation_api_key: str | None = _env(
        "KIDS_MODERATION_API_KEY", _env("OPENAI_API_KEY", _env("CLOSEAI_API_KEY"))
    )
    moderation_base_url: str | None = _env(
        "KIDS_MODERATION_BASE_URL", _env("OPENAI_BASE_URL", _env("CLOSEAI_BASE_URL"))
    )

    # ---------- 安全 / 鉴权 / 限流 / 可观测（生产级）----------
    api_keys: str | None = _env("KIDS_API_KEYS")  # 逗号分隔；留空=开放模式
    jwt_secret: str | None = _env("KIDS_JWT_SECRET")  # 与认证服务 AUTH_JWT_SECRET 共享
    jwt_algorithm: str = _env("KIDS_JWT_ALGORITHM", "HS256")
    cors_origins: str = _env("KIDS_CORS_ORIGINS", "*")  # 逗号分隔来源白名单
    max_body_bytes: int = int(_env("KIDS_MAX_BODY_BYTES", str(64 * 1024)))
    knowledge_max_upload_bytes: int = int(
        _env("KIDS_KNOWLEDGE_MAX_UPLOAD_BYTES", str(100 * 1024 * 1024))
    )
    knowledge_index_async: bool = (
        _env("KIDS_KNOWLEDGE_INDEX_ASYNC", "true") or "true"
    ).lower() in ("1", "true", "yes")
    knowledge_pdf_ocr_max_pages: int = int(
        _env("KIDS_KNOWLEDGE_PDF_OCR_MAX_PAGES", "15")
    )
    # 检索是否按学生档案/请求参数过滤年级、学科（默认关闭，全库检索）
    knowledge_scope_filter: bool = (
        _env("KIDS_KNOWLEDGE_SCOPE_FILTER", "false") or "false"
    ).lower() in ("1", "true", "yes")
    # 简单聊天模式：无 onboarding/学情/学习域工具，仅聊天 + 知识库检索
    simple_chat_mode: bool = (
        _env("KIDS_SIMPLE_CHAT_MODE", "true") or "true"
    ).lower() in ("1", "true", "yes")
    hsts_max_age: int = int(_env("KIDS_HSTS_MAX_AGE", "0"))  # >0 时下发 Strict-Transport-Security
    metrics_token: str | None = _env("KIDS_METRICS_TOKEN")  # /metrics 抓取令牌
    api_rate_limit_per_min: int = int(_env("KIDS_API_RATE_LIMIT_PER_MIN", "60"))
    redis_url: str | None = _env("KIDS_REDIS_URL")  # 配置后限流跨实例共享
    ratelimit_fail_open: bool = (
        _env("KIDS_RATELIMIT_FAIL_OPEN", "true") or "true"
    ).lower() in ("1", "true", "yes")
    ratelimit_max_clients: int = int(_env("KIDS_RATELIMIT_MAX_CLIENTS", "10000"))

    # ---------- 生产环境 / 上线门禁 ----------
    app_env: str = _env("KIDS_ENV", "development") or "development"  # development | production
    require_auth: bool = (_env("KIDS_REQUIRE_AUTH", "") or "").lower() in (
        "1",
        "true",
        "yes",
    )
    ingest_token: str | None = _env("KIDS_INGEST_TOKEN")  # 灌库专用 Token，与 API Key 分离
    trusted_proxy_hops: int = int(_env("KIDS_TRUSTED_PROXY_HOPS", "0"))  # Nginx 反代时设为 1
    health_public_detail: bool = (
        _env("KIDS_HEALTH_PUBLIC_DETAIL", "") or ""
    ).lower() in ("1", "true", "yes")
    quiz_session_ttl_seconds: int = int(_env("KIDS_QUIZ_SESSION_TTL_SECONDS", "3600"))
    quiz_session_backend: str = _env("KIDS_QUIZ_SESSION_BACKEND", "auto") or "auto"
    mysql_audit_enabled: bool = (
        _env("KIDS_MYSQL_AUDIT_ENABLED", "true") or "true"
    ).lower() in ("1", "true", "yes")

    # ---------- 安全护栏词库外部化 ----------
    safety_words_path: str | None = _env("KIDS_SAFETY_WORDS_PATH")

    # ---------- Prompt 模板（可外部化）----------
    system_prompt_file: str | None = _env("KIDS_SYSTEM_PROMPT_FILE")
    system_prompt_extra: str | None = _env("KIDS_SYSTEM_PROMPT_EXTRA")

    # ---------- 长期记忆治理 ----------
    memory_max_items: int = int(_env("KIDS_MEMORY_MAX_ITEMS", "50"))
    memory_ttl_days: int = int(_env("KIDS_MEMORY_TTL_DAYS", "0"))  # 0=不过期

    # ---------- 合规：家长同意 / 数据留存 ----------
    require_parent_consent: bool = (
        _env("KIDS_REQUIRE_PARENT_CONSENT", "false") or "false"
    ).lower() in ("1", "true", "yes")
    consent_policy_version: str = _env("KIDS_CONSENT_POLICY_VERSION", "2025-06-01") or "2025-06-01"
    data_retention_days: int = int(_env("KIDS_DATA_RETENTION_DAYS", "365"))  # 0=不自动清理

    # ---------- 可观测：LangSmith / OpenTelemetry ----------
    enable_tracing: bool = (_env("KIDS_ENABLE_TRACING", "false") or "").lower() in (
        "1",
        "true",
        "yes",
    )
    langsmith_project: str | None = _env("KIDS_LANGSMITH_PROJECT", _env("LANGCHAIN_PROJECT"))
    otel_enabled: bool = (_env("KIDS_OTEL_ENABLED", "false") or "").lower() in (
        "1",
        "true",
        "yes",
    )
    otel_exporter_endpoint: str = (
        _env("KIDS_OTEL_EXPORTER_ENDPOINT", "http://localhost:4318/v1/traces") or ""
    )
    otel_service_name: str = _env("KIDS_OTEL_SERVICE_NAME", "kid-assistant") or "kid-assistant"
    retention_sweep_token: str | None = _env("KIDS_RETENTION_SWEEP_TOKEN")
    embedded_ui_enabled: bool = (
        _env("KIDS_EMBEDDED_UI", "") or ""
    ).lower() in ("1", "true", "yes")
    moderation_fail_open: bool = (
        _env("KIDS_MODERATION_FAIL_OPEN", "true") or "true"
    ).lower() in ("1", "true", "yes")

    log_level: str = _env("KIDS_LOG_LEVEL", "INFO")
    log_format: str = _env("KIDS_LOG_FORMAT", "text")  # text | json

    chunk_size: int = int(_env("KIDS_CHUNK_SIZE", "300"))
    chunk_overlap: int = int(_env("KIDS_CHUNK_OVERLAP", "80"))
    retrieve_top_k: int = int(_env("KIDS_TOP_K", "4"))

    api_host: str = _env("KIDS_API_HOST", "0.0.0.0")
    api_port: int = int(_env("KIDS_API_PORT", "8001"))

    base_dir: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "data"
    knowledge_file: Path = BASE_DIR / "data" / "kids_knowledge.txt"
    index_dir: Path = BASE_DIR / "data" / "index"
    memory_dir: Path = BASE_DIR / "data" / "memory"

    def ensure_dirs(self) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def llamaindex_persist_dir(self) -> Path:
        return self.index_dir / "llamaindex"

    @property
    def local_index_file(self) -> Path:
        return self.index_dir / "kids_vectors.json"

    @property
    def long_term_store_file(self) -> Path:
        return self.memory_dir / "long_term_store.json"

    def check_llm(self) -> list[str]:
        missing = []
        if not self.llm_api_key:
            missing.append("对话大模型 API Key（CLOSEAI_API_KEY 或 KIDS_LLM_API_KEY）")
        if not self.llm_base_url:
            missing.append("对话大模型 Base URL（CLOSEAI_BASE_URL 或 KIDS_LLM_BASE_URL）")
        return missing

    def check_embedding(self) -> list[str]:
        missing = []
        if not self.embed_api_key:
            missing.append("嵌入模型 API Key（SILICONFLOW_API_KEY 或 KIDS_EMBED_API_KEY）")
        if not self.embed_base_url:
            missing.append("嵌入模型 Base URL（SILICONFLOW_BASE_URL 或 KIDS_EMBED_BASE_URL）")
        return missing

    @property
    def llm_configured(self) -> bool:
        """是否已配置在线大模型（缺 Key 时 calculator 等离线能力仍可用）。"""
        return len(self.check_llm()) == 0

    @property
    def embedding_configured(self) -> bool:
        """是否已配置 Embedding（未配置时可切 keyword 向量后端）。"""
        return len(self.check_embedding()) == 0

    @property
    def web_search_enabled(self) -> bool:
        return self.tavily_enabled or self.google_search_enabled

    @property
    def tavily_enabled(self) -> bool:
        return bool(self.tavily_api_key)

    @property
    def google_search_enabled(self) -> bool:
        return bool(self.google_api_key and self.google_cse_id)

    @property
    def moderation_configured(self) -> bool:
        return self.moderation_enabled and bool(self.moderation_api_key)

    @property
    def mysql_configured(self) -> bool:
        """是否已配置 MySQL（URL 或 USER+DATABASE）。"""
        if self.mysql_url:
            return True
        return bool(self.mysql_user and self.mysql_database)

    @property
    def is_production(self) -> bool:
        return (self.app_env or "").lower() == "production"

    @property
    def auth_required(self) -> bool:
        """生产门禁：production 或 KIDS_REQUIRE_AUTH 时强制鉴权。"""
        return self.is_production or self.require_auth

    @property
    def auth_enabled(self) -> bool:
        """是否启用 API Key 鉴权（配置了 KIDS_API_KEYS 即启用）。"""
        return bool((self.api_keys or "").strip())

    @property
    def jwt_enabled(self) -> bool:
        return bool((self.jwt_secret or "").strip())

    @property
    def credentials_auth_enabled(self) -> bool:
        """JWT 或 API Key 任一配置即视为已启用鉴权凭证。"""
        return self.auth_enabled or self.jwt_enabled

    @property
    def embedded_ui_allowed(self) -> bool:
        """生产默认关闭内嵌 HTML UI，避免绕过前端 JWT/ConsentGate。"""
        if self.embedded_ui_enabled:
            return True
        return not self.is_production

    def validate_production(self) -> list[str]:
        """启动时校验生产配置，返回错误列表（空=通过）。"""
        errors: list[str] = []
        if not self.is_production and not self.auth_required:
            return errors

        if self.auth_required and not self.credentials_auth_enabled:
            errors.append(
                "生产模式必须配置 KIDS_API_KEYS 或 KIDS_JWT_SECRET（当前为开放模式）"
            )
        if self.is_production:
            if "*" in self.cors_origin_list:
                errors.append("生产模式禁止 KIDS_CORS_ORIGINS=*，请配置具体域名")
            if not self.ingest_token:
                errors.append("生产模式必须配置 KIDS_INGEST_TOKEN，限制 /api/ingest")
            if not self.require_parent_consent:
                errors.append("儿童产品生产环境建议 KIDS_REQUIRE_PARENT_CONSENT=true")
            if not self.retention_sweep_token:
                errors.append("生产模式建议配置 KIDS_RETENTION_SWEEP_TOKEN（留存清理 Cron）")
            if self.trusted_proxy_hops < 1:
                errors.append("生产模式经 Nginx 反代时 KIDS_TRUSTED_PROXY_HOPS 应 >= 1")
            if self.ratelimit_fail_open:
                errors.append("生产模式建议 KIDS_RATELIMIT_FAIL_OPEN=false")
            if self.moderation_enabled and self.moderation_fail_open:
                errors.append("生产模式启用 Moderation 时建议 KIDS_MODERATION_FAIL_OPEN=false")
            mem = self.memory_backend.lower()
            if mem in ("file", "memory"):
                errors.append(
                    f"生产模式长期记忆应使用 postgres，当前 memory_backend={mem}"
                )
            if not self.redis_url:
                errors.append("生产模式建议配置 KIDS_REDIS_URL（限流 + 出题会话）")

        workers = int(_env("WEB_CONCURRENCY", "1") or "1")
        if workers > 1:
            mem = self.memory_backend.lower()
            st = self.short_term_backend.lower()
            if mem in ("file", "memory") or st in ("memory", "sqlite"):
                errors.append(
                    f"多 Worker({workers}) 需 postgres 记忆 + redis 限流，"
                    f"当前 memory={mem} short_term={st}"
                )
            if not self.redis_url:
                errors.append("多 Worker 必须配置 KIDS_REDIS_URL 共享限流")
            qb = self.quiz_session_backend.lower()
            session_shared = bool(self.redis_url) or self.mysql_configured
            if qb in ("auto", "redis", "mysql") and not session_shared:
                errors.append(
                    f"多 Worker({workers}) 需 KIDS_REDIS_URL 或 KIDS_MYSQL_URL 共享出题会话"
                    f"（当前 KIDS_QUIZ_SESSION_BACKEND={qb}）"
                )
            if qb == "redis" and not self.redis_url:
                errors.append("KIDS_QUIZ_SESSION_BACKEND=redis 必须配置 KIDS_REDIS_URL")
            if qb == "mysql" and not self.mysql_configured:
                errors.append("KIDS_QUIZ_SESSION_BACKEND=mysql 必须配置 KIDS_MYSQL_URL")
        return errors

    @property
    def rag_engine(self) -> str:
        """health 展示用：llamaindex | keyword | legacy."""
        b = self.vector_backend.lower()
        if b in ("local", "milvus", "memory"):
            return "llamaindex"
        if b == "keyword":
            return "keyword"
        return "legacy"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in (self.cors_origins or "*").split(",") if o.strip()]


settings = Settings()
