#!/usr/bin/env python3
"""Move per-claim provenance out of the reader's sentence and into frontmatter.

An evidence bullet used to end like this:

    - It offered to provide **documentation from her doctor**. — [[Lana Fish Allergy]]  (base)

The tail is metadata. It is the same link on every bullet (one page carried
`— [[Lana Fish Allergy]]  (base)` four times in a row), it is punctuation the eye has to step over
on the way to the next fact, and `(base)` is a schema word that means nothing to a reader. The page
already declares where it is grounded, in `sources:` and `prerequisites:`, where the tools read it
from. Saying it again per-sentence buys the reader nothing and costs them the end of every line.

So: **lift, then strip.** Some pages cite a raw note ONLY in the body, so stripping without lifting
would delete the page's grounding — `check_evidence.py` builds its haystack from linked notes, and
a link that exists nowhere else is the only thing tying a number to the note it came from. The
order matters and the tool enforces it: a tail is removed only once its target is in frontmatter.

**What it will not touch.** A link the sentence is built around:

    Because [[What is Lana's fish allergy and treatment plan?]] establishes that the allergy is
    confirmed, the follow-up built on that.

    - …we planned to drop the epipen off Thursday. — the epipen itself comes from [[X]]

These read as prose and carry information; deleting them would cost the reader something real.
Telling them apart from a bare tail is a judgement about what a sentence is *doing*, which is
exactly what the repo's no-regex-for-intent tenet reserves for the assistant. So the mechanical
rule here is deliberately narrow — a tail is `— [[link]]` with an optional `(base)` / `(derived)`
and **nothing else between the dash and the link** — and anything with prose in it is reported
under AMBIGUOUS for a human to read and decide. The script never guesses.

Usage:
  migrate_attributions.py --wiki "Notes/📚 Wiki" --check     # dry run: tails, lifts, ambiguities
  migrate_attributions.py --wiki "Notes/📚 Wiki" --apply
  migrate_attributions.py --selftest
Standard library only.
"""
from __future__ import annotations

import argparse
import re
import tempfile
from pathlib import Path

# Folders whose files are not reader-facing articles.
SKIP_DIRS = ("@References",)
SKIP_NAMES = ("index.md", "log.md")

# Only articles. A space index (`wiki-space-index`) also carries `— [[note]]` tails, but there the
# tail is the page's job: the index is a map of the space, and "which raw note is this leaf
# grounded in" is the column a reader is there to consult, not metadata they step over. It is also
# a different schema — a `sources:` key on an index is a key no tool reads. Leave them to a human.
ARTICLE_TYPE = "wiki-faq"

# A BARE attribution tail: an em dash, a wikilink, an optional short parenthetical tag — and
# nothing else. The `(?=\s*(?:—|$))` is what keeps it bare: whatever follows must be the next tail
# or the end of the line, so `— the epipen comes from [[X]]` (prose before the link) can never
# match. The tag is any short parenthetical, not just `(base)`/`(derived)`, because the tags were
# hand-written and drifted — `(base fact from source)` is the same metadata wearing longer words.
_TAIL = re.compile(r"\s*—\s*\[\[([^\]]+)\]\]\s*(?:\([^)]{0,40}\))?(?=\s*(?:—|$))")

# Any dash-introduced segment containing a link, bare or not. What survives _TAIL removal and still
# matches this is prose wrapped around a link: report it, never touch it.
_ANY_TAIL = re.compile(r"\s*—\s*[^—]*?\[\[[^\]]+\]\]")

# Lines a tail is never stripped from, whatever they look like:
#   ```      a fence — verbatim source, and everything between two of them
#   >        a quotation — immutable by the content-preservation rule
#   #        a heading — a tail there is a structural oddity for a human to see
_EXEMPT = (">", "#")


def _split(text: str) -> tuple[str, str]:
    """Return (frontmatter, body). Frontmatter excludes the `---` fences."""
    if not text.startswith("---"):
        return "", text
    parts = text.split("---", 2)
    return (parts[1], parts[2]) if len(parts) == 3 else ("", text)


def _fm_links(fm: str) -> set[str]:
    return set(re.findall(r"\[\[([^\]]+)\]\]", fm))


