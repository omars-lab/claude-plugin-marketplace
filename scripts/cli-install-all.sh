#!/bin/bash

# Install all plugins using Claude CLI (non-interactive)
# Run this OUTSIDE of a Claude session
# Usage: ./cli-install-all.sh

set -e

MARKETPLACE_NAME="oeid-claude-plugins"
MARKETPLACE_PATH="/Users/omar.eid/workspace/oeid-claude-plugin-marketplace"

echo "🚀 Installing all plugins via Claude CLI..."
echo ""
echo "⚠️  Make sure you're running this OUTSIDE of a Claude session!"
echo ""

# Check if we're in a Claude session
if [ -n "$CLAUDECODE" ]; then
    echo "❌ Error: Cannot run inside a Claude Code session."
    echo "   Please exit Claude and run this script from your terminal."
    exit 1
fi

# Check if claude CLI is available
if ! command -v claude &> /dev/null; then
    echo "❌ Error: 'claude' CLI not found in PATH"
    exit 1
fi

# Get list of plugins
plugins=(
    "claude-permission-config-manager"
    "discover-oeid-plugins"
    "noteplan-daily-organizer"
    "noteplan-note-creator"
    "noteplan-structure-analyzer"
    "noteplan-templates"
)

# Install each plugin
failed=0
for plugin in "${plugins[@]}"; do
    echo "📦 Installing $plugin..."

    # Use -p flag for non-interactive prompt
    if claude -p "/plugin install $plugin@$MARKETPLACE_NAME" --no-color 2>&1 | grep -q "successfully\|installed\|complete"; then
        echo "   ✓ Success"
    else
        echo "   ✗ Failed or already installed"
        failed=$((failed + 1))
    fi
    echo ""

    # Brief delay to avoid overwhelming the system
    sleep 1
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $failed -eq 0 ]; then
    echo "✅ All plugins installed successfully!"
else
    echo "⚠️  Some plugins may have failed or were already installed"
fi
echo ""
echo "Next steps:"
echo "  1. Start a new Claude session"
echo "  2. Test with: /discover-oeid-plugins:explore-plugins"
echo ""
