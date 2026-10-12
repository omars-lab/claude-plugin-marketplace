#!/usr/bin/env python3
"""PreToolUse (Bash) hook: before a git commit/merge/push/rebase/cherry-pick,
state the current branch and the other active sessions so Claude confirms it
is on the intended branch.

Gated by `COMMIT_REMINDER=1` in `concurrent-session.conf` (repo or global) and
fires only when another session is active in the same working tree. It only
adds context; it never sets a permissionDecision.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _conf  # noqa: E402
import _sessions  # noqa: E402

CONF_NAME = "concurrent-session.conf"
GIT_WRITE_RE = re.compile(r"\bgit\b.*\b(commit|merge|push|rebase|cherry-pick)\b")


def current_branch(cwd: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "branch", "--show-current"], capture_output=True, text=True, timeout=3
        )
        branch = proc.stdout.strip()
        return branch or "(detached HEAD)"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def main() -> int:
    payload = _conf.read_stdin_json()
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not GIT_WRITE_RE.search(command):
        return 0
    conf, _ = _conf.load_kv_with_fallback(CONF_NAME)
    if conf is None or not _conf.truthy(conf.get("ENABLED", "1"), default=True):
        return 0
    if not _conf.truthy(conf.get("COMMIT_REMINDER", "1"), default=True):
        return 0
    transcript_path = payload.get("transcript_path") or ""
    if not transcript_path:
        return 0
    session_id = payload.get("session_id") or Path(transcript_path).stem
    cwd = payload.get("cwd") or os.getcwd()
    window = float(conf.get("ACTIVE_WINDOW_MIN") or 10)
    include_sub = _conf.truthy(conf.get("INCLUDE_SUBDIR_SESSIONS", "1"), default=True)
    others = _sessions.other_active_sessions(transcript_path, session_id, window, cwd, include_sub)
    if not others:
        return 0
    branch = current_branch(cwd)
    context = (
        f"Current branch: {branch}. Other active sessions in this working tree:\n"
        f"{_sessions.format_sessions(others)}\n"
        "Confirm this is the intended branch and that every staged file is yours before continuing."
    )
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": context}}))
    return 0


def selftest() -> int:
    import tempfile
    import time

    from _selftest import SelfTest

    t = SelfTest(__file__)
    tmp = Path(tempfile.mkdtemp(prefix="guardrail-commit-"))
    home = tmp / "home"
    (home / ".claude" / "hooks").mkdir(parents=True)
    repo = tmp / "repo"
    (repo / ".claude" / "hooks").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "trunk", str(repo)], check=True)
    conf = repo / ".claude" / "hooks" / CONF_NAME
    conf.write_text("ENABLED=1\nCOMMIT_REMINDER=1\n", encoding="utf-8")
    proj = tmp / "projects" / "-repo"
    proj.mkdir(parents=True)
    now = time.time()

    def mk(name: str, minutes_ago: float) -> Path:
        p = proj / name
        p.write_text('{"cwd":"%s","gitBranch":"other"}\n' % repo, encoding="utf-8")
        os.utime(p, (now - minutes_ago * 60, now - minutes_ago * 60))
        return p

    own = mk("self0000-0000.jsonl", 0)
    mk("peer0000-0000.jsonl", 1)
    env = {"CLAUDE_PROJECT_DIR": str(repo), "HOME": str(home)}

    def payload(command: str) -> dict:
        return {
            "session_id": "self0000-0000",
            "transcript_path": str(own),
            "cwd": str(repo),
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }

    t.assert_quiet(t.run(payload("ls -la"), env), "quiet for a non-git command")
    t.assert_quiet(t.run(payload("git status && git diff"), env), "quiet for read-only git")
    rc, out, err = t.run(payload("git add -A && git commit -m 'x'"), env)
    try:
        data = json.loads(out)
    except ValueError:
        data = {}
    ctx = data.get("hookSpecificOutput", {}).get("additionalContext", "")
    t.check(rc == 0 and "Current branch: trunk" in ctx and "peer0000 on branch other" in ctx, "commit with a peer active adds branch context", out + err)
    t.check("permissionDecision" not in out, "never sets a permissionDecision", out)
    t.assert_flags(t.run(payload("git push origin HEAD"), env), "Current branch", "push is covered")
    t.assert_flags(t.run(payload("git cherry-pick abc123"), env), "Current branch", "cherry-pick is covered")
    t.assert_quiet(t.run(dict(payload("git commit -m x"), tool_name="Write"), env), "ignores non-Bash tools")
    conf.write_text("ENABLED=1\nCOMMIT_REMINDER=0\n", encoding="utf-8")
    t.assert_quiet(t.run(payload("git commit -m x"), env), "COMMIT_REMINDER=0 is quiet")
    conf.unlink()
    t.assert_quiet(t.run(payload("git commit -m x"), env), "quiet with no conf")
    (home / ".claude" / "hooks" / CONF_NAME).write_text("ENABLED=1\n", encoding="utf-8")
    t.assert_flags(t.run(payload("git commit -m x"), env), "Current branch", "global fallback conf arms it")
    (proj / "peer0000-0000.jsonl").unlink()
    t.assert_quiet(t.run(payload("git commit -m x"), env), "quiet when no other session is active")
    return t.report()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    try:
        sys.exit(main())
    except Exception as exc:  # never block a tool call
        print(f"[remind-commit-branch] hook error ignored: {exc}", file=sys.stderr)
        sys.exit(0)
