#!/usr/bin/env python3
"""PreToolUse (Bash) hook: before `git worktree add` opens yet another working
tree, make the session reuse or remove the finished ones first.

The tenet: parallel worktrees are cheap to create and expensive to reconcile,
and finished ones pile up because nobody removes them. So when the repo already
has a budget's worth of working trees, this hook looks at each one and sorts it:

  * **finished** — not the primary checkout, not locked, nothing unsaved
    (`git status --porcelain` is empty), its commit is on a remote branch, and
    no *other* Claude Code session has touched it lately. Removing it loses
    nothing; reusing it costs nothing.
  * **live** — anything else, with the reason (unsaved changes, not pushed,
    locked, in use by another session).

If any are finished, the hook **denies** the `worktree add` and hands the
session the exact commands: reuse one (`git -C <path> switch -c <new>
origin/main`) or `git worktree remove` it, then run the command again. That is
work the session can do itself, so nobody is asked to click "yes".

When every tree is live it **nudges** by default: the command goes ahead
(through the normal permission check) and the session is told which trees
are piling up and what would land each one (commits ahead of / behind the
default branch, changes that exist only on disk). Asking a person every time
blocked parallel work without consolidating anything, so `DECISION=ask` (or
`deny`) is now opt-in.

It fires on `git worktree add` only. A new branch inside an existing tree
(`switch -c`, `checkout -b`, `branch <new>`) adds no tree — and starting the
next branch in the same worktree is exactly what the tenet recommends — so
those pass untouched, as do list / remove / prune / move.

"Another session is using it": a transcript under `~/.claude/projects` (a
session or a subagent), other than the caller's own, changed in the last
IN_USE_MINUTES and naming the tree's path. The caller's own transcript is
skipped, because the hook's own message names those paths and would otherwise
mark every listed tree as in use from then on. Lines carrying this hook's own
`[branch-sprawl]` message are skipped in every transcript, for the same reason.

Config `.claude/hooks/branch-sprawl.conf` (repo wins, else global
`~/.claude/hooks/branch-sprawl.conf`); absent means ON with the defaults:

    ENABLED=1            # 0 opts the repo (or the machine) out
    MAX_WORKTREES=5      # look once this many working trees already exist
    DECISION=nudge       # when every tree is live: nudge (go ahead), ask, or deny
    IN_USE_MINUTES=120   # how recent another session's transcript must be

What it cannot catch: worktrees made outside a Bash `git` call (an agent's
own isolated worktree, for one), or in a different repo than the command's.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _conf  # noqa: E402

CONF_NAME = "branch-sprawl.conf"
DEFAULT_MAX = 5
DEFAULT_DECISION = "nudge"
DECISIONS = ("nudge", "ask", "deny")
OWN_MARK = "[branch-sprawl]"
DEFAULT_IN_USE_MIN = 120
TAIL_BYTES = 64 * 1024

# One git invocation: from a `git` word to the next command separator.
GIT_SPAN_RE = re.compile(r"(?<![\w./-])git\b([^\n;|&]*)")
# Leading `-C dir`, `-c k=v`, `--git-dir=…` options before the subcommand.
LEADING_OPT_RE = re.compile(r"^\s*(?:(?:-[cC]\s+\S+|-[cC]\S+|--[\w-]+(?:=\S+)?)\s+)*(\S+)?")
# `git worktree add …` (not list / remove / prune / move / repair / lock …).
WORKTREE_ADD_RE = re.compile(r"^\s*add(?:\s|$)")


def subcommand(span: str) -> tuple[str, str]:
    """(subcommand, the rest of the span after it). Skips leading -C/-c opts."""
    m = LEADING_OPT_RE.match(span)
    sub = ((m.group(1) if m else "") or "").strip("'\"")
    rest = span[m.end():] if m else span
    return sub, rest


def offending(command: str) -> list[str]:
    """Every `git worktree add` in `command`."""
    hits: list[str] = []
    for m in GIT_SPAN_RE.finditer(command):
        sub, rest = subcommand(m.group(1))
        if sub == "worktree" and WORKTREE_ADD_RE.match(rest):
            hits.append(("git" + m.group(1)).strip())
    return hits


def target_root(hit: str, project: Path, cwd: str) -> Path:
    """The repo a `git … worktree add` acts on: its `-C` dirs (git chains them,
    a relative one against the last), else the project."""
    try:
        words = shlex.split(hit)
    except ValueError:
        words = hit.split()
    root = Path(cwd or project)
    named = False
    for i, w in enumerate(words[1:], 1):
        if w == "worktree":
            break
        if w == "-C" and i + 1 < len(words):
            root, named = root / words[i + 1], True
        elif w.startswith("-C") and len(w) > 2:
            root, named = root / w[2:], True
    return root if named else project


def git(*args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, timeout=4)
    except (OSError, subprocess.SubprocessError):
        return None


def list_worktrees(root: Path) -> list[dict] | None:
    """Every working tree (bare repo excluded), primary first. None when
    `root` is not a git repo (fail open)."""
    proc = git("-C", str(root), "worktree", "list", "--porcelain")
    if proc is None or proc.returncode != 0:
        return None
    trees = []
    for record in proc.stdout.split("\n\n"):
        lines = record.strip().splitlines()
        if not lines or not lines[0].startswith("worktree ") or any(l.strip() == "bare" for l in lines):
            continue
        branch = next((l[len("branch "):] for l in lines if l.startswith("branch ")), "")
        trees.append({
            "path": lines[0][len("worktree "):],
            "branch": branch.replace("refs/heads/", "") or "(detached)",
            "locked": any(l.startswith("locked") for l in lines),
            "prunable": any(l.startswith("prunable") for l in lines),
        })
    for i, t in enumerate(trees):
        t["primary"] = i == 0
    return trees


def recent_transcripts(own: str, window_min: float, now: float) -> list[Path]:
    """Session and subagent transcripts other than the caller's own, changed
    within the window."""
    base = Path(os.environ.get("HOME", "~")).expanduser() / ".claude" / "projects"
    cutoff = now - window_min * 60.0
    own_path = os.path.realpath(own) if own else ""
    found: list[Path] = []

    def scan(directory: str, depth: int) -> None:
        try:
            entries = list(os.scandir(directory))
        except OSError:
            return
        for e in entries:
            try:
                if e.is_file(follow_symlinks=False) and e.name.endswith(".jsonl"):
                    if e.stat().st_mtime >= cutoff and os.path.realpath(e.path) != own_path:
                        found.append(Path(e.path))
                elif depth > 0 and e.is_dir(follow_symlinks=False):
                    scan(e.path, depth - 1)
            except OSError:
                continue

    # projects/<slug>/<sid>.jsonl and projects/<slug>/<sid>/subagents/<id>.jsonl
    scan(str(base), 3)
    return found


def _tail(path: Path) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > TAIL_BYTES:
                fh.seek(size - TAIL_BYTES)
            text = fh.read().decode("utf-8", errors="ignore")
    except OSError:
        return ""
    # This hook's own message names every tree; it is not a sign anyone works there.
    return "\n".join(l for l in text.splitlines() if OWN_MARK not in l)


def in_use_paths(paths: list[str], transcripts: list[Path]) -> set[str]:
    """The tree paths some other recent transcript names. A path must be
    followed by a separator so `/repo` doesn't match `/repo-other`."""
    tails = [_tail(p) for p in transcripts]
    used = set()
    for path in paths:
        # macOS: git prints /private/var/… while a session may record /var/… (and the reverse).
        p = path.rstrip("/")
        spellings = {p, os.path.realpath(p), p[len("/private"):] if p.startswith("/private/") else p}
        pat = re.compile("(?:" + "|".join(re.escape(s) for s in spellings) + r")(?=[/\"'\s\\]|$)")
        if any(pat.search(t) for t in tails):
            used.add(path)
    return used


