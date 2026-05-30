#!/bin/bash
# setup.sh — Create venv and install optional dependencies for noteplan-sweep.
#
# Run this once after cloning, or after pulling updates that add new deps:
#   cd plugins/noteplan-manager/bin
#   bash setup.sh
#
# After setup, noteplan-sweep auto-detects the venv and re-execs with it.
# No manual venv activation needed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

echo "Setting up noteplan-sweep venv at $VENV ..."

python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"

echo "Installing Playwright browser (chromium) ..."
"$VENV/bin/playwright" install chromium

echo ""
echo "✓ Setup complete. noteplan-sweep will auto-use the venv."
echo "  To verify: noteplan-sweep --version"
