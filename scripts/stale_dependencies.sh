#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

candidate_uv_lock="$(mktemp)"
uv_tree="$(mktemp)"
build_system_outdated="$(mktemp)"
npm_outdated="$(mktemp)"
cleanup() {
    rm -f \
        "$candidate_uv_lock" "$uv_tree" \
        "$build_system_outdated" "$npm_outdated"
}
trap cleanup EXIT

uv run python -m scripts.dependency_upgrades resolve-python \
    --output "$candidate_uv_lock"
uv tree --outdated --depth=1 --all-groups > "$uv_tree"
uv run python -m scripts.dependency_upgrades resolve-build-system \
    --output "$build_system_outdated"

set +e
npm --prefix frontend outdated --json > "$npm_outdated"
npm_status=$?
set -e
if ((npm_status > 1)); then
    echo "npm outdated failed with exit code $npm_status." >&2
    exit "$npm_status"
fi

uv run python -m scripts.dependency_upgrades report \
    --candidate-uv-lock "$candidate_uv_lock" \
    --uv-tree "$uv_tree" \
    --build-system-outdated "$build_system_outdated" \
    --npm-outdated "$npm_outdated"
