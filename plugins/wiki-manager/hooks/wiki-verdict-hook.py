#!/usr/bin/env python3
"""Stop hook: keep every wiki article's newcomer verdict fresh.

A wiki article's **verdict** (`@References/@Verdicts/<space>/<topic>/<question>.md`) is a
running report card written by the `review-as-newcomer` skill. It stores the `page_hash` of
the article it judged, so when the article changes the verdict is provably out of date.

This hook is advisory and mechanical — it never writes a note and never judges content. When
articles were edited this turn and their verdict is stale, it nudges once with the exact
command to re-review. Claude does the reading.

**Why a hash and not an mtime.** `wiki-concept-hook.py` guards its stale-map nudge with an
mtime comparison because the concept map has no record of what it was built from. A verdict
does: the stored `page_hash`. Once the verdict is rewritten for the new content the hash
matches and the nudge stops by construction — no clock, no touch-ordering, no re-fire. The
content-hash dedup TTL below only stops an *identical* nudge repeating while the same pages
stay unreviewed.

Safe everywhere: no-op unless the cwd is a NotePlan vault with a Notes/📚 Wiki/.
Opt out per repo with .claude/hooks/wiki-inbox.conf → VERDICT_NUDGE=0.
Standard library only. Always exits 0.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

HOOK_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(HOOK_DIR.parent / "bin"))
from check_verdicts import page_hash, verdict_path, frontmatter, fm_value  # noqa: E402

WIKI_REL = "Notes/📚 Wiki"
CONF_REL = ".claude/hooks/wiki-inbox.conf"
DEDUP_TTL_SECS = 3600.0
MAX_LISTED = 8

WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}


def _find_vault() -> Path | None:
    cwd = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    if (cwd / "Notes").is_dir() and (cwd / "Calendar").is_dir() and (cwd / WIKI_REL).is_dir():
        return cwd
    return None


def _conf(vault: Path) -> dict:
    conf = {}
    try:
        for line in (vault / CONF_REL).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                conf[k.strip()] = v.strip()
    except OSError:
        pass
    return conf


def _written_paths(transcript: Path) -> set[str]:
    """file_paths of Write/Edit/MultiEdit tool_use blocks in the transcript."""
    out: set[str] = set()

    def walk(obj):
        if isinstance(obj, dict):
            if obj.get("type") == "tool_use" and obj.get("name") in WRITE_TOOLS:
                fp = obj.get("input", {}).get("file_path", "")
                if fp:
                    out.add(fp)
                return
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for it in obj:
                walk(it)

    try:
        with transcript.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        walk(json.loads(line))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def stale_articles(vault: Path, written: set[str]) -> list[str]:
    """Of the articles written this turn, those whose verdict is missing or hash-stale."""
    wiki = vault / WIKI_REL
    stale: list[str] = []
    for p in sorted(written):
        if not p.endswith(".md") or WIKI_REL not in p or "@References" in p:
            continue
        art = Path(p)
        if not art.is_file():
            continue
        try:
            rel = art.relative_to(wiki)
        except ValueError:
            continue
        if len(rel.parts) < 2:
            continue  # hub / log / map at the wiki root
        text = art.read_text(encoding="utf-8", errors="replace")
        if fm_value(frontmatter(text), "type") != "wiki-faq":
            continue
        vp = verdict_path(art, wiki)
        if not vp.is_file():
            stale.append(art.stem)
            continue
        stored = fm_value(frontmatter(vp.read_text(encoding="utf-8", errors="replace")), "page_hash")
        if stored != page_hash(art):
            stale.append(art.stem)
    return stale


def _build_reason(vault: Path, written: set[str]) -> str | None:
    stale = stale_articles(vault, written)
    if not stale:
        return None
    shown = stale[:MAX_LISTED]
    more = len(stale) - len(shown)
    tail = f" (+{more} more)" if more > 0 else ""
    names = "; ".join(f"“{s}”" for s in shown)
    return (
        f"{len(stale)} wiki article(s) changed and their newcomer verdict is now stale: "
        f"{names}{tail}. Re-read each as a first-time reader and update its verdict "
        "(skill: review-as-newcomer). Check the whole wiki with: "
        "python3 \"${CLAUDE_PLUGIN_ROOT}/bin/check_verdicts.py\" --wiki \"Notes/📚 Wiki\""
    )


# ---------------------------------------------------------------------------
# dedup (content-hash TTL, matching wiki-concept-hook.py)
# ---------------------------------------------------------------------------
def _dedup_path() -> Path:
    return HOOK_DIR / "verdict-hook-triggers.jsonl"


def _recent_hashes(now: float) -> set[str]:
    seen: set[str] = set()
    try:
        with _dedup_path().open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("hash") and now - e.get("ts", 0) < DEDUP_TTL_SECS:
                    seen.add(e["hash"])
    except OSError:
        pass
    return seen


def _record_hash(h: str, now: float) -> None:
    try:
        with _dedup_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now, "hash": h}) + "\n")
    except OSError:
        pass


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        return 0
    transcript = payload.get("transcript_path", "")
    if not transcript or not os.path.isfile(transcript):
        return 0

    vault = _find_vault()
    if vault is None:
        return 0
    if _conf(vault).get("VERDICT_NUDGE", "1") == "0":
        return 0

    written = _written_paths(Path(transcript))
    if not written:
        return 0

    reason = _build_reason(vault, written)
    if not reason:
        return 0

    now = time.time()
    h = hashlib.md5(reason.encode("utf-8")).hexdigest()
    if h in _recent_hashes(now):
        return 0
    _record_hash(h, now)

    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------
def _selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        vault = Path(d) / "vault"
        wiki = vault / WIKI_REL
        topic = wiki / "📦 Past Work" / "Exp"
        topic.mkdir(parents=True)
        (vault / "Notes").mkdir(exist_ok=True)
        (vault / "Calendar").mkdir()
        (wiki / "log.md").write_text("# Log\n", encoding="utf-8")

        art = topic / "How do I run an A-B test?.md"
        art.write_text("---\ntitle: How do I run an A-B test?\ntype: wiki-faq\n---\n"
                       "# How do I run an A-B test?\nStratify first.\n", encoding="utf-8")
        other = vault / "Notes" / "🏡 Personal" / "diary.md"
        other.parent.mkdir(parents=True)
        other.write_text("# diary\n", encoding="utf-8")

        # no verdict yet -> stale
        r = _build_reason(vault, {str(art)})
        assert r is not None and "How do I run an A-B test?" in r, r
        assert "1 wiki article(s)" in r, r

        # a non-wiki note written this turn must never trigger the nudge
        assert _build_reason(vault, {str(other)}) is None

        # the wiki log/map at the wiki root is not an article
        assert _build_reason(vault, {str(wiki / "log.md")}) is None

        # write a matching verdict -> the nudge stops, with no clock involved
        vp = verdict_path(art, wiki)
        vp.parent.mkdir(parents=True, exist_ok=True)
        vp.write_text(f"---\nof_page: \"[[How do I run an A-B test?]]\"\n"
                      f"page_hash: {page_hash(art)}\nreviewed: 2026-09-16\nverdict: lean\n---\n"
                      "# Newcomer read — verdict\n", encoding="utf-8")
        assert _build_reason(vault, {str(art)}) is None, "fresh verdict must silence the nudge"

        # touching the article without changing a byte must NOT re-fire (hash, not mtime)
        os.utime(art, (time.time() + 10, time.time() + 10))
        assert _build_reason(vault, {str(art)}) is None, "mtime alone must not flag stale"

        # a real edit re-triggers it
        art.write_text(art.read_text(encoding="utf-8") + "\nThen measure.\n", encoding="utf-8")
        r2 = _build_reason(vault, {str(art)})
        assert r2 is not None and "verdict is now stale" in r2, r2

        print("wiki-verdict-hook selftest: OK "
              "(stale on change, silent when hash matches, mtime-proof, wiki-only)")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    raise SystemExit(main())
