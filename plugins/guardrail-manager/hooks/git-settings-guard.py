#!/usr/bin/env python3
"""SessionStart + PreToolUse (Bash) hook: keep a checkout's git settings sane.

Two settings in a checkout's own `.git/config` break things quietly:

  core.bare = true       git stops treating the folder as a checkout. Every
                         status, commit and merge fails with "must be run in a
                         work tree", and worktrees made from it misbehave.
  core.hooksPath = …     an absolute path, a `~` path, or a folder outside the
                         repo makes every worktree run one checkout's hooks
                         (or none, once that folder moves). A relative folder
                         that does not exist turns the hooks off without a word.

What it does:

  SessionStart           reads both settings for the checkout the session opens
                         in and, when one is wrong, says which and gives the
                         exact command that fixes it. It never changes them.
  PreToolUse (Bash)      denies a `git config` that would set `core.bare true`,
                         or set a repo's `core.hooksPath` to an absolute, `~`,
                         `$VAR` or `../` path (`--global`/`--system` hooks
                         folders are a normal machine-wide setup and allowed).
                         Before any other git command it repeats the SessionStart
                         report when a setting is wrong, at most once per ten
                         minutes per session unless the problem changes.

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
    return found


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


def enabled() -> bool:
    conf, _ = _conf.load_kv_with_fallback(CONF_NAME)
    return conf is None or _conf.truthy(conf.get("ENABLED", "1"), default=True)


def main() -> int:
    payload = _conf.read_stdin_json()
    event = payload.get("hook_event_name") or ""
    if not enabled():
        return 0
    cwd = Path(payload.get("cwd") or _conf.project_root())

    if event == "SessionStart":
        top = checkout_top(cwd)
        found = problems(top) if top else []
        if found:
            print(report(top, found))
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
    found = problems(top) if top else []
    if found and _should_remind(payload.get("session_id") or "", found, time.time()):
        out = {"hookEventName": "PreToolUse", "additionalContext": report(top, found)}
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

    # core.hooksPath problems.
    git("config", "core.hooksPath", str(repo / ".githooks"))
    rc, out, _ = t.run(start(), env)
    t.check("absolute path" in out and "config core.hooksPath .githooks" in out, "absolute hooksPath is reported, fix points at .githooks", out)
    git("config", "core.hooksPath", "../elsewhere")
    t.assert_flags(t.run(start(), env), "outside the repo", "hooksPath outside the repo is reported")
    git("config", "core.hooksPath", "no-such-hooks")
    t.assert_flags(t.run(start(), env), "does not exist", "hooksPath to a missing folder is reported")
    (repo / ".githooks").rmdir()
    t.assert_flags(t.run(start(), env), "--unset core.hooksPath", "with no .githooks the fix is to unset")
    (repo / ".githooks").mkdir()

    # A worktree reads the shared config, so a bad absolute path shows there too.
    git("config", "core.hooksPath", str(repo / ".githooks"))
    wt = tmp / "repo-wt"
    git("worktree", "add", "-q", "-b", "side", str(wt))
    (wt / ".githooks").mkdir(exist_ok=True)
    t.assert_flags(t.run(start(wt), env), "absolute path", "a worktree reports the shared absolute hooksPath")
    git("config", "core.hooksPath", ".githooks")
    t.assert_quiet(t.run(start(wt), env), "a worktree with the relative hooksPath is quiet")

    # Opt out.
    git("config", "core.bare", "true")
    conf = repo / ".claude" / "hooks" / CONF_NAME
    conf.write_text("ENABLED=0\n", encoding="utf-8")
    t.assert_quiet(t.run(start(), env), "repo ENABLED=0 silences the report")
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
