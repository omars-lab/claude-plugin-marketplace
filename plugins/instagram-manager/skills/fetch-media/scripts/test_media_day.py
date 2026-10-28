#!/usr/bin/env python3
"""Offline tests for media_day.py: a stand-in fetch_media.py writes log lines and exits."""
import datetime as dt
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import media_day  # noqa: E402

# Each start of the stand-in takes its next exit code and log line from a file of "rc|line".
FAKE = """import os, sys, datetime as dt
home = os.environ["INSTAGRAM_HOME"]
plan = os.path.join(home, "plan.txt")
steps = open(plan).read().splitlines()
rc, line = steps[0].split("|", 1)
open(plan, "w").write("\\n".join(steps[1:]))
t = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
with open(os.path.join(home, ".cache", "logs", "fetch-media.log"), "a") as fh:
    fh.write(f"{t} pid={os.getpid()} {line}\\n")
sys.exit(int(rc))
"""


class Day(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".cache", "logs"))
        self.fake = os.path.join(self.root, "fake_fetch.py")
        with open(self.fake, "w") as fh:
            fh.write(FAKE)
        self.waits = []
        for p in [mock.patch.dict(os.environ, {"INSTAGRAM_HOME": self.root}),
                  mock.patch.object(media_day, "FETCH", self.fake),
                  mock.patch.object(media_day, "wait_until", lambda until, why: self.waits.append(why))]:
            p.start()
            self.addCleanup(p.stop)

    def plan(self, *steps):
        with open(os.path.join(self.root, "plan.txt"), "w") as fh:
            fh.write("\n".join(steps))

    def test_waits_after_a_refusal_and_ends_when_nothing_is_left(self):
        soon = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.plan("0|ev=run_end ok=40 bad=1 todo=41", f"5|ev=refused reason=run_gap may_start={soon}",
                  "0|ev=run_end ok=0 bad=0 todo=0")
        self.assertEqual(media_day.main([]), 0)
        self.assertEqual(self.waits, ["run_gap"])

    def test_a_run_where_every_post_timed_out_is_not_the_end(self):
        self.plan("0|ev=run_end ok=0 bad=0 todo=30", "0|ev=run_end ok=0 bad=0 todo=0")
        self.assertEqual(media_day.main([]), 0)
        self.assertFalse(open(os.path.join(self.root, "plan.txt")).read())   # both runs started

    def test_a_stop_ends_the_day(self):
        self.plan("1|ev=run_end ok=3 bad=0 todo=9 stopped=yes", "0|ev=run_end ok=9 bad=0 todo=9")
        self.assertEqual(media_day.main([]), 1)
        self.assertEqual(self.waits, [])

    def test_a_pause_waits_until_it_ends(self):
        until = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.plan(f"4|ev=refused reason=cooldown until={until}", "0|ev=run_end ok=0 bad=0 todo=0")
        self.assertEqual(media_day.main([]), 0)
        self.assertEqual(self.waits, ["paused"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
