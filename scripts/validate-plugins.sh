#!/usr/bin/env bash
# validate-plugins.sh - Validate all plugins against framework standards
# Run: make validate-plugins
# Or:  ./scripts/validate-plugins.sh [plugin-name]

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

MARKETPLACE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLUGINS_DIR="$MARKETPLACE_DIR/plugins"
MARKETPLACE_JSON="$MARKETPLACE_DIR/.claude-plugin/marketplace.json"

pass=0
fail=0
warn=0

check() {
  local label="$1"
  local result="$2"
  if [ "$result" = "pass" ]; then
    echo -e "  ${GREEN}✓${NC} $label"
    pass=$((pass + 1))
  elif [ "$result" = "warn" ]; then
    echo -e "  ${YELLOW}⚠${NC} $label"
    warn=$((warn + 1))
  else
    echo -e "  ${RED}✗${NC} $label"
    fail=$((fail + 1))
  fi
}

validate_plugin() {
  local plugin_dir="$1"
  local plugin_name
  plugin_name="$(basename "$plugin_dir")"

  echo -e "\n${BLUE}Validating ${plugin_name}...${NC}"

  # plugin.json exists and is valid JSON
  if [ -f "$plugin_dir/.claude-plugin/plugin.json" ]; then
    if python3 -m json.tool "$plugin_dir/.claude-plugin/plugin.json" > /dev/null 2>&1; then
      check "plugin.json exists and is valid JSON" "pass"
    else
      check "plugin.json exists but is INVALID JSON" "fail"
    fi
  else
    check "plugin.json missing" "fail"
  fi

  # version-tracking.json exists with valid commit hash
  if [ -f "$plugin_dir/.claude-plugin/version-tracking.json" ]; then
    local commit
    commit=$(python3 -c "import json; print(json.load(open('$plugin_dir/.claude-plugin/version-tracking.json')).get('versionCommit',''))" 2>/dev/null || echo "")
    if [ -n "$commit" ] && [ ${#commit} -ge 7 ]; then
      check "version-tracking.json exists with commit hash" "pass"
    else
      check "version-tracking.json exists but versionCommit is empty or too short" "warn"
    fi
  else
    check "version-tracking.json missing" "warn"
  fi

  # introduce skill exists
  if [ -f "$plugin_dir/skills/introduce/SKILL.md" ]; then
    check "introduce skill exists" "pass"
  else
    check "introduce skill missing" "warn"
  fi

  # At least one functional skill (besides introduce)
  local skill_count
  skill_count=$(find "$plugin_dir/skills" -name "SKILL.md" -not -path "*/introduce/*" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$skill_count" -ge 1 ]; then
    check "Has $skill_count functional skill(s)" "pass"
  else
    check "No functional skills found (only introduce)" "warn"
  fi

  # Check functional skills have mandatory patterns
  for skill_file in $(find "$plugin_dir/skills" -name "SKILL.md" -not -path "*/introduce/*" 2>/dev/null); do
    local skill_name
    skill_name="$(basename "$(dirname "$skill_file")")"

    if grep -q "TaskCreate\|TaskUpdate\|Task " "$skill_file" 2>/dev/null; then
      check "Skill '$skill_name' references task management" "pass"
    else
      check "Skill '$skill_name' missing task management references" "warn"
    fi

    if grep -q "AskUserQuestion" "$skill_file" 2>/dev/null; then
      check "Skill '$skill_name' references AskUserQuestion" "pass"
    else
      check "Skill '$skill_name' missing AskUserQuestion references" "warn"
    fi

    # YAML frontmatter check
    if head -1 "$skill_file" | grep -q "^---$"; then
      if grep -q "^name:" "$skill_file" && grep -q "^description:" "$skill_file"; then
        check "Skill '$skill_name' has YAML frontmatter with name and description" "pass"
      else
        check "Skill '$skill_name' has frontmatter but missing name/description" "warn"
      fi
    else
      check "Skill '$skill_name' missing YAML frontmatter" "warn"
    fi
  done

  # README exists and is minimal
  if [ -f "$plugin_dir/README.md" ]; then
    local readme_lines
    readme_lines=$(wc -l < "$plugin_dir/README.md" | tr -d ' ')
    if [ "$readme_lines" -le 50 ]; then
      check "README.md exists and is minimal ($readme_lines lines)" "pass"
    else
      check "README.md exists but is $readme_lines lines (target: <50)" "warn"
    fi
  else
    check "README.md missing" "warn"
  fi

  # Registered in marketplace.json
  if grep -q "\"$plugin_name\"" "$MARKETPLACE_JSON" 2>/dev/null; then
    check "Registered in marketplace.json" "pass"
  else
    check "NOT registered in marketplace.json" "fail"
  fi
}

# Marketplace-level checks
validate_marketplace() {
  echo -e "${BLUE}Validating marketplace structure...${NC}"

  # marketplace.json valid
  if python3 -m json.tool "$MARKETPLACE_JSON" > /dev/null 2>&1; then
    check "marketplace.json is valid JSON" "pass"
  else
    check "marketplace.json is INVALID JSON" "fail"
  fi

  # No duplicate plugin names
  local dupes
  dupes=$(python3 -c "
import json
with open('$MARKETPLACE_JSON') as f:
    data = json.load(f)
names = [p['name'] for p in data['plugins']]
dupes = [n for n in set(names) if names.count(n) > 1]
print(' '.join(dupes) if dupes else '')
" 2>/dev/null || echo "ERROR")

  if [ -z "$dupes" ]; then
    check "No duplicate plugin names in marketplace.json" "pass"
  else
    check "Duplicate plugin names: $dupes" "fail"
  fi

  # All registered plugins have directories
  local missing
  missing=$(python3 -c "
import json, os
with open('$MARKETPLACE_JSON') as f:
    data = json.load(f)
for p in data['plugins']:
    d = os.path.join('$PLUGINS_DIR', p['name'])
    if not os.path.isdir(d):
        print(p['name'])
" 2>/dev/null || echo "ERROR")

  if [ -z "$missing" ]; then
    check "All registered plugins have directories" "pass"
  else
    for m in $missing; do
      check "Registered plugin '$m' has no directory" "fail"
    done
  fi

  # All plugin directories are registered
  local unregistered
  unregistered=$(python3 -c "
import json, os
with open('$MARKETPLACE_JSON') as f:
    data = json.load(f)
registered = {p['name'] for p in data['plugins']}
for d in sorted(os.listdir('$PLUGINS_DIR')):
    if os.path.isdir(os.path.join('$PLUGINS_DIR', d)) and d not in registered:
        print(d)
" 2>/dev/null || echo "ERROR")

  if [ -z "$unregistered" ]; then
    check "All plugin directories are registered" "pass"
  else
    for u in $unregistered; do
      check "Plugin directory '$u' is NOT registered in marketplace.json" "warn"
    done
  fi
}

# Main
echo -e "${BLUE}Plugin Marketplace Validation${NC}"
echo -e "${BLUE}=============================${NC}"

validate_marketplace

if [ $# -gt 0 ]; then
  # Validate specific plugin
  if [ -d "$PLUGINS_DIR/$1" ]; then
    validate_plugin "$PLUGINS_DIR/$1"
  else
    echo -e "${RED}Plugin '$1' not found in $PLUGINS_DIR${NC}"
    exit 1
  fi
else
  # Validate all plugins
  for plugin_dir in "$PLUGINS_DIR"/*/; do
    [ -d "$plugin_dir" ] && validate_plugin "$plugin_dir"
  done
fi

# Summary
echo -e "\n${BLUE}Summary${NC}"
echo -e "  ${GREEN}✓ $pass passed${NC}"
[ $warn -gt 0 ] && echo -e "  ${YELLOW}⚠ $warn warnings${NC}"
[ $fail -gt 0 ] && echo -e "  ${RED}✗ $fail failed${NC}"

if [ $fail -gt 0 ]; then
  exit 1
fi
