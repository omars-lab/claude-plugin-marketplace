#!/usr/bin/env python3
"""Topic folders: fixed subdirs of the screenshots root for one kind of screenshot,
whatever plan it belongs to (e.g. every chat with one particular tool).

The list lives with the user's screenshots, not in this repo:
    <screenshots root>/.topic-folders.json
    {"version": 1, "topics": [{"folder": "🏢 Example Tool Chats",
                               "describe": "Chats in Example Tool's web assistant panel",
                               "signals": ["'Example Tool' label in the reply box", "..."]}]}

Usage:
    python3 topic_folders.py --root R --list
    python3 topic_folders.py --root R --add --folder "🏢 Example Tool Chats" \\
        --describe "Chats in Example Tool's assistant" --signal "label in the reply box"
    python3 topic_folders.py --root R --move --folder "🏢 Example Tool Chats" --entries moves.json

moves.json: [{"src": "<desktop path>", "slug": "story-link-check", "excerpt": "optional"}, ...]
Each file is renamed to "YYYYMMDD-HHMMSS <slug>.png" (time from the macOS name, else mtime),
moved (never copied), and added to the folder's INDEX.md with update_index.py.

Output (JSON on stdout). Exit 1 if any move failed.
"""
import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

NAME = re.compile(r"(\d{4})-(\d{2})-(\d{2}) at (\d{1,2})\.(\d{2})\.(\d{2})\s?(AM|PM)")
CONFIG = ".topic-folders.json"


def resolve(src: str) -> Path | None:
    p = Path(src).expanduser()
    if p.exists():
        return p
    want = unicodedata.normalize("NFC", p.name).replace(" ", " ")
    if p.parent.exists():
        for c in p.parent.iterdir():
            if unicodedata.normalize("NFC", c.name).replace(" ", " ") == want:
                return c
    return None


def stamp(p: Path) -> str:
    m = NAME.search(unicodedata.normalize("NFC", p.name).replace(" ", " "))
    if m:
        y, mo, d, h, mi, s, ampm = m.groups()
        h = int(h) % 12 + (12 if ampm == "PM" else 0)
        return f"{y}{mo}{d}-{h:02d}{mi}{s}"
    return dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y%m%d-%H%M%S")


def load(root: Path) -> dict:
    f = root / CONFIG
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"version": 1, "topics": []}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="screenshots root, e.g. ~/Desktop/Screenshots")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list", action="store_true")
    mode.add_argument("--add", action="store_true")
    mode.add_argument("--move", action="store_true")
    ap.add_argument("--folder")
    ap.add_argument("--describe", default="")
    ap.add_argument("--signal", action="append", default=[])
    ap.add_argument("--entries")
    args = ap.parse_args()

    root = Path(args.root).expanduser()
    if not root.exists():
        raise SystemExit(f"Screenshots root not found: {root}")
    cfg = load(root)

    if args.list:
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        return 0

    if not args.folder:
        raise SystemExit("--folder is required")

    if args.add:
        topic = next((t for t in cfg["topics"] if t["folder"] == args.folder), None)
        if topic is None:
            topic = {"folder": args.folder, "describe": "", "signals": []}
            cfg["topics"].append(topic)
        if args.describe:
            topic["describe"] = args.describe
        topic["signals"] = list(dict.fromkeys(topic["signals"] + args.signal))
        (root / CONFIG).write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (root / args.folder).mkdir(exist_ok=True)
        print(json.dumps({"config": str(root / CONFIG), "topic": topic}, ensure_ascii=False, indent=2))
        return 0

    if not any(t["folder"] == args.folder for t in cfg["topics"]):
        raise SystemExit(f"{args.folder!r} is not a topic folder; add it with --add first")
    dest = root / args.folder
    dest.mkdir(exist_ok=True)
    index_script = Path(__file__).with_name("update_index.py")
    entries = json.loads(Path(args.entries).read_text(encoding="utf-8") if args.entries else sys.stdin.read())
    moved, failed = [], []
    for e in entries:
        src = resolve(e["src"])
        if src is None:
            failed.append({"src": e["src"], "error": "not found"})
            continue
        new = f"{stamp(src)} {e['slug']}{src.suffix.lower()}"
        if (dest / new).exists():
            failed.append({"src": e["src"], "error": f"{new} already exists"})
            continue
        day = dt.datetime.fromtimestamp(src.stat().st_mtime).date().isoformat()
        shutil.move(str(src), dest / new)
        entry = {"new_filename": new, "original": src.name, "mtime": day, "ocr_excerpt": e.get("excerpt", "")}
        r = subprocess.run([sys.executable, str(index_script), "--subdir", str(dest), "--entry",
                            json.dumps(entry, ensure_ascii=False)], capture_output=True, text=True)
        moved.append({"from": src.name, "to": new, "index": "ok" if r.returncode == 0 else r.stderr.strip()})
    print(json.dumps({"folder": str(dest), "moved": moved, "failed": failed}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