def default_branch(root: Path) -> str:
    """origin's default branch (`origin/main` when origin/HEAD isn't set)."""
    proc = git("-C", str(root), "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    return proc.stdout.strip() if proc and proc.returncode == 0 and proc.stdout.strip() else "origin/main"


def landing_hint(t: dict, base: str) -> str:
    """What would land a live tree: how far it is from `base`, and the next step."""
    proc = git("-C", t["path"], "rev-list", "--left-right", "--count", f"{base}...HEAD")
    if proc is None or proc.returncode != 0:
        return ""
    try:
        behind, ahead = (int(n) for n in proc.stdout.split())
    except ValueError:
        return ""
    where = f"{ahead} ahead, {behind} behind {base}"
    if t["why"] == "has unsaved changes" and ahead == 0:
        return f"{where}; its work is only on disk: commit it to a branch and open a PR, or drop it"
    if t["why"] == "has commits not pushed anywhere":
        return f"{where}; push the branch and open a PR"
    if ahead == 0 and t["why"] != "has unsaved changes":
        return f"{where}; nothing of its own, so it can be reused once its session is done"
    return where


def classify(trees: list[dict], used: set[str]) -> None:
    """Set `why` on every tree: "" when finished, else the reason it's live."""
    for t in trees:
        if t["primary"]:
            t["why"] = "the main checkout"
            continue
        if t["locked"]:
            t["why"] = "locked (an agent is working in it)"
            continue
        if t["prunable"]:
            t["why"] = ""  # its folder is already gone; `git worktree prune` clears it
            continue
        status = git("-C", t["path"], "status", "--porcelain")
        if status is None or status.returncode != 0:
            t["why"] = "could not be read"
            continue
        if status.stdout.strip():
            t["why"] = "has unsaved changes"
            continue
        pushed = git("-C", t["path"], "branch", "-r", "--contains", "HEAD")
        if pushed is None or pushed.returncode != 0 or not pushed.stdout.strip():
            t["why"] = "has commits not pushed anywhere"
            continue
        t["why"] = "in use by another session" if t["path"] in used else ""


def message(trees: list[dict], budget: int, hits: list[str], decision: str, base: str) -> tuple[bool, str]:
    """(any finished, the text for the session)."""
    done = [t for t in trees if not t["why"]]
    live = [t for t in trees if t["why"]]
    if done:
        head = f"{OWN_MARK} {len(trees)} working trees already (budget {budget}); not adding another: {' ; '.join(hits)}\n"
        lines = [head, "These hold nothing unsaved, their work is pushed, and no other session is using them:"]
        for t in done:
            if t["prunable"]:
                lines.append(f"  - {t['path']} ({t['branch']}): folder already gone -> git worktree prune")
            else:
                lines.append(f"  - {t['path']} ({t['branch']})")
        lines += [
            "Reuse one instead of adding a tree: git -C <path> switch -c <new-branch> origin/main",
            "or remove the ones you are done with: git worktree remove <path>  (the branch stays)",
            "then run your command again. Skip any your own session is still working in.",
        ]
        return True, "\n".join(lines)
    if decision == "nudge":
        head = f"{OWN_MARK} {len(trees) + 1} working trees with this new one (budget {budget}); going ahead: {' ; '.join(hits)}\n"
    else:
        head = f"{OWN_MARK} {len(trees)} working trees already (budget {budget}); not adding another: {' ; '.join(hits)}\n"
    lines = [head, "Every tree holds live work:"]
    for t in live:
        hint = "" if t["primary"] else landing_hint(t, base)
        lines.append(f"  - {t['path']} ({t['branch']}): {t['why']}" + (f" ({hint})" if hint else ""))
    if decision == "nudge":
        lines.append("Consolidate as you go: land one of these, and when this new tree's PR merges, "
                     "start the next branch in it (git switch -c <next> origin/main) or remove it.")
    else:
        lines.append("Land one back on main first, or go ahead if this new front is worth it.")
    return False, "\n".join(lines)


def conf_int(conf: dict | None, key: str, default: int) -> int:
    try:
        return int((conf or {}).get(key, default))
    except (TypeError, ValueError):
        return default


def main() -> int:
    payload = _conf.read_stdin_json()
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if "git" not in command or "worktree" not in command:
        return 0
    conf, _ = _conf.load_kv_with_fallback(CONF_NAME)
    if conf is not None and not _conf.truthy(conf.get("ENABLED", "1"), default=True):
        return 0
    hits = offending(command)
    if not hits:
        return 0
    budget = conf_int(conf, "MAX_WORKTREES", DEFAULT_MAX)
    # `git -C <other repo> worktree add` adds a tree to that repo, so count its trees.
    root = target_root(hits[0], Path(_conf.project_root()), payload.get("cwd") or os.getcwd())
    trees = list_worktrees(root)
    if trees is None and root != Path(_conf.project_root()):
        # Can't read the named repo: count the project's trees, as before.
        root = Path(_conf.project_root())
        trees = list_worktrees(root)
    if trees is None or len(trees) < budget:
        return 0
    window = conf_int(conf, "IN_USE_MINUTES", DEFAULT_IN_USE_MIN)
    others = recent_transcripts(payload.get("transcript_path") or "", window, time.time())
    classify(trees, in_use_paths([t["path"] for t in trees if not t["primary"]], others))
    decision = ((conf or {}).get("DECISION", DEFAULT_DECISION) or DEFAULT_DECISION).strip().lower()
    if decision not in DECISIONS:
        decision = DEFAULT_DECISION
    any_done, reason = message(trees, budget, hits, decision, default_branch(root))
    if any_done:
        decision = "deny"  # the session can clean up itself; don't make a person click through
    if decision == "nudge":
        # No permissionDecision: the command still goes through the normal permission check.
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": reason}}))
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}))
    return 0


