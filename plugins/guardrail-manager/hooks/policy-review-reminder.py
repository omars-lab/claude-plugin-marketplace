#!/usr/bin/env python3
"""Stop hook: remind about a review step the session's own transcript shows was
skipped.

Generalises the pattern "if this session touched X and the X-review never ran,
say so before the turn ends". Each repo declares its policies in
`.claude/hooks/policy-review.conf` (INI, one section per policy):

    [privacy]
    SIGNAL_REGEX = premium:\\s*true|career|resume
    DONE_REGEX   = privacy.review
    MESSAGE      = This session touched personal content.
        Run the privacy-review skill before publishing.
    # optional
    ENABLED      = 1          # default on
    IGNORE_CASE  = 1          # default on
    CHANNEL      = stderr     # stderr (default) | system | block
    MESSAGE_FILE = docs/policies/privacy-reminder.md   # instead of MESSAGE

A policy fires when SIGNAL_REGEX matches the transcript and DONE_REGEX does
not. Channels: `stderr` prints the reminder for the person; `system` emits a
systemMessage; `block` returns decision=block so Claude itself has to act on
the reminder (honours stop_hook_active, so it fires once per stop). Always exits
0 and never raises past main(); an invalid regex prints one note and skips.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _conf  # noqa: E402

CONF_NAME = "policy-review.conf"


def _regex(value: str, ignore_case: bool):
    return re.compile(value, re.IGNORECASE if ignore_case else 0)


def evaluate(parser, transcript: str, root: Path) -> tuple[list[str], list[str], list[str], list[str]]:
    """Returns (stderr_msgs, system_msgs, block_msgs, notes)."""
    stderr_msgs, system_msgs, block_msgs, notes = [], [], [], []
    for section in parser.sections():
        get = lambda key, default="": parser.get(section, key, fallback=default)  # noqa: E731
        if not _conf.truthy(get("ENABLED", "1"), default=True):
            continue
        ignore_case = _conf.truthy(get("IGNORE_CASE", "1"), default=True)
        signal, done = get("SIGNAL_REGEX"), get("DONE_REGEX")
        if not signal:
            notes.append(f"[policy-review:{section}] SIGNAL_REGEX missing; skipped")
            continue
        try:
            if not _regex(signal, ignore_case).search(transcript):
                continue
            if done and _regex(done, ignore_case).search(transcript):
                continue
        except re.error as exc:
            notes.append(f"[policy-review:{section}] invalid regex ({exc}); skipped")
            continue
        message = get("MESSAGE").strip()
        message_file = get("MESSAGE_FILE").strip()
        if message_file:
            try:
                message = (root / message_file).read_text(encoding="utf-8").strip()
            except OSError:
                notes.append(f"[policy-review:{section}] MESSAGE_FILE {message_file} unreadable; skipped")
                continue
        if not message:
            message = f"policy '{section}' was triggered this session and its review step did not run."
        text = f"[policy-review:{section}] {message}"
        channel = get("CHANNEL", "stderr").strip().lower()
        if channel == "block":
            block_msgs.append(text)
        elif channel == "system":
            system_msgs.append(text)
        else:
            stderr_msgs.append(text)
    return stderr_msgs, system_msgs, block_msgs, notes


def main() -> int:
    payload = _conf.read_stdin_json()
    root = _conf.project_root()
    parser = _conf.load_ini(_conf.repo_conf_path(CONF_NAME, root))
    if parser is None:
        return 0
    transcript_path = payload.get("transcript_path") or ""
    if not transcript_path or not os.path.isfile(transcript_path):
        return 0
    try:
        transcript = Path(transcript_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0
    stderr_msgs, system_msgs, block_msgs, notes = evaluate(parser, transcript, root)
    for note in notes:
        print(note, file=sys.stderr)
    for msg in stderr_msgs:
        print(msg, file=sys.stderr)
    out: dict = {}
    if system_msgs:
        out["systemMessage"] = "\n\n".join(system_msgs)
    if block_msgs and not payload.get("stop_hook_active"):
        out["decision"] = "block"
        out["reason"] = "\n\n".join(block_msgs)
    elif block_msgs:
        # Already re-entered once because of us; surface without blocking again.
        print("\n\n".join(block_msgs), file=sys.stderr)
    if out:
        print(json.dumps(out))
    return 0


def selftest() -> int:
    import tempfile

    sys.path.insert(0, str(HERE))
    from _selftest import SelfTest

    t = SelfTest(__file__)
    tmp = Path(tempfile.mkdtemp(prefix="guardrail-policy-"))
    root = tmp / "repo"
    (root / ".claude" / "hooks").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "docs" / "reminder.md").write_text("Reminder text from a file.\n", encoding="utf-8")
    conf = root / ".claude" / "hooks" / CONF_NAME

    def transcript(text: str) -> str:
        f = tempfile.NamedTemporaryFile("w", dir=tmp, suffix=".jsonl", delete=False)
        f.write(text)
        f.close()
        return f.name

    def run(text: str, extra: dict | None = None, project=root):
        payload = {"transcript_path": transcript(text), "hook_event_name": "Stop"}
        payload.update(extra or {})
        return t.run(payload, env={"CLAUDE_PROJECT_DIR": str(project)})

    conf.write_text(
        "[privacy]\n"
        "SIGNAL_REGEX = premium:\\s*true|career-development|job.?search\n"
        "DONE_REGEX = privacy.review\n"
        "MESSAGE = This session touched sensitive content.\n"
        "    Run the privacy-review skill before publishing.\n",
        encoding="utf-8",
    )
    t.assert_flags(run("editing docs/career-development/foo.mdx with premium: true"), "[policy-review:privacy]", "flags signal with no review")
    t.assert_flags(run("editing docs/career-development/foo.mdx with premium: true"), "Run the privacy-review skill", "multi-line MESSAGE is carried")
    t.assert_quiet(run("refactored the diagram component and fixed a selector"), "ignores unrelated session")
    t.assert_quiet(run("career-development premium: true; ran privacy-review and kept it off"), "ignores when review already ran")
    t.assert_quiet(run("premium: true", project=tmp / "nowhere"), "quiet when conf absent")

    conf.write_text(
        "[privacy]\nSIGNAL_REGEX = premium:\\s*true\nDONE_REGEX = privacy.review\nMESSAGE = privacy msg\n"
        "[boundary]\nSIGNAL_REGEX = ledger\\.tsv\nDONE_REGEX = boundary-check\nMESSAGE_FILE = docs/reminder.md\n"
        "[off]\nENABLED = 0\nSIGNAL_REGEX = .\nMESSAGE = never\n",
        encoding="utf-8",
    )
    rc, out, err = run("premium: true and wrote ledger.tsv")
    t.check(rc == 0 and "[policy-review:privacy]" in err and "[policy-review:boundary]" in err, "two policies fire independently", err)
    t.check("Reminder text from a file." in err, "MESSAGE_FILE is read relative to the repo", err)
    t.check("never" not in err, "ENABLED=0 section is skipped", err)
    t.assert_flags(run("wrote ledger.tsv"), "[policy-review:boundary]", "second policy fires alone")
    rc, out, err = run("wrote ledger.tsv then ran make claude-boundary-check")
    t.check(rc == 0 and "boundary" not in err, "DONE_REGEX silences a policy", err)

    conf.write_text("[bad]\nSIGNAL_REGEX = (unclosed\nMESSAGE = x\n", encoding="utf-8")
    rc, out, err = run("anything")
    t.check(rc == 0 and "invalid regex" in err and "[policy-review:bad] x" not in err, "invalid regex is noted, never crashes", err)

    conf.write_text("[b]\nSIGNAL_REGEX = ship\nMESSAGE = review first\nCHANNEL = block\n", encoding="utf-8")
    rc, out, err = run("about to ship")
    try:
        data = json.loads(out)
    except ValueError:
        data = {}
    t.check(rc == 0 and data.get("decision") == "block" and "review first" in data.get("reason", ""), "CHANNEL=block emits a block decision", out)
    rc, out, err = run("about to ship", {"stop_hook_active": True})
    t.check(rc == 0 and out.strip() == "" and "review first" in err, "block honours stop_hook_active (no loop)", out + err)

    conf.write_text("[s]\nSIGNAL_REGEX = ship\nMESSAGE = sys msg\nCHANNEL = system\n", encoding="utf-8")
    rc, out, err = run("about to ship")
    t.check(rc == 0 and '"systemMessage"' in out and "sys msg" in out, "CHANNEL=system emits systemMessage", out)
    return t.report()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    try:
        sys.exit(main())
    except Exception as exc:  # never break a stop
        print(f"[policy-review] hook error ignored: {exc}", file=sys.stderr)
        sys.exit(0)
