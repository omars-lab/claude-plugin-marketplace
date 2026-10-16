#!/usr/bin/env python3
"""Find the Claude Code session a technique screenshot was taken from.

Claude Code saves every session as ~/.claude/projects/<project>/<session-id>.jsonl. This
script matches a spec's typed prompts (user_prompt and prompt_input blocks) against the
prompts in those files, near the time the screenshot was taken, and records the best match
in the spec as source.session. The internal view links to it, so a post can be expanded
with the back story later. The post view never shows it: the path holds a username and
project names.

Matching is by word overlap, not exact text, because specs fix the user's typos.
Session times are UTC; source.taken is local time (this machine's zone, or --utc-offset).

Usage:
    python3 find_session.py --spec <spec.json>              # report the best matches
    python3 find_session.py --spec <spec.json> --write      # also save source.session
    python3 find_session.py --all --write                   # every spec under pages/specs/
    python3 find_session.py --text "words from the prompt" --taken "2026-01-01 09:00"

Output (JSON on stdout), per spec:
    {"spec", "best": {"path", "session_id", "uuid", "timestamp", "cwd", "title", "score",
                      "minutes_off", "prompt"}, "others": [...]}
A match scores 0–1 (share of the spec's prompt words found in one session prompt).
--write only saves a match scoring at least --min-score (default 0.5) and taken within
--max-minutes (default 30) of the screenshot. Sessions older than cleanupPeriodDays in
~/.claude/settings.json (30 days by default) are deleted by Claude Code, so find them early.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

PROJECTS = Path.home() / ".claude" / "projects"
GENERATED = ("This session is being continued", "Base directory for this skill", "Caveat:")
WORD = re.compile(r"[a-z0-9][a-z0-9_\-./]{3,}")


def words(text: str) -> set[str]:
    return set(WORD.findall(text.lower()))


def local_to_utc(taken: str, offset: str | None) -> dt.datetime:
    t = dt.datetime.fromisoformat(taken.replace(" ", "T"))
    if offset:
        sign = 1 if offset[0] != "-" else -1
        h, m = int(offset.lstrip("+-")[:2]), int(offset.lstrip("+-")[2:] or 0)
        t = t.replace(tzinfo=dt.timezone(sign * dt.timedelta(hours=h, minutes=m)))
    else:
        t = t.astimezone()  # this machine's zone
    return t.astimezone(dt.timezone.utc)


def prompt_text(rec: dict) -> str | None:
    """Text the user typed or queued, or None for tool results and system records."""
    if rec.get("type") == "queue-operation" and rec.get("operation") == "enqueue":
        c = rec.get("content")
    elif rec.get("type") == "user" and not rec.get("isMeta"):
        c = (rec.get("message") or {}).get("content")
        if isinstance(c, list):
            c = " ".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text")
    else:
        return None
    if not isinstance(c, str) or not c.strip() or c.lstrip().startswith("<"):
        return None  # empty, or a harness wrapper such as <task-notification>
    if rec.get("isCompactSummary") or c.startswith(GENERATED):
        return None  # written by Claude Code, not typed; long enough to match anything
    return c


def claude_text(rec: dict) -> str | None:
    """Prose Claude wrote in an assistant record (not tool calls)."""
    if rec.get("type") != "assistant":
        return None
    c = (rec.get("message") or {}).get("content")
    if isinstance(c, list):
        c = " ".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text")
    return c if isinstance(c, str) and c.strip() else None


def scan(needles: list[set[str]], at: dt.datetime, hours: float, claude: list[set[str]] | None = None) -> list[dict]:
    """needles match typed prompts; claude (optional) matches Claude's own prose, for
    screenshots that show no typed prompt."""
    lo, hi = at - dt.timedelta(hours=hours), at + dt.timedelta(hours=hours)
    best: dict[str, dict] = {}
    for f in PROJECTS.glob("*/*.jsonl"):
        # A session that ended before the window can't hold the screenshot.
        if dt.datetime.fromtimestamp(f.stat().st_mtime, dt.timezone.utc) < lo:
            continue
        title = cwd = None
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"ai-title"' in line and title is None:
                    try:
                        title = json.loads(line).get("aiTitle")
                    except ValueError:
                        pass
                    continue
                if '"user"' not in line and '"queue-operation"' not in line and not (claude and '"assistant"' in line):
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                ts = rec.get("timestamp")
                if not ts:
                    continue
                when = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if not lo <= when <= hi:
                    continue
                cwd = rec.get("cwd") or cwd
                text, pool = prompt_text(rec), needles
                if not text and claude:
                    text, pool = claude_text(rec), claude
                if not text:
                    continue
                have = words(text)
                score = max((len(n & have) / len(n) for n in pool if n), default=0)
                if score == 0:
                    continue
                minutes = abs((when - at).total_seconds()) / 60
                key = str(f)
                if key not in best or (score, -minutes) > (best[key]["score"], -best[key]["minutes_off"]):
                    best[key] = {"path": str(f), "session_id": f.stem, "uuid": rec.get("uuid"),
                                 "timestamp": ts, "cwd": cwd, "title": title, "score": round(score, 2),
                                 "minutes_off": round(minutes, 1), "prompt": text[:160]}
        for m in best.values():
            if m["path"] == str(f) and title:
                m["title"] = title
    return sorted(best.values(), key=lambda m: (-m["score"], m["minutes_off"]))


def needles_from_spec(spec: dict, types=("user_prompt", "prompt_input")) -> list[set[str]]:
    texts = [b.get("text", "") for b in spec.get("blocks", []) if b.get("type") in types]
    return [w for w in (words(t) for t in texts) if len(w) >= 3]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--spec", action="append")
    g.add_argument("--all", action="store_true")
    g.add_argument("--text")
    ap.add_argument("--taken", help="with --text: local time the screenshot was taken")
    ap.add_argument("--utc-offset", help="zone of source.taken, e.g. -0500 (default: this machine's)")
    ap.add_argument("--hours", type=float, default=6, help="search this many hours either side")
    ap.add_argument("--min-score", type=float, default=0.5)
    ap.add_argument("--max-minutes", type=float, default=30,
                    help="--write only saves a match this close to source.taken")
    ap.add_argument("--write", action="store_true", help="save the best match as source.session")
    args = ap.parse_args()

    if not PROJECTS.exists():
        raise SystemExit(f"No Claude Code sessions folder at {PROJECTS}")

    if args.text:
        if not args.taken:
            raise SystemExit("--text needs --taken")
        hits = scan([words(args.text)], local_to_utc(args.taken, args.utc_offset), args.hours)
        print(json.dumps({"best": hits[0] if hits else None, "others": hits[1:4]}, ensure_ascii=False, indent=2))
        return 0

    root = lib.find_root(args.root)
    paths = sorted(lib.specs_dir(root).glob("*.json")) if args.all else [Path(s).expanduser() for s in args.spec]
    results = []
    for p in paths:
        spec = json.loads(p.read_text(encoding="utf-8"))
        taken = (spec.get("source") or {}).get("taken")
        needles = needles_from_spec(spec)
        claude = needles_from_spec(spec, ("recap", "assistant_text"))
        if not taken or not (needles or claude):
            results.append({"spec": p.name, "best": None, "reason": "no source.taken, and no prompt or Claude text to match"})
            continue
        at = local_to_utc(taken, args.utc_offset)
        hits = scan(needles, at, args.hours)
        if not hits or hits[0]["score"] < args.min_score:
            hits = sorted(hits + scan(needles, at, args.hours, claude), key=lambda m: (-m["score"], m["minutes_off"]))
        if not hits or hits[0]["score"] < args.min_score:
            oldest = min((f.stat().st_mtime for f in PROJECTS.glob("*/*.jsonl")), default=None)
            if oldest and dt.datetime.fromtimestamp(oldest, dt.timezone.utc) > at:
                results.append({"spec": p.name, "best": None, "reason": "older than every saved session; "
                                "Claude Code deletes sessions after cleanupPeriodDays (30 by default)"})
                continue
        best = hits[0] if hits else None
        saved = False
        if args.write and best and best["score"] >= args.min_score and best["minutes_off"] <= args.max_minutes:
            spec.setdefault("source", {})["session"] = {k: best[k] for k in ("path", "session_id", "uuid", "timestamp", "cwd", "title")}
            p.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            saved = True
        results.append({"spec": p.name, "best": best, "saved": saved, "others": hits[1:3]})
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
