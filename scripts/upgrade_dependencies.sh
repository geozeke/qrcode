#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

export UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"

if [[ -n "$(git status --porcelain=v1 --untracked-files=all)" ]]; then
    echo "Cannot upgrade dependencies with a dirty worktree." >&2
    echo "Commit, stash, or discard local changes before running just upgrade." >&2
    exit 1
fi

before_versions="$(mktemp)"
commit_message="$(mktemp)"
candidate_uv_lock="$(mktemp)"
npm_outdated="$(mktemp)"
upgrade_packages="$(mktemp)"
cleanup() {
    rm -f \
        "$before_versions" "$commit_message" "$candidate_uv_lock" \
        "$npm_outdated" "$upgrade_packages"
}
trap cleanup EXIT

uv run python -m scripts.dependency_upgrades snapshot \
    --output "$before_versions"
uv run python -m scripts.dependency_upgrades resolve-python \
    --output "$candidate_uv_lock"

set +e
npm --prefix frontend outdated --json > "$npm_outdated"
npm_status=$?
set -e
if ((npm_status > 1)); then
    echo "npm outdated failed with exit code $npm_status." >&2
    exit "$npm_status"
fi

uv run python -m scripts.dependency_upgrades select \
    --candidate-uv-lock "$candidate_uv_lock" \
    --npm-outdated "$npm_outdated" \
    > "$upgrade_packages"

if [[ ! -s "$upgrade_packages" ]]; then
    echo "No outdated top-level dependencies found; no commit created."
    exit 0
fi

python_packages=()
javascript_packages=()
while IFS=$'\t' read -r ecosystem package; do
    case "$ecosystem" in
        python)
            python_packages+=("$package")
            ;;
        javascript)
            javascript_packages+=("$package")
            ;;
        *)
            echo "Unknown dependency ecosystem: $ecosystem" >&2
            exit 1
            ;;
    esac
done < "$upgrade_packages"

if ((${#python_packages[@]})); then
    uv_args=()
    for package in "${python_packages[@]}"; do
        uv_args+=(--upgrade-package "$package")
    done
    uv sync --all-groups "${uv_args[@]}"
fi

if ((${#javascript_packages[@]})); then
    npm --prefix frontend update "${javascript_packages[@]}" --no-fund
fi

if ! uv run python -m scripts.dependency_upgrades message \
    --before "$before_versions" \
    --output "$commit_message"; then
    git restore -- \
        pyproject.toml uv.lock \
        frontend/package.json frontend/package-lock.json
    echo "No compatible top-level dependency updates found; no commit created."
    exit 0
fi

git add -- \
    pyproject.toml uv.lock \
    frontend/package.json frontend/package-lock.json

if git diff --cached --quiet; then
    echo "No dependency file changes found; no commit created."
    exit 0
fi

git commit -F "$commit_message"
echo "Created a local dependency upgrade commit. Review it before pushing."
