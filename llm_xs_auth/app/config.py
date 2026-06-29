"""认证服务配置。

与 llm_xs 共享 JWT 密钥（AUTH_JWT_SECRET = KIDS_JWT_SECRET），
llm_xs 验证本服务签发的 JWT 即可识别用户身份。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BASE_DIR = Path(__file__).resolve().parent.parent
TUTORIAL_ROOT = BASE_DIR.parent  # langchain1.2_tutorial/

load_dotenv(TUTORIAL_ROOT / ".env", override=False)
load_dotenv(BASE_DIR / ".env", override=True)

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---- 数据库（默认 SQLite，开箱即用）----
DATABASE_URL = os.getenv(
    "AUTH_DATABASE_URL",
    f"sqlite+aiosqlite:///{(DATA_DIR / 'auth.db').as_posix()}",
)

engine = create_async_engine(DATABASE_URL, echo=False)
session_maker = async_sessionmaker(engine, expire_on_commit=False)

# ---- JWT 密钥（与 llm_xs 的 KIDS_JWT_SECRET 保持一致）----
JWT_SECRET = os.getenv(
    "AUTH_JWT_SECRET",
    "kids-auth-shared-secret-change-me-32bytes!",
)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("AUTH_TOKEN_EXPIRE_MINUTES", "720"))  # 默认 12h（半天）

# ---- 服务参数 ----
API_HOST = os.getenv("AUTH_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("AUTH_API_PORT", "8002"))

# ---- llm_xs 大模型后端地址（登录后跳转用）----
LLM_XS_URL = os.getenv("LLM_XS_URL", "http://localhost:8001")
LLM_XS_FRONTEND_URL = os.getenv("LLM_XS_FRONTEND_URL", "http://localhost:5175")

# ---- CORS 来源白名单（逗号分隔；生产务必收敛到前端域名，勿用 *）----
# 默认放行本地前端开发端口；可用 AUTH_CORS_ORIGINS 覆盖。
_default_cors = ",".join(
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        LLM_XS_FRONTEND_URL,
    ]
)
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("AUTH_CORS_ORIGINS", _default_cors).split(",")
    if o.strip()
]
