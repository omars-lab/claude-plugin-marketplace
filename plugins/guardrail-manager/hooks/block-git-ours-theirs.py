#!/usr/bin/env python3
"""PreToolUse (Bash) hook: deny any git command that resolves a conflict by
taking one side wholesale instead of working it by hand.

The tenet: a merge, rebase or cherry-pick conflict is resolved by reading both
sides, keeping both intents and re-running the gates. `-X ours`, `-X theirs`,
`-s ours`, `checkout --ours/--theirs`, `merge-file --ours/--theirs` and the
`merge=ours` driver all silently discard one side's work, usually another
session's, and nothing downstream notices.

Unlike the advisory hooks in this plugin, this one is ON by default and sets a
`deny` permissionDecision. Opt out per repo or machine with
`.claude/hooks/git-conflicts.conf` containing `ENABLED=0`; there is no other
switch, because a guard that verifies nothing until configured is not a guard.

What it catches, anywhere a `git` word starts a command (including inside
`sh -c "…"` strings):

    git merge|rebase|cherry-pick|pull|revert|stash … -X ours|theirs
    git … -Xtheirs / --strategy-option=ours / --strategy-option theirs
    git merge … -s ours / --strategy ours / --strategy=ours
    git checkout|restore|merge-file … --ours | --theirs   (git diff --ours is read-only and allowed)
    git config … merge.ours.driver / merge.<x>.driver     (the .gitattributes merge=ours trick)

What it cannot catch: overwriting a conflicted file with a regenerated one, or
closing a PR to avoid a conflict. Those stay in the tenet, not in the hook.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _conf  # noqa: E402

CONF_NAME = "git-conflicts.conf"

# One git invocation: from a `git` word to the next command separator.
GIT_SPAN_RE = re.compile(r"(?<![\w./-])git\b([^\n;|&]*)")
# Leading `-C dir`, `-c k=v`, `--git-dir=…` style options before the subcommand.
LEADING_OPT_RE = re.compile(r"^\s*(?:(?:-[cC]\s+\S+|-[cC]\S+|--[\w-]+(?:=\S+)?)\s+)*(\S+)?")
SIDE = r"(?:ours|theirs)"
STRATEGY_OPTION_RE = re.compile(
    rf"(?:^|\s)(?:-X\s*{SIDE}|--strategy-option(?:=|\s+){SIDE})(?=\s|$|['\"])"
)
STRATEGY_RE = re.compile(rf"(?:^|\s)(?:-s\s+ours|--strategy(?:=|\s+)ours)(?=\s|$|['\"])")
SIDE_FLAG_RE = re.compile(rf"(?:^|\s)--{SIDE}(?=\s|$|['\"])")
OURS_DRIVER_RE = re.compile(r"\bmerge\.(?:ours\b|[\w-]+\.driver\b)")
READ_ONLY_SUBCOMMANDS = {"diff", "log", "show", "diff-tree", "diff-files", "diff-index"}

TENET = (
    "Conflicts are worked by hand: read both sides, keep both intents, re-run the gates. "
    "Never `-X ours/theirs`, `-s ours`, `checkout/restore --ours/--theirs`, "
    "`merge-file --ours/--theirs` or a `merge=ours` driver — each discards one side's work "
    "silently, usually another session's. Open the conflicted file, resolve the markers "
    "yourself, then `git add <file>` by name and continue. "
    "(~/.claude/CLAUDE.md, 'Git in shared working trees'; opt out with "
    ".claude/hooks/git-conflicts.conf ENABLED=0.)"
)


def offending(command: str) -> list[str]:
    """Every git invocation in `command` that takes a side wholesale."""
    hits: list[str] = []
    for m in GIT_SPAN_RE.finditer(command):
        span = m.group(1)
        sub = (LEADING_OPT_RE.match(span) or re.match("", "")).group(1) or ""
        sub = sub.strip("'\"")
        text = "git" + span
        if STRATEGY_OPTION_RE.search(span) or STRATEGY_RE.search(span) or OURS_DRIVER_RE.search(span):
            hits.append(text.strip())
        elif SIDE_FLAG_RE.search(span) and sub not in READ_ONLY_SUBCOMMANDS:
            hits.append(text.strip())
    return hits


def main() -> int:
    payload = _conf.read_stdin_json()
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if "git" not in command:
        return 0
    conf, _ = _conf.load_kv_with_fallback(CONF_NAME)
    if conf is not None and not _conf.truthy(conf.get("ENABLED", "1"), default=True):
        return 0
    hits = offending(command)
    if not hits:
        return 0
    reason = "[block-git-ours-theirs] denied: " + " ; ".join(hits) + "\n" + TENET
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


DENIED = [
    "git merge -X ours feature",
    "git merge -Xtheirs feature",
    "git merge --strategy-option=theirs feature",
    "git merge --strategy-option ours feature",
    "git merge -s ours feature",
    "git merge --strategy ours feature",
    "git merge --strategy=ours feature",
    "git rebase -X theirs main",
    "git cherry-pick -X ours abc123",
    "git pull -X theirs origin main",
    "git revert -X ours HEAD",
    "git checkout --ours docs/x.md",
    "git checkout --theirs -- docs/x.md",
    "git restore --theirs docs/x.md",
    "git merge-file --ours a b c",
    "git -C /tmp/repo merge -X theirs main",
    "git -c core.editor=true rebase -Xours main",
    "export PATH=/x:$PATH; git merge -X ours main",
    "git fetch && git merge -X theirs origin/main && git push",
    'sh -c "git merge -X theirs main"',
    "git config merge.ours.driver true",
    "git config --global merge.keep-mine.driver true",
    "GIT_EDITOR=true git rebase -X theirs main",
]

ALLOWED = [
    "ls -la",
    "git status && git diff",
    "git merge feature",
    "git merge --no-ff feature",
    "git rebase main",
    "git cherry-pick abc123",
    "git diff --ours",
    "git diff --theirs docs/x.md",
    "git log --oneline -5",
    "git checkout -b feat/x",
    "git checkout main -- docs/x.md",
    "git restore --staged docs/x.md",
    "git commit -s -m 'signed off'",
    "git merge -s recursive feature",
    "git merge -X renormalize feature",
    "git merge -X ignore-space-change feature",
    "git config merge.conflictstyle diff3",
    "git config user.name 'Omar Eid'",
    "grep -rn 'X theirs' docs/",
    "echo 'their sours' | cat",
    "digit merge -X theirs main",
    "git ours-theirs-test",
]


def selftest() -> int:
    import tempfile

    from _selftest import SelfTest

    t = SelfTest(__file__)
    tmp = Path(tempfile.mkdtemp(prefix="guardrail-ours-theirs-"))
    home = tmp / "home"
    (home / ".claude" / "hooks").mkdir(parents=True)
    repo = tmp / "repo"
    (repo / ".claude" / "hooks").mkdir(parents=True)
    env = {"CLAUDE_PROJECT_DIR": str(repo), "HOME": str(home)}

    def payload(command: str, tool: str = "Bash") -> dict:
        return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"command": command}}

    def decision(out: str) -> str:
        try:
            return json.loads(out).get("hookSpecificOutput", {}).get("permissionDecision", "")
        except ValueError:
            return ""

    for cmd in DENIED:
        rc, out, err = t.run(payload(cmd), env)
        t.check(rc == 0 and decision(out) == "deny" and "worked by hand" in out, f"denies: {cmd}", out + err)
    for cmd in ALLOWED:
        t.assert_quiet(t.run(payload(cmd), env), f"allows: {cmd}")

    t.assert_quiet(t.run(payload("git merge -X ours main", tool="Write"), env), "ignores non-Bash tools")
    rc, out, _ = t.run(payload("git merge -X ours main && git checkout --theirs f"), env)
    t.check(out.count("git ") == 2 or ("git merge -X ours main" in out and "git checkout --theirs f" in out), "names every offending invocation", out)
    t.check(rc == 0 and decision(out) == "deny", "no conf at all still denies (on by default)", out)

    conf = repo / ".claude" / "hooks" / CONF_NAME
    conf.write_text("ENABLED=0\n", encoding="utf-8")
    t.assert_quiet(t.run(payload("git merge -X ours main"), env), "repo ENABLED=0 opts out")
    conf.unlink()
    (home / ".claude" / "hooks" / CONF_NAME).write_text("ENABLED=0\n", encoding="utf-8")
    t.assert_quiet(t.run(payload("git merge -X ours main"), env), "global ENABLED=0 opts out")
    conf.write_text("ENABLED=1\n", encoding="utf-8")
    rc, out, _ = t.run(payload("git merge -X ours main"), env)
    t.check(decision(out) == "deny", "repo ENABLED=1 overrides a global opt-out", out)
    return t.report()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    try:
        sys.exit(main())
    except Exception as exc:  # a broken guard must not block unrelated commands
        print(f"[block-git-ours-theirs] hook error ignored: {exc}", file=sys.stderr)
        sys.exit(0)
