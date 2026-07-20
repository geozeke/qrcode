#!/usr/bin/env bash
set -euo pipefail

for command_name in git node npm uv; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "qrcode requires $command_name. See docs/development.md." >&2
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
    echo "qrcode requires Node.js 22.13+ or 24+." >&2
    exit 1
fi

install_e2e_browser() {
    echo "Ensuring the Playwright Chromium browser is installed"
    npm --prefix frontend exec -- playwright install chromium
}

if [[ -f .init/setup ]]; then
    install_e2e_browser
    echo "Initial setup is already complete."
    exit 0
fi

mkdir -p .init
uv sync --locked --all-groups
npm --prefix frontend ci --no-fund
install_e2e_browser
touch .init/setup
echo "Setup complete. Run 'just test' to execute the host test suite."
