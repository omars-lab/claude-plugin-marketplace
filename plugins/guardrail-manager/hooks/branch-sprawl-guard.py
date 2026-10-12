#!/usr/bin/env python3
"""PreToolUse (Bash) hook: warn before spawning yet another branch or worktree
when the checkout already carries a budget's worth of parallel work.

The tenet: parallel branches and worktrees are cheap to create and expensive to
reconcile. Past a handful, the work to spawn one more is dwarfed by the work to
land them all back on main — and every extra one drifts further from main while
you are not looking. So when the worktree count is already at or over the
budget, this hook interrupts a *creating* git command (`worktree add`,
`checkout -b/-B`, `switch -c/-C`, `branch <new>`, `--orphan`) and asks you to
reconcile something to main first rather than open a new front.

It fires on the *create* verbs only: `worktree list|remove|prune|move`,
`branch -d|-D|-m|-M|--list|--merged|…`, `checkout <ref>`, `switch <ref>` all
pass untouched, because those either reduce sprawl or just move around it.

Decision is **ask** by default — a warning with teeth: it shows the count and
the reconcile-first message and lets you consciously proceed, rather than
silently blocking (which trains a reflex override) or silently passing (which
verifies nothing). Set `DECISION=deny` to make it a hard stop.

The budget is the number of *working trees* the repo has (the primary checkout
plus every `git worktree add`), which is the concrete count of parallel fronts
and is instant to read. The bare repo itself is not counted.

Config `.claude/hooks/branch-sprawl.conf` (repo wins, else global
`~/.claude/hooks/branch-sprawl.conf`); absent means ON with the defaults, like
block-git-ours-theirs — a guard the user asked for should not wait to be
configured:

    ENABLED=1            # 0 opts the repo (or the machine) out
    MAX_WORKTREES=5      # fire when this many working trees already exist
    DECISION=ask         # or `deny` for a hard stop

What it cannot catch: creating a worktree in a *different* repo than the one the
command runs in, or branches spawned outside a Bash `git` call. Those stay in
the tenet, not the hook.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _conf  # noqa: E402

CONF_NAME = "branch-sprawl.conf"
DEFAULT_MAX = 5
DEFAULT_DECISION = "ask"

# One git invocation: from a `git` word to the next command separator.
GIT_SPAN_RE = re.compile(r"(?<![\w./-])git\b([^\n;|&]*)")
# Leading `-C dir`, `-c k=v`, `--git-dir=…` options before the subcommand.
LEADING_OPT_RE = re.compile(r"^\s*(?:(?:-[cC]\s+\S+|-[cC]\S+|--[\w-]+(?:=\S+)?)\s+)*(\S+)?")

# `git worktree add …` (not list / remove / prune / move / repair / lock …).
WORKTREE_ADD_RE = re.compile(r"^\s*add(?:\s|$)")
# `git checkout -b|-B <name>` or `git checkout --orphan <name>`.
CHECKOUT_CREATE_RE = re.compile(r"(?:^|\s)(?:-[bB]|--orphan)(?=\s)")
# `git switch -c|-C|--create|--force-create|--orphan <name>`.
SWITCH_CREATE_RE = re.compile(r"(?:^|\s)(?:-[cC]|--create|--force-create|--orphan)(?=\s)")
# `git branch` flags that mean list / delete / rename / inspect — never a create.
BRANCH_NONCREATE_RE = re.compile(
    r"(?:^|\s)(?:-[dDmMlvar]|--delete|--move|--list|--all|--remotes|--verbose"
    r"|--show-current|--merged|--no-merged|--contains|--no-contains|--points-at"
    r"|--sort|--format|--edit-description|--set-upstream-to|--unset-upstream|-u)\b"
)
# A non-option word after the subcommand — the branch name that makes it a create.
POSITIONAL_RE = re.compile(r"(?:^|\s)(?!-)(\S+)")

TENET = (
    "Parallel branches/worktrees are cheap to spawn and expensive to reconcile. "
    "You already have {n} working trees (budget {max}). Land one back on main before "
    "opening another front: finish or PR an existing branch, then "
    "`git worktree remove <path>` the ones already merged. "
    "(~/.claude/CLAUDE.md 'Git in shared working trees'; opt out with "
    ".claude/hooks/branch-sprawl.conf ENABLED=0, or raise MAX_WORKTREES.)"
)


def subcommand(span: str) -> tuple[str, str]:
    """(subcommand, the rest of the span after it). Skips leading -C/-c opts."""
    m = LEADING_OPT_RE.match(span)
    sub = ((m.group(1) if m else "") or "").strip("'\"")
    rest = span[m.end():] if m else span
    return sub, rest


def is_branch_create(rest: str) -> bool:
    """`git branch` with a name and none of the list/delete/rename/inspect flags."""
    if BRANCH_NONCREATE_RE.search(rest):
        return False
    # A copy (`-c`/`-C`) or a plain `branch <name>` both need a positional name.
    return POSITIONAL_RE.search(rest) is not None


def offending(command: str) -> list[str]:
    """Every git invocation in `command` that creates a branch or worktree."""
    hits: list[str] = []
    for m in GIT_SPAN_RE.finditer(command):
        span = m.group(1)
        sub, rest = subcommand(span)
        text = ("git" + span).strip()
        if sub == "worktree" and WORKTREE_ADD_RE.match(rest):
            hits.append(text)
        elif sub == "checkout" and CHECKOUT_CREATE_RE.search(rest):
            hits.append(text)
        elif sub == "switch" and SWITCH_CREATE_RE.search(rest):
            hits.append(text)
        elif sub == "branch" and is_branch_create(rest):
            hits.append(text)
    return hits


def count_worktrees(root: Path) -> int | None:
    """Working trees the repo has (primary + `worktree add`s); the bare repo
    itself is not one. None when `root` is not a git repo (fail open)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=4,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    n = 0
    for record in proc.stdout.split("\n\n"):
        lines = record.strip().splitlines()
        if lines and lines[0].startswith("worktree ") and not any(
            l.strip() == "bare" for l in lines
        ):
            n += 1
    return n


