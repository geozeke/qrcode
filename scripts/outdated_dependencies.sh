#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

uv_tree="$(mktemp)"
npm_outdated="$(mktemp)"
cleanup() {
    rm -f "$uv_tree" "$npm_outdated"
}
trap cleanup EXIT

uv tree --outdated --depth=1 --all-groups > "$uv_tree"

set +e
npm --prefix frontend outdated --json > "$npm_outdated"
npm_status=$?
set -e
if ((npm_status > 1)); then
    echo "npm outdated failed with exit code $npm_status." >&2
    exit "$npm_status"
fi

uv run python -m scripts.dependency_upgrades report \
    --uv-tree "$uv_tree" \
    --npm-outdated "$npm_outdated"
