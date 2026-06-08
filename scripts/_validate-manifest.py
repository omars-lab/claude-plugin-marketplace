#!/usr/bin/env python3
# _validate-manifest.py — schema + referential check for ONE suggested-plugins.json.
# Called by validate-governance.sh (kept as a separate file to avoid bash
# heredoc-in-$()-quoting hazards). Prints TSV lines: <level>\t<message>, where
# level ∈ fail|info. Exit code is always 0; the caller counts fail lines.
#
# Args: <manifest.json> <marketplace.json> <this-marketplace-name>
#
# Checks:
#   - manifest is valid JSON with a top-level {"plugins": [...]}
#   - each entry is an object with a "plugin" string of form "<name>@<marketplace>"
#   - for refs whose <marketplace> is THIS marketplace, <name> exists in
#     marketplace.json (catches dangling/typo'd refs — the documentation-manager
#     bug class). Refs to other marketplaces are counted but not failed (we can't
#     see their registry from here).
import json
import sys


def emit(level, msg):
    print(f"{level}\t{msg}")


def main():
    manifest_path, mp_json_path, mp_name = sys.argv[1], sys.argv[2], sys.argv[3]

    try:
        m = json.load(open(manifest_path))
    except (OSError, ValueError) as e:
        emit("fail", f"invalid JSON: {e}")
        return

    if not isinstance(m, dict) or not isinstance(m.get("plugins"), list):
        emit("fail", 'missing top-level {"plugins": [...]}')
        return

    try:
        reg = {p.get("name") for p in json.load(open(mp_json_path)).get("plugins", [])}
    except (OSError, ValueError) as e:
        emit("fail", f"cannot read marketplace.json: {e}")
        return

    n_ours = n_other = 0
    for i, entry in enumerate(m["plugins"]):
        if not isinstance(entry, dict):
            emit("fail", f"plugins[{i}] is not an object")
            continue
        ref = entry.get("plugin")
        if not isinstance(ref, str) or "@" not in ref:
            emit("fail", f"plugins[{i}].plugin missing or not '<name>@<marketplace>': {ref!r}")
            continue
        name, mp = ref.split("@", 1)
        if mp == mp_name:
            n_ours += 1
            if name not in reg:
                emit("fail", f"{ref} -> '{name}' NOT in {mp_name} marketplace.json (dangling ref)")
        else:
            n_other += 1  # ref to a marketplace we don't own -> info only

    emit("info", f"{len(m['plugins'])} entries: {n_ours} ours, {n_other} external (not ref-checked)")


if __name__ == "__main__":
    main()