def strip_tails(body: str) -> tuple[str, list[str], list[str]]:
    """Strip bare attribution tails from prose and bullet lines alike.

    Returns (new_body, links_removed, ambiguous_lines). Bullets are not the only carrier: most of
    the tails in the vault sit at the end of a lead-in paragraph, sometimes stranded after a colon
    (`The questions, grouped as raised: — [[note]]  (base)`), which reads worse than the bullet
    case, not better. What protects a real sentence is the shape of `_TAIL`, not the line's prefix.
    """
    out: list[str] = []
    removed: list[str] = []
    ambiguous: list[str] = []
    in_fence = False
    for line in body.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence or line.lstrip().startswith(_EXEMPT):
            out.append(line)
            continue
        found = [m.group(1) for m in _TAIL.finditer(line)]
        new = _TAIL.sub("", line).rstrip()
        if _ANY_TAIL.search(new):
            # Prose wrapped around a link survived. Leave the WHOLE line alone — half-stripping it
            # would mix a machine edit into a line a human still has to read.
            ambiguous.append(line.strip())
            out.append(line)
            continue
        removed += found
        out.append(new if found else line)
    return "\n".join(out), removed, ambiguous


def add_sources(fm: str, links: list[str]) -> tuple[str, list[str]]:
    """Merge links into the `sources:` block, creating it if absent. Returns (fm, added)."""
    have = _fm_links(fm)
    add = [ln for ln in dict.fromkeys(links) if ln not in have]
    if not add:
        return fm, []
    lines = fm.split("\n")
    new_items = [f'  - "[[{ln}]]"' for ln in add]
    for i, line in enumerate(lines):
        if line.strip() == "sources:":
            # Append after the block's existing items.
            j = i + 1
            while j < len(lines) and lines[j].startswith("  -"):
                j += 1
            lines[j:j] = new_items
            return "\n".join(lines), add
    # No `sources:` block. Put one after the last frontmatter key, before the trailing blank.
    j = len(lines)
    while j > 0 and not lines[j - 1].strip():
        j -= 1
    lines[j:j] = ["sources:"] + new_items
    return "\n".join(lines), add


def migrate_text(text: str, is_raw: callable) -> tuple[str, dict]:
    """Lift body-only source links into frontmatter, then strip the bare tails.

    `is_raw(link) -> bool` says whether a link names a raw note (so it belongs in `sources:`). A
    tail pointing at a wiki ARTICLE is a dependency edge; those are not auto-added to `prerequisites:`
    because an edge also needs its reciprocal `leads_to:` on the target, and inventing graph edges
    is not this tool's job. They are reported instead.
    """
    fm, body = _split(text)
    if not fm or f"type: {ARTICLE_TYPE}" not in fm:
        return text, {"tails": 0, "lifted": 0, "ambiguous": [], "unlifted_edges": []}

    new_body, removed, ambiguous = strip_tails(body)
    raw = [ln for ln in removed if is_raw(ln)]
    known = _fm_links(fm)
    edges = [ln for ln in dict.fromkeys(removed) if not is_raw(ln) and ln not in known]
    new_fm, added = add_sources(fm, raw)
    return (
        f"---{new_fm}---{new_body}",
        {"tails": len(removed), "lifted": len(added), "ambiguous": ambiguous,
         "unlifted_edges": edges},
    )


def _articles(wiki: Path):
    for p in sorted(wiki.rglob("*.md")):
        if any(d in p.parts for d in SKIP_DIRS) or p.name in SKIP_NAMES:
            continue
        if p.name.startswith("🗺️"):
            continue
        yield p


def migrate(wiki: Path, raw: Path, apply: bool) -> dict:
    # A link is "raw" if a note by that name exists outside the wiki. `--raw` is usually the whole
    # Notes/ tree, which CONTAINS the wiki, so subtract the articles — otherwise every article link
    # would look raw and land in `sources:`, which is the schema violation this tool must not make.
    wiki_stems = {p.stem for p in wiki.rglob("*.md")}
    raw_stems = ({p.stem for p in raw.rglob("*.md")} - wiki_stems) if raw and raw.exists() else set()
    totals = {"files": 0, "tails": 0, "lifted": 0}
    ambiguous: list[tuple[str, str]] = []
    edges: list[tuple[str, str]] = []
    for p in _articles(wiki):
        text = p.read_text(encoding="utf-8")
        new, c = migrate_text(text, lambda ln: ln in raw_stems)
        ambiguous += [(p.name, a) for a in c["ambiguous"]]
        edges += [(p.name, e) for e in c["unlifted_edges"]]
        if new != text:
            totals["files"] += 1
            totals["tails"] += c["tails"]
            totals["lifted"] += c["lifted"]
            if apply:
                p.write_text(new, encoding="utf-8")
    return {"totals": totals, "ambiguous": ambiguous, "edges": edges}