# ── selftest ────────────────────────────────────────────────────────────────
CREATE = [
    "git worktree add ../feat-x",
    "git worktree add -b feat/x ../feat-x main",
    "git -C /some/repo worktree add ../y",
    "git fetch && git worktree add ../z origin/main",
    'sh -c "git worktree add ../w"',
]

QUIET = [
    # A new branch in an existing tree adds no tree: the recommended move.
    "git checkout -b feat/x",
    "git switch -c feat/x origin/main",
    "git -C /some/worktree switch -c research/x origin/main",
    "git branch feat/x",
    "git checkout --orphan gh-pages",
    "git worktree list",
    "git worktree list --porcelain",
    "git worktree remove ../feat-x",
    "git worktree prune",
    "git worktree move ../a ../b",
    "git branch -D feat/x",
    "git checkout main",
    "git status && git diff",
    "ls -la",
    "grep -rn 'worktree add' docs/",
]


def selftest() -> int:
    import shutil
    import tempfile

    from _selftest import SelfTest

    t = SelfTest(__file__)
    tmp = Path(tempfile.mkdtemp(prefix="guardrail-sprawl-"))
    home = tmp / "home"
    (home / ".claude" / "hooks").mkdir(parents=True)
    projects = home / ".claude" / "projects" / "-some-project"
    projects.mkdir(parents=True)
    origin = tmp / "origin.git"
    repo = tmp / "repo"
    (repo / ".claude" / "hooks").mkdir(parents=True)
    env = {"CLAUDE_PROJECT_DIR": str(repo), "HOME": str(home)}
    own = projects / "own-session.jsonl"
    own.write_text("{}\n", encoding="utf-8")

    def run_git(*args: str, cwd: Path = repo) -> None:
        subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                       check=True, capture_output=True, text=True)

    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, capture_output=True)
    run_git("init", "-q", "-b", "main")
    (repo / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    run_git("add", ".gitignore")
    run_git("commit", "-q", "-m", "init")
    run_git("remote", "add", "origin", str(origin))
    run_git("push", "-q", "origin", "main")

    conf = repo / ".claude" / "hooks" / CONF_NAME

    def payload(command: str, tool: str = "Bash") -> dict:
        return {"hook_event_name": "PreToolUse", "tool_name": tool, "transcript_path": str(own),
                "tool_input": {"command": command}}

    def decision(out: str) -> str:
        try:
            return json.loads(out).get("hookSpecificOutput", {}).get("permissionDecision", "")
        except ValueError:
            return ""

    def context(out: str) -> str:
        try:
            return json.loads(out).get("hookSpecificOutput", {}).get("additionalContext", "")
        except ValueError:
            return ""

    def nudged(out: str) -> bool:
        """Went ahead (no permission decision) with the live-work note for the session."""
        return decision(out) == "" and "live work" in context(out) and "going ahead" in context(out)

    # Detection: with a budget of 0 and only the primary tree (live), creates nudge.
    conf.write_text("MAX_WORKTREES=0\n", encoding="utf-8")
    for cmd in CREATE:
        rc, out, err = t.run(payload(cmd), env, cwd=str(repo))
        t.check(rc == 0 and nudged(out), f"nudges: {cmd}", out + err)
    for cmd in QUIET:
        t.assert_quiet(t.run(payload(cmd), env, cwd=str(repo)), f"quiet: {cmd}")
    t.assert_quiet(t.run(payload("git worktree add ../w", tool="Write"), env, cwd=str(repo)),
                   "ignores non-Bash tools")

    # A finished tree (clean, pushed, unused) → deny with reuse/remove commands.
    done = tmp / "wt-done"
    run_git("worktree", "add", "-q", "-b", "done", str(done), "main")
    conf.write_text("MAX_WORKTREES=2\n", encoding="utf-8")
    rc, out, _ = t.run(payload("git worktree add ../new"), env, cwd=str(repo))
    t.check(decision(out) == "deny" and str(done) in out and "git worktree remove" in out,
            "finished tree → deny, names it and the remove command", out)

    # `git -C <other repo> worktree add` counts that repo's trees, not the project's.
    other_repo = tmp / "other-repo"
    subprocess.run(["git", "init", "-q", str(other_repo)], check=True, capture_output=True)
    t.assert_quiet(t.run(payload(f"git -C {other_repo} worktree add ../new"), env, cwd=str(repo)),
                   "-C names another repo with one tree → quiet")
    rc, out, _ = t.run(payload(f"git -C {repo} worktree add ../new"), env, cwd=str(repo))
    t.check(decision(out) == "deny", "-C naming the project still counts the project", out)

    # The caller's own transcript naming it doesn't make it in use.
    own.write_text(json.dumps({"cwd": str(done)}) + "\n", encoding="utf-8")
    rc, out, _ = t.run(payload("git worktree add ../new"), env, cwd=str(repo))
    t.check(decision(out) == "deny", "own transcript naming a tree is ignored", out)

    # Another session's transcript naming it only inside this hook's own message → still finished.
    other = projects / "other-session.jsonl"
    other.write_text(json.dumps({"text": f"{OWN_MARK} Every tree holds live work: {done} (x)"}) + "\n",
                     encoding="utf-8")
    rc, out, _ = t.run(payload("git worktree add ../new"), env, cwd=str(repo))
    t.check(decision(out) == "deny", "the hook's own message in another transcript isn't a mention", out)

    # Another session's recent transcript naming it → live → nudge.
    other.write_text(json.dumps({"cwd": str(done)}) + "\n", encoding="utf-8")
    rc, out, _ = t.run(payload("git worktree add ../new"), env, cwd=str(repo))
    t.check(nudged(out) and "another session" in out, "other session in it → nudge", out)
    t.check("can be reused once its session is done" in out, "a tree with nothing of its own says it can be reused", out)
    # DECISION=ask brings back the prompt for the all-live case.
    conf.write_text("MAX_WORKTREES=2\nDECISION=ask\n", encoding="utf-8")
    rc, out, _ = t.run(payload("git worktree add ../new"), env, cwd=str(repo))
    t.check(decision(out) == "ask" and "not adding another" in out, "DECISION=ask asks when all live", out)
    conf.write_text("MAX_WORKTREES=2\n", encoding="utf-8")
    # …but a prefix match (`wt-done` vs `wt-done-2`) is not a mention.
    other.write_text(json.dumps({"cwd": str(done) + "-2"}) + "\n", encoding="utf-8")
    rc, out, _ = t.run(payload("git worktree add ../new"), env, cwd=str(repo))
    t.check(decision(out) == "deny", "path prefix isn't a mention", out)
    # …and an old transcript doesn't count.
    other.write_text(json.dumps({"cwd": str(done)}) + "\n", encoding="utf-8")
    old = time.time() - 3 * 3600
    os.utime(other, (old, old))
    rc, out, _ = t.run(payload("git worktree add ../new"), env, cwd=str(repo))
    t.check(decision(out) == "deny", "a transcript older than the window doesn't count", out)
    other.unlink()

    # A subagent transcript counts too.
    sub = projects / "parent-sid" / "subagents"
    sub.mkdir(parents=True)
    (sub / "agent-1.jsonl").write_text(json.dumps({"cwd": str(done)}) + "\n", encoding="utf-8")
    rc, out, _ = t.run(payload("git worktree add ../new"), env, cwd=str(repo))
    t.check(nudged(out), "subagent in it → nudge", out)
    shutil.rmtree(projects / "parent-sid")

    # Unsaved changes → live, and the note says the work is only on disk.
    (done / "x.txt").write_text("x", encoding="utf-8")
    rc, out, _ = t.run(payload("git worktree add ../new"), env, cwd=str(repo))
    t.check(nudged(out) and "unsaved" in out and "only on disk" in out, "unsaved changes → nudge", out)
    (done / "x.txt").unlink()

    # Commits not pushed → live, and the note says to push.
    run_git("commit", "-q", "--allow-empty", "-m", "local", cwd=done)
    rc, out, _ = t.run(payload("git worktree add ../new"), env, cwd=str(repo))
    t.check(nudged(out) and "not pushed" in out and "1 ahead" in out and "push the branch" in out,
            "unpushed commits → nudge", out)
    run_git("push", "-q", "origin", "done", cwd=done)
    rc, out, _ = t.run(payload("git worktree add ../new"), env, cwd=str(repo))
    t.check(decision(out) == "deny", "pushed to its own branch → finished", out)

    # Locked → live.
    run_git("worktree", "lock", str(done))
    rc, out, _ = t.run(payload("git worktree add ../new"), env, cwd=str(repo))
    t.check(nudged(out) and "locked" in out, "locked → nudge", out)

    # DECISION=deny makes the all-live case a hard stop too.
    conf.write_text("MAX_WORKTREES=2\nDECISION=deny\n", encoding="utf-8")
    rc, out, _ = t.run(payload("git worktree add ../new"), env, cwd=str(repo))
    t.check(decision(out) == "deny" and "live work" in out, "DECISION=deny denies when all live", out)
    run_git("worktree", "unlock", str(done))

    # Under budget stays quiet.
    conf.write_text("MAX_WORKTREES=5\n", encoding="utf-8")
    t.assert_quiet(t.run(payload("git worktree add ../new"), env, cwd=str(repo)), "under budget stays quiet")

    # Opt-out: repo then global; repo ENABLED=1 overrides a global opt-out.
    conf.write_text("ENABLED=0\nMAX_WORKTREES=0\n", encoding="utf-8")
    t.assert_quiet(t.run(payload("git worktree add ../new"), env, cwd=str(repo)), "repo ENABLED=0 opts out")
    conf.unlink()
    (home / ".claude" / "hooks" / CONF_NAME).write_text("ENABLED=0\n", encoding="utf-8")
    t.assert_quiet(t.run(payload("git worktree add ../new"), env, cwd=str(repo)), "global ENABLED=0 opts out")
    conf.write_text("MAX_WORKTREES=0\n", encoding="utf-8")
    rc, out, _ = t.run(payload("git worktree add ../new"), env, cwd=str(repo))
    t.check(decision(out) in ("ask", "deny"), "repo conf overrides a global opt-out", out)
    conf.unlink()
    (home / ".claude" / "hooks" / CONF_NAME).unlink()

    # No conf: default budget 5, two trees → quiet.
    t.assert_quiet(t.run(payload("git worktree add ../new"), env, cwd=str(repo)),
                   "no conf + 2 trees under default budget stays quiet")

    # Not a git repo → fail open.
    bare = tmp / "notgit"
    (bare / ".claude" / "hooks").mkdir(parents=True)
    (bare / ".claude" / "hooks" / CONF_NAME).write_text("MAX_WORKTREES=0\n", encoding="utf-8")
    t.assert_quiet(
        t.run(payload("git worktree add ../w"), {"CLAUDE_PROJECT_DIR": str(bare), "HOME": str(home)}, cwd=str(bare)),
        "non-git project dir fails open",
    )
    shutil.rmtree(tmp, ignore_errors=True)
    return t.report()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    try:
        sys.exit(main())
    except Exception as exc:  # a broken guard must not block unrelated commands
        print(f"[branch-sprawl] hook error ignored: {exc}", file=sys.stderr)
        sys.exit(0)
