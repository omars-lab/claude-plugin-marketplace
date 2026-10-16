#!/usr/bin/env python3
"""Fetch the pre-context behind one technique, as bounded excerpts for Claude to read, then
record what Claude wrote from it.

Fetch (default): reads the technique's linked session (the hub's archived copy first, then the
original, then the copy another Mac backed up to hub.json "backup", fetched into a temporary
folder) around the screenshot's message, and the git history of the folder it ran in.

    session-before  prompts and Claude's prose leading up to it (to the previous compaction, ≤ 40)
    session-after   what came of it, up to --after-minutes later
    files           files Edit/Write/NotebookEdit touched in that window
    git             commits in the session's folder from 1h before to 2h after
    related         other techniques with the same mechanism

Mark (--mark): after Claude writes context/<slug>.md, records spec.context (file, fetched,
sources) and, optionally, the suggested focus and back story. A suggestion is shown in the post
view once confirmed, so it is privacy-scanned with the spec's replacements applied, and refused
if anything is left.

Usage:
    python3 fetch_context.py --spec <slug> [--sources session-before,session-after,git,files,related]
    python3 fetch_context.py --spec <slug> --mark [--suggested-focus TEXT] [--suggested-backstory TEXT]
Output: JSON on stdout. Every excerpt is cut to --max-chars; nothing prints whole transcripts.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "recreate-technique" / "scripts"))
import lib  # noqa: E402
import scan_privacy  # noqa: E402
from find_session import prompt_text, claude_text  # noqa: E402
from hide_secrets import hide  # noqa: E402
sys.path.insert(0, str(HERE.parents[2] / "sync-studio" / "scripts"))
from sync_studio import remote_path  # noqa: E402

DEFAULT_SOURCES = ("session-before", "session-after", "git", "files", "related")
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


def ts(rec: dict) -> dt.datetime | None:
    t = rec.get("timestamp")
    return dt.datetime.fromisoformat(t.replace("Z", "+00:00")) if isinstance(t, str) else None


def cut(text: str, n: int) -> str:
    """The text with passwords and keys hidden, then cut to n characters."""
    text = " ".join(hide(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def session_file(spec: dict, root: Path) -> Path | None:
    s = (spec.get("source") or {}).get("session") or {}
    for p in ([root / s["archived"]] if s.get("archived") else []) + ([Path(s["path"])] if s.get("path") else []):
        if p.exists():
            return p
    return backed_up_copy(s, root)


def backed_up_copy(s: dict, root: Path) -> Path | None:
    """A session archived on another Mac: copy it from the hub's backup (make backup there) into a
    temporary folder, never into the hub. A copy already in the temp folder is reused."""
    backup = lib.hub_settings(root).get("backup") or {}
    if not (s.get("archived") and s.get("session_id") and backup.get("host") and backup.get("dest")):
        return None
    local = Path(tempfile.gettempdir()) / "technique-sessions" / "backup" / f"{s['session_id']}.jsonl"
    if local.exists():
        return local
    local.parent.mkdir(parents=True, exist_ok=True)
    src = f"{backup['dest'].rstrip('/')}/archive/sessions/{s['session_id']}.jsonl"
    r = subprocess.run(["rsync", "-a", "-e", "ssh -o BatchMode=yes -o ConnectTimeout=8",
                        f"{backup['host']}:{remote_path(src)}", str(local)], capture_output=True, text=True)
    return local if r.returncode == 0 and local.exists() else None


def excerpt(rec: dict, n: int) -> dict | None:
    text = prompt_text(rec)
    if text:
        return {"t": rec.get("timestamp"), "who": "user", "text": cut(text, n)}
    text = claude_text(rec)
    if text:
        return {"t": rec.get("timestamp"), "who": "claude", "text": cut(text, n)}
    return None


def touched(rec: dict) -> list[str]:
    if rec.get("type") != "assistant":
        return []
    out = []
    for part in (rec.get("message") or {}).get("content") or []:
        if isinstance(part, dict) and part.get("type") == "tool_use" and part.get("name") in EDIT_TOOLS:
            p = (part.get("input") or {}).get("file_path") or (part.get("input") or {}).get("notebook_path")
            if p:
                out.append(p)
    return out


def read_session(path: Path, uuid: str | None, at: dt.datetime | None, args) -> dict:
    recs = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    # The screenshot's message: its uuid, else the last record at or before the timestamp.
    idx = next((i for i, r in enumerate(recs) if uuid and r.get("uuid") == uuid), None)
    if idx is None and at:
        idx = max((i for i, r in enumerate(recs) if ts(r) and ts(r) <= at), default=None)
    if idx is None:
        return {"found": False, "note": "the screenshot's message isn't in this session file"}
    anchor = ts(recs[idx]) or at
    before, after, files = [], [], []
    for r in reversed(recs[:idx + 1]):
        if r.get("isCompactSummary") or len(before) >= args.max_turns:
            break
        e = excerpt(r, args.max_chars)
        if e:
            before.append(e)
        files += touched(r)
    until = anchor + dt.timedelta(minutes=args.after_minutes) if anchor else None
    for r in recs[idx + 1:]:
        t = ts(r)
        if until and t and t > until:
            break
        e = excerpt(r, args.max_chars)
        if e:
            after.append(e)
        files += touched(r)
    return {"found": True, "anchor": anchor.isoformat() if anchor else None,
            "before": list(reversed(before)), "after": after[: args.max_turns],
            "files": sorted(set(files))}


def git_window(cwd: str | None, anchor: str | None, max_commits: int) -> dict:
    if not cwd or not Path(cwd).is_dir():
        return {"note": f"folder not on this Mac: {cwd}"}
    top = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode != 0 or not anchor:
        return {"note": f"not a git repo, or no time to search around: {cwd}"}
    at = dt.datetime.fromisoformat(anchor)
    since, until = (at - dt.timedelta(hours=1)).isoformat(), (at + dt.timedelta(hours=2)).isoformat()
    # The user's own commits: CI and bots commit to the same branches in the same hour.
    me = subprocess.run(["git", "-C", cwd, "config", "user.email"], capture_output=True, text=True).stdout.strip()

    def run(author):
        cmd = ["git", "-C", cwd, "log", "--all", "--no-merges", f"--since={since}", f"--until={until}",
               f"-n{max_commits}", "--format=%x1e%h%x1f%cI%x1f%s", "--shortstat"] + ([f"--author={author}"] if author else [])
        return subprocess.run(cmd, capture_output=True, text=True).stdout
    log = run(me) if me else ""
    scope = "yours" if log.strip() else "all authors"
    if not log.strip():
        log = run(None)
    commits = []
    for chunk in log.split("\x1e")[1:]:
        head, _, stat = chunk.partition("\n")
        sha, date, subject = (head.split("\x1f") + ["", ""])[:3]
        commits.append({"sha": sha, "date": date, "subject": subject, "stat": " ".join(stat.split())})
    remote = subprocess.run(["git", "-C", cwd, "remote", "get-url", "origin"], capture_output=True, text=True).stdout.strip()
    return {"repo": top.stdout.strip(), "remote": remote or None, "authors": scope, "commits": commits}


def related(spec: dict, root: Path) -> list[dict]:
    mech = (spec.get("technique") or {}).get("mechanism")
    out = []
    for other in lib.load_specs(root):
        if other.get("slug") == spec.get("slug"):
            continue
        why = []
        if mech and (other.get("technique") or {}).get("mechanism") == mech:
            why.append(f"same mechanism ({mech})")
        if why:
            out.append({"slug": other["slug"], "title": (other.get("technique") or {}).get("title"), "why": why})
    return out


def mark(spec_path: Path, spec: dict, root: Path, args) -> dict:
    ctx = dict(spec.get("context") or {})
    ctx_file = Path("context") / f"{spec['slug']}.md"
    if not (root / ctx_file).exists():
        raise SystemExit(f"write {ctx_file} first; --mark records it")
    ctx.update(file=str(ctx_file), fetched=dt.date.today().isoformat(),
               sources=args.sources.split(",") if args.sources else ctx.get("sources", list(DEFAULT_SOURCES)))
    for key, text in (("suggested_focus", args.suggested_focus), ("suggested_backstory", args.suggested_backstory)):
        if text is None:
            continue
        # What would show in the post once confirmed: the text with this spec's replacements applied.
        rules = lib.redactions_for(spec, root)
        shown = lib.apply_redactions({"x": text}, rules)["x"]
        left = scan_privacy.scan({"x": shown}, tuple(r["replace"] for r in rules))
        if left:
            raise SystemExit(f"{key} would show {left[0]['match']!r} in the post; add a replacement or reword it")
        ctx[key] = text
    spec["context"] = ctx
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"slug": spec["slug"], "context": ctx}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("--spec", required=True, help="slug")
    ap.add_argument("--sources", help="comma list; default: " + ",".join(DEFAULT_SOURCES))
    ap.add_argument("--max-turns", type=int, default=40)
    ap.add_argument("--max-chars", type=int, default=600)
    ap.add_argument("--after-minutes", type=int, default=60)
    ap.add_argument("--max-commits", type=int, default=15)
    ap.add_argument("--mark", action="store_true")
    ap.add_argument("--suggested-focus")
    ap.add_argument("--suggested-backstory")
    args = ap.parse_args()

    root = lib.find_root(args.root)
    spec_path = lib.specs_dir(root) / f"{args.spec}.json"
    if not spec_path.exists():
        raise SystemExit(f"no spec {spec_path}")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if args.mark:
        print(json.dumps(mark(spec_path, spec, root, args), ensure_ascii=False, indent=2))
        return 0

    sources = args.sources.split(",") if args.sources else list(DEFAULT_SOURCES)
    session = (spec.get("source") or {}).get("session") or {}
    out = {"slug": spec["slug"], "sources": sources, "notes": []}
    path = session_file(spec, root)
    sess = {}
    if not session:
        out["notes"].append("no linked session; run find_session.py first")
    elif not path:
        out["notes"].append("the session file is gone, and no archived copy was found here or in the backup")
    else:
        at = dt.datetime.fromisoformat(session["timestamp"].replace("Z", "+00:00")) if session.get("timestamp") else None
        sess = read_session(path, session.get("uuid"), at, args)
        if not sess.get("found"):
            out["notes"].append(sess.get("note"))
        out["session"] = {"file": str(path), "title": session.get("title"), "cwd": session.get("cwd"),
                          "anchor": sess.get("anchor")}
        if "session-before" in sources:
            out["before"] = sess.get("before", [])
        if "session-after" in sources:
            out["after"] = sess.get("after", [])
        if "files" in sources:
            out["files"] = sess.get("files", [])
    if "git" in sources:
        out["git"] = git_window(session.get("cwd"), sess.get("anchor") or session.get("timestamp", "").replace("Z", "+00:00") or None,
                                args.max_commits)
    if "related" in sources:
        out["related"] = related(spec, root)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
