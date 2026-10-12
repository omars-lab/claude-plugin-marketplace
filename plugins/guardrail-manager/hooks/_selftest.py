"""Tiny selftest harness shared by the guardrail-manager hooks.

Each hook accepts `--selftest` (checked before reading stdin, otherwise the
hook would hang waiting on a payload). The hook builds fixtures, runs itself as
a subprocess with a JSON payload, and asserts on exit code and output.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys


class SelfTest:
    def __init__(self, script: str):
        self.script = script
        self.passed = 0
        self.failed = 0

    def run(self, payload: dict, env: dict | None = None, cwd: str | None = None) -> tuple[int, str, str]:
        full_env = dict(os.environ)
        if env:
            full_env.update(env)
        proc = subprocess.run(
            [sys.executable, self.script],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=full_env,
            cwd=cwd,
            timeout=30,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def check(self, cond: bool, name: str, detail: str = "") -> None:
        if cond:
            self.passed += 1
            print(f"  ok   {name}")
        else:
            self.failed += 1
            print(f"  FAIL {name}" + (f"\n       {detail}" if detail else ""))

    def assert_flags(self, result: tuple[int, str, str], needle: str, name: str) -> None:
        rc, out, err = result
        combined = out + err
        self.check(rc == 0 and needle.lower() in combined.lower(), name, f"rc={rc} out={out!r} err={err!r}")

    def assert_quiet(self, result: tuple[int, str, str], name: str) -> None:
        rc, out, err = result
        self.check(rc == 0 and out.strip() == "" and err.strip() == "", name, f"rc={rc} out={out!r} err={err!r}")

    def report(self) -> int:
        total = self.passed + self.failed
        status = "PASS" if self.failed == 0 else "FAIL"
        print(f"{status}: {self.passed}/{total} checks passed ({os.path.basename(self.script)})")
        return 0 if self.failed == 0 else 1
