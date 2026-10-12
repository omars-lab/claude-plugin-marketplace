"""Find other Claude Code sessions that are active in the same working tree.

Claude Code keeps one transcript per session under
`~/.claude/projects/<slug-of-cwd>/<session_id>.jsonl`. Sessions that share a
project directory share the checkout: uncommitted files, the current branch,
the index. That is where the wrong-branch commits and cross-session file
clobbers come from.

Detection rules:

  * project dir = dirname(transcript_path). It is not rebuilt from cwd because
    the slug is lossy.
  * only `*.jsonl` at depth 1 count; `<sid>/subagents/*.jsonl` are children of a
    session already counted.
  * the caller's own session_id is skipped, as is anything whose mtime is older
    than the activity window.
  * with include_subdirs, sibling dirs named `<slug>-*` are scanned too and a
    session there counts when its last recorded cwd sits under the caller's
    cwd. A git worktree has a different cwd and is correctly not flagged.

The last 64KB of each transcript is read for the most recent `cwd` and
`gitBranch` values so the scan stays cheap on large transcripts.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

TAIL_BYTES = 64 * 1024
_CWD_RE = re.compile(r'"cwd":"((?:[^"\\]|\\.)*)"')
_BRANCH_RE = re.compile(r'"gitBranch":"((?:[^"\\]|\\.)*)"')


def _tail(path: Path, nbytes: int = TAIL_BYTES) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > nbytes:
                fh.seek(size - nbytes)
            return fh.read().decode("utf-8", errors="ignore")
    except OSError:
        return ""


def _last(regex: re.Pattern, text: str) -> str | None:
    found = regex.findall(text)
    if not found:
        return None
    return found[-1].encode("utf-8").decode("unicode_escape", errors="ignore")


def _session_files(directory: Path):
    try:
        for entry in os.scandir(directory):
            if entry.is_file(follow_symlinks=False) and entry.name.endswith(".jsonl"):
                yield Path(entry.path)
    except OSError:
        return


def _describe(path: Path, now: float) -> dict:
    tail = _tail(path)
    try:
        age_min = max(0.0, (now - path.stat().st_mtime) / 60.0)
    except OSError:
        age_min = 0.0
    return {
        "sid": path.stem,
        "branch": _last(_BRANCH_RE, tail) or "unknown",
        "cwd": _last(_CWD_RE, tail),
        "age_min": age_min,
        "path": str(path),
    }


def other_active_sessions(
    transcript_path: str,
    session_id: str,
    window_min: float,
    cwd: str,
    include_subdirs: bool = True,
    now: float | None = None,
) -> list[dict]:
    """Sessions other than `session_id` active within `window_min` minutes."""
    now = time.time() if now is None else now
    project_dir = Path(transcript_path).parent
    own_stem = Path(transcript_path).stem
    cutoff = now - window_min * 60.0
    found: list[dict] = []

    def _recent(path: Path) -> bool:
        try:
            return path.stat().st_mtime >= cutoff
        except OSError:
            return False

    for path in _session_files(project_dir):
        if path.stem in (session_id, own_stem):
            continue
        if not _recent(path):
            continue
        found.append(_describe(path, now))

    if include_subdirs and cwd:
        prefix = cwd.rstrip("/") + "/"
        parent = project_dir.parent
        slug = project_dir.name + "-"
        try:
            siblings = [Path(e.path) for e in os.scandir(parent) if e.is_dir(follow_symlinks=False) and e.name.startswith(slug)]
        except OSError:
            siblings = []
        for sib in siblings:
            for path in _session_files(sib):
                if path.stem in (session_id, own_stem) or not _recent(path):
                    continue
                info = _describe(path, now)
                if info["cwd"] and info["cwd"].startswith(prefix):
                    found.append(info)

    found.sort(key=lambda s: s["age_min"])
    return found


def format_sessions(sessions: list[dict]) -> str:
    return "\n".join(
        f"  - {s['sid'][:8]} on branch {s['branch']} ({int(round(s['age_min']))}m ago)" for s in sessions
    )
