#!/usr/bin/env python3
"""SessionStart + PreToolUse (Bash) + PostToolUse hook: keep a checkout's git settings sane.

Two settings in a checkout's own `.git/config` break things quietly:

  core.bare = true       git stops treating the folder as a checkout. Every
                         status, commit and merge fails with "must be run in a
                         work tree", and worktrees made from it misbehave.
  core.hooksPath = …     an absolute path, a `~` path, or a folder outside the
                         repo makes every worktree run one checkout's hooks
                         (or none, once that folder moves). A relative folder
                         that does not exist turns the hooks off without a word.
  user.email = …@….invalid   a throwaway identity (a domain that cannot exist:
                         .invalid, .test, .example, example.com, localhost) in the
                         checkout's own config means a test ran git against the
                         real repo, usually because GIT_DIR was set. New commits
                         would be authored as it. A real repo-local identity (a
                         work address) is fine and stays quiet.

What it does:

  SessionStart           reads these settings for the checkout the session opens
                         in and, when one is wrong, says which and gives the
                         exact command that fixes it.
  PreToolUse (Bash)      denies a `git config` that would set `core.bare true`,
                         or set a repo's `core.hooksPath` to an absolute, `~`,
                         `$VAR` or `../` path (`--global`/`--system` hooks
                         folders are a normal machine-wide setup and allowed).
                         Before any other git command it repeats the SessionStart
                         report when a setting is wrong, at most once per ten
                         minutes per session unless the problem changes.
  PostToolUse            runs the same check right after a worktree is made:
                         a Bash `git worktree add`, EnterWorktree, or an Agent
                         call with `isolation: "worktree"`.

The one fix it makes by itself: `core.hooksPath` written as an absolute path to
the repo's own hooks folder (`<repo>/.githooks`, or the main checkout's
`.githooks` seen from a linked worktree) is rewritten to the relative path
(`.githooks`), and the hook says what it changed. Claude Code itself writes that
absolute path when it makes a worktree: it turns the relative value into an
absolute one and runs `git config` inside the new worktree, which lands in the
config every worktree shares. The fix is safe because the relative folder names
the same committed hooks in every checkout. It is made only when that folder
exists in the checkout being checked, never when `core.bare` is true, and never
for `.git/hooks` (a relative `.git/...` breaks in linked worktrees). Everything
else (a folder outside the repo, a missing folder, `~` or `$VAR`) stays a
report with the fix command. Turn the fix off with `AUTO_FIX=0`.

Not used: the WorktreeCreate hook event. Defining it replaces Claude Code's own
worktree creation (the hook must make the worktree and print its path), so a
guard there would break every worktree.

ON by default, like block-git-ours-theirs: a guard that checks nothing until it
is configured is not a guard. Opt out per repo or machine with
`.claude/hooks/git-settings.conf` containing `ENABLED=0`.
"""
from __future__ import annotations

import hashlib
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

CONF_NAME = "git-settings.conf"
REMIND_EVERY_MIN = 10

# One git invocation: from a `git` word to the next command separator.
GIT_SPAN_RE = re.compile(r"(?<![\w./-])git\b([^\n;|&]*)")
# Leading `-C dir`, `-c k=v`, `--git-dir=…` style options before the subcommand.
LEADING_OPT_RE = re.compile(r"^\s*(?:(?:-[cC]\s+\S+|-[cC]\S+|--[\w-]+(?:=\S+)?)\s+)*(\S+)?")
TRUE_WORDS = {"true", "yes", "on", "1"}
# `git config` options that take the next word as their value.
VALUE_OPTS = {"-f", "--file", "--blob", "--type", "--default", "--comment", "--value"}
MACHINE_SCOPES = {"--global", "--system"}
# Email domains that cannot belong to a real person: the reserved test names (RFC 2606/6761).
TEST_EMAIL_RE = re.compile(
    r"@(?:[\w.-]+\.)?(?:invalid|test|example|localhost|example\.(?:com|org|net))$|@localhost$",
    re.IGNORECASE,
)


def _tokens(span: str) -> list[str]:
    try:
        return shlex.split(span)
    except ValueError:  # an unclosed quote, e.g. the tail of `sh -c "git …"`
        return [w.strip("'\"") for w in span.split()]


