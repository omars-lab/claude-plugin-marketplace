#!/usr/bin/env python3
"""Copy every session a technique links to into the hub's archive, before Claude Code deletes the
original (cleanupPeriodDays, 30 by default). Records the copy in the spec as
source.session.archived (a path relative to the root). Re-runs copy only what is new.

A session whose spec already says it was archived, but which has neither a copy here nor its
original, was archived on another Mac (and `make backup` there sends it upstream): it counts
as "elsewhere", not "missing".

Usage:
    python3 archive_sessions.py [--root R]

Output (JSON): {"archived": [slug...], "already": N, "elsewhere": [slug...], "missing": [{"slug", "path"}], "dir"}
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "recreate-technique" / "scripts"))
import lib  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    args = ap.parse_args()
    root = lib.find_root(args.root)
    archive = lib.archive_dir(root)
    archive.mkdir(parents=True, exist_ok=True)
    out = {"archived": [], "already": 0, "elsewhere": [], "missing": [], "dir": str(archive)}
    for path in lib.spec_paths(root):
        spec = json.loads(path.read_text(encoding="utf-8"))
        session = (spec.get("source") or {}).get("session")
        if not session:
            continue
        dest = archive / f"{session['session_id']}.jsonl"
        rel = str(dest.relative_to(root))
        if dest.exists():
            out["already"] += 1
        elif Path(session["path"]).exists():
            shutil.copy2(session["path"], dest)
            out["archived"].append(spec["slug"])
        elif session.get("archived"):
            out["elsewhere"].append(spec["slug"])
            continue
        else:
            out["missing"].append({"slug": spec["slug"], "path": session["path"]})
            continue
        if session.get("archived") != rel:
            session["archived"] = rel
            path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
