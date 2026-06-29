"""认证服务启动入口。

用法：python run.py  →  http://localhost:8002
"""

from __future__ import annotations

import uvicorn

from app.config import API_HOST, API_PORT

if __name__ == "__main__":
    print(f"启动认证服务：http://{API_HOST}:{API_PORT}")
    print("浏览器打开 http://localhost:%d 注册/登录" % API_PORT)
    uvicorn.run("app.main:app", host=API_HOST, port=API_PORT, reload=False)