def _config_setting(tokens: list[str]) -> tuple[str, str, set[str]] | None:
    """(key, value, scope flags) for a `git config` that sets a value, else None."""
    # Drop everything up to and including the `config` subcommand.
    try:
        words = tokens[tokens.index("config") + 1 :]
    except ValueError:
        return None
    if words and words[0] == "set":
        words = words[1:]
    flags: set[str] = set()
    positional: list[str] = []
    skip = False
    for w in words:
        if skip:
            skip = False
            continue
        if w.startswith("-"):
            flags.add(w.split("=", 1)[0])
            if w in VALUE_OPTS:
                skip = True
            continue
        positional.append(w)
    if len(positional) < 2 or flags & {"--unset", "--unset-all", "--get", "--get-all", "--get-regexp", "-l", "--list"}:
        return None
    return positional[0].lower(), positional[1], flags


def _bad_hooks_value(value: str) -> str:
    """Why a hooksPath value is wrong for a repo's own config, or ''."""
    if value.startswith(("/", "~", "$")):
        return "an absolute path ties every worktree to one checkout's hooks"
    norm = os.path.normpath(value)
    if norm == ".." or norm.startswith("../"):
        return "a folder outside the repo is not the repo's own hooks"
    return ""


def offending(command: str) -> list[str]:
    """Every `git config` in `command` that would break a checkout's settings."""
    hits: list[str] = []
    for m in GIT_SPAN_RE.finditer(command):
        span = m.group(1)
        sub = ((LEADING_OPT_RE.match(span) or re.match("", "")).group(1) or "").strip("'\"")
        if sub != "config":
            continue
        setting = _config_setting(_tokens(span))
        if setting is None:
            continue
        key, value, flags = setting
        text = ("git" + span).strip()
        if key == "core.bare" and value.lower() in TRUE_WORDS:
            hits.append(f"{text} (core.bare true makes this checkout stop working as one)")
        elif key == "core.hookspath" and not (flags & MACHINE_SCOPES):
            why = _bad_hooks_value(value)
            if why:
                hits.append(f"{text} ({why})")
    return hits


def checkout_top(start: Path) -> Path | None:
    """The nearest folder at or above `start` holding a `.git` entry."""
    try:
        here = start.resolve()
    except OSError:
        return None
    for folder in (here, *here.parents):
        if (folder / ".git").exists():
            return folder
    return None


def _git_config(top: Path, key: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(top), "config", "--local", "--get", key],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def problems(top: Path) -> list[str]:
    """Plain-words problems with `top`'s settings, each with its fix."""
    found: list[str] = []
    bare = _git_config(top, "core.bare")
    if bare.lower() in TRUE_WORDS:
        found.append(
            f"core.bare is true, so git does not treat {top} as a checkout "
            f"(status, commit and merge fail). Fix: git -C {shlex.quote(str(top))} config core.bare false"
        )
    hooks = _git_config(top, "core.hooksPath")
    if hooks:
        why = _bad_hooks_value(hooks)
        if not why and not (top / hooks).is_dir():
            why = "that folder does not exist, so no hooks run"
        if why:
            fix = (
                f"git -C {shlex.quote(str(top))} config core.hooksPath .githooks"
                if (top / ".githooks").is_dir()
                else f"git -C {shlex.quote(str(top))} config --unset core.hooksPath"
            )
            found.append(f"core.hooksPath is {hooks!r}: {why}. Fix: {fix}")
    email = _git_config(top, "user.email")
    if email and TEST_EMAIL_RE.search(email):
        name = _git_config(top, "user.name")
        q = shlex.quote(str(top))
        fix = f"git -C {q} config --unset user.email"
        if name:
            fix += f" && git -C {q} config --unset user.name"
        found.append(
            f"user.email is {email!r} in this checkout's own settings: a test's throwaway identity, "
            f"so new commits would be authored as it. A test probably ran git here with GIT_DIR set. Fix: {fix}"
        )
    return found


