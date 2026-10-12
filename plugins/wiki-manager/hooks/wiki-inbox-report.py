#!/usr/bin/env python3
"""SessionStart hook: report what's ready to ingest into the wiki.

Report-only. This hook NEVER mutates a note. It prints a short status of the
Unorganized inbox to stdout, which Claude Code adds to the conversation as
context, then suggests running `/wiki-manager:manage-wiki`.

Safe everywhere:
- No-op (exit 0, no output) unless the cwd is a NotePlan vault — a `Notes/` AND
  `Calendar/` directory — with a `Notes/🗑️ Unorganized/` inbox. So it stays
  silent in every other repo where wiki-manager happens to be enabled.
- Rate-limited via a marker in $TMPDIR keyed by session id: it re-fires only when
  the inbox state changes or REMIND_EVERY_MIN has passed, so it won't nag on
  every resume.
- Opt out per repo with `.claude/hooks/wiki-inbox.conf`:
      ENABLED=0                 # turn the nudge off for this repo
      REMIND_EVERY_MIN=180      # minimum minutes between identical nudges

Standard library only. Always exits 0.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

INBOX_REL = "Notes/🗑️ Unorganized"
WIKI_REL = "Notes/📚 Wiki"
LOG_REL = "Notes/📚 Wiki/log.md"
CONF_REL = ".claude/hooks/wiki-inbox.conf"
DEFAULT_REMIND_MIN = 180.0

# Heuristic secret markers — a mechanical SAFETY net that flags files for the
# human to review, NOT an intent classifier. The skill does the real reading.
SECRET_HINTS = ("password", "passwd", "api key", "api_key", "apikey",
                "secret", "token", "pas is", "pwd is", "private key")


def _load_conf(vault: Path) -> dict:
    conf = {}
    path = vault / CONF_REL
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            conf[k.strip()] = v.strip()
    except OSError:
        pass
    return conf


def _find_vault() -> Path | None:
    cwd = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    if (cwd / "Notes").is_dir() and (cwd / "Calendar").is_dir() and (cwd / INBOX_REL).is_dir():
        return cwd
    return None


def _inbox_md(vault: Path) -> list[Path]:
    return [p for p in (vault / INBOX_REL).rglob("*.md") if p.is_file()]


def _newest_log_mtime(vault: Path) -> float:
    log = vault / LOG_REL
    try:
        return log.stat().st_mtime
    except OSError:
        return 0.0


def _scan(vault: Path) -> dict:
    files = _inbox_md(vault)
    log_mtime = _newest_log_mtime(vault)
    wiki_exists = (vault / WIKI_REL).is_dir()
    new_since = []
    secret_flags = []
    for p in files:
        try:
            mt = p.stat().st_mtime
        except OSError:
            continue
        if mt > log_mtime:
            new_since.append(p)
        # cheap secret sniff on small files only
        try:
            if p.stat().st_size <= 200_000:
                low = p.read_text(encoding="utf-8", errors="ignore").lower()
                if any(h in low for h in SECRET_HINTS):
                    secret_flags.append(p)
        except OSError:
            continue
    return {
        "total": len(files),
        "new": len(new_since),
        "secrets": len(secret_flags),
        "wiki_exists": wiki_exists,
        "newest_mtime": max((p.stat().st_mtime for p in files), default=0.0),
    }


def _marker(session_id: str) -> Path:
    base = Path(os.environ.get("TMPDIR") or "/tmp")
    return base / f"wiki-inbox-{session_id or 'unknown'}"


def _signature(state: dict) -> str:
    return f"{state['total']}:{state['new']}:{state['secrets']}:{int(state['newest_mtime'])}:{state['wiki_exists']}"


def _should_fire(marker: Path, sig: str, remind_min: float, now: float) -> bool:
    try:
        last = marker.read_text(encoding="utf-8").strip()
        age_min = (now - marker.stat().st_mtime) / 60.0
    except OSError:
        return True
    return sig != last or age_min >= remind_min


def _record(marker: Path, sig: str) -> None:
    try:
        marker.write_text(sig, encoding="utf-8")
    except OSError:
        pass


def _report(state: dict) -> str:
    lines = [f"🗂️  Wiki inbox — Notes/🗑️ Unorganized/: {state['total']} notes"]
    if not state["wiki_exists"]:
        lines.append("📚  No wiki yet — run /wiki-manager:manage-wiki to scaffold Notes/📚 Wiki/ and index.")
        if state["secrets"]:
            lines.append(f"⚠️  {state['secrets']} file(s) may contain a secret — review before indexing.")
        return "\n".join(lines)
    if state["new"]:
        lines.append(f"🔎  {state['new']} new/changed since last index.")
    else:
        lines.append("✓  Nothing new since last index.")
    if state["secrets"]:
        lines.append(f"⚠️  {state['secrets']} file(s) may contain a secret — review before indexing.")
    if state["new"] or state["secrets"]:
        lines.append("→  Run /wiki-manager:manage-wiki to ingest.")
    return "\n".join(lines)


def main() -> int:
    # SessionStart passes a JSON payload on stdin; session_id keys the rate-limit.
    session_id = ""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        session_id = str(payload.get("session_id", ""))
    except (json.JSONDecodeError, ValueError):
        pass

    vault = _find_vault()
    if vault is None:
        return 0

    conf = _load_conf(vault)
    if conf.get("ENABLED", "1") == "0":
        return 0
    try:
        remind_min = float(conf.get("REMIND_EVERY_MIN", DEFAULT_REMIND_MIN))
    except ValueError:
        remind_min = DEFAULT_REMIND_MIN

    state = _scan(vault)
    # Nothing worth saying if the wiki exists and there's no new material / no flags.
    if state["wiki_exists"] and not state["new"] and not state["secrets"]:
        return 0

    marker = _marker(session_id)
    sig = _signature(state)
    now = time.time()
    if not _should_fire(marker, sig, remind_min, now):
        return 0
    _record(marker, sig)

    print(_report(state))
    return 0


def _selftest() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        vault = Path(d)
        (vault / "Calendar").mkdir()
        inbox = vault / INBOX_REL
        inbox.mkdir(parents=True)
        (inbox / "a.md").write_text("# A\nsome note\n", encoding="utf-8")
        (inbox / "b.md").write_text("# B\nIcloud pas is HUNTER2\n", encoding="utf-8")
        os.environ["CLAUDE_PROJECT_DIR"] = str(vault)
        st = _scan(vault)
        assert st["total"] == 2, st
        assert st["new"] == 2, st  # no log.md yet -> all new
        assert st["secrets"] == 1, st  # "pas is" hint
        assert not st["wiki_exists"], st
        rep = _report(st)
        assert "No wiki yet" in rep and "secret" in rep, rep
    print("wiki-inbox-report selftest: OK")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    raise SystemExit(main())