def _report(r: dict, apply: bool) -> None:
    t = r["totals"]
    verb = "rewrote" if apply else "would rewrite"
    print(f"{verb} {t['files']} file(s): {t['tails']} attribution tail(s) stripped, "
          f"{t['lifted']} link(s) lifted into sources:")
    if r["edges"]:
        print(f"\n{len(r['edges'])} tail(s) pointed at a wiki ARTICLE not already in frontmatter.")
        print("An edge needs its reciprocal leads_to:, so wire these by hand:")
        for name, e in r["edges"]:
            print(f"   ! {name}: [[{e}]]")
    if r["ambiguous"]:
        print(f"\n{len(r['ambiguous'])} AMBIGUOUS line(s) left untouched — prose wraps the link.")
        print("Read each and decide whether it earns its place:")
        for name, line in r["ambiguous"]:
            print(f"   ? {name}\n     {line[:160]}")


def _selftest() -> None:
    raw = {"budget note", "Lana Fish Allergy"}
    is_raw = lambda ln: ln in raw

    # 1. a bare tail is stripped and its raw note lifted into a sources: block that did not exist
    out, c = migrate_text(
        "---\ntitle: Q\ntype: wiki-faq\nkind: base\n---\n## Evidence\n- We spent $5. — [[budget note]]  (base)\n",
        is_raw)
    assert "— [[budget note]]" not in out, out
    assert "- We spent $5." in out, out
    assert 'sources:\n  - "[[budget note]]"' in out, out
    assert c["tails"] == 1 and c["lifted"] == 1, c

    # 2. the same link on four bullets lifts ONCE and strips four times
    body = "".join(f"- fact {i}. — [[Lana Fish Allergy]]  (base)\n" for i in range(4))
    out, c = migrate_text(f"---\ntitle: Q\ntype: wiki-faq\n---\n## Evidence\n{body}", is_raw)
    assert c["tails"] == 4 and c["lifted"] == 1, c
    assert out.count("[[Lana Fish Allergy]]") == 1, out

    # 3. a link already in frontmatter is not added twice
    out, c = migrate_text(
        '---\ntitle: Q\ntype: wiki-faq\nsources:\n  - "[[budget note]]"\n---\n'
        "## Evidence\n- A fact. — [[budget note]]\n", is_raw)
    assert c["tails"] == 1 and c["lifted"] == 0, c
    assert out.count("[[budget note]]") == 1, out

    # 4. PROSE around a link is not a tail — the whole line survives untouched, and is reported
    src = ("---\ntitle: Q\ntype: wiki-faq\n---\n## Evidence\n"
           "- We dropped the epipen. — [[Lana Fish Allergy]]  (base) — the epipen itself "
           "comes from [[Another answer]]  (derived)\n")
    out, c = migrate_text(src, is_raw)
    assert out == src, out
    assert c["tails"] == 0 and len(c["ambiguous"]) == 1, c

    # 5. a link inside a sentence, not after a dash, is never in scope
    src = "---\ntitle: Q\ntype: wiki-faq\n---\n## Evidence\nBecause [[Another answer]] establishes X, Y.\n"
    out, c = migrate_text(src, is_raw)
    assert out == src and c["tails"] == 0, c

    # 6. a tail naming a wiki ARTICLE is stripped but NOT auto-wired — an edge needs its mirror
    out, c = migrate_text(
        "---\ntitle: Q\ntype: wiki-faq\n---\n## Evidence\n- A step. — [[Another answer]]  (derived)\n", is_raw)
    assert c["tails"] == 1 and c["lifted"] == 0, c
    assert c["unlifted_edges"] == ["Another answer"], c
    assert "prerequisites" not in out, out

    # 7. a tail on a PARAGRAPH is stripped too, including one stranded after a colon
    out, c = migrate_text(
        "---\ntitle: Q\ntype: wiki-faq\n---\n## Evidence\nThe questions, as raised: — [[budget note]]  (base)\n",
        is_raw)
    assert "The questions, as raised:\n" in out, out
    assert c["tails"] == 1, c

    # 8. a hand-drifted tag is still a tag
    out, c = migrate_text(
        "---\ntitle: Q\ntype: wiki-faq\n---\n## Evidence\nA styling fact. — [[budget note]]  (base fact from "
        "source)\n", is_raw)
    assert out.rstrip().endswith("A styling fact."), out
    assert c["tails"] == 1, c

    # 9. a duplicate tail after an inline "Because [[X]] establishes…" goes; the inline link stays
    out, c = migrate_text(
        "---\ntitle: Q\ntype: wiki-faq\n---\n## Evidence\nBecause [[Another answer]] establishes X, this follows. "
        "— [[Another answer]]  (derived)\n", is_raw)
    assert out.rstrip().endswith("this follows."), out
    assert "Because [[Another answer]] establishes" in out, out

    # 10. fenced blocks and blockquotes are verbatim source — never touched
    src = ("---\ntitle: Q\ntype: wiki-faq\n---\n## Evidence\n```\nfoo. — [[budget note]]  (base)\n```\n"
           "> quoted. — [[budget note]]  (base)\n")
    out, c = migrate_text(src, is_raw)
    assert out == src and c["tails"] == 0, c

    # 11. a space index is a map, not an article — there the tail IS the column the reader wants
    src = ("---\ntitle: 🏢 X\ntype: wiki-space-index\n---\n## Base facts\n"
           "- Host is `h`. — [[budget note]]\n")
    out, c = migrate_text(src, is_raw)
    assert out == src and c["tails"] == 0, c
    assert "sources:" not in out, out

    # 12. idempotent
    once, _ = migrate_text(
        "---\ntitle: Q\ntype: wiki-faq\n---\n## Evidence\n- We spent $5. — [[budget note]]  (base)\n", is_raw)
    twice, c = migrate_text(once, is_raw)
    assert twice == once and c["tails"] == 0, c

    # 13. end to end on a tempdir, including the lift-before-strip ordering
    with tempfile.TemporaryDirectory() as d:
        wiki, rawdir = Path(d) / "w" / "🏡 Personal", Path(d) / "r"
        wiki.mkdir(parents=True)
        rawdir.mkdir()
        (rawdir / "Lana Fish Allergy.md").write_text("# raw\n", encoding="utf-8")
        (wiki / "q.md").write_text(
            "---\ntitle: q\ntype: wiki-faq\nkind: derived\n---\n## Evidence\n"
            "- A fact. — [[Lana Fish Allergy]]  (base)\n", encoding="utf-8")
        (wiki.parent / "@References").mkdir()
        (wiki.parent / "@References" / "article.md").write_text(
            "---\ntype: wiki-faq\n---\n- T. — [[budget note]]  (base)\n", encoding="utf-8")
        r = migrate(wiki.parent, rawdir, apply=True)
        assert r["totals"] == {"files": 1, "tails": 1, "lifted": 1}, r
        got = (wiki / "q.md").read_text(encoding="utf-8")
        assert 'sources:\n  - "[[Lana Fish Allergy]]"' in got, got
        assert "— [[Lana Fish Allergy]]" not in got, got
        # the template under @References is not a reader-facing page and is left alone
        assert "— [[budget note]]" in (wiki.parent / "@References" / "article.md").read_text(
            encoding="utf-8")

    print("migrate_attributions selftest: OK (bare tail stripped after its link is lifted into "
          "sources: + repeated link lifted once + paragraph and colon-stranded tails + drifted "
          "tags + prose-wrapped link left for a human + fences and quotes verbatim + article "
          "edges reported not invented + space indexes and @References spared + idempotent)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--wiki")
    ap.add_argument("--raw", help="raw inbox dir; a tail naming one of its notes goes to sources:")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
        return 0
    if not a.wiki or not (a.check or a.apply):
        ap.error("--wiki with --check or --apply (or --selftest)")
    _report(migrate(Path(a.wiki), Path(a.raw) if a.raw else None, a.apply), a.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