def _main_root(top: Path) -> Path | None:
    """The main checkout's folder (the one holding the shared `.git`), seen from any worktree."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(top), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    common = Path(proc.stdout.strip()) if proc.returncode == 0 and proc.stdout.strip() else None
    return common.parent if common is not None and common.name == ".git" else None


def relative_hooks(top: Path, value: str) -> str:
    """The relative path to write instead of an absolute `value`, or '' when the swap is not safe.

    Safe means: `value` is an absolute path to a folder inside this checkout or the main
    checkout (not the checkout itself, not under `.git`), and the same relative folder exists
    in `top`, so git finds the same committed hooks there after the swap.
    """
    if not value.startswith("/"):
        return ""
    target = os.path.realpath(value)
    roots = [top]
    main = _main_root(top)
    if main is not None:
        roots.append(main)
    for root in roots:
        rel = os.path.relpath(target, os.path.realpath(root))
        first = Path(rel).parts[0] if rel != "." else "."
        if first in (".", "..", ".git"):
            continue
        if (top / rel).is_dir():
            return Path(rel).as_posix()
    return ""


def fix_hooks_path(top: Path) -> str:
    """Rewrite an absolute hooksPath that points at the repo's own hooks to the relative path.

    Returns what changed in plain words, or '' when nothing was changed."""
    if _git_config(top, "core.bare").lower() in TRUE_WORDS:
        return ""
    value = _git_config(top, "core.hooksPath")
    rel = relative_hooks(top, value) if value else ""
    if not rel:
        return ""
    try:
        proc = subprocess.run(
            ["git", "-C", str(top), "config", "--local", "core.hooksPath", rel],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if proc.returncode != 0:
        return ""
    return (
        f"[git-settings-guard] Fixed core.hooksPath for {top}: it was the absolute path {value!r}, "
        f"now the relative {rel!r}, so every worktree runs its own copy of the repo's hooks. "
        "Claude Code writes that absolute path itself when it makes a worktree (EnterWorktree, an "
        "Agent worktree, claude --worktree), so this is expected after one. Tell the user in one line. "
        "To stop this fix, put AUTO_FIX=0 in .claude/hooks/git-settings.conf."
    )


def report(top: Path, found: list[str]) -> str:
    lines = "\n".join(f"- {p}" for p in found)
    return (
        f"[git-settings-guard] This checkout's git settings are wrong ({top}):\n{lines}\n"
        "Tell the user what is wrong and the fix; change the setting only if they agree. "
        "git keeps no history of its settings, so also ask whether a tool or another session set it."
    )


def _marker(session_id: str) -> Path:
    base = Path(os.environ.get("TMPDIR") or "/tmp")
    return base / f"guardrail-git-settings-{session_id or 'unknown'}"


def _should_remind(session_id: str, found: list[str], now: float) -> bool:
    marker = _marker(session_id)
    digest = hashlib.sha1("\n".join(found).encode()).hexdigest()
    try:
        same = marker.read_text().strip() == digest
        age_min = (now - marker.stat().st_mtime) / 60.0
    except OSError:
        same, age_min = False, 0.0
    if same and age_min < REMIND_EVERY_MIN:
        return False
    try:
        marker.write_text(digest)
    except OSError:
        pass
    return True


def _settings() -> dict[str, str]:
    conf, _ = _conf.load_kv_with_fallback(CONF_NAME)
    return conf or {}


def enabled(conf: dict[str, str]) -> bool:
    return _conf.truthy(conf.get("ENABLED", "1"), default=True)


def auto_fix(conf: dict[str, str]) -> bool:
    return _conf.truthy(conf.get("AUTO_FIX", "1"), default=True)


def check(top: Path | None, fix: bool) -> tuple[str, list[str]]:
    """(what the hook fixed, the problems left) for checkout `top`."""
    if top is None:
        return "", []
    fixed = fix_hooks_path(top) if fix else ""
    return fixed, problems(top)


# `git … worktree add` (any leading options, e.g. `git -C dir worktree add`).
WORKTREE_ADD_RE = re.compile(r"^\s*worktree\s+add\b")


def worktree_add_dirs(command: str, cwd: Path) -> list[Path]:
    """The folder each `git worktree add` in `command` ran from (its `-C dir`, else cwd)."""
    dirs: list[Path] = []
    for m in GIT_SPAN_RE.finditer(command):
        span = m.group(1)
        lead = LEADING_OPT_RE.match(span)
        rest = span[lead.start(1):] if lead and lead.group(1) else ""
        if not WORKTREE_ADD_RE.match(rest):
            continue
        where = cwd
        words = _tokens(span[: lead.start(1)] if lead and lead.group(1) else "")
        for i, w in enumerate(words):
            if w == "-C" and i + 1 < len(words):
                where = where / os.path.expanduser(words[i + 1])
            elif w.startswith("-C") and len(w) > 2:
                where = where / os.path.expanduser(w[2:])
        dirs.append(where)
    return dirs


def post_tool_dirs(payload: dict, cwd: Path) -> list[Path]:
    """Where to check after this tool call, or [] when it did not make a worktree."""
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    if tool == "Bash":
        return worktree_add_dirs(tool_input.get("command") or "", cwd)
    if tool == "EnterWorktree":
        dirs = [cwd]
        resp = payload.get("tool_response")
        if isinstance(resp, dict):
            for key in ("worktreePath", "worktree_path", "path"):
                if isinstance(resp.get(key), str) and resp[key]:
                    dirs.append(Path(resp[key]))
        return dirs
    if tool == "Agent" and tool_input.get("isolation") == "worktree":
        return [cwd]
    return []


def main() -> int:
    payload = _conf.read_stdin_json()
    event = payload.get("hook_event_name") or ""
    conf = _settings()
    if not enabled(conf):
        return 0
    fix = auto_fix(conf)
    cwd = Path(payload.get("cwd") or _conf.project_root())

    if event == "SessionStart":
        top = checkout_top(cwd)
        fixed, found = check(top, fix)
        if fixed:
            print(fixed)
        if found:
            print(report(top, found))
        return 0

    if event == "PostToolUse":
        seen: set[Path] = set()
        notes: list[str] = []
        fixes: list[str] = []
        for where in post_tool_dirs(payload, cwd):
            top = checkout_top(where)
            if top is None or top in seen:
                continue
            seen.add(top)
            fixed, found = check(top, fix)
            if fixed:
                fixes.append(fixed)
                notes.append(fixed)
            if found and _should_remind(payload.get("session_id") or "", found, time.time()):
                notes.append(report(top, found))
        if notes:
            out: dict = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "\n".join(notes)}}
            if fixes:
                out["systemMessage"] = " ".join(f.split(" Tell the user")[0] for f in fixes)
            print(json.dumps(out))
        return 0

    if event != "PreToolUse" or payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not GIT_SPAN_RE.search(command):
        return 0
    hits = offending(command)
    if hits:
        reason = (
            "[git-settings-guard] denied: " + " ; ".join(hits) + "\n"
            "A checkout keeps core.bare false and a core.hooksPath inside the repo, written "
            "relative (e.g. .githooks), so every worktree runs its own hooks. If the user really "
            "wants this, they run it themselves; opt out with .claude/hooks/git-settings.conf ENABLED=0."
        )
        out = {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}
        print(json.dumps({"hookSpecificOutput": out}))
        return 0
    top = checkout_top(cwd)
    fixed, found = check(top, fix)
    notes = [fixed] if fixed else []
    if found and _should_remind(payload.get("session_id") or "", found, time.time()):
        notes.append(report(top, found))
    if notes:
        out = {"hookEventName": "PreToolUse", "additionalContext": "\n".join(notes)}
        print(json.dumps({"hookSpecificOutput": out}))
    return 0


DENIED = [
    "git config core.bare true",
    "git config --bool core.bare true",
    "git config --local core.bare yes",
    "git config set core.bare true",
    "git -C /tmp/repo config core.bare true",
    "git config core.hooksPath /srv/repo/.githooks",
    "git config core.hookspath ~/hooks",
    "git config --local core.hooksPath $HOME/hooks",
    "git config core.hooksPath ../shared-hooks",
    "git config set --local core.hooksPath /abs/hooks",
    "git fetch && git config core.bare true",
    'sh -c "git config core.bare true"',
]

ALLOWED = [
    "ls -la",
    "git status",
    "git config core.bare false",
    "git config --get core.bare",
    "git config --unset core.hooksPath",
    "git config core.hooksPath .githooks",
    "git config core.hooksPath ./tools/hooks",
    "git config --global core.hooksPath ~/.githooks",
    "git config --system core.hooksPath /etc/git-hooks",
    "git config user.name 'Some One'",
    "git -c core.bare=true status",
    "git init --bare /tmp/mirror.git",
    "grep -rn 'core.bare true' docs/",
]


def selftest() -> int:
    import tempfile

    from _selftest import SelfTest

    t = SelfTest(__file__)
    tmp = Path(tempfile.mkdtemp(prefix="guardrail-git-settings-"))
    home = tmp / "home"
    (home / ".claude" / "hooks").mkdir(parents=True)
    repo = tmp / "repo"
    (repo / ".claude" / "hooks").mkdir(parents=True)
    (repo / ".githooks").mkdir()
    env = {"CLAUDE_PROJECT_DIR": str(repo), "HOME": str(home), "TMPDIR": str(tmp),
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    genv = dict(os.environ, **env)

    def git(*args: str, cwd: Path = repo) -> None:
        subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, env=genv)

    def hooks_path() -> str:
        proc = subprocess.run(["git", "-C", str(repo), "config", "--local", "--get", "core.hooksPath"],
                              capture_output=True, text=True, env=genv)
        return proc.stdout.strip()

    git("init", "-q", "-b", "trunk")
    git("commit", "-q", "--allow-empty", "-m", "start")

    def bash(command: str, cwd: Path = repo, sid: str = "s1") -> dict:
        return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": sid,
                "cwd": str(cwd), "tool_input": {"command": command}}

    def start(cwd: Path = repo) -> dict:
        return {"hook_event_name": "SessionStart", "source": "startup", "cwd": str(cwd)}

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

    # Commands that would break the settings are denied; everything else passes quietly.
    for cmd in DENIED:
        rc, out, err = t.run(bash(cmd), env)
        t.check(rc == 0 and decision(out) == "deny", f"denies: {cmd}", out + err)
    for cmd in ALLOWED:
        t.assert_quiet(t.run(bash(cmd), env), f"allows: {cmd}")
    t.assert_quiet(t.run(dict(bash("git config core.bare true"), tool_name="Write"), env), "ignores non-Bash tools")

    # Healthy checkout: quiet at session start and before git commands.
    t.assert_quiet(t.run(start(), env), "healthy checkout: session start is quiet")
    git("config", "core.hooksPath", ".githooks")
    t.assert_quiet(t.run(start(), env), "relative .githooks that exists is fine")
    t.assert_quiet(t.run(start(tmp / "home"), env), "not a checkout: quiet")

    # core.bare true in a checkout.
    git("config", "core.bare", "true")
    rc, out, err = t.run(start(), env)
    t.check(rc == 0 and "core.bare is true" in out and "config core.bare false" in out, "session start reports core.bare true with the fix", out + err)
    sub = repo / "deep" / "er"
    sub.mkdir(parents=True)
    t.assert_flags(t.run(start(sub), env), "core.bare is true", "found from a subfolder too")
    rc, out, err = t.run(bash("git status"), env)
    t.check("core.bare is true" in context(out) and decision(out) == "", "before a git command: adds the report, does not deny", out + err)
    t.assert_quiet(t.run(bash("git log -1"), env), "the same problem is not repeated within ten minutes")
    t.assert_flags(t.run(bash("git log -1", sid="s2"), env), "core.bare is true", "a different session hears it once too")
    t.assert_quiet(t.run(bash("ls -la", sid="s3"), env), "a non-git command stays quiet")
    git("config", "core.bare", "false")

    conf = repo / ".claude" / "hooks" / CONF_NAME

    # An absolute path to the repo's own .githooks is rewritten to the relative path.
    git("config", "core.hooksPath", str(repo / ".githooks"))
    rc, out, err = t.run(start(), env)
    t.check(rc == 0 and "Fixed core.hooksPath" in out and "'.githooks'" in out and "[git-settings-guard] This checkout" not in out,
            "session start: absolute path to its own .githooks is fixed and said", out + err)
    t.check(hooks_path() == ".githooks", "the setting now reads .githooks", hooks_path())
    t.assert_quiet(t.run(start(), env), "after the fix the next session start is quiet")
    git("config", "core.hooksPath", str(repo / ".githooks") + "/")
    t.run(start(), env)
    t.check(hooks_path() == ".githooks", "a trailing slash is fixed too", hooks_path())
    git("config", "core.hooksPath", str(repo / ".githooks"))
    rc, out, err = t.run(bash("git status", sid="fix1"), env)
    t.check("Fixed core.hooksPath" in context(out) and decision(out) == "" and hooks_path() == ".githooks",
            "before a git command: fixed and said, not denied", out + err)

    # AUTO_FIX=0: the same absolute path only warns, and the setting is left alone.
    git("config", "core.hooksPath", str(repo / ".githooks"))
    conf.write_text("AUTO_FIX=0\n", encoding="utf-8")
    rc, out, err = t.run(start(), env)
    t.check("absolute path" in out and "config core.hooksPath .githooks" in out and "Fixed" not in out,
            "AUTO_FIX=0: absolute hooksPath is reported with the fix command", out + err)
    t.check(hooks_path() == str(repo / ".githooks"), "AUTO_FIX=0: the setting is not changed", hooks_path())
    conf.unlink()

    # Absolute paths that are not the repo's own hooks folder only warn.
    outside = tmp / "shared-hooks"
    outside.mkdir()
    git("config", "core.hooksPath", str(outside))
    rc, out, err = t.run(start(), env)
    t.check("absolute path" in out and "Fixed" not in out and hooks_path() == str(outside),
            "absolute path outside the repo: warns, setting left alone", out + err)
    git("config", "core.hooksPath", str(repo / ".git" / "hooks"))
    rc, out, err = t.run(start(), env)
    t.check("absolute path" in out and "Fixed" not in out and hooks_path() == str(repo / ".git" / "hooks"),
            "absolute path to .git/hooks: warns, never rewritten to a relative .git path", out + err)
    git("config", "core.hooksPath", str(repo / "no-such-hooks"))
    rc, out, err = t.run(start(), env)
    t.check("absolute path" in out and "Fixed" not in out, "absolute path to a missing folder in the repo: warns", out + err)
    git("config", "core.hooksPath", str(repo / ".githooks"))
    git("config", "core.bare", "true")
    rc, out, err = t.run(start(), env)
    t.check("core.bare is true" in out and "Fixed" not in out and hooks_path() == str(repo / ".githooks"),
            "core.bare true: nothing is fixed, both are reported", out + err)
    git("config", "core.bare", "false")

    git("config", "core.hooksPath", "../elsewhere")
    t.assert_flags(t.run(start(), env), "outside the repo", "hooksPath outside the repo is reported")
    git("config", "core.hooksPath", "no-such-hooks")
    t.assert_flags(t.run(start(), env), "does not exist", "hooksPath to a missing folder is reported")
    (repo / ".githooks").rmdir()
    t.assert_flags(t.run(start(), env), "--unset core.hooksPath", "with no .githooks the fix is to unset")
    (repo / ".githooks").mkdir()

    # A linked worktree reads the shared config. Claude Code's own worktree setup writes the
    # main checkout's hooks folder there as an absolute path; seen from the worktree it is fixed.
    wt = tmp / "repo-wt"
    git("worktree", "add", "-q", "-b", "side", str(wt))
    (wt / ".githooks").mkdir(exist_ok=True)
    git("config", "core.hooksPath", str(repo / ".githooks"), cwd=wt)
    rc, out, err = t.run(start(wt), env)
    t.check("Fixed core.hooksPath" in out and hooks_path() == ".githooks",
            "linked worktree: the main checkout's absolute .githooks is fixed to .githooks", out + err)
    t.assert_quiet(t.run(start(wt), env), "a worktree with the relative hooksPath is quiet")
    git("config", "core.hooksPath", str(wt / ".githooks"))
    t.run(start(wt), env)
    t.check(hooks_path() == ".githooks", "linked worktree: its own absolute .githooks is fixed too", hooks_path())
    bare_wt = tmp / "repo-wt-nohooks"
    git("worktree", "add", "-q", "-b", "nohooks", str(bare_wt))
    git("config", "core.hooksPath", str(repo / ".githooks"))
    rc, out, err = t.run(start(bare_wt), env)
    t.check("absolute path" in out and "Fixed" not in out and hooks_path() == str(repo / ".githooks"),
            "a worktree with no .githooks folder: warns, does not rewrite the shared setting", out + err)

    # PostToolUse: the check runs right after a worktree is made, and only then.
    def post(tool: str, tool_input: dict, cwd: Path = repo, response: object = None) -> dict:
        p = {"hook_event_name": "PostToolUse", "tool_name": tool, "session_id": "post",
             "cwd": str(cwd), "tool_input": tool_input}
        if response is not None:
            p["tool_response"] = response
        return p

    def post_out(out: str) -> tuple[str, str]:
        try:
            data = json.loads(out)
        except ValueError:
            return "", ""
        return data.get("hookSpecificOutput", {}).get("additionalContext", ""), data.get("systemMessage", "")

    cases = [
        ("Bash", {"command": f"git worktree add -b p1 {tmp / 'p1'}"}, repo, None, "after a Bash git worktree add"),
        ("Bash", {"command": f"git -C {repo} worktree add -b p2 {tmp / 'p2'}"}, tmp, None, "after git -C <repo> worktree add from elsewhere"),
        ("EnterWorktree", {"name": "x"}, wt, {"worktreePath": str(wt)}, "after EnterWorktree"),
        ("Agent", {"prompt": "p", "isolation": "worktree"}, repo, {"status": "async_launched"}, "after an Agent call that made a worktree"),
    ]
    for tool, tool_input, cwd, resp, name in cases:
        git("config", "core.hooksPath", str(repo / ".githooks"))
        rc, out, err = t.run(post(tool, tool_input, cwd, resp), env)
        ctx, msg = post_out(out)
        t.check(rc == 0 and "Fixed core.hooksPath" in ctx and "Fixed core.hooksPath" in msg and hooks_path() == ".githooks",
                f"PostToolUse {name}: fixed, told to Claude and the user", out + err)
    git("config", "core.hooksPath", str(repo / ".githooks"))
    for tool, tool_input, name in [
        ("Bash", {"command": "git status"}, "a Bash command that is not a worktree add"),
        ("Bash", {"command": "git worktree list"}, "git worktree list"),
        ("Agent", {"prompt": "p"}, "an Agent call with no worktree"),
        ("Write", {"file_path": "x"}, "another tool"),
    ]:
        t.assert_quiet(t.run(post(tool, tool_input), env), f"PostToolUse ignores {name}")
    t.check(hooks_path() == str(repo / ".githooks"), "PostToolUse left the setting alone for those", hooks_path())
    conf.write_text("AUTO_FIX=0\n", encoding="utf-8")
    rc, out, err = t.run(post("EnterWorktree", {"name": "x"}, wt), env)
    ctx, msg = post_out(out)
    t.check("absolute path" in ctx and not msg and hooks_path() == str(repo / ".githooks"),
            "PostToolUse with AUTO_FIX=0: warns only", out + err)
    conf.unlink()
    git("config", "core.hooksPath", ".githooks")

    # A test's throwaway identity in the checkout's own config; a real one stays quiet.
    git("config", "user.email", "t@t.invalid")
    git("config", "user.name", "t")
    rc, out, err = t.run(start(), env)
    t.check("throwaway identity" in out and "--unset user.email" in out and "--unset user.name" in out,
            "a .invalid user.email is reported with both unsets", out + err)
    for fake in ("ci@example.com", "x@build.test", "me@localhost", "a@b.example"):
        git("config", "user.email", fake)
        t.assert_flags(t.run(start(), env), "throwaway identity", f"test identity {fake} is reported")
    for real in ("someone@company.io", "dev@examples.com", "x@invalid-domain.org"):
        git("config", "user.email", real)
        t.assert_quiet(t.run(start(), env), f"a real-looking repo identity {real} is quiet")
    git("config", "--unset", "user.email")
    git("config", "--unset", "user.name")
    t.assert_quiet(t.run(start(), env), "no repo identity: quiet")

    # Opt out.
    git("config", "core.bare", "true")
    conf.write_text("ENABLED=0\n", encoding="utf-8")
    t.assert_quiet(t.run(start(), env), "repo ENABLED=0 silences the report")
    git("config", "core.bare", "false")
    git("config", "core.hooksPath", str(repo / ".githooks"))
    t.assert_quiet(t.run(start(), env), "repo ENABLED=0 also turns the fix off")
    t.check(hooks_path() == str(repo / ".githooks"), "repo ENABLED=0: the setting is not changed", hooks_path())
    git("config", "core.hooksPath", ".githooks")
    git("config", "core.bare", "true")
    t.assert_quiet(t.run(bash("git config core.bare true"), env), "repo ENABLED=0 allows the command")
    conf.unlink()
    (home / ".claude" / "hooks" / CONF_NAME).write_text("ENABLED=0\n", encoding="utf-8")
    t.assert_quiet(t.run(start(), env), "global ENABLED=0 silences it")
    conf.write_text("ENABLED=1\n", encoding="utf-8")
    t.assert_flags(t.run(start(), env), "core.bare is true", "repo ENABLED=1 overrides a global opt-out")
    return t.report()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    try:
        sys.exit(main())
    except Exception as exc:  # a broken guard must not block unrelated commands
        print(f"[git-settings-guard] hook error ignored: {exc}", file=sys.stderr)
        sys.exit(0)
