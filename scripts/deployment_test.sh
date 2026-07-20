#!/usr/bin/env bash
set -euo pipefail

script_dir="${BASH_SOURCE[0]%/*}"
source "$script_dir/compose_cli.sh"

docker info >/dev/null
configure_compose_cli
"${compose_cli[@]}" version

image="${QR_IMAGE:-qrcode:host-test}"
version="${QR_IMAGE_VERSION:-host-test}"
revision="${QR_IMAGE_REVISION:-$(git rev-parse HEAD 2>/dev/null || echo unknown)}"
created="${QR_IMAGE_CREATED:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"

if docker buildx version >/dev/null 2>&1; then
    build=(docker buildx build --load)
elif command -v docker-buildx >/dev/null 2>&1; then
    build=(docker-buildx build --load)
else
    build=(docker build)
fi

"${build[@]}" \
    --build-arg VERSION="$version" \
    --build-arg REVISION="$revision" \
    --build-arg CREATED="$created" \
    --tag "$image" .

test "$(docker image inspect --format '{{.Config.User}}' "$image")" = "qrcode"
test "$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.version"}}' "$image")" = "$version"
test "$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image")" = "$revision"
test "$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.created"}}' "$image")" = "$created"
test "$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.licenses"}}' "$image")" = "MIT"
case "$(docker run --rm --entrypoint python "$image" --version)" in
    "Python 3.12."*) ;;
    *) echo "The production image is not using Python 3.12." >&2; exit 1 ;;
esac
case "$(docker run --rm --entrypoint uv "$image" --version)" in
    "uv 0.11.29 "*) ;;
    *) echo "The production image is not using uv 0.11.29." >&2; exit 1 ;;
esac

QR_IMAGE="$image" bash "$script_dir/compose_smoke.sh"
QR_IMAGE="$image" bash "$script_dir/proxy_smoke.sh"

echo "Docker deployment tests passed for $image."
