#!/usr/bin/env python3
"""Stop hook (config-driven, shipped by task-management-manager): non-blocking
reminder to keep the task files tidy.

Fires when Claude finishes a turn. It CANNOT see the live in-session task list,
so it reasons from the task files and nudges when something looks off:
  - an open `- [ ]` item sitting in the done file, or a closed `- [x]` in backlog
  - a PENDING_MARKER left in the done file (closed task whose SHA was never backfilled)
  - open backlog items still outstanding (surfaced only alongside a real issue)

No-op unless the repo's .claude/hooks/task-management.conf exists and
ENABLE_TASK_SYNC is truthy. Task-file paths / markers / verify-command come from
the conf. ALWAYS exits 0 — advises via stderr, never blocks.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _taskconf  # noqa: E402

OPEN_RE = re.compile(r"^\s*-\s*\[\s\]\s")
DONE_RE = re.compile(r"^\s*-\s*\[[xX]\]\s")


def read_lines(p: Path):
    return p.read_text(encoding="utf-8", errors="ignore").splitlines() if p.exists() else []


def main() -> int:
    # Consume stdin (Stop payload) but we don't need anything from it.
    try:
        sys.stdin.read()
    except Exception:
        pass

    conf = _taskconf.load_conf()
    if not _taskconf.enabled(conf, "ENABLE_TASK_SYNC"):
        return 0

    root = _taskconf.project_root()
    done = _taskconf.done_file(conf)
    backlog = _taskconf.backlog_file(conf)
    pending = _taskconf.pending_marker(conf)
    done_marker = _taskconf.done_marker(conf)
    verify = _taskconf.verify_command(conf)

    done_lines = read_lines(root / done)
    backlog_lines = read_lines(root / backlog)

    problems = []

    for i, ln in enumerate(done_lines, 1):
        if OPEN_RE.match(ln):
            problems.append(f"{done}:{i} has an OPEN task — move it to {backlog}.")
        elif DONE_RE.match(ln) and pending in ln:
            problems.append(f"{done}:{i} is closed but still {pending} — backfill the commit SHA.")
    for i, ln in enumerate(backlog_lines, 1):
        if DONE_RE.match(ln):
            problems.append(f"{backlog}:{i} has a CLOSED task — move it to {done} with {done_marker}(...) #git:<sha>.")

    if not problems:
        return 0  # silent when tidy — no nagging

    open_count = sum(1 for ln in backlog_lines if OPEN_RE.match(ln))
    print("Task-file reminder (advisory, not blocking):", file=sys.stderr)
    for p in problems:
        print("  • " + p, file=sys.stderr)
    if open_count:
        print(f"  • ({open_count} open task(s) still in {backlog}.)", file=sys.stderr)
    print(f"  Run `{verify}` to verify after fixing.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
