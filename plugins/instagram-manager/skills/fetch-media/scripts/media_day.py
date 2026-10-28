#!/usr/bin/env python3
"""Thumbnail runs at the set pace, one after another: 1 hour on, 1 hour off, 9am to 9pm local.

Starts fetch_media.py for each run with the arguments given here (e.g. --all --limit 150
--one-request). fetch_media.py keeps every rule itself (the hour, the gaps, the day cap, the night,
the pauses after a stop); this only waits until it may start again, and starts it.

  - A refused start (exit 5: run_gap, day_cap or night) waits until its may_start.
  - A pause after a stop (exit 4) waits until the pause ends; fetch_media.py then tries one test post.
  - It ends on a stop (exit 1), on any other exit, or once a run finds nothing left to fetch.

Logs go to the same .cache/logs/fetch-media.log, as ev=day_* lines; a day_wait line every 10
minutes while it waits. Usage:
  media_day.py --all --limit 150 --one-request
"""
import datetime as dt
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, os.pardir, "shared", "scripts"))
from home import cache  # noqa: E402
from log import log, log_to  # noqa: E402

FETCH = os.path.join(HERE, "fetch_media.py")
HEARTBEAT = 600       # s between day_wait lines
SETTLE = 60           # s past may_start before starting, so the start is not refused by a second


def child_lines(path, pid):
    """The log lines the run with this pid wrote."""
    mark = f" pid={pid} "
    try:
        with open(path) as fh:
            return [line for line in fh if mark in line]
    except OSError:
        return []


def field(line, key):
    m = re.search(rf"\b{key}=(\S+)", line or "")
    return m.group(1) if m else None


def wait_until(until, why):
    while True:
        left = (until - dt.datetime.now(dt.timezone.utc)).total_seconds()
        if left <= 0:
            return
        log("day_wait", why=why, until=until.strftime("%Y-%m-%dT%H:%M:%SZ"), minutes_left=round(left / 60))
        time.sleep(min(left, HEARTBEAT))


def parse(stamp):
    return dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    log_path = cache("logs", "fetch-media.log")
    log_to(log_path)
    log("day_start", args="_".join(a.lstrip("-") for a in args) or "none")
    runs = 0
    while True:
        log("day_run_before", run=runs + 1)
        child = subprocess.Popen([sys.executable, FETCH, *args])
        rc = child.wait()
        lines = child_lines(log_path, child.pid)
        log("day_run_after", run=runs + 1, rc=rc, child=child.pid)
        if rc == 5:
            refused = next((ln for ln in reversed(lines) if "ev=refused" in ln), "")
            may = field(refused, "may_start")
            if not may:
                log("day_end", reason="refused_without_time")
                return 5
            wait_until(parse(may) + dt.timedelta(seconds=SETTLE), field(refused, "reason") or "refused")
            continue
        if rc == 4:
            refused = next((ln for ln in reversed(lines) if "ev=refused" in ln), "")
            until = field(refused, "until")
            if not until:
                log("day_end", reason="paused_without_time")
                return 4
            wait_until(parse(until) + dt.timedelta(seconds=SETTLE), "paused")
            continue
        if rc != 0:
            log("day_end", reason="stopped" if rc == 1 else f"exit_{rc}", runs=runs)
            return rc
        runs += 1
        end = next((ln for ln in reversed(lines) if "ev=run_end" in ln), "")
        if field(end, "ok") == "0" and field(end, "bad") == "0":
            log("day_end", reason="nothing_left", runs=runs)
            return 0


if __name__ == "__main__":
    sys.exit(main())
