set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default: help

help:
    @just --list

setup:
    uv sync --all-groups
    npm --prefix frontend ci

sync:
    uv sync --frozen --all-groups
    npm --prefix frontend ci

lint:
    uv run ruff check .
    uv run ruff format --check .
    npm --prefix frontend run lint

typecheck:
    uv run mypy src
    npm --prefix frontend run check

test:
    uv run pytest
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
    bash scripts/bump_version.sh {{version}}

tag-release:
    bash scripts/release_tags.sh
