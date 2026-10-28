#!/usr/bin/env python3
"""UserPromptSubmit hook (config-driven, shipped by task-management-manager): a
gentle, non-blocking nudge to track work as tasks.

We can't read the in-session (live) task list from a hook, so this doesn't try
to detect "zero tasks" precisely. Instead it emits a short reminder of the
convention as additional context on each user turn, EXCEPT when the prompt is
clearly conversational/planning.

No-op unless the repo's .claude/hooks/task-management.conf exists and
ENABLE_TRACK_NUDGE is truthy. The reminder text can be overridden via
TRACK_NUDGE_MESSAGE in the conf.

Contract (unchanged): stdin JSON with `prompt`; stdout on exit 0 is added to the
model's context; NEVER blocks (always exit 0).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _taskconf  # noqa: E402

# Substrings that suggest the user is asking/thinking, not requesting work that
# should be tracked. Conservative: when unsure, we still nudge (nudging is cheap).
SKIP_HINTS = re.compile(
    r"\b(plan|what|why|how|explain|show|tell me|is it|does|can you explain|"
    r"thoughts?|question)\b",
    re.IGNORECASE,
)

DEFAULT_REMINDER = (
    "[track-tasks] Reminder: track each feature you implement and each question "
    "you investigate as a task (TaskCreate/TaskUpdate). If you're starting work "
    "and have no active task for it, create one first. See CLAUDE.md → "
    "\"Track your work\". (This is an automated nudge, not a user instruction.)"
)


def main() -> int:
    conf = _taskconf.load_conf()
    if not _taskconf.enabled(conf, "ENABLE_TRACK_NUDGE"):
        try:
            sys.stdin.read()
        except Exception:
            pass
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # never break the turn

    prompt = str(payload.get("prompt", ""))

    # Very short or clearly interrogative prompts: stay silent.
    if len(prompt.strip()) < 12:
        return 0
    if prompt.strip().endswith("?") and SKIP_HINTS.search(prompt):
        return 0

    print(_taskconf.track_nudge_message(conf) or DEFAULT_REMINDER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
