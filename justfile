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

image:
    docker build --tag qrcode:local .

compose-smoke:
    docker compose up --build --wait
    docker compose down

check: lint typecheck test

outdated:
    uv tree --outdated --depth=1 --all-groups
    npm --prefix frontend outdated

upgrade:
    bash scripts/upgrade_dependencies.sh

bump version:
    bash scripts/bump_version.sh {{version}}

tag-release:
    bash scripts/release_tags.sh
