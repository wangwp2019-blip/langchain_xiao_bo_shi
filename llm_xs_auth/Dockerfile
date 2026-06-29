# 小博士认证服务镜像（FastAPI + fastapi-fullauth，默认 SQLite）
FROM python:3.12-slim AS builder

WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt ./requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# ---- 运行时 ----
FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AUTH_API_HOST=0.0.0.0 \
    AUTH_API_PORT=8002

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY . .

RUN useradd -m -u 10002 authuser \
    && mkdir -p /app/data \
    && chown -R authuser:authuser /app
USER authuser

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8002/api/health').status==200 else 1)" || exit 1

CMD ["python", "run.py"]