def main() -> int:
    payload = _conf.read_stdin_json()
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if "git" not in command or not any(
        v in command for v in ("worktree", "checkout", "switch", "branch")
    ):
        return 0
    conf, _ = _conf.load_kv_with_fallback(CONF_NAME)
    if conf is not None and not _conf.truthy(conf.get("ENABLED", "1"), default=True):
        return 0
    hits = offending(command)
    if not hits:
        return 0
    try:
        budget = int((conf or {}).get("MAX_WORKTREES", DEFAULT_MAX))
    except (TypeError, ValueError):
        budget = DEFAULT_MAX
    n = count_worktrees(_conf.project_root())
    if n is None or n < budget:
        return 0
    decision = ((conf or {}).get("DECISION", DEFAULT_DECISION) or DEFAULT_DECISION).strip().lower()
    if decision not in ("ask", "deny"):
        decision = DEFAULT_DECISION
    reason = (
        "[branch-sprawl] " + ("denied" if decision == "deny" else "reconcile first") + ": "
        + " ; ".join(hits) + "\n" + TENET.format(n=n, max=budget)
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


# ── selftest ────────────────────────────────────────────────────────────────
# Detection corpus runs against a real one-worktree repo with MAX_WORKTREES=0,
# so the budget is always met and only the create-verb detection is under test.
CREATE = [
    "git worktree add ../feat-x",
    "git worktree add -b feat/x ../feat-x main",
    "git checkout -b feat/x",
    "git checkout -B feat/x origin/main",
    "git switch -c feat/x",
    "git switch --create feat/x",
    "git switch -C feat/x main",
    "git branch feat/x",
    "git branch -f feat/x main",
    "git branch -c old new",
    "git checkout --orphan gh-pages",
    "git -C /some/repo checkout -b y",
    "git fetch && git checkout -b feat/z origin/main",
    'sh -c "git worktree add ../w"',
    "export PATH=/x:$PATH; git switch -c feat/q",
]

QUIET = [
    "git worktree list",
    "git worktree list --porcelain",
    "git worktree remove ../feat-x",
    "git worktree prune",
    "git worktree move ../a ../b",
    "git branch",
    "git branch -a",
    "git branch -r",
    "git branch -v",
    "git branch --list 'feat/*'",
    "git branch -d feat/x",
    "git branch -D feat/x",
    "git branch -m old new",
    "git branch -M main",
    "git branch --show-current",
    "git branch --merged origin/master",
    "git branch --set-upstream-to=origin/x",
    "git checkout main",
    "git checkout -- docs/x.md",
    "git checkout main -- docs/x.md",
    "git switch main",
    "git status && git diff",
    "git log --oneline -5",
    "ls -la",
    "grep -rn 'checkout -b' docs/",
]


def selftest() -> int:
    import os
    import tempfile

    from _selftest import SelfTest

    t = SelfTest(__file__)
    tmp = Path(tempfile.mkdtemp(prefix="guardrail-sprawl-"))
    home = tmp / "home"
    (home / ".claude" / "hooks").mkdir(parents=True)
    repo = tmp / "repo"
    (repo / ".claude" / "hooks").mkdir(parents=True)
    env = {"CLAUDE_PROJECT_DIR": str(repo), "HOME": str(home)}

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True,
                       capture_output=True, text=True)

    git("init", "-q")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit",
        "--allow-empty", "-q", "-m", "init")

    conf = repo / ".claude" / "hooks" / CONF_NAME
    conf.write_text("MAX_WORKTREES=0\nDECISION=ask\n", encoding="utf-8")

    def payload(command: str, tool: str = "Bash") -> dict:
        return {"hook_event_name": "PreToolUse", "tool_name": tool,
                "tool_input": {"command": command}}

    def decision(out: str) -> str:
        try:
            return json.loads(out).get("hookSpecificOutput", {}).get("permissionDecision", "")
        except ValueError:
            return ""

    for cmd in CREATE:
        rc, out, err = t.run(payload(cmd), env, cwd=str(repo))
        t.check(rc == 0 and decision(out) == "ask" and "reconcile" in out.lower(),
                f"warns: {cmd}", out + err)
    for cmd in QUIET:
        t.assert_quiet(t.run(payload(cmd), env, cwd=str(repo)), f"quiet: {cmd}")

    t.assert_quiet(t.run(payload("git checkout -b x", tool="Write"), env, cwd=str(repo)),
                   "ignores non-Bash tools")

    # Budget: one real worktree (the primary) is under a budget of 5.
    conf.write_text("MAX_WORKTREES=5\n", encoding="utf-8")
    t.assert_quiet(t.run(payload("git checkout -b x"), env, cwd=str(repo)),
                   "under budget stays quiet")
    conf.write_text("MAX_WORKTREES=1\n", encoding="utf-8")
    rc, out, _ = t.run(payload("git worktree add ../w"), env, cwd=str(repo))
    t.check(decision(out) == "ask", "at budget (1 tree ≥ 1) fires", out)

    # DECISION=deny is a hard stop.
    conf.write_text("MAX_WORKTREES=0\nDECISION=deny\n", encoding="utf-8")
    rc, out, _ = t.run(payload("git checkout -b x"), env, cwd=str(repo))
    t.check(decision(out) == "deny", "DECISION=deny denies", out)

    # Opt-out: repo then global; repo ENABLED=1 overrides a global opt-out.
    conf.write_text("ENABLED=0\n", encoding="utf-8")
    t.assert_quiet(t.run(payload("git checkout -b x"), env, cwd=str(repo)),
                   "repo ENABLED=0 opts out")
    conf.unlink()
    (home / ".claude" / "hooks" / CONF_NAME).write_text("MAX_WORKTREES=0\n", encoding="utf-8")
    rc, out, _ = t.run(payload("git checkout -b x"), env, cwd=str(repo))
    t.check(decision(out) == "ask", "global conf ON fires with no repo conf", out)
    (home / ".claude" / "hooks" / CONF_NAME).write_text("ENABLED=0\n", encoding="utf-8")
    t.assert_quiet(t.run(payload("git checkout -b x"), env, cwd=str(repo)),
                   "global ENABLED=0 opts out")
    conf.write_text("MAX_WORKTREES=0\n", encoding="utf-8")
    rc, out, _ = t.run(payload("git checkout -b x"), env, cwd=str(repo))
    t.check(decision(out) == "ask", "repo conf overrides a global opt-out", out)

    # No conf anywhere → ON by default (like block-git-ours-theirs).
    conf.unlink()
    (home / ".claude" / "hooks" / CONF_NAME).unlink()
    rc, out, _ = t.run(payload("git worktree add ../w"), env, cwd=str(repo))
    # default budget 5, one tree → under budget → quiet (correct: default is lenient).
    t.check(decision(out) == "", "no conf + 1 tree under default budget stays quiet", out)

    # Not a git repo → fail open.
    bare = tmp / "notgit"
    (bare / ".claude" / "hooks").mkdir(parents=True)
    (bare / ".claude" / "hooks" / CONF_NAME).write_text("MAX_WORKTREES=0\n", encoding="utf-8")
    t.assert_quiet(
        t.run(payload("git checkout -b x"), {"CLAUDE_PROJECT_DIR": str(bare), "HOME": str(home)}, cwd=str(bare)),
        "non-git project dir fails open",
    )
    return t.report()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    try:
        sys.exit(main())
    except Exception as exc:  # a broken guard must not block unrelated commands
        print(f"[branch-sprawl] hook error ignored: {exc}", file=sys.stderr)
        sys.exit(0)
