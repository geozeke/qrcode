set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

# Show the available project recipes
default: help

# Require initial setup to be complete
_require_setup:
    #!/usr/bin/env bash
    if [[ ! -f .init/setup ]]; then
        echo 'Please run "just setup" first.' >&2
        exit 1
    fi

# List available recipes and their descriptions
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
    bash scripts/setup.sh

# Synchronize installed dependencies with both lockfiles
sync: _require_setup
    uv sync --frozen --all-groups
    npm --prefix frontend ci --no-fund

# Start the backend and frontend development servers
run: _require_setup
    bash scripts/run_dev.sh

# Check Python and frontend linting and Python formatting
lint:
    uv run ruff check .
    uv run ruff format --check .
    npm --prefix frontend run lint

# Run Python and frontend static type checks
typecheck:
    uv run mypy src
    npm --prefix frontend run check

# Run the host backend and frontend test suites
test: _require_setup
    uv run pytest --tb=short
    npm --prefix frontend run test -- --run

# Run the Playwright end-to-end browser tests
test-e2e:
    npm --prefix frontend run test:e2e

# Validate direct dependency licenses against project policy
licenses:
    uv run python scripts/check_dependency_licenses.py

# Serve the Zensical documentation site locally
docs-serve:
    uv run --group docs zensical serve

# Build the Zensical documentation site in strict mode
docs-build:
    uv run --group docs zensical build --clean --strict

# Build the local production container image
image:
    docker build --tag qrcode:local .

# Test the application through its Docker Compose deployment
compose-smoke:
    docker build --tag qrcode:local .
    QR_IMAGE=qrcode:local bash scripts/compose_smoke.sh

# Test the reverse-proxy Docker Compose deployment
proxy-smoke:
    docker build --tag qrcode:local .
    QR_IMAGE=qrcode:local bash scripts/proxy_smoke.sh

# Run all on-host Docker deployment tests
deployment-test:
    bash scripts/deployment_test.sh

# Run the complete host quality-check suite
check: lint typecheck test docs-build licenses

# Report outdated direct Python and frontend dependencies
outdated:
    uv tree --outdated --depth=1 --all-groups
    npm --prefix frontend outdated

# Update dependency constraints and lockfiles
upgrade:
    bash scripts/upgrade_dependencies.sh

# Update project files to the specified release version
bump version:
    bash scripts/bump_version.sh {{ version }}

# Create and push the current version's release tag
tag-release:
    bash scripts/release_tags.sh
