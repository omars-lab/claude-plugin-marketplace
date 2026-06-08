#!/usr/bin/env bash
# compare-plugins.sh — the ONE definition of "missing / not-enabled / stale".
#
# Sourceable library shared by:
#   - the SessionStart hook (~/.claude/hooks/check-suggested-plugins.sh)
#   - the reconcile-plugins skill
#
# It is pure read-only: it reads a repo's .claude/suggested-plugins.json and
# compares each suggested plugin against install state and the repo's
# enabledPlugins, classifying every entry as ok | missing | not-enabled | stale.
#
# No interactive auth, no network, no writes. Headless/CI safe.
#
# Override these for tests (see --self-test in the hook):
#   GOV_MARKETPLACES_DIR  default: ~/.claude/plugins/marketplaces
#   GOV_KNOWN_MARKETPLACES default: ~/.claude/plugins/known_marketplaces.json
#
# Usage:
#   source compare-plugins.sh
#   gov_compare /path/to/repo        # prints TSV: status<TAB>ref<TAB>detail
#
# Requires: python3 (already a hard dep of this marketplace's tooling).

GOV_MARKETPLACES_DIR="${GOV_MARKETPLACES_DIR:-$HOME/.claude/plugins/marketplaces}"
GOV_KNOWN_MARKETPLACES="${GOV_KNOWN_MARKETPLACES:-$HOME/.claude/plugins/known_marketplaces.json}"

# gov_compare REPO_DIR
# Emits one TSV line per suggested plugin:
#   <status>\t<plugin@marketplace>\t<detail>
# where status ∈ ok|missing|not-enabled|stale and detail carries the fix hint
# payload (e.g. "1.1.0<1.3.0" for stale). Emits nothing and returns 0 if the
# repo has no manifest (manifest-gated: callers treat empty output as "no-op").
gov_compare() {
  local repo_dir="$1"
  local manifest="$repo_dir/.claude/suggested-plugins.json"
  [ -f "$manifest" ] || return 0

  GOV_MARKETPLACES_DIR="$GOV_MARKETPLACES_DIR" \
  GOV_KNOWN_MARKETPLACES="$GOV_KNOWN_MARKETPLACES" \
  python3 - "$manifest" "$repo_dir/.claude/settings.json" <<'PY'
import json, os, sys

manifest_path, settings_path = sys.argv[1], sys.argv[2]
mp_dir = os.environ["GOV_MARKETPLACES_DIR"]
known_path = os.environ["GOV_KNOWN_MARKETPLACES"]

def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default

manifest = load(manifest_path, {})
suggested = manifest.get("plugins", [])

settings = load(settings_path, {})
enabled = settings.get("enabledPlugins", {})

# Resolve each marketplace's on-disk root. A directory-source marketplace lives
# at its repo path (installLocation); a github-source one lives under
# GOV_MARKETPLACES_DIR/<mp>. known_marketplaces.json records installLocation for
# both, so prefer it; fall back to the conventional GOV_MARKETPLACES_DIR/<mp>.
known = load(known_path, {})

def marketplace_root(mp):
    loc = (known.get(mp) or {}).get("installLocation")
    if loc and os.path.isdir(loc):
        return loc
    return os.path.join(mp_dir, mp)

def installed_dir(name, mp):
    return os.path.join(marketplace_root(mp), "plugins", name)

def marketplace_version(name, mp):
    """Version registered for <name> in <mp>'s marketplace.json, or None."""
    mj = load(os.path.join(marketplace_root(mp), ".claude-plugin", "marketplace.json"), None)
    if not mj:
        return None
    for p in mj.get("plugins", []):
        if p.get("name") == name:
            return p.get("version")
    return None

def installed_version(name, mp):
    pj = load(os.path.join(installed_dir(name, mp), ".claude-plugin", "plugin.json"), None)
    return pj.get("version") if pj else None

def vtuple(v):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except (ValueError, AttributeError):
        return None

for entry in suggested:
    ref = entry.get("plugin", "")          # "name@marketplace"
    if "@" not in ref:
        continue
    name, mp = ref.split("@", 1)

    if not os.path.isdir(installed_dir(name, mp)):
        print(f"missing\t{ref}\t")
        continue
    if not enabled.get(ref, False):
        print(f"not-enabled\t{ref}\t")
        continue

    inst, reg = installed_version(name, mp), marketplace_version(name, mp)
    it, rt = vtuple(inst), vtuple(reg)
    if it and rt and it < rt:
        print(f"stale\t{ref}\t{inst}<{reg}")
        continue

    print(f"ok\t{ref}\t")
PY
}
