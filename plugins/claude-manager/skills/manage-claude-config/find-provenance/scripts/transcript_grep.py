#!/usr/bin/env python3
"""Find the transcript line that proves a claim, and cite it by coordinates.

Claude Code appends every session to `~/.claude/projects/<slug>/<session>.jsonl`,
one JSON object per line. Subagent transcripts of a session live under
`<slug>/<session>/subagents/*.jsonl`. This script greps those files for a
substring and prints, per hit, the coordinates a citation needs
(file, 1-based line, timestamp) plus the entry's role and a short excerpt.

The label on each hit matters more than the hit itself. A substring inside a
`tool_use` input was written by that turn; the same substring inside a
`tool_result` only proves it already existed on disk; a `human` hit is the
person's own words. Reading a read-back as authorship is how audits end up
pointing at whoever last opened the file.

Usage:
  transcript_grep.py --session <uuid> --find "<substring>" [--human-only]
  transcript_grep.py --repo <path>     --find "<substring>" [--human-only]
  transcript_grep.py --selftest

Options:
  --session UUID     one session; also searches its subagent transcripts
  --repo PATH        every transcript for a working directory (default: cwd)
  --find TEXT        exact substring; its HTML-escaped twin is also tried
  --human-only       only the person's own turns (no tool results, no
                     system notifications)
  --limit N          stop after N hits per file (default 20)
  --context N        excerpt characters on each side of the match (default 120)
  --projects-dir D   override ~/.claude/projects (used by --selftest)

Output, one hit per line, tab separated:
  <file>:<line>  <timestamp>  <role>  <excerpt>

Nothing here writes anything. Commit coordinates (session id, line,
timestamp), never the excerpt: transcripts hold whatever the session held.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import tempfile
from pathlib import Path

DEFAULT_PROJECTS = Path.home() / ".claude" / "projects"
NON_ALNUM = re.compile(r"[^A-Za-z0-9]")


# ---------------------------------------------------------------- locating


def slug_for(repo: str) -> str:
    """Absolute path with every non-alphanumeric character replaced by '-'."""
    return NON_ALNUM.sub("-", str(Path(repo).resolve()))


def files_for_repo(projects: Path, repo: str) -> list[Path]:
    d = projects / slug_for(repo)
    if not d.is_dir():
        sys.exit(f"no transcripts for {repo}\n  looked in: {d}")
    return sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)


def files_for_session(projects: Path, session: str) -> list[Path]:
    hits: list[Path] = []
    for main in sorted(projects.glob(f"*/{session}.jsonl")):
        hits.append(main)
        sub = main.parent / session / "subagents"
        if sub.is_dir():
            hits.extend(sorted(sub.glob("*.jsonl")))
    if not hits:
        sys.exit(f"session {session} has no transcript under {projects}")
    return hits


# ----------------------------------------------------------------- reading


def variants(pattern: str) -> list[str]:
    """The pattern and its HTML-escaped twin (plan text quoted back into a
    user turn arrives with `<` as `&lt;`)."""
    esc = html.escape(pattern)
    return [pattern] if esc == pattern else [pattern, esc]


def blocks(entry: dict):
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict):
                yield b


def is_human(entry: dict) -> bool:
    """The person's own turn: a user entry whose content is plain text or text
    blocks, with no tool_result block and no system envelope."""
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return False
        text = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    else:
        return False
    stripped = text.lstrip()
    return not stripped.startswith(("<task-notification>", "<system-reminder>", "<local-command"))


def classify(entry: dict, pats: list[str]) -> tuple[str, str]:
    """(role label, text that holds the match)."""
    kind = entry.get("type", "?")
    if is_human(entry):
        content = (entry.get("message") or {}).get("content")
        text = content if isinstance(content, str) else " ".join(
            b.get("text", "") for b in blocks(entry) if b.get("type") == "text"
        )
        return "human", text
    labels = []
    text = ""
    for b in blocks(entry):
        t = b.get("type")
        if t == "tool_use":
            body = json.dumps(b.get("input", {}))
            if any(p in body for p in pats):
                labels.append(f"tool_use:{b.get('name', '?')}")
                text = text or body
        elif t in ("text", "thinking"):
            body = b.get(t, "")
            if any(p in body for p in pats):
                labels.append(t)
                text = text or body
        elif t == "tool_result":
            body = b.get("content")
            body = body if isinstance(body, str) else json.dumps(body)
            if any(p in body for p in pats):
                labels.append("tool_result")
                text = text or body
    return f"{kind}:{','.join(labels)}" if labels else f"{kind}:raw", text


def excerpt(text: str, pats: list[str], width: int) -> str:
    for p in pats:
        i = text.find(p)
        if i >= 0:
            lo, hi = max(0, i - width), i + len(p) + width
            return ("..." if lo else "") + text[lo:hi].replace("\n", " ") + ("..." if hi < len(text) else "")
    return text[: 2 * width].replace("\n", " ")


def grep_file(path: Path, pats: list[str], human_only: bool, limit: int, width: int) -> list[str]:
    out: list[str] = []
    with path.open(errors="replace") as fh:
        for n, raw in enumerate(fh, 1):
            if not any(p in raw for p in pats):
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                entry = {"type": "unparsed"}
            if human_only and not is_human(entry):
                continue
            role, text = classify(entry, pats)
            text = text or raw
            ts = entry.get("timestamp") or "-"
            out.append(f"{path}:{n}\t{ts}\t{role}\t{excerpt(text, pats, width)}")
            if len(out) >= limit:
                break
    return out


# ---------------------------------------------------------------- selftest


def selftest() -> int:
    failures = 0

    def check(name: str, ok: bool) -> None:
        nonlocal failures
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
        failures += 0 if ok else 1

    with tempfile.TemporaryDirectory() as tmp:
        projects = Path(tmp) / "projects"
        repo = Path(tmp) / "repo"
        repo.mkdir()
        slug = slug_for(str(repo))
        sid = "11111111-2222-3333-4444-555555555555"
        d = projects / slug
        d.mkdir(parents=True)
        main = d / f"{sid}.jsonl"
        rows = [
            {"type": "user", "timestamp": "2026-01-01T00:00:01Z",
             "message": {"role": "user", "content": "please make whorl &lt; 12 the needle rule"}},
            {"type": "assistant", "timestamp": "2026-01-01T00:00:02Z",
             "message": {"role": "assistant", "content": [
                 {"type": "tool_use", "name": "Write", "input": {"file_path": "x", "content": "needle rule here"}}]}},
            {"type": "user", "timestamp": "2026-01-01T00:00:03Z",
             "message": {"role": "user", "content": [
                 {"type": "tool_result", "content": "file has needle rule"}]}},
            {"type": "user", "timestamp": "2026-01-01T00:00:04Z",
             "message": {"role": "user", "content": "<task-notification>needle done</task-notification>"}},
        ]
        main.write_text("".join(json.dumps(r) + "\n" for r in rows))
        sub = d / sid / "subagents"
        sub.mkdir(parents=True)
        (sub / "agent-abc.jsonl").write_text(json.dumps(
            {"type": "assistant", "timestamp": "2026-01-01T00:00:05Z",
             "message": {"role": "assistant", "content": [{"type": "text", "text": "subagent saw the needle"}]}}) + "\n")

        pats = variants("needle")
        files = files_for_session(projects, sid)
        check("session resolves main transcript plus subagent", len(files) == 2 and files[0] == main)
        all_hits = [h for f in files for h in grep_file(f, pats, False, 20, 40)]
        check("all hits counted across both files", len(all_hits) == 5)
        human = [h for f in files for h in grep_file(f, pats, True, 20, 40)]
        check("human-only keeps the person's turn only", len(human) == 1 and "\thuman\t" in human[0])
        check("human hit cites line 1 with its timestamp", human[0].split("\t")[0].endswith(":1") and "2026-01-01T00:00:01Z" in human[0])
        check("task notification is not a human turn", not any(":4\t" in h and "\thuman\t" in h for h in all_hits))
        check("tool_use hit is labelled as authorship", any("assistant:tool_use:Write" in h for h in all_hits))
        check("tool_result hit is labelled as a read-back", any("user:tool_result" in h for h in all_hits))
        esc = grep_file(main, variants("whorl < 12"), True, 20, 40)
        check("HTML-escaped twin of the pattern matches", len(esc) == 1)
        by_repo = files_for_repo(projects, str(repo))
        check("repo path resolves through its slug", by_repo == [main])
        limited = grep_file(main, pats, False, 2, 40)
        check("--limit caps hits per file", len(limited) == 2)

    print(f"selftest: {failures} failure(s)")
    return 1 if failures else 0


# -------------------------------------------------------------------- main


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--session", help="session uuid (also searches its subagents)")
    p.add_argument("--repo", help="working directory whose transcripts to search (default: cwd)")
    p.add_argument("--find", help="exact substring to locate")
    p.add_argument("--human-only", action="store_true")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--context", type=int, default=120)
    p.add_argument("--projects-dir", default=str(DEFAULT_PROJECTS))
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args()

    if args.selftest:
        return selftest()
    if not args.find:
        p.error("--find is required (or --selftest)")

    projects = Path(args.projects_dir).expanduser()
    files = files_for_session(projects, args.session) if args.session else files_for_repo(projects, args.repo or os.getcwd())
    pats = variants(args.find)
    total = 0
    for f in files:
        for hit in grep_file(f, pats, args.human_only, args.limit, args.context):
            print(hit)
            total += 1
    if total == 0:
        print("no hits: try a shorter substring without quotes or angle brackets", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
