#!/usr/bin/env bash
# validate-governance.sh — cross-repo validation for the plugin-governance feature.
# Run: make validate-governance   (or: ./scripts/validate-governance.sh [REPO ...])
#
# ─────────────────────────────────────────────────────────────────────────────
# WHY THIS EXISTS (the gap it closes)
# ─────────────────────────────────────────────────────────────────────────────
# The marketplace validates ITSELF (make validate-plugins: structure, versions,
# marketplace.json↔plugin.json parity). The SessionStart hook validates ONE
# consuming repo at session start. But nothing validates the *seam between* the
# marketplace and the repos that consume it via .claude/suggested-plugins.json.
#
# The motivating bug: a stale `documentation-manager@oeid-claude-plugins` ref in
# a repo's enabledPlugins was a silent no-op — the plugin didn't exist in the
# marketplace, but nothing flagged it. A suggested-plugins.json can carry the
# same class of dangling/typo'd reference. This script catches it.
#
# ─────────────────────────────────────────────────────────────────────────────
# WHAT IT CHECKS
# ─────────────────────────────────────────────────────────────────────────────
#   1. Hook self-test ....... the shared classification engine still produces the
#                             expected missing/not-enabled/stale output (headless,
#                             fixture-backed — no live ~/.claude needed).
#   2. Engine reachability .. the hook can locate compare-plugins.sh the same way
#                             it will at session start (via known_marketplaces.json
#                             installLocation, with fallbacks).
#   3. Per-manifest, for every discovered .claude/suggested-plugins.json:
#      a. Schema ............ valid JSON; top-level {plugins:[...]}; each entry has
#                             a "plugin" string of the form "<name>@<marketplace>".
#      b. Referential ....... every "<name>@<marketplace>" whose <marketplace> is
#                             THIS marketplace resolves to a real plugin in our
#                             marketplace.json. (Refs to OTHER marketplaces — e.g.
#                             @claude-plugins-official, @earlbear-claude-plugins —
#                             are out of our authority and are reported as info,
#                             not failed: we can't see their registries here.)
#
# ─────────────────────────────────────────────────────────────────────────────
# ASSUMPTIONS (stated so they can be checked / changed deliberately)
# ─────────────────────────────────────────────────────────────────────────────
#   A1. Consuming repos are SIBLINGS of this marketplace repo under the same
#       parent dir (../workspace, ../personalbook, ../projects/omars-lab.github.io,
#       ../prompts). Discovery is RELATIVE — no absolute paths, no ~/Users leak,
#       so the script is safe to commit and run on any clone. A repo that isn't
#       present is silently skipped (not an error): you may not have every repo
#       checked out. Override the set by passing repo paths as arguments.
#   A2. This marketplace's name (from marketplace.json `name`) is the authority
#       boundary: only refs to it are referentially validated here. We deliberately
#       do NOT fail on refs to marketplaces we don't own — we can't see their
#       registry, and false failures would train people to ignore this check.
#   A3. python3 is available (already a hard dep of the marketplace tooling).
#   A4. The manifest schema is `oeid-suggested-plugins/v1` as documented in
#       discover-oeid-plugins/skills/reconcile-plugins/guides/comparison-contract.md.
#       `required` and `reason` are advisory and not validated for content here.
#
# Exit 0 only if every check passes. Headless/CI-safe: no network, no auth, no
# writes. Designed to be wired into `make validate`.

set -uo pipefail

GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'

MARKETPLACE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MARKETPLACE_JSON="$MARKETPLACE_DIR/.claude-plugin/marketplace.json"
HOOK="$HOME/.claude/hooks/check-suggested-plugins.sh"
# Where this marketplace's reusable governance engine lives in-tree (the copy of
# record; the installed copy is what the hook actually sources at runtime).
ENGINE_INTREE="$MARKETPLACE_DIR/plugins/discover-oeid-plugins/scripts/compare-plugins.sh"

pass=0; fail=0; info=0
ok()   { echo -e "  ${GREEN}✓${NC} $1"; pass=$((pass+1)); }
bad()  { echo -e "  ${RED}✗${NC} $1";   fail=$((fail+1)); }
note() { echo -e "  ${YELLOW}ℹ${NC} $1"; info=$((info+1)); }

# This marketplace's name — the authority boundary for referential checks (A2).
MP_NAME="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['name'])" "$MARKETPLACE_JSON" 2>/dev/null)"

echo -e "${BLUE}Plugin Governance — cross-repo validation${NC}"
echo -e "${BLUE}=========================================${NC}"
echo "  marketplace: $MP_NAME"

