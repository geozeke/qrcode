#!/usr/bin/env bash
set -euo pipefail

script_dir="${BASH_SOURCE[0]%/*}"
source "$script_dir/compose_cli.sh"
configure_compose_cli

project_name="qrcode-smoke-${GITHUB_RUN_ID:-local}-$$"
secret="ci-render-token-secret-with-at-least-32-bytes"
host_port="${QR_TEST_HOST_PORT:-18080}"
headers_file="$(mktemp)"
preview_file="$(mktemp)"
download_file="$(mktemp)"
compose=("${compose_cli[@]}" --project-name "$project_name")
export QR_RENDER_TOKEN_SECRET="$secret"
export QR_IMAGE="${QR_IMAGE:-qrcode:local}"
export QR_HOST_PORT="$host_port"

cleanup() {
    status="$?"
    if ((status != 0)); then
        "${compose[@]}" ps || true
        "${compose[@]}" logs --no-color || true
    fi
    "${compose[@]}" down --volumes --remove-orphans || true
    rm -f -- "$headers_file" "$preview_file" "$download_file"
    return "$status"
}
trap cleanup EXIT

"${compose[@]}" up --detach --wait --wait-timeout 120 --no-build

base_url="http://127.0.0.1:$host_port"
curl --fail --silent --show-error "$base_url/health" \
    | grep --fixed-strings '"status":"ok"'
curl --fail --silent --show-error "$base_url/" \
    | grep --fixed-strings "QR Code Generator"

container_id="$("${compose[@]}" ps --quiet qrcode)"
test "$(docker inspect --format '{{.Config.User}}' "$container_id")" = "qrcode"
test "$(docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' "$container_id")" = "true"
test "$(docker inspect --format '{{.HostConfig.Init}}' "$container_id")" = "true"
test "$(docker inspect --format '{{.HostConfig.Memory}}' "$container_id")" = "536870912"
test "$(docker inspect --format '{{.HostConfig.NanoCpus}}' "$container_id")" = "1000000000"
test "$(docker inspect --format '{{.HostConfig.PidsLimit}}' "$container_id")" = "128"
test "$(docker inspect --format '{{.State.Health.Status}}' "$container_id")" = "healthy"
test "$(docker inspect --format '{{(index (index .NetworkSettings.Ports "8080/tcp") 0).HostIp}}' "$container_id")" = "127.0.0.1"
test "$("${compose[@]}" exec --no-TTY qrcode id -u)" != "0"

request='{"payload_type":"url","payload":{"url":"example.com/host-test"},"error_correction":"M","output_format":"png"}'
curl --fail --silent --show-error \
    --dump-header "$headers_file" \
    --output "$preview_file" \
    --form-string "request=$request" \
    "$base_url/api/preview"
grep -i '^content-type: image/png' "$headers_file"
grep -i '^cache-control: no-store' "$headers_file"
test -s "$preview_file"
render_token="$(awk 'tolower($1) == "x-render-token:" {gsub("\\r", "", $2); print $2}' "$headers_file")"
test -n "$render_token"

curl --fail --silent --show-error \
    --output "$download_file" \
    --form-string "request=$request" \
    --form-string "render_token=$render_token" \
    "$base_url/api/download"
test -s "$download_file"

"${compose[@]}" stop --timeout 30 qrcode
test "$(docker inspect --format '{{.State.Status}}' "$container_id")" = "exited"
