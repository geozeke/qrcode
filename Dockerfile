FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
RUN groupadd --gid 10001 qrcode \
    && useradd --uid 10001 --gid qrcode --create-home qrcode
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
COPY --from=frontend-build /app/frontend/build ./web/
RUN chown -R qrcode:qrcode /app

USER qrcode
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"
CMD ["sh", "-c", "uvicorn qrcode_web.app:create_app --factory --host 0.0.0.0 --port ${PORT}"]
