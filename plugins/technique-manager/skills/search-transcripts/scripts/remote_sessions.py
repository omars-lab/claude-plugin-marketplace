#!/usr/bin/env python3
"""Find Claude Code transcripts on another Mac by the words in them, copy the matches to a
temporary folder here, and cut bounded snippets around each match, so a technique's back
story can be researched when its sessions were not recorded on this Mac.

Searches, over SSH (BatchMode: no password prompt):
    .claude/projects            every session Claude Code still keeps on that Mac
    <backup dest>/archive/sessions  the hub's backed-up copies (hub.json "backup"), when run in a hub
Paths are relative to the home folder there; --dir replaces the list.

Usage:
    python3 remote_sessions.py search  --grep "words" [--grep "more words"] [--any] [--since 2026-09-01]
    python3 remote_sessions.py fetch   --grep "words" ... [--out DIR] [--max-mb 200]
    python3 remote_sessions.py snippets --grep "words" ... FILE_OR_DIR ... [--chars 300] [--max 40]

    --host H     the Mac to search (default: hub.json "transcripts.host", then "backup.host",
                 then studio.json "host")
    --grep T     fixed text, case-insensitive; repeat it. A file must hold every one (--any: one)

Output (JSON on stdout):
    search   {"host", "dirs", "files": [{"path", "bytes", "modified"}]}  newest first
    fetch    {"host", "out", "files": [{"path", "local", "bytes", "modified"}], "skipped": [...]}
    snippets {"files": N, "snippets": [{"file", "session", "line", "timestamp", "role", "cwd", "text"}]}
The copies are whole transcripts and can hold anything: keep them in the temporary folder,
never in the hub repo or a post.
"""
import argparse
import datetime as dt
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "recreate-technique" / "scripts"))
import lib  # noqa: E402
from find_session import prompt_text, claude_text  # noqa: E402

STUDIO = Path.home() / ".config" / "technique-manager" / "studio.json"
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]


def hub_root(raw: str | None) -> Path | None:
    """The hub this runs in (--root, or the current folder), if any."""
    root = Path(raw).expanduser() if raw else Path.cwd()
    return root if lib.is_hub(root) else None


def pick_host(args, hub: dict) -> str:
    studio = json.loads(STUDIO.read_text(encoding="utf-8")) if STUDIO.exists() else {}
    host = args.host or (hub.get("transcripts") or {}).get("host") or (hub.get("backup") or {}).get("host") \
        or studio.get("host")
    if not host:
        raise SystemExit("No host: pass --host, or set hub.json \"transcripts\": {\"host\": ...}")
    return host


def pick_dirs(args, hub: dict) -> list[str]:
    if args.dir:
        return args.dir
    dirs = (hub.get("transcripts") or {}).get("dirs") or [".claude/projects"]
    dest = (hub.get("backup") or {}).get("dest")
    if dest and not (hub.get("transcripts") or {}).get("dirs"):
        dirs = dirs + [dest.rstrip("/") + "/archive/sessions"]
    return dirs


def search(host: str, dirs: list[str], needles: list[str], any_of: bool, since: str | None) -> list[dict]:
    """One SSH call: find the .jsonl files, keep those holding the words, stat what's left."""
    q = [shlex.quote(d) for d in dirs]
    find = f"find {' '.join(q)} -name '*.jsonl' -type f" + (f" -newermt {shlex.quote(since)}" if since else "")
    if any_of:
        greps = ["xargs -0 grep -lFi --null " + " ".join(f"-e {shlex.quote(n)}" for n in needles)]
    else:
        greps = [f"xargs -0 grep -lFi --null -e {shlex.quote(n)}" for n in needles]
    # Missing dirs are fine (cd into home first; find's complaint goes to /dev/null).
    script = f"cd && {find} -print0 2>/dev/null | " + " | ".join(greps) + " | xargs -0 stat -f '%z %m %N'"
    r = subprocess.run(SSH + [host, script], capture_output=True, text=True)
    if r.returncode not in (0, 1, 123):  # grep/xargs exit 1/123 when nothing matched
        raise SystemExit(f"Search on {host} failed: {(r.stderr or r.stdout).strip()[-300:]}")
    files = []
    for line in r.stdout.splitlines():
        size, mtime, path = line.split(" ", 2)
        files.append({"path": path, "bytes": int(size),
                      "modified": dt.datetime.fromtimestamp(int(mtime)).isoformat(timespec="minutes")})
    return sorted(files, key=lambda f: f["modified"], reverse=True)


