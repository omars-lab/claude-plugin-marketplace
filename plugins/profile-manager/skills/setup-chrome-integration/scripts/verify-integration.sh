#!/usr/bin/env zsh
# verify-integration.sh
# Standalone diagnostic for profile-manager:setup-chrome-integration
# Run after setup to confirm all components are healthy.
# Usage: zsh scripts/verify-integration.sh

PASS="✓ PASS"
FAIL="✗ FAIL"
ALL_PASSED=true

# Resolve the latest installed profile-manager version
_pfm_resolve_mcp_config() {
  local base="${HOME}/.claude/plugins/cache/oeid-claude-plugins/profile-manager"
  local latest_version
  latest_version=$(ls "${base}" 2>/dev/null \
    | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' \
    | sort -t. -k1,1n -k2,2n -k3,3n \
    | tail -1)
  echo "${base}/${latest_version}/skills/setup-chrome-integration/mcp-chrome.json"
}

MCP_CONFIG=$(_pfm_resolve_mcp_config)

echo ""
echo "Chrome Integration — Verification"
echo "──────────────────────────────────────"

# 1. Chrome for Testing is running (informational — starts on demand via claude-with-chrome)
printf "Chrome for Testing running:    "
if pgrep -f "Google Chrome for Testing.*--remote-debugging-port" > /dev/null 2>&1; then
  PID=$(pgrep -f "Google Chrome for Testing.*--remote-debugging-port" | head -1)
  echo "${PASS} (PID: ${PID})"
else
  echo "- INFO (not running — starts on demand when claude-with-chrome is invoked)"
fi

# 2. Debug port responds (informational — only valid if Chrome is already running)
printf "Debug port 9222 responds:      "
RESP=$(curl -s --max-time 3 http://127.0.0.1:9222/json/version 2>/dev/null)
BROWSER=$(echo "${RESP}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Browser','?'))" 2>/dev/null)
if [[ -n "${BROWSER}" ]]; then
  echo "${PASS} (${BROWSER})"
else
  echo "- INFO (port not responding — expected if Chrome not yet started)"
fi

# 3. claude-with-chrome alias is defined
printf "claude-with-chrome alias:      "
if zsh -c 'source ~/.zshrc 2>/dev/null; type claude-with-chrome 2>/dev/null' | grep -q alias; then
  echo "${PASS}"
else
  echo "${FAIL} (alias not found — check ~/.zshrc for the managed block)"
  ALL_PASSED=false
fi

# 4. Log directory exists
printf "Log directory:                 "
LOG_DIR="${HOME}/Library/Logs/profile-manager"
if [[ -d "${LOG_DIR}" ]]; then
  echo "${PASS} (${LOG_DIR})"
else
  echo "${FAIL} (${LOG_DIR} not found — will be created on first Chrome start)"
  ALL_PASSED=false
fi

# 5. mcp-chrome.json resolves to a valid plugin cache path
printf "mcp-chrome.json (plugin):      "
if [[ -f "${MCP_CONFIG}" ]]; then
  echo "${PASS} (${MCP_CONFIG})"
else
  echo "${FAIL} (not found at ${MCP_CONFIG} — run make update in the plugin marketplace)"
  ALL_PASSED=false
fi

# 6. Neither settings.json nor .claude.json has chrome-devtools in default config
printf "MCP isolation (both configs):  "
python3 - << 'PYEOF'
import json, pathlib, sys

found_in = []
for name in ['.claude/settings.json', '.claude.json']:
    path = pathlib.Path.home() / name
    if not path.exists():
        continue
    try:
        s = json.loads(path.read_text())
        if 'chrome-devtools' in s.get('mcpServers', {}):
            found_in.append(name)
    except Exception:
        pass

if found_in:
    print(f"✗ FAIL (chrome-devtools still in: {', '.join(found_in)})")
    sys.exit(1)
else:
    print("✓ PASS (chrome-devtools not in default config)")
PYEOF
[[ $? -ne 0 ]] && ALL_PASSED=false

# 7. .zshrc has managed block
printf "~/.zshrc managed block:        "
if grep -q "profile-manager:setup-chrome-integration" ~/.zshrc 2>/dev/null; then
  echo "${PASS}"
else
  echo "${FAIL} (tagged block not found in ~/.zshrc)"
  ALL_PASSED=false
fi

echo "──────────────────────────────────────"
if ${ALL_PASSED}; then
  echo "All checks passed."
else
  echo "Some checks failed — see above."
fi
echo ""
echo "MCP config:  ${MCP_CONFIG}"
echo "Invoke with: claude-with-chrome"
echo "Logs:        tail -f ~/Library/Logs/profile-manager/chrome-for-testing.log"
echo "             Console.app → ~/Library/Logs → profile-manager/"
echo ""
