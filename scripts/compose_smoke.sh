#!/usr/bin/env bash
set -euo pipefail

project_name="qrcode-smoke-${GITHUB_RUN_ID:-local}-$$"
secret="ci-render-token-secret-with-at-least-32-bytes"
compose=(docker compose --project-name "$project_name")

cleanup() {
    QR_RENDER_TOKEN_SECRET="$secret" "${compose[@]}" down --volumes --remove-orphans
}
trap cleanup EXIT

QR_RENDER_TOKEN_SECRET="$secret" QR_IMAGE="${QR_IMAGE:-qrcode:local}" \
    "${compose[@]}" up --detach --wait --wait-timeout 120 --no-build

curl --fail --silent --show-error http://127.0.0.1:8080/health \
    | grep --fixed-strings '"status":"ok"'
curl --fail --silent --show-error http://127.0.0.1:8080/ \
    | grep --fixed-strings "QR Code Generator"

container_id="$("${compose[@]}" ps --quiet qrcode)"
test "$(docker inspect --format '{{.Config.User}}' "$container_id")" = "qrcode"
test "$(docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' "$container_id")" = "true"
test "$(docker inspect --format '{{.State.Health.Status}}' "$container_id")" = "healthy"
test "$("${compose[@]}" exec --no-TTY qrcode id -u)" != "0"

"${compose[@]}" stop --timeout 30 qrcode
test "$(docker inspect --format '{{.State.Status}}' "$container_id")" = "exited"
