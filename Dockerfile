FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

ARG UV_VERSION=0.11.29

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    QR_WEB_ROOT="/app/web" \
    PORT=8080

WORKDIR /app
RUN groupadd --gid 10001 qrcode \
    && useradd --uid 10001 --gid qrcode --create-home qrcode
RUN pip install --no-cache-dir "uv==${UV_VERSION}"

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ ./src/
RUN UV_NO_CACHE=1 UV_PYTHON_DOWNLOADS=never \
    uv sync --locked --no-dev --no-editable --python /usr/local/bin/python3.12
COPY --from=frontend-build /app/frontend/build ./web/
RUN chown -R qrcode:qrcode /app

ARG VERSION=0.0.0-dev
ARG REVISION=unknown
ARG CREATED=unknown
LABEL org.opencontainers.image.title="QR Code Generator" \
    org.opencontainers.image.description="Private, stateless QR code generator" \
    org.opencontainers.image.source="https://github.com/geozeke/qrcode" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.version="${VERSION}" \
    org.opencontainers.image.revision="${REVISION}" \
    org.opencontainers.image.created="${CREATED}"

USER qrcode
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"
CMD ["sh", "-c", "uvicorn qrcode_web.app:create_app --factory --host 0.0.0.0 --port ${PORT} --timeout-graceful-shutdown 30"]
