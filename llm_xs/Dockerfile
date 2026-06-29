# 小博士后端镜像（多阶段：builder 装依赖 -> slim 运行时，非 root）
FROM python:3.12-slim AS builder

WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.docker.txt ./requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# ---- 运行时 ----
FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    KIDS_API_HOST=0.0.0.0 \
    KIDS_API_PORT=8001 \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY . .

# 非 root 运行
RUN useradd -m -u 10001 appuser \
    && mkdir -p /app/data/index /app/data/memory /tmp/prometheus_multiproc \
    && chown -R appuser:appuser /app /tmp/prometheus_multiproc
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/api/health').status==200 else 1)" || exit 1

CMD ["gunicorn", "-c", "gunicorn_conf.py", "app.api:app"]
