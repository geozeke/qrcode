set shell := ["bash", "-eu", "-o", "pipefail", "-c"]
project_name := "qrcode"

default: help

# Require initial setup to be complete
_require_setup:
    #!/usr/bin/env bash
    if [[ ! -f .init/setup ]]; then
        echo 'Please run "just setup" first.' >&2
        exit 1
    fi

help:
    @just --list

# Remove generated caches, reports, and build outputs
clean:
    #!/usr/bin/env bash
    echo "Cleaning generated caches, reports, and build outputs"
    rm -rf -- \
        .mypy_cache .pytest_cache .ruff_cache .uv-cache \
        build coverage dist htmlcov site \
        frontend/.svelte-kit frontend/build frontend/coverage \
        frontend/playwright-report frontend/test-results
    rm -f -- .coverage .coverage.* coverage.xml
    find src tests frontend/src frontend/tests \
        -type d -name __pycache__ -prune -exec rm -rf -- {} +
    find src -type d -name '*.egg-info' -prune -exec rm -rf -- {} +
    find src tests frontend/src frontend/tests \
        -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

# Remove generated files and installed project environments
reset: clean
    #!/usr/bin/env bash
    echo "Resetting project state"
    rm -rf -- .init .venv frontend/node_modules node_modules

# Create locked Python and frontend development environments
setup:
    #!/usr/bin/env bash
    if [[ -f .init/setup ]]; then
        echo "Initial setup is already complete. To start fresh, run:"
        echo
        echo "just reset"
        echo "just setup"
        exit 0
    fi
    for command_name in git node npm uv; do
        if ! command -v "$command_name" >/dev/null 2>&1; then
            echo "{{ project_name }} requires $command_name. See docs/development.md." >&2
            exit 1
        fi
    done
    node_version="$(node --version | sed -E 's/^v([0-9]+)\.([0-9]+).*/\1 \2/')"
    read -r node_major node_minor <<< "$node_version"
    if [[ ! "$node_major" =~ ^[0-9]+$ ]] \
        || [[ ! "$node_minor" =~ ^[0-9]+$ ]] \
        || ((node_major < 22)) \
        || ((node_major == 22 && node_minor < 13)) \
        || ((node_major == 23)); then
        echo "{{ project_name }} requires Node.js 22.13+ or 24+." >&2
        exit 1
    fi
    mkdir -p .init
    uv sync --locked --all-groups
    npm --prefix frontend ci --no-fund
    touch .init/setup
    echo "Setup complete. Run 'just test' to execute the host test suite."

sync: _require_setup
    uv sync --frozen --all-groups
    npm --prefix frontend ci --no-fund

lint:
    uv run ruff check .
    uv run ruff format --check .
    npm --prefix frontend run lint

typecheck:
    uv run mypy src
    npm --prefix frontend run check

test: _require_setup
    uv run pytest --tb=short
    npm --prefix frontend run test -- --run

test-e2e:
    npm --prefix frontend run test:e2e

licenses:
    uv run python scripts/check_dependency_licenses.py

docs-serve:
    uv run --group docs zensical serve

docs-build:
    uv run --group docs zensical build --clean --strict

image:
    docker build --tag qrcode:local .

compose-smoke:
    docker build --tag qrcode:local .
    QR_IMAGE=qrcode:local bash scripts/compose_smoke.sh

proxy-smoke:
    docker build --tag qrcode:local .
    QR_IMAGE=qrcode:local bash scripts/proxy_smoke.sh

deployment-test:
    bash scripts/deployment_test.sh

check: lint typecheck test docs-build licenses

outdated:
    uv tree --outdated --depth=1 --all-groups
    npm --prefix frontend outdated

upgrade:
    bash scripts/upgrade_dependencies.sh

bump version:
    bash scripts/bump_version.sh {{ version }}

tag-release:
    bash scripts/release_tags.sh
