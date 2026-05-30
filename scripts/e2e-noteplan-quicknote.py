#!/usr/bin/env python3
"""
End-to-end tests for oeid-noteplan-quicknote via x-callback-url.

Each test fires DataStore.invokePluginCommandByName through NotePlan's
x-callback-url scheme using the hidden `createNote` command, waits for
the file to appear on disk, asserts the filename and location, then
cleans up.

Requirements: NotePlan must be running with the plugin installed.
"""

import json
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

NOTEPLAN_ROOT = Path.home() / "Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
NOTES_ROOT = NOTEPLAN_ROOT / "Notes"
PLUGIN_ID = "oeid.noteplan-quicknote"
COMMAND = "Create Note (API)"
WAIT_SECS = 4
TIMEOUT_SECS = 12

GREEN = "\033[0;32m"
RED   = "\033[0;31m"
YELLOW = "\033[0;33m"
NC    = "\033[0m"


def fire(params: dict) -> None:
    payload = json.dumps(params)
    qs = urllib.parse.urlencode({
        "pluginName": PLUGIN_ID,
        "command": COMMAND,
        "arg0": payload,
    })
    url = f"noteplan://x-callback-url/runPlugin?{qs}"
    subprocess.run(["open", url], check=True)


def wait_for_file(path: Path, timeout: int = TIMEOUT_SECS) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            return True
        time.sleep(0.5)
    return False


def run_test(label: str, params: dict, expected_path: Path) -> bool:
    print(f"  {label} ... ", end="", flush=True)
    # Clean up any leftover from a previous run
    if expected_path.exists():
        expected_path.unlink()

    fire(params)
    found = wait_for_file(expected_path)

    if found:
        print(f"{GREEN}✓{NC}")
        expected_path.unlink()  # clean up
        return True
    else:
        print(f"{RED}✗  not found: {expected_path.relative_to(NOTES_ROOT)}{NC}")
        return False


def main():
    # Verify NotePlan is running
    result = subprocess.run(["pgrep", "-x", "NotePlan"], capture_output=True)
    if result.returncode != 0:
        print(f"{RED}✗ NotePlan is not running. Start it first.{NC}")
        sys.exit(1)

    from datetime import date, timedelta
    today = date.today()
    ymd = today.strftime("%y%m%d")
    yesterday = (today - timedelta(days=1)).strftime("%y%m%d")

    tests = [
        (
            "work plan",
            {"domain": "work", "type": "plan", "title": "e2e Test Plan", "workstream": "🎯 Impact", "status": "🔮 Future"},
            NOTES_ROOT / "🏢 ServiceNow/📆 Plans/🎯 Impact" / f"🏢{ymd}🎯 e2e Test Plan.md",
        ),
        (
            "personal plan",
            {"domain": "personal", "type": "plan", "title": "e2e Test Plan", "workstream": "🌱 Growth", "status": "🔮 Future"},
            NOTES_ROOT / "🏡 Personal/🏡📆 Plans/Present/🌱 Growth" / f"🏡{ymd}🌱 e2e Test Plan.md",
        ),
        (
            "NaqshCoffee plan",
            {"domain": "coffee", "type": "plan", "title": "e2e Test Plan", "workstream": "🎨 Design", "status": "🔮 Future"},
            NOTES_ROOT / "☕️ NaqshCoffee/📆 Plans" / f"☕️{ymd}🎨 e2e Test Plan.md",
        ),
        (
            "EarlBear plan",
            {"domain": "earlbear", "type": "plan", "title": "e2e Test Plan", "workstream": "👨🏻‍💼 Strategy", "status": "🔮 Future"},
            NOTES_ROOT / "👥 EarlBear/📆 Plans" / f"👥{ymd}👨🏻‍💼 e2e Test Plan.md",
        ),
        (
            "work meeting (today)",
            {"domain": "work", "type": "meeting", "title": "e2e Test Meeting", "daysAgo": 0},
            NOTES_ROOT / "🏢 ServiceNow/👤 Meetings" / f"🏢 {ymd} e2e Test Meeting.md",
        ),
        (
            "work meeting (1 day ago)",
            {"domain": "work", "type": "meeting", "title": "e2e Backdated Meeting", "daysAgo": 1},
            NOTES_ROOT / "🏢 ServiceNow/👤 Meetings" / f"🏢 {yesterday} e2e Backdated Meeting.md",
        ),
        (
            "personal meeting",
            {"domain": "personal", "type": "meeting", "title": "e2e Test Meeting", "daysAgo": 0},
            NOTES_ROOT / "🏡 Personal/🏡👥 Meetings" / f"🏡 {ymd} e2e Test Meeting.md",
        ),
        (
            "EarlBear meeting (👥 Meetings, not 👥👤)",
            {"domain": "earlbear", "type": "meeting", "title": "e2e Test Meeting", "daysAgo": 0},
            NOTES_ROOT / "👥 EarlBear/👥 Meetings" / f"👥 {ymd} e2e Test Meeting.md",
        ),
        (
            "work note",
            {"domain": "work", "type": "note", "title": "e2e Test Note"},
            NOTES_ROOT / "🏢 ServiceNow/📝 Notes" / "🏢📝 e2e Test Note.md",
        ),
        (
            "personal note",
            {"domain": "personal", "type": "note", "title": "e2e Test Note"},
            NOTES_ROOT / "🏡 Personal/🏡📝 Notes" / "🏡📝 e2e Test Note.md",
        ),
    ]

    print(f"{YELLOW}Running {len(tests)} e2e tests (timeout {TIMEOUT_SECS}s each)...{NC}")
    passed = sum(run_test(label, params, path) for label, params, path in tests)
    failed = len(tests) - passed

    print()
    if failed == 0:
        print(f"{GREEN}✓ {passed}/{len(tests)} passed{NC}")
    else:
        print(f"{RED}✗ {failed}/{len(tests)} failed  ({passed} passed){NC}")
        sys.exit(1)


if __name__ == "__main__":
    main()
