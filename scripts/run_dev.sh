#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${QR_RENDER_TOKEN_SECRET:-}" ]]; then
    QR_RENDER_TOKEN_SECRET="$(uv run python -c 'import secrets; print(secrets.token_hex(32))')"
    export QR_RENDER_TOKEN_SECRET
fi

for port in 8080 5173; do
    if uv run python -c \
        "import socket; connection = socket.create_connection(('127.0.0.1', $port), timeout=0.2); connection.close()" \
        >/dev/null 2>&1; then
        echo "Port $port is already in use; stop the existing local server." >&2
        exit 1
    fi
done

uv run uvicorn qrcode_web.app:create_app \
    --factory --reload --host 127.0.0.1 --port 8080 &
backend_pid=$!

cleanup() {
    trap - EXIT INT TERM
    if kill -0 "$backend_pid" 2>/dev/null; then
        kill "$backend_pid" 2>/dev/null || true
    fi
    wait "$backend_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

backend_ready=false
for _ in {1..50}; do
    if uv run python -c \
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=1)" \
        >/dev/null 2>&1; then
        backend_ready=true
        break
    fi
    if ! kill -0 "$backend_pid" 2>/dev/null; then
        echo "Backend failed to start on http://127.0.0.1:8080." >&2
        wait "$backend_pid"
        exit 1
    fi
    sleep 0.1
done

if [[ "$backend_ready" != true ]]; then
    echo "Backend did not become ready on http://127.0.0.1:8080." >&2
    exit 1
fi

echo "Backend ready on http://127.0.0.1:8080. Starting frontend."
frontend_status=0
npm --prefix frontend run dev -- --strictPort || frontend_status=$?
if ((frontend_status != 0 && frontend_status != 130)); then
    exit "$frontend_status"
fi
