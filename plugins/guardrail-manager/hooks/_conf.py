"""Shared config loading for guardrail-manager hooks.

The plugin ships the engines and wires them on their events for every repo, but
each repo opts in by dropping a conf file into `.claude/hooks/`. No conf means
every hook is a silent no-op, which keeps uniform plugin firing safe.

Two conf shapes are used:

  KEY=value   (`load_kv`)  for flag-style confs such as concurrent-session.conf
  INI         (`load_ini`) for confs with one section per rule, such as
              policy-review.conf, where values are regexes and multi-line text

Some confs also honor a global fallback at `~/.claude/hooks/<name>` so a rule
that is about the machine (many sessions in one working tree) rather than one
repo can be turned on once.
"""
from __future__ import annotations

import configparser
import os
from pathlib import Path

TRUTHY = ("1", "true", "yes", "on")


def project_root() -> Path:
    """The repo the hook runs in: CLAUDE_PROJECT_DIR, else cwd."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env).resolve() if env else Path.cwd()


def repo_conf_path(name: str, root: Path | None = None) -> Path:
    return (root or project_root()) / ".claude" / "hooks" / name


def global_conf_path(name: str) -> Path:
    return Path(os.path.expanduser("~")) / ".claude" / "hooks" / name


def truthy(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    val = val.strip().lower()
    if val == "":
        return default
    return val in TRUTHY


def load_kv(path: Path) -> dict[str, str] | None:
    """Parse a KEY=value file. '#' comments and blank lines are ignored, inline
    comments and surrounding quotes are stripped. None when the file is absent."""
    if not path.is_file():
        return None
    data: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            val = val.split("#", 1)[0].strip().strip('"').strip("'")
            data[key.strip()] = val
    except OSError:
        return None
    return data


def load_kv_with_fallback(name: str, root: Path | None = None) -> tuple[dict[str, str] | None, Path | None]:
    """Repo conf wins; otherwise the global conf; otherwise (None, None)."""
    for path in (repo_conf_path(name, root), global_conf_path(name)):
        conf = load_kv(path)
        if conf is not None:
            return conf, path
    return None, None


def load_ini(path: Path) -> configparser.ConfigParser | None:
    """Parse an INI conf. Interpolation is off and inline comments are not
    recognised so regex values may contain '%', '#' and ';'. Keys keep their
    case. None when the file is absent or unparsable."""
    if not path.is_file():
        return None
    parser = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=None)
    parser.optionxform = str  # type: ignore[assignment]
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, OSError):
        return None
    return parser


def read_stdin_json() -> dict:
    """The hook payload. Any failure yields an empty dict so callers no-op."""
    import json
    import sys

    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (ValueError, OSError):
        return {}
