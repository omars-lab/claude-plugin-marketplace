"""Shared config loader for the task-management-manager hook engines.

The plugin ships the engines and wires them uniformly on their events, but each
repo opts in (and picks task-file paths) via a repo-local config:

    ${CLAUDE_PROJECT_DIR}/.claude/hooks/task-management.conf

Schema (KEY=value, '#'-comments and blank lines ignored):

    DONE_FILE=docs/tasks/done.md
    BACKLOG_FILE=docs/tasks/backlog.md
    ENABLE_GUARD_DELETION=1
    ENABLE_CHECK_FILES=1
    ENABLE_TRACK_NUDGE=0
    ENABLE_TASK_SYNC=0
    # high-value knobs (optional — sensible defaults if unset):
    VERIFY_COMMAND=make tasks-check
    DONE_MARKER=@done
    PENDING_MARKER=#git:pending
    TRACK_NUDGE_MESSAGE=<override the pre-work nudge text>
    ALLOW_UNRECORDED_DELETE_REASONS=duplicate,superseded

Gating contract (keeps uniform plugin firing SAFE):
  - conf absent               -> every hook is a no-op.
  - ENABLE_<X> unset/0/false  -> that hook is a no-op.
  - DONE_FILE/BACKLOG_FILE    -> default to docs/tasks/{done,backlog}.md if unset.

Deletion-guard exception (opt-in, narrow): a repo may list reason tags under
ALLOW_UNRECORDED_DELETE_REASONS. A TaskUpdate deletion whose `metadata.deleteReason`
matches one of them skips the doc-recorded check entirely — for tasks that were never
real, standalone work (e.g. an ad-hoc duplicate of something tracked elsewhere), where
requiring a done/backlog line would just be busywork, not a safety net. Unset/empty ->
no exceptions accepted, matching prior behavior.
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DONE = "docs/tasks/done.md"
DEFAULT_BACKLOG = "docs/tasks/backlog.md"
DEFAULT_VERIFY = "make tasks-check"
DEFAULT_DONE_MARKER = "@done"
DEFAULT_PENDING_MARKER = "#git:pending"


def project_root() -> Path:
    """The repo we're running in — CLAUDE_PROJECT_DIR, else cwd."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env).resolve() if env else Path.cwd()


def load_conf(root: Path | None = None) -> dict | None:
    """Parse task-management.conf from the repo. Returns a dict, or None if the
    file is absent (→ caller no-ops)."""
    if root is None:
        root = project_root()
    conf_path = root / ".claude" / "hooks" / "task-management.conf"
    if not conf_path.exists():
        return None
    data: dict[str, str] = {}
    try:
        for line in conf_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            # strip inline comment + optional quotes
            val = val.split("#", 1)[0].strip().strip('"').strip("'")
            data[key.strip()] = val
    except OSError:
        return None
    return data


def enabled(conf: dict | None, key: str) -> bool:
    """True only when conf is present and conf[key] is a truthy flag."""
    if not conf:
        return False
    return conf.get(key, "0").strip().lower() in ("1", "true", "yes", "on")


def done_file(conf: dict | None) -> str:
    return (conf or {}).get("DONE_FILE", DEFAULT_DONE)


def backlog_file(conf: dict | None) -> str:
    return (conf or {}).get("BACKLOG_FILE", DEFAULT_BACKLOG)


def verify_command(conf: dict | None) -> str:
    return (conf or {}).get("VERIFY_COMMAND", DEFAULT_VERIFY)


def done_marker(conf: dict | None) -> str:
    return (conf or {}).get("DONE_MARKER", DEFAULT_DONE_MARKER)


def pending_marker(conf: dict | None) -> str:
    return (conf or {}).get("PENDING_MARKER", DEFAULT_PENDING_MARKER)


def track_nudge_message(conf: dict | None) -> str | None:
    """Optional override of the pre-work nudge text; None → engine default."""
    val = (conf or {}).get("TRACK_NUDGE_MESSAGE", "").strip()
    return val or None


def allow_unrecorded_delete_reasons(conf: dict | None) -> set[str]:
    """Reason tags (lowercased) that skip the doc-recorded check on deletion."""
    raw = (conf or {}).get("ALLOW_UNRECORDED_DELETE_REASONS", "")
    return {t.strip().lower() for t in raw.split(",") if t.strip()}
