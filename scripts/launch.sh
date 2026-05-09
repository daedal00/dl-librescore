#!/bin/bash
# ── LibreScore Desktop Launcher (macOS / Linux) ──
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Ensure uv is installed
if ! command -v uv &>/dev/null; then
    echo "Installing uv (Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Add uv to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv &>/dev/null; then
        echo "ERROR: uv installation failed. Please install manually:"
        echo "  https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
    echo "uv installed successfully!"
fi

echo "Starting LibreScore..."
cd "$SCRIPT_DIR"
exec uv run dl_librescore_app.py
