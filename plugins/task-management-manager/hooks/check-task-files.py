#!/usr/bin/env python3
"""Guard the task-file invariant (config-driven, shipped by task-management-manager):
  - <DONE_FILE>    contains ONLY closed tasks  (`- [x] …`)
  - <BACKLOG_FILE> contains ONLY open tasks    (`- [ ] …`)

Task-file paths come from the repo's .claude/hooks/task-management.conf
(DONE_FILE / BACKLOG_FILE, defaulting to docs/tasks/{done,backlog}.md). The hook
is a no-op unless the conf exists and ENABLE_CHECK_FILES is truthy.

Two modes (unchanged from the original loose hook):
  1. Hook mode (stdin = PostToolUse JSON): if the tool touched a task file,
     re-check both files; on violation exit 2 with an explanation so Claude
     fixes it. Non-task-file edits are ignored (exit 0).
  2. CLI mode (no stdin / `--check`): check both files, print a report,
     exit 0 clean / 1 on violation. Used by `make tasks-check`.

Only lines beginning with the task-item bullet `- [x]` / `- [ ]` are treated as
tasks; header prose that merely mentions `[x]` is ignored.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _taskconf  # noqa: E402

OPEN_RE = re.compile(r"^\s*-\s*\[\s\]\s")     # - [ ]
DONE_RE = re.compile(r"^\s*-\s*\[[xX]\]\s")   # - [x]


def violations(root: Path, done: str, backlog: str):
    errs = []
    dpath, bpath = root / done, root / backlog

    if dpath.exists():
        for i, line in enumerate(dpath.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if OPEN_RE.match(line):
                errs.append(f"{done}:{i}: OPEN task in done.md → move to {backlog}: {line.strip()}")
    if bpath.exists():
        for i, line in enumerate(bpath.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if DONE_RE.match(line):
                errs.append(f"{backlog}:{i}: DONE task in backlog.md → move to {done}: {line.strip()}")
    return errs


def touched_task_file(payload, done: str, backlog: str) -> bool:
    ti = payload.get("tool_input", {}) or {}
    blob = json.dumps(ti)
    return (done in blob) or (backlog in blob)


def main() -> int:
    root = _taskconf.project_root()
    conf = _taskconf.load_conf(root)

    cli_flag = "--check" in sys.argv[1:]
    # Config gate: no-op unless enabled (CLI --check always runs, for `make`).
    if not cli_flag and not _taskconf.enabled(conf, "ENABLE_CHECK_FILES"):
        # still drain stdin so the hook doesn't leave a broken pipe
        try:
            sys.stdin.read()
        except Exception:
            pass
        return 0

    done = _taskconf.done_file(conf)
    backlog = _taskconf.backlog_file(conf)

    # CLI mode is explicit (`--check`) so we NEVER block on stdin.read() under
    # `make`, where stdin is neither a tty nor closed. Hook mode is the default.
    raw = "" if cli_flag else sys.stdin.read()

    hook_mode = False
    if raw.strip():
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict) and "tool_name" in payload:
                hook_mode = True
                if not touched_task_file(payload, done, backlog):
                    return 0  # unrelated edit — nothing to check
        except Exception:
            pass  # fall through to CLI mode

    errs = violations(root, done, backlog)
    if not errs:
        if not hook_mode:
            print(f"task files OK — {done} has only closed tasks, {backlog} only open tasks.")
        return 0

    header = "Task-file invariant violated:" if not hook_mode else \
        "BLOCKED: task-file invariant violated after this edit —"
    print(header, file=sys.stderr)
    for e in errs:
        print("  " + e, file=sys.stderr)
    dm = _taskconf.done_marker(conf)
    print(f"Fix: closed tasks (`- [x] … {dm}(...) #git:...`) belong in {done}; "
          f"open tasks (`- [ ] …`) belong in {backlog}.", file=sys.stderr)
    return 2 if hook_mode else 1


if __name__ == "__main__":
    sys.exit(main())
