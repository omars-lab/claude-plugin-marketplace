#!/usr/bin/env python3
"""UserPromptSubmit + SessionStart hook: warn when other Claude Code sessions
are active in the same working tree.

Sessions that share a checkout share uncommitted files, the index and the
current branch. Without a reminder the failure modes are: committing on the
branch another session switched to, staging another session's in-flight files,
and `git restore`/`checkout` wiping someone else's work.

Opt in with `.claude/hooks/concurrent-session.conf` in the repo, or once for the
whole machine with `~/.claude/hooks/concurrent-session.conf`:

    ENABLED=1
    ACTIVE_WINDOW_MIN=10        # a transcript touched within this many minutes counts
    REMIND_EVERY_MIN=30         # repeat at most this often unless the count grows
    COMMIT_REMINDER=1           # also arm remind-commit-branch (PreToolUse Bash)
    INCLUDE_SUBDIR_SESSIONS=1   # sessions started in a subdirectory count too

Output goes to stdout, which Claude Code adds to the conversation as context.
SessionStart always reports when other sessions exist; UserPromptSubmit is
rate-limited through a marker file in $TMPDIR keyed by session id.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _conf  # noqa: E402
import _sessions  # noqa: E402

CONF_NAME = "concurrent-session.conf"

RULE = (
    "They share this checkout's uncommitted files, index and branch. "
    "Run `git branch --show-current` before every commit, never stage files you did not change, "
    "never `git restore .`/`checkout -- .`, and prefer a git worktree per session."
)


def _marker(session_id: str) -> Path:
    base = Path(os.environ.get("TMPDIR") or "/tmp")
    return base / f"guardrail-session-{session_id or 'unknown'}"


def _should_fire(marker: Path, count: int, remind_every_min: float, now: float) -> bool:
    try:
        last_count = int(marker.read_text().strip() or "0")
        age_min = (now - marker.stat().st_mtime) / 60.0
    except (OSError, ValueError):
        return True
    return count > last_count or age_min >= remind_every_min


def _record(marker: Path, count: int) -> None:
    try:
        marker.write_text(str(count))
    except OSError:
        pass


def main() -> int:
    payload = _conf.read_stdin_json()
    conf, _ = _conf.load_kv_with_fallback(CONF_NAME)
    if conf is None or not _conf.truthy(conf.get("ENABLED", "1"), default=True):
        return 0
    transcript_path = payload.get("transcript_path") or ""
    if not transcript_path:
        return 0
    session_id = payload.get("session_id") or Path(transcript_path).stem
    cwd = payload.get("cwd") or os.getcwd()
    window = float(conf.get("ACTIVE_WINDOW_MIN") or 10)
    remind_every = float(conf.get("REMIND_EVERY_MIN") or 30)
    include_sub = _conf.truthy(conf.get("INCLUDE_SUBDIR_SESSIONS", "1"), default=True)
    now = time.time()

    others = _sessions.other_active_sessions(transcript_path, session_id, window, cwd, include_sub, now)
    count = len(others)
    marker = _marker(session_id)
    event = payload.get("hook_event_name") or ""
    if count == 0:
        _record(marker, 0)
        return 0
    if event != "SessionStart" and not _should_fire(marker, count, remind_every, now):
        return 0
    _record(marker, count)
    noun = "session" if count == 1 else "sessions"
    print(f"[concurrent-session-guard] {count} other Claude Code {noun} active in this working tree:")
    print(_sessions.format_sessions(others))
    print(RULE)
    return 0


def selftest() -> int:
    import tempfile

    from _selftest import SelfTest

    t = SelfTest(__file__)
    tmp = Path(tempfile.mkdtemp(prefix="guardrail-sessions-"))
    home = tmp / "home"
    (home / ".claude" / "hooks").mkdir(parents=True)
    repo = tmp / "repo"
    (repo / ".claude" / "hooks").mkdir(parents=True)
    conf = repo / ".claude" / "hooks" / CONF_NAME
    conf.write_text("ENABLED=1\nACTIVE_WINDOW_MIN=10\nREMIND_EVERY_MIN=30\n", encoding="utf-8")
    cwd = str(repo)
    projects = tmp / "projects"
    proj = projects / "-repo"
    proj.mkdir(parents=True)
    now = time.time()

    def mk(path: Path, cwd_val: str, branch: str, minutes_ago: float) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"type":"user","cwd":"%s","gitBranch":"%s"}\n' % (cwd_val, branch), encoding="utf-8")
        os.utime(path, (now - minutes_ago * 60, now - minutes_ago * 60))
        return path

    own = mk(proj / "self0000-0000.jsonl", cwd, "main", 0)
    mk(proj / "recent00-0000.jsonl", cwd, "feature-x", 2)
    mk(proj / "stale000-0000.jsonl", cwd, "old", 40)
    mk(proj / "recent00-0000" / "subagents" / "agent-1.jsonl", cwd, "feature-x", 1)
    sib = projects / "-repo-scripts"
    mk(sib / "subdir00-0000.jsonl", cwd + "/scripts", "feature-y", 3)
    mk(sib / "elsewher-0000.jsonl", "/elsewhere/repo-scripts", "zzz", 1)

    env = {"CLAUDE_PROJECT_DIR": str(repo), "TMPDIR": str(tmp / "t"), "HOME": str(home)}
    (tmp / "t").mkdir()
    payload = {"session_id": "self0000-0000", "transcript_path": str(own), "cwd": cwd, "hook_event_name": "UserPromptSubmit"}

    rc, out, err = t.run(payload, env)
    t.check(rc == 0 and "2 other Claude Code sessions" in out, "counts recent sibling and subdir sessions", out + err)
    t.check("recent00 on branch feature-x" in out and "subdir00 on branch feature-y" in out, "lists sid, branch and age", out)
    t.check("stale000" not in out and "self0000" not in out, "excludes self and stale sessions", out)
    t.check("agent-1" not in out and "elsewher" not in out, "excludes subagent files and unrelated subdir sessions", out)
    t.check("git branch --show-current" in out, "prints the shared-tree rule", out)

    t.assert_quiet(t.run(payload, env), "rate-limited on the next prompt")
    mk(proj / "newer000-0000.jsonl", cwd, "feature-z", 1)
    rc, out, err = t.run(payload, env)
    t.check(rc == 0 and "3 other" in out, "re-fires when the count grows", out + err)
    t.assert_quiet(t.run(payload, env), "quiet again after the growth was reported")
    rc, out, err = t.run(dict(payload, hook_event_name="SessionStart"), env)
    t.check(rc == 0 and "3 other" in out, "SessionStart always reports", out + err)

    conf.write_text("ENABLED=0\n", encoding="utf-8")
    t.assert_quiet(t.run(dict(payload, session_id="fresh-1"), env), "ENABLED=0 is quiet")
    conf.unlink()
    t.assert_quiet(t.run(dict(payload, session_id="fresh-2"), env), "quiet with no conf anywhere")
    (home / ".claude" / "hooks" / CONF_NAME).write_text("ENABLED=1\nACTIVE_WINDOW_MIN=10\n", encoding="utf-8")
    rc, out, err = t.run(dict(payload, session_id="fresh-3"), env)
    t.check(rc == 0 and "3 other" in out, "global fallback conf enables the guard", out + err)
    (home / ".claude" / "hooks" / CONF_NAME).write_text("ENABLED=1\nINCLUDE_SUBDIR_SESSIONS=0\n", encoding="utf-8")
    rc, out, err = t.run(dict(payload, session_id="fresh-4"), env)
    t.check(rc == 0 and "2 other" in out and "subdir00" not in out, "INCLUDE_SUBDIR_SESSIONS=0 ignores subdir sessions", out + err)

    lonely = projects / "-lonely"
    solo = mk(lonely / "solo0000-0000.jsonl", str(tmp / "lonely"), "main", 0)
    t.assert_quiet(t.run({"session_id": "solo0000-0000", "transcript_path": str(solo), "cwd": str(tmp / "lonely"), "hook_event_name": "SessionStart"}, env), "quiet when alone")
    return t.report()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    try:
        sys.exit(main())
    except Exception as exc:  # never block a prompt
        print(f"[concurrent-session-guard] hook error ignored: {exc}", file=sys.stderr)
        sys.exit(0)