def fetch(host: str, files: list[dict], out: Path, max_mb: float) -> tuple[list[dict], list[dict]]:
    """Copy the newest files first until --max-mb, keeping their folders (relative to home)."""
    take, skipped, total = [], [], 0
    for f in files:
        if total + f["bytes"] > max_mb * 1024 * 1024:
            skipped.append({"path": f["path"], "bytes": f["bytes"], "reason": f"over --max-mb {max_mb:g}"})
            continue
        total += f["bytes"]
        take.append(f)
    if not take:
        return [], skipped
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as listing:
        listing.write("\n".join(f["path"] for f in take) + "\n")
    # Source "host:" is the home folder there, so the paths in the list are relative to it.
    r = subprocess.run(["rsync", "-a", f"--files-from={listing.name}", f"{host}:", f"{out}/"],
                       capture_output=True, text=True)
    Path(listing.name).unlink()
    if r.returncode != 0:
        raise SystemExit(f"rsync from {host} failed: {r.stderr.strip()}")
    return [{**f, "local": str(out / f["path"])} for f in take], skipped


def record_text(rec: dict) -> tuple[str | None, str | None]:
    """(role, text) for one transcript line: a typed prompt, Claude's prose, or a tool call/result."""
    if (t := prompt_text(rec)):
        return "user", t
    if (t := claude_text(rec)):
        return "claude", t
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, list):
        parts = []
        for c in content:
            if c.get("type") == "tool_use":
                parts.append(f"[{c.get('name')}] {json.dumps(c.get('input'), ensure_ascii=False)}")
            elif c.get("type") == "tool_result":
                body = c.get("content")
                parts.append(body if isinstance(body, str) else json.dumps(body, ensure_ascii=False))
        if parts:
            return "tool", "\n".join(parts)
    return None, None


def snippets(paths: list[Path], needles: list[str], chars: int, limit: int) -> tuple[int, list[dict]]:
    """A window of `chars` either side of each match, one per transcript line, newest file first."""
    files = sorted({p for path in paths for p in ([path] if path.is_file() else path.rglob("*.jsonl"))},
                   key=lambda p: p.stat().st_mtime, reverse=True)
    low = [n.lower() for n in needles]
    out = []
    for f in files:
        with f.open(encoding="utf-8", errors="replace") as fh:
            for n, line in enumerate(fh, 1):
                if not any(x in line.lower() for x in low):
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                role, text = record_text(rec)
                if not text:
                    continue
                at = min((i for i in (text.lower().find(x) for x in low) if i >= 0), default=-1)
                if at < 0:
                    continue  # the words were in metadata, not in what was said
                a, b = max(0, at - chars), at + chars
                piece = " ".join(text[a:b].split())
                out.append({"file": str(f), "session": rec.get("sessionId"), "line": n,
                            "timestamp": rec.get("timestamp"), "role": role, "cwd": rec.get("cwd"),
                            "text": ("…" if a else "") + piece + ("…" if b < len(text) else "")})
                if len(out) >= limit:
                    return len(files), out
    return len(files), out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=("search", "fetch", "snippets"))
    ap.add_argument("paths", nargs="*", help="snippets: transcript files or folders")
    ap.add_argument("--grep", action="append", required=True)
    ap.add_argument("--any", action="store_true", help="a file needs only one of the --grep texts")
    ap.add_argument("--host")
    ap.add_argument("--dir", action="append", help="folder to search there, relative to its home; repeatable")
    ap.add_argument("--since", help="only files changed on or after this date (YYYY-MM-DD)")
    ap.add_argument("--root", help="the hub (default: the current folder, if it is one)")
    ap.add_argument("--out", help="fetch: where to copy (default: a folder under the system temp dir)")
    ap.add_argument("--max-mb", type=float, default=200, help="fetch: stop copying past this many MB")
    ap.add_argument("--chars", type=int, default=300, help="snippets: characters either side of a match")
    ap.add_argument("--max", type=int, default=40, help="snippets: at most this many")
    args = ap.parse_args()

    if args.action == "snippets":
        if not args.paths:
            raise SystemExit("snippets needs the fetched files or their folder")
        n, found = snippets([Path(p).expanduser() for p in args.paths], args.grep, args.chars, args.max)
        print(json.dumps({"files": n, "snippets": found}, ensure_ascii=False, indent=2))
        return 0

    root = hub_root(args.root)
    hub = lib.hub_settings(root) if root else {}
    host, dirs = pick_host(args, hub), pick_dirs(args, hub)
    files = search(host, dirs, args.grep, args.any, args.since)
    if args.action == "search":
        print(json.dumps({"host": host, "dirs": dirs, "files": files}, ensure_ascii=False, indent=2))
        return 0
    out = Path(args.out).expanduser() if args.out else \
        Path(tempfile.gettempdir()) / "technique-sessions" / lib.slugify(" ".join(args.grep), 40)
    copied, skipped = fetch(host, files, out, args.max_mb)
    print(json.dumps({"host": host, "out": str(out), "files": copied, "skipped": skipped},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
