#!/usr/bin/env bash
set -euo pipefail

script_dir="${BASH_SOURCE[0]%/*}"
source "$script_dir/compose_cli.sh"
configure_compose_cli

project_name="qrcode-proxy-${GITHUB_RUN_ID:-local}-$$"
secret="ci-render-token-secret-with-at-least-32-bytes"
app_port="${QR_TEST_HOST_PORT:-18080}"
proxy_port="${QR_TEST_PROXY_PORT:-18081}"
compose=(
    "${compose_cli[@]}"
    --project-name "$project_name"
    --file compose.yaml
    --file compose.proxy.yaml
)
export QR_RENDER_TOKEN_SECRET="$secret"
export QR_IMAGE="${QR_IMAGE:-qrcode:local}"
export QR_HOST_PORT="$app_port"
export QR_PROXY_HOST_PORT="$proxy_port"

cleanup() {
    status="$?"
    if ((status != 0)); then
        "${compose[@]}" ps || true
        "${compose[@]}" logs --no-color || true
    fi
    "${compose[@]}" down --volumes --remove-orphans || true
    return "$status"
}
trap cleanup EXIT

"${compose[@]}" up --detach --wait --wait-timeout 120 --no-build

curl --fail --silent --show-error "http://127.0.0.1:$proxy_port/health" \
    | grep --fixed-strings '"status":"ok"'
if curl --fail --silent --max-time 2 "http://127.0.0.1:$app_port/health"; then
    echo "The application port remained published with the proxy override." >&2
    exit 1
fi

app_container_id="$("${compose[@]}" ps --quiet qrcode)"
proxy_container_id="$("${compose[@]}" ps --quiet proxy)"
test "$(docker inspect --format '{{json (index .NetworkSettings.Ports "8080/tcp")}}' "$app_container_id")" = "null"
test "$(docker inspect --format '{{len .NetworkSettings.Networks}}' "$app_container_id")" = "1"
test "$(docker inspect --format '{{len .NetworkSettings.Networks}}' "$proxy_container_id")" = "2"
test "$(docker inspect --format '{{.Config.User}}' "$proxy_container_id")" = "101:101"
test "$(docker inspect --format '{{(index (index .NetworkSettings.Ports "8080/tcp") 0).HostIp}}' "$proxy_container_id")" = "127.0.0.1"

proxy_config="$("${compose[@]}" exec --no-TTY proxy nginx -T 2>&1)"
grep --fixed-strings "client_max_body_size 5m" <<<"$proxy_config"
grep --fixed-strings "zone=preview:10m rate=2r/s" <<<"$proxy_config"
grep --fixed-strings "zone=download:10m rate=30r/m" <<<"$proxy_config"

status="$({ head -c $((5 * 1024 * 1024 + 1)) /dev/zero \
    | curl --silent --output /dev/null --write-out '%{http_code}' \
        --request POST --data-binary @- "http://127.0.0.1:$proxy_port/api/preview"; } 2>/dev/null)"
test "$status" = "413"
