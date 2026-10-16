#!/usr/bin/env python3
"""Set up a technique hub: a private git repo that holds the specs, replacements, context, notes
and comment threads, with the screenshots left where they are.

Copies the specs (and _redactions.json) and techniques.json from the current techniques folder
into <hub>/, writes hub.json (where the screenshots are), the Makefile, CLAUDE.md, .gitignore and
a pre-push hook that only allows the remotes listed in hub.json. Then points every
technique-manager script at the hub (~/.config/technique-manager/settings.json).
Never deletes anything. Refuses if the hub already has specs.

Usage:
    python3 migrate_to_hub.py --hub ~/workspace/technique-hub [--from <techniques folder>]
        [--allow-remote <host:path>]...

Output (JSON): {"hub", "specs": N, "screenshots", "files": [...]}
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "recreate-technique" / "scripts"))
import lib  # noqa: E402

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
SKILLS = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hub", required=True)
    ap.add_argument("--from", dest="src")
    ap.add_argument("--allow-remote", action="append", default=[],
                    help="a remote URL pushes may go to (repeat); the pre-push hook refuses any other")
    args = ap.parse_args()

    hub = Path(args.hub).expanduser()
    src = lib.find_root(args.src) if args.src else lib.DEFAULT_ROOT
    src = lib.find_root(str(src))
    if lib.is_hub(src):
        raise SystemExit(f"{src} is already a hub")
    if not (hub / ".git").exists():
        raise SystemExit(f"{hub} is not a git repo; clone or init it first")
    if (hub / "specs").exists() and any((hub / "specs").glob("*.json")):
        raise SystemExit(f"{hub}/specs already has specs; refusing to overwrite")

    files = []
    (hub / "specs").mkdir(parents=True, exist_ok=True)
    for p in sorted(lib.specs_dir(src).glob("*.json")):
        shutil.copy2(p, hub / "specs" / p.name)
    if (src / "techniques.json").exists():
        shutil.copy2(src / "techniques.json", hub / "techniques.json")
        files.append("techniques.json")
    for d in ("context", "notes"):
        (hub / d).mkdir(exist_ok=True)
        (hub / d / ".gitkeep").touch()

    home = str(Path.home())
    shots = str(src).replace(home, "~", 1)
    backup = {"host": args.allow_remote[0].split(":", 1)[0], "dest": "git/" + hub.name + "-files"} if args.allow_remote else None
    (hub / lib.HUB_FILE).write_text(json.dumps({"screenshots": shots, "allow_remotes": args.allow_remote,
                                                 "port": 8790, "backup": backup}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files.append(lib.HUB_FILE)
    n = len(lib.spec_paths(hub))

    tm = str(SKILLS).replace(home, "$(HOME)", 1)
    for name in ("Makefile", "CLAUDE.md", ".gitignore"):
        text = (TEMPLATES / name).read_text(encoding="utf-8").replace("{{TM}}", tm)
        target = hub / name
        if target.exists():
            raise SystemExit(f"{target} exists; merge the template by hand: {TEMPLATES / name}")
        target.write_text(text, encoding="utf-8")
        files.append(name)

    # Session hook: each Claude session in the hub starts and ends with a background backup
    # (add-only) and studio sync. The settings are merged; anything already there is kept.
    hooks = hub / ".claude" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATES / "sync-hub.sh", hooks / "sync-hub.sh")
    os.chmod(hooks / "sync-hub.sh", 0o755)
    settings_path = hub / ".claude" / "settings.json"
    claude = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    for event, when in (("SessionStart", "start"), ("SessionEnd", "end")):
        claude.setdefault("hooks", {}).setdefault(event, []).append({"hooks": [{
            "type": "command", "command": f'"$CLAUDE_PROJECT_DIR"/.claude/hooks/sync-hub.sh {when}', "timeout": 10}]})
    settings_path.write_text(json.dumps(claude, indent=2) + "\n", encoding="utf-8")
    files += [".claude/hooks/sync-hub.sh", ".claude/settings.json"]

    hook = hub / ".git" / "hooks" / "pre-push"
    shutil.copy2(TEMPLATES / "pre-push", hook)
    os.chmod(hook, 0o755)
    files.append(".git/hooks/pre-push")

    lib.SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    settings = json.loads(lib.SETTINGS.read_text(encoding="utf-8")) if lib.SETTINGS.exists() else {}
    settings["root"] = str(hub).replace(home, "~", 1)
    lib.SETTINGS.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"hub": str(hub), "specs": n, "screenshots": shots, "files": files,
                      "settings": str(lib.SETTINGS)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
