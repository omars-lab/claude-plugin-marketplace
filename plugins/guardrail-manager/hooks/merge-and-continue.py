#!/usr/bin/env python3
"""Stop hook: when the session is about to stop to ask whether to merge, send it
back to merge and carry on.

In repos where the owner has said "merge your own PRs and keep going", a turn
that ends on "shall I merge?" or "PR is open, ready to merge" is a wasted round
trip. This hook reads the last assistant message; if it asks about a merge and
the session is in one of the listed repos, it returns decision=block with an
instruction to merge once the PR is clean and continue with the next item.

Opt in with `.claude/hooks/merge-and-continue.conf` in a repo, or once for the
machine at `~/.claude/hooks/merge-and-continue.conf` (KEY=value):

    ENABLED=1
    # basename of the git top-level; worktrees like bikar-work match too
    REPO_REGEX=^(3d-models|3d-model-hub|bikar|qiyas)(-.*)?$
    # optional overrides
    ASK_REGEX=...
    MESSAGE=...

Honours stop_hook_active, so it fires at most once per stop. Always exits 0.
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

CONF_NAME = "merge-and-continue.conf"

DEFAULT_ASK = "|".join([
    r"\b(shall|should|can|may) i (go ahead and )?merge\b",
    r"\bwant me to (go ahead and )?merge\b",
    r"\b(ready|good|clear|ok|okay) (for you )?to merge\b",
    r"\bready for (your )?(merge|review)\b",
    r"\bawaiting (your )?(merge|approval|go)\b",
    r"\b(left|leaving) (it |them |the prs? |pr #?\d+ )?(open|unmerged)\b",
    r"\b(open|opened),? (but )?not (yet )?merged\b",
    r"\bmerge (it|this|them|now)\s*\?",
    r"\bsay (the word|go)\b[^.\n]*\bmerge",
])

DEFAULT_MESSAGE = (
    "You were about to stop to ask about a merge. In this repo, merging our own PRs is "
    "already approved: poll `gh pr view N --json mergeStateStatus` until it is CLEAN, run "
    "`gh pr merge N --squash` (never --auto), delete the branch and its worktree, then carry "
    "on with the next item in ROI order. Leave a PR open only when it waits on a call that is "
    "the owner's (a look, a print, a filament choice, a secret); say so in one line and still "
    "carry on with the next item."
)


def last_assistant_text(payload: dict) -> str:
    """The final assistant message: from the payload when the host sends it,
    otherwise the last assistant entry with text in the transcript."""
    text = payload.get("last_assistant_message")
    if isinstance(text, str) and text.strip():
        return text
    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return ""
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") != "assistant":
            continue
        content = (entry.get("message") or {}).get("content")
        if isinstance(content, str):
            parts = [content]
        elif isinstance(content, list):
            parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        else:
            parts = []
        text = "\n".join(p for p in parts if p)
        if text.strip():
            return text
    return ""


def repo_name(cwd: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return Path(proc.stdout.strip()).name if proc.returncode == 0 else ""


def main() -> int:
    payload = _conf.read_stdin_json()
    if payload.get("stop_hook_active"):
        return 0
    cwd = payload.get("cwd") or str(_conf.project_root())
    conf, _ = _conf.load_kv_with_fallback(CONF_NAME, Path(cwd))
    if conf is None or not _conf.truthy(conf.get("ENABLED"), default=True):
        return 0
    repo_regex = conf.get("REPO_REGEX", "")
    name = repo_name(cwd)
    try:
        if not name or (repo_regex and not re.search(repo_regex, name)):
            return 0
        ask = re.compile(conf.get("ASK_REGEX") or DEFAULT_ASK, re.IGNORECASE)
    except re.error as exc:
        print(f"[merge-and-continue] invalid regex ({exc}); skipped", file=sys.stderr)
        return 0
    if not ask.search(last_assistant_text(payload)):
        return 0
    message = conf.get("MESSAGE") or DEFAULT_MESSAGE
    print(json.dumps({"decision": "block", "reason": f"[merge-and-continue] {message}"}))
    return 0


def selftest() -> int:
    import tempfile

    from _selftest import SelfTest

    t = SelfTest(__file__)
    tmp = Path(tempfile.mkdtemp(prefix="guardrail-merge-"))
    home = tmp / "home"
    (home / ".claude" / "hooks").mkdir(parents=True)

    def git_repo(name: str) -> Path:
        path = tmp / name
        path.mkdir()
        subprocess.run(["git", "init", "-q", str(path)], check=True)
        return path

    bikar_work, other = git_repo("bikar-work"), git_repo("website")
    plain = tmp / "not-a-repo"
    plain.mkdir()

    def transcript(*texts: str) -> str:
        f = tempfile.NamedTemporaryFile("w", dir=tmp, suffix=".jsonl", delete=False)
        for text in texts:
            f.write(json.dumps({"type": "user", "message": {"content": "go"}}) + "\n")
            f.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {}},
                {"type": "text", "text": text},
            ]}}) + "\n")
        f.close()
        return f.name

    def run(*texts: str, cwd: Path = bikar_work, extra: dict | None = None):
        payload = {"hook_event_name": "Stop", "cwd": str(cwd), "transcript_path": transcript(*texts)}
        payload.update(extra or {})
        return t.run(payload, env={"HOME": str(home), "CLAUDE_PROJECT_DIR": str(cwd)})

    def blocks(result) -> bool:
        rc, out, _ = result
        try:
            return rc == 0 and json.loads(out).get("decision") == "block"
        except ValueError:
            return False

    ask = "PR #12 is CLEAN. Shall I merge it?"
    t.assert_quiet(run(ask), "quiet when no conf exists")

    conf = home / ".claude" / "hooks" / CONF_NAME
    conf.write_text("ENABLED=1\nREPO_REGEX=^(3d-models|3d-model-hub|bikar|qiyas)(-.*)?$\n", encoding="utf-8")
    t.check(blocks(run(ask)), "blocks a merge question in a listed repo's worktree")
    rc, out, _ = run(ask)
    t.check("gh pr merge" in out and "--squash" in out, "the reason says how to merge", out)
    for text in (
        "Opened #7. Want me to merge?",
        "All gates green, ready to merge.",
        "The PR is open, not merged yet.",
        "Leaving PR #261 open for your review.",
    ):
        t.check(blocks(run(text)), f"blocks: {text!r}")
    t.assert_quiet(run("Merged #263 and deleted the branch. Next: the lobed border."), "quiet after a merge report")
    t.assert_quiet(run("Shall I merge it?", "Merged it; moving on to #87."), "reads only the last assistant message")
    t.assert_quiet(run(ask, cwd=other), "quiet in a repo the conf does not list")
    t.assert_quiet(run(ask, cwd=plain), "quiet outside a git repo")
    t.assert_quiet(run(ask, extra={"stop_hook_active": True}), "honours stop_hook_active (no loop)")
    t.check(blocks(run("nothing", extra={"last_assistant_message": ask})), "prefers last_assistant_message from the payload")

    repo_conf = bikar_work / ".claude" / "hooks"
    repo_conf.mkdir(parents=True)
    (repo_conf / CONF_NAME).write_text("ENABLED=0\n", encoding="utf-8")
    t.assert_quiet(run(ask), "a repo conf with ENABLED=0 overrides the global one")
    (repo_conf / CONF_NAME).write_text("REPO_REGEX=(unclosed\n", encoding="utf-8")
    rc, out, err = run(ask)
    t.check(rc == 0 and out.strip() == "" and "invalid regex" in err, "invalid regex is noted, never crashes", err)
    return t.report()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    try:
        sys.exit(main())
    except Exception as exc:  # never break a stop
        print(f"[merge-and-continue] hook error ignored: {exc}", file=sys.stderr)
        sys.exit(0)
