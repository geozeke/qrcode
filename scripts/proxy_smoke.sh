#!/usr/bin/env bash
set -euo pipefail

project_name="qrcode-proxy-${GITHUB_RUN_ID:-local}-$$"
secret="ci-render-token-secret-with-at-least-32-bytes"
compose=(
    docker compose
    --project-name "$project_name"
    --file compose.yaml
    --file compose.proxy.yaml
)

cleanup() {
    QR_RENDER_TOKEN_SECRET="$secret" "${compose[@]}" down --volumes --remove-orphans
}
trap cleanup EXIT

QR_RENDER_TOKEN_SECRET="$secret" QR_IMAGE="${QR_IMAGE:-qrcode:local}" \
    "${compose[@]}" up --detach --wait --wait-timeout 120 --no-build

curl --fail --silent --show-error http://127.0.0.1:8081/health \
    | grep --fixed-strings '"status":"ok"'
if curl --fail --silent --max-time 2 http://127.0.0.1:8080/health; then
    echo "The application port remained published with the proxy override." >&2
    exit 1
fi

proxy_config="$("${compose[@]}" exec --no-TTY proxy nginx -T 2>&1)"
grep --fixed-strings "client_max_body_size 5m" <<<"$proxy_config"
grep --fixed-strings "zone=preview:10m rate=2r/s" <<<"$proxy_config"
grep --fixed-strings "zone=download:10m rate=30r/m" <<<"$proxy_config"

status="$({ head -c $((5 * 1024 * 1024 + 1)) /dev/zero \
    | curl --silent --output /dev/null --write-out '%{http_code}' \
        --request POST --data-binary @- http://127.0.0.1:8081/api/preview; } 2>/dev/null)"
test "$status" = "413"
