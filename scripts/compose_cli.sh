#!/usr/bin/env bash

# Select the Compose v2 CLI form available on the current host.
configure_compose_cli() {
    if docker compose version >/dev/null 2>&1; then
        compose_cli=(docker compose)
    elif command -v docker-compose >/dev/null 2>&1; then
        compose_cli=(docker-compose)
    else
        echo "Docker Compose is required (docker compose or docker-compose)." >&2
        return 1
    fi
}
