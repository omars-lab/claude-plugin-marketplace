#!/bin/bash

# Install a single plugin by symlinking it to the Claude plugins directory
# Usage: ./install-plugin.sh <plugin-name>

if [ -z "$1" ]; then
    echo "Usage: $0 <plugin-name>"
    exit 1
fi

PLUGIN_NAME="$1"
MARKETPLACE_NAME="oeid-claude-plugins"
MARKETPLACE_PATH="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_SOURCE="$MARKETPLACE_PATH/plugins/$PLUGIN_NAME"
MARKETPLACE_BASE="$HOME/.claude/plugins/marketplaces/$MARKETPLACE_NAME"
INSTALL_BASE="$MARKETPLACE_BASE/plugins"
PLUGIN_DEST="$INSTALL_BASE/$PLUGIN_NAME"

# Check if plugin exists in source
if [ ! -d "$PLUGIN_SOURCE" ]; then
    echo "Error: Plugin '$PLUGIN_NAME' not found in $MARKETPLACE_PATH/plugins/"
    exit 1
fi

# Check if plugin has required structure
if [ ! -f "$PLUGIN_SOURCE/.claude-plugin/plugin.json" ]; then
    echo "Error: Plugin '$PLUGIN_NAME' missing .claude-plugin/plugin.json"
    exit 1
fi

# Create marketplace directory structure if it doesn't exist
mkdir -p "$INSTALL_BASE"

# Create marketplace.json if it doesn't exist
if [ ! -f "$MARKETPLACE_BASE/marketplace.json" ]; then
    if [ -f "$MARKETPLACE_PATH/.claude-plugin/marketplace.json" ]; then
        cp "$MARKETPLACE_PATH/.claude-plugin/marketplace.json" "$MARKETPLACE_BASE/marketplace.json"
    fi
fi

# Remove existing installation (symlink or directory)
if [ -L "$PLUGIN_DEST" ] || [ -d "$PLUGIN_DEST" ]; then
    rm -rf "$PLUGIN_DEST"
fi

# Create symlink
ln -s "$PLUGIN_SOURCE" "$PLUGIN_DEST"

if [ $? -eq 0 ]; then
    echo "✓ Successfully installed $PLUGIN_NAME"
    exit 0
else
    echo "✗ Failed to install $PLUGIN_NAME"
    exit 1
fi
