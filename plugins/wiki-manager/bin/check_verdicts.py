#!/usr/bin/env python3
"""Verdict freshness: every wiki article must have a current newcomer verdict.

A **verdict** is a running report card written by the `review-as-newcomer` skill, kept in a
parallel tree that mirrors the wiki:

    Notes/📚 Wiki/<space>/<topic>/<question>.md
    Notes/📚 Wiki/@References/@Verdicts/<space>/<topic>/<question>.md

Each verdict records the `page_hash` of the article content it judged. When the article changes,
the stored hash no longer matches and the verdict is **stale** — the page has to be re-read as a
newcomer before its report card means anything again.

This module owns the hash rule so the skill, the validator and the Stop hook cannot drift:
`--hash <file>` prints exactly the digest a verdict must store.

Checks:
  · stale   — no verdict for an article, or the stored page_hash ≠ the article's current hash
  · orphan  — a verdict whose article no longer exists (renamed or deleted)

Usage:
  check_verdicts.py --wiki "Notes/📚 Wiki"
  check_verdicts.py --wiki "Notes/📚 Wiki" --strict     # exit 1 if anything is stale/orphaned
  check_verdicts.py --wiki "Notes/📚 Wiki" --json       # machine-readable (used by the Stop hook)
  check_verdicts.py --hash "<path to article>.md"
  check_verdicts.py --selftest
Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

VERDICTS_REL = ("@References", "@Verdicts")
HASH_LEN = 12


def page_hash(path: Path) -> str:
    """The article's content fingerprint: short sha256 of the file's bytes.

    Deliberately the WHOLE file, frontmatter included — a changed `prerequisites`, space or title
    changes what a newcomer reads just as much as a rewritten paragraph does. Newlines are
    normalized so an editor rewriting CRLF does not read as a content change.
    """
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()[:HASH_LEN]


def frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[4:end]
    return ""


def fm_value(fm: str, key: str) -> str | None:
    for line in fm.splitlines():
        m = re.match(rf"^{re.escape(key)}\s*:\s*(.+?)\s*$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


def is_article(p: Path, wiki: Path) -> bool:
    """A real FAQ article — not the hub, the log, a template, a verdict, or a space folder-note.

    Public because it is the *shared* definition of "a page the tooling cares about":
    `check_verdicts` asks it which pages need a verdict, and `wiki-concept-hook` asks it whether
    a write could have changed the concept map. Both must agree, or the hook nudges about a map
    that cannot have gone stale — which is exactly what it did when it carried its own
    suffix-matching copy of this rule. The `type: wiki-faq` test is the same fact `wiki_map.py`
    projects, so "is an article" and "is in the map" cannot drift apart.

    Returns False for a path that is missing or unreadable (a deletion, a race) rather than
    raising: every caller is advisory and would rather skip a file than crash on it.
    """
    if p.name in ("index.md", "log.md") or "@References" in p.parts:
        return False
    try:
        rel = p.relative_to(wiki)
    except ValueError:
        return False          # not under the wiki at all
    if len(rel.parts) < 2:
        return False          # the hub, the log, the map — anything at the wiki root is structure
    if len(rel.parts) == 2 and p.stem == p.parent.name:
        return False          # a space folder-note (📦 Past Work/📦 Past Work.md)
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return fm_value(frontmatter(text), "type") == "wiki-faq"


def verdict_path(article: Path, wiki: Path) -> Path:
    return wiki.joinpath(*VERDICTS_REL, article.relative_to(wiki))


def article_path(verdict: Path, wiki: Path) -> Path:
    return wiki / verdict.relative_to(wiki.joinpath(*VERDICTS_REL))


def check(wiki: Path) -> dict:
    articles = [p for p in sorted(wiki.rglob("*.md")) if is_article(p, wiki)]
    vroot = wiki.joinpath(*VERDICTS_REL)

    stale: list[tuple[str, str]] = []   # (article rel path, reason)
    fresh = 0
    for art in articles:
        vp = verdict_path(art, wiki)
        rel = str(art.relative_to(wiki))
        if not vp.is_file():
            stale.append((rel, "no verdict yet"))
            continue
        stored = fm_value(frontmatter(vp.read_text(encoding="utf-8", errors="ignore")), "page_hash")
        current = page_hash(art)
        if stored is None:
            stale.append((rel, "verdict has no page_hash"))
        elif stored != current:
            stale.append((rel, f"page changed since review (verdict {stored} ≠ page {current})"))
        else:
            fresh += 1

    orphans: list[str] = []
    if vroot.is_dir():
        for vp in sorted(vroot.rglob("*.md")):
            if not article_path(vp, wiki).is_file():
                orphans.append(str(vp.relative_to(vroot)))

    return {
        "articles": len(articles),
        "fresh": fresh,
        "stale": stale,
        "orphans": orphans,
    }


def _print_report(r: dict) -> None:
    print(f"articles: {r['articles']}   fresh verdicts: {r['fresh']}")
    print()
    print(f"1. Stale verdicts (re-read the page as a newcomer): {len(r['stale'])}")
    for rel, why in r["stale"]:
        print(f"   ✗ {rel} — {why}")
    print()
    print(f"2. Orphan verdicts (article gone — delete or re-point): {len(r['orphans'])}")
    for rel in r["orphans"]:
        print(f"   · {rel}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wiki", help="wiki directory (Notes/📚 Wiki)")
    ap.add_argument("--hash", dest="hash_path",
                    help="print the page_hash a verdict must store for this article, then exit")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a report")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any verdict is stale/orphaned")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()
    if args.hash_path:
        p = Path(args.hash_path)
        if not p.is_file():
            print(f"no such file: {p}", file=sys.stderr)
            return 2
        print(page_hash(p))
        return 0
    if not args.wiki:
        ap.error("--wiki is required (or use --hash / --selftest)")

    wiki = Path(args.wiki)
    if not wiki.is_dir():
        print(f"not a directory: {wiki}", file=sys.stderr)
        return 2
    r = check(wiki)
    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        _print_report(r)
    if args.strict and (r["stale"] or r["orphans"]):
        return 1
    return 0


def _selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        wiki = Path(d) / "📚 Wiki"
        topic = wiki / "📦 Past Work" / "Exp"
        topic.mkdir(parents=True)
        # structure that must be ignored: hub, log, space folder-note
        (wiki / "index.md").write_text("# Hub\n", encoding="utf-8")
        (wiki / "log.md").write_text("# Log\n", encoding="utf-8")
        (wiki / "📦 Past Work" / "📦 Past Work.md").write_text(
            "---\ntype: wiki-space-index\n---\n# 📦 Past Work\n", encoding="utf-8")

        art = topic / "How do I run an A-B test?.md"
        art.write_text("---\ntitle: How do I run an A-B test?\ntype: wiki-faq\n---\n"
                       "# How do I run an A-B test?\nStratify first.\n", encoding="utf-8")
        art2 = topic / "Which metric should I pick?.md"
        art2.write_text("---\ntitle: Which metric should I pick?\ntype: wiki-faq\n---\n"
                        "# Which metric should I pick?\nPick one.\n", encoding="utf-8")

        # no verdicts at all yet
        r = check(wiki)
        assert r["articles"] == 2, r          # hub/log/folder-note excluded
        assert r["fresh"] == 0, r
        assert len(r["stale"]) == 2, r
        assert all("no verdict yet" in why for _, why in r["stale"]), r

        # write a matching verdict for art → fresh
        vp = verdict_path(art, wiki)
        vp.parent.mkdir(parents=True, exist_ok=True)
        vp.write_text(f"---\nof_page: \"[[How do I run an A-B test?]]\"\n"
                      f"page_hash: {page_hash(art)}\nreviewed: 2026-09-16\nverdict: lean\n---\n"
                      "# Newcomer read — verdict\n", encoding="utf-8")
        r = check(wiki)
        assert r["fresh"] == 1, r
        assert [rel for rel, _ in r["stale"]] == [str(art2.relative_to(wiki))], r
        assert r["orphans"] == [], r

        # edit the page → the stored hash no longer matches → stale
        art.write_text(art.read_text(encoding="utf-8") + "\nAnd then test.\n", encoding="utf-8")
        r = check(wiki)
        assert r["fresh"] == 0, r
        assert any("page changed since review" in why
                   for rel, why in r["stale"] if rel == str(art.relative_to(wiki))), r

        # a verdict with no page_hash is stale for that reason
        vp.write_text("---\nof_page: \"[[x]]\"\nreviewed: 2026-09-16\n---\n# v\n", encoding="utf-8")
        r = check(wiki)
        assert any(why == "verdict has no page_hash"
                   for rel, why in r["stale"] if rel == str(art.relative_to(wiki))), r

        # delete the article → its verdict is an orphan, and it stops counting as an article
        art.unlink()
        r = check(wiki)
        assert r["articles"] == 1, r
        assert r["orphans"] == ["📦 Past Work/Exp/How do I run an A-B test?.md"], r

        # hash rule: stable across calls, and newline-normalized
        a = topic / "crlf.md"
        a.write_text("---\ntype: wiki-faq\n---\n# x\nline\n", encoding="utf-8")
        h1 = page_hash(a)
        a.write_bytes(a.read_bytes().replace(b"\n", b"\r\n"))
        assert page_hash(a) == h1, "CRLF rewrite must not read as a content change"
        assert len(h1) == HASH_LEN, h1

        print("check_verdicts selftest: OK "
              "(stale/fresh/orphan + structural skips + stable newline-normalized hash)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
