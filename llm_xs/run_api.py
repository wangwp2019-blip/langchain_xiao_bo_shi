"""FastAPI 服务入口（LangGraph 原生版，默认端口 8001）。

用法：
    python run_api.py
然后浏览器打开 http://localhost:8001
"""

from __future__ import annotations

import uvicorn

from app.config import settings
from app.logging_setup import configure_logging

if __name__ == "__main__":
    configure_logging()
    print(f"启动 LangGraph 版服务：http://{settings.api_host}:{settings.api_port}")
    print("浏览器访问 http://localhost:%d 开始和小博士聊天。" % settings.api_port)
    uvicorn.run(
        "app.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