# ── 1. Hook self-test ────────────────────────────────────────────────────────
echo -e "\n${BLUE}1. Hook self-test (classification engine)${NC}"
if [ -x "$HOOK" ]; then
  if "$HOOK" --self-test >/tmp/gov-selftest.$$ 2>&1; then
    ok "hook --self-test passed ($(grep -c PASS /tmp/gov-selftest.$$)/3)"
  else
    bad "hook --self-test FAILED:"; sed 's/^/      /' /tmp/gov-selftest.$$
  fi
  rm -f /tmp/gov-selftest.$$
else
  # Not installed → not a marketplace-side failure, but worth surfacing.
  note "hook not installed at $HOOK (skipping self-test; install to enable session-start checks)"
fi

# ── 2. Engine reachability ───────────────────────────────────────────────────
echo -e "\n${BLUE}2. Engine reachability${NC}"
if [ -f "$ENGINE_INTREE" ]; then
  ok "in-tree engine present: plugins/discover-oeid-plugins/scripts/compare-plugins.sh"
else
  bad "in-tree engine MISSING at $ENGINE_INTREE"
fi
# The hook resolves the *installed* engine via known_marketplaces.json. Mirror
# that resolution here so a broken install path is caught in CI, not at runtime.
KNOWN="$HOME/.claude/plugins/known_marketplaces.json"
if [ -f "$KNOWN" ]; then
  resolved="$(python3 - "$KNOWN" "$MP_NAME" <<'PY' 2>/dev/null
import json, os, sys
known = json.load(open(sys.argv[1])); name = sys.argv[2]
loc = (known.get(name) or {}).get("installLocation", "")
cand = os.path.join(loc, "plugins/discover-oeid-plugins/scripts/compare-plugins.sh")
print(cand if loc and os.path.isfile(cand) else "")
PY
)"
  if [ -n "$resolved" ]; then
    ok "hook can resolve installed engine via known_marketplaces.json"
  else
    note "installed engine not resolvable via known_marketplaces.json (ok in CI; hook falls back at runtime)"
  fi
else
  note "no known_marketplaces.json here (ok in CI/headless)"
fi

# ── 3. Per-manifest schema + referential integrity ───────────────────────────
echo -e "\n${BLUE}3. Suggested-plugins manifests${NC}"

# Discover manifests. If repo paths were passed as args, use those; else scan
# sibling repos relatively (A1). Silently skip repos that aren't checked out.
declare -a REPOS
if [ "$#" -gt 0 ]; then
  REPOS=("$@")
else
  PARENT="$(dirname "$MARKETPLACE_DIR")"
  for r in workspace personalbook projects/omars-lab.github.io prompts; do
    [ -d "$PARENT/$r" ] && REPOS+=("$PARENT/$r")
  done
fi

manifest_count=0
for repo in "${REPOS[@]}"; do
  manifest="$repo/.claude/suggested-plugins.json"
  [ -f "$manifest" ] || continue
  manifest_count=$((manifest_count+1))
  echo -e "  ${BLUE}$(basename "$repo")${NC}  ($manifest)"

  # Schema + referential check (extracted to _validate-manifest.py to keep this
  # shell free of heredoc-in-$() quoting hazards). Prints TSV: level<TAB>message.
  out="$(python3 "$MARKETPLACE_DIR/scripts/_validate-manifest.py" "$manifest" "$MARKETPLACE_JSON" "$MP_NAME")"

  while IFS=$'\t' read -r level msg; do
    [ -z "$level" ] && continue
    case "$level" in
      fail) bad "$msg" ;;
      info) note "$msg" ;;
      *)    ok "$msg" ;;
    esac
  done <<< "$out"
  # If no fail line was emitted for this manifest, credit a schema pass.
  echo "$out" | grep -q "^fail" || ok "$(basename "$repo"): schema + refs OK"
done

[ "$manifest_count" -eq 0 ] && note "no suggested-plugins.json manifests discovered (pass repo paths as args to target specific repos)"

# ── Summary ──────────────────────────────────────────────────────────────────
echo -e "\n${BLUE}Summary${NC}"
echo -e "  ${GREEN}✓ $pass passed${NC}"
[ "$info" -gt 0 ] && echo -e "  ${YELLOW}ℹ $info info${NC}"
if [ "$fail" -gt 0 ]; then
  echo -e "  ${RED}✗ $fail failed${NC}"
  exit 1
fi
echo -e "  ${GREEN}All governance checks passed.${NC}"
