#!/usr/bin/env python3
"""Lean the reader-facing body of every wiki page.

Three mechanical transforms, each removing text that a reader in NotePlan either sees and
cannot use, or reads as a second copy of something they already read:

1. **`## Answer` → `## Evidence`.** The answer is the bold `**Short answer.**` line above it;
   the section below holds the *evidence* for that answer, with `— [[source]]` attributions.
   Calling it "Answer" announces a second answer and then delivers a bibliography, which is
   why the pages read as repetitive. Renaming moves nothing — it just labels the block for
   what it is, so a newcomer knows the bold line is the takeaway and the section is the
   sourcing they may skip.

2. **Drop the `> [!context]` / `> [!gap]` marker line.** Obsidian callout syntax, which
   NotePlan does not implement: it renders the marker as a literal italic `[!context]` line,
   directly beneath a `## Context` heading that already says the same word.

3. **Unquote `## Context` and `## Gaps`.** Only a quotation should look like a quotation.
   NotePlan renders `>` as a grey, italic, left-ruled block — the visual language of "these
   are someone else's words". `## Context` and `## Gaps` are the author's own synthesis, so
   that shape is a lie about who is speaking, and a heavy one on a page meant to read light.
   The `>` was there because `check_evidence.py` keyed its grounding exemption on the prefix;
   the exemption now keys on the SECTION instead, which is what it always meant. Run this
   transform with a matching `check_evidence.py` (wiki-manager >= 0.8.0) or those paragraphs
   become newly grounding-checked.

   This is the one transform that assumes something about content: that nothing under those
   two headings was a genuine quotation. That is the rule the sections are written under, and
   `--check` prints every line it would unquote so the assumption stays reviewable.

4. **Strip HTML comments — from reader-facing pages only.** NotePlan renders `<!-- … -->` as
   ordinary visible body text; it does not hide them. Authoring scaffolding addressed to the
   *writer* therefore lands in the *reader's* page. The templates under `@References/` are the
   exception: their whole audience is the author, the comments are the only guidance they
   carry, and nobody reads them as a wiki page. `--templates` names that folder, so the rule
   is one path rather than a list of filenames to keep in sync.

All four are mechanical line transforms on structurally-identified lines (an exact heading,
an exact marker, a comment delimiter, a blockquote inside a named section) — no judgement
about what content *means*, so this is a transform script rather than something the assistant
must read and classify.

Usage:
  migrate_body_shape.py --wiki "Notes/📚 Wiki" --check      # dry run, report only
  migrate_body_shape.py --wiki "Notes/📚 Wiki" --apply
  migrate_body_shape.py --wiki "Notes/📚 Wiki" --apply --templates ""   # strip comments everywhere
  migrate_body_shape.py --selftest
Standard library only.
"""
from __future__ import annotations

import argparse
import re
import tempfile
from pathlib import Path

ANSWER_HEADING = "## Answer"
EVIDENCE_HEADING = "## Evidence"

# The sections that hold the author's own synthesis. Exempt from grounding (see
# check_evidence.py SYNTHESIS_SECTIONS) and therefore written as plain prose, not blockquotes.
SYNTHESIS_SECTIONS = ("## Context", "## Gaps")

# Author-facing, not reader-facing: the page templates a new article is copied from.
TEMPLATES_DIR = "@References"

# An exact callout marker line: `> [!context]`, `>[!gap]`, with optional trailing text.
_MARKER = re.compile(r"^>\s*\[!(?:context|gap)\]\s*(.*)$")
# `1.` / `2)` — a numbered list item, which stays its own line rather than folding into prose.
_ORDERED = re.compile(r"^\d+[.)]\s")


def rename_answer_heading(lines: list[str]) -> tuple[list[str], int]:
    out, n = [], 0
    for line in lines:
        if line.strip() == ANSWER_HEADING:
            out.append(EVIDENCE_HEADING)
            n += 1
        else:
            out.append(line)
    return out, n


def drop_callout_markers(lines: list[str]) -> tuple[list[str], int]:
    """Remove the marker, keep the blockquote.

    `> [!context]` alone on its line disappears entirely. `> [!context] some text` keeps the
    text as `> some text`, so no content is ever lost to this transform.
    """
    out, n = [], 0
    for line in lines:
        m = _MARKER.match(line)
        if not m:
            out.append(line)
            continue
        n += 1
        rest = m.group(1).strip()
        if rest:
            out.append(f"> {rest}")
    return out, n


def unquote_synthesis(lines: list[str]) -> tuple[list[str], int]:
    """Strip the leading `>` from every line inside `## Context` / `## Gaps`, rejoining paragraphs.

    A blockquote is how markdown says "someone else's words". These two sections are the
    author's, so the quotation styling misattributes them — and NotePlan renders it loudly
    (grey ground, italic, left rule).

    Removing the `>` is not enough on its own. A blockquote wraps its paragraph over several
    physical lines, each carrying its own `>`, and the renderer flows them back together. Plain
    prose gets no such courtesy in NotePlan — a hard newline IS a line break — so the same four
    lines would come out as four stubs, and any `**bold**` or `[[link]]` spanning the break would
    render as literal markup. So consecutive quoted lines are **joined into one physical line**,
    which is the vault's paragraph rule anyway.

    A bare `>` (or any unquoted line) ends the paragraph. A line that is itself block-level once
    unquoted — a bullet, a heading, a table row — is kept on its own line rather than folded into
    the prose. The section ends at the next `## `, so a `###` sub-heading stays inside it.
    """
    out: list[str] = []
    n = 0
    section = ""
    para: list[str] = []

    def flush() -> None:
        if para:
            out.append(" ".join(para))
            para.clear()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            flush()
            section = stripped
            out.append(line)
            continue
        if section in SYNTHESIS_SECTIONS and stripped.startswith(">"):
            n += 1
            rest = stripped[1:].strip()
            if not rest:                       # a bare `>` separates two quoted paragraphs
                flush()
            elif rest[0] in "-*#|" or _ORDERED.match(rest):
                flush()                        # block-level: stands alone, never folded in
                out.append(rest)
            else:
                para.append(rest)
            continue
        flush()
        out.append(line)
    flush()
    return out, n


def strip_html_comments(lines: list[str]) -> tuple[list[str], int]:
    """Drop whole `<!-- … -->` blocks, including multi-line ones.

    Also swallows a blank line left immediately after a removed block, so stripping a comment
    that sat between two paragraphs does not leave a double blank line behind.
    """
    out: list[str] = []
    n = 0
    inside = False
    for line in lines:
        if inside:
            if "-->" in line:
                inside = False
            continue
        if line.lstrip().startswith("<!--"):
            n += 1
            if "-->" not in line:
                inside = True
            # collapse a blank line that only existed to separate the comment
            if out and out[-1].strip() == "":
                out.pop()
            continue
        out.append(line)
    return out, n


def migrate_text(text: str, comments: bool = True) -> tuple[str, dict[str, int]]:
    lines = text.split("\n")
    lines, n_head = rename_answer_heading(lines)
    lines, n_mark = drop_callout_markers(lines)
    lines, n_quot = unquote_synthesis(lines)
    n_cmt = 0
    if comments:
        lines, n_cmt = strip_html_comments(lines)
    counts = {"headings": n_head, "markers": n_mark, "unquoted": n_quot, "comments": n_cmt}
    return "\n".join(lines), counts


def migrate(wiki: Path, apply: bool, templates: str = TEMPLATES_DIR) -> dict:
    """Rewrite every page under `wiki`; `templates` names the author-facing folder to spare."""
    changed: list[tuple[str, dict[str, int]]] = []
    totals = {"headings": 0, "markers": 0, "unquoted": 0, "comments": 0}
    for p in sorted(wiki.rglob("*.md")):
        rel = p.relative_to(wiki)
        is_template = bool(templates) and templates in rel.parts
        text = p.read_text(encoding="utf-8")
        new, counts = migrate_text(text, comments=not is_template)
        if new == text:
            continue
        changed.append((str(rel), counts))
        for k, v in counts.items():
            totals[k] += v
        if apply:
            p.write_text(new, encoding="utf-8")
    return {"files": changed, "totals": totals, "applied": apply}


def _report(r: dict) -> None:
    t = r["totals"]
    verb = "rewrote" if r["applied"] else "would rewrite"
    print(f"{verb} {len(r['files'])} file(s): "
          f"{t['headings']} heading(s) renamed, {t['markers']} callout marker(s) dropped, "
          f"{t['unquoted']} synthesis line(s) unquoted, {t['comments']} HTML comment(s) stripped")
    for rel, c in r["files"]:
        bits = [f"{v} {k}" for k, v in c.items() if v]
        print(f"   · {rel} — {', '.join(bits)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wiki", help="wiki root (the folder holding the spaces)")
    ap.add_argument("--apply", action="store_true", help="write the changes")
    ap.add_argument("--check", action="store_true", help="dry run (default)")
    ap.add_argument("--templates", default=TEMPLATES_DIR, metavar="DIR",
                    help=f"folder whose pages are author-facing and keep their HTML comments "
                         f"(default: {TEMPLATES_DIR}; pass an empty string to spare nothing)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.wiki:
        ap.error("--wiki is required (or use --selftest)")
    wiki = Path(args.wiki)
    if not wiki.is_dir():
        ap.error(f"not a directory: {wiki}")
    if args.apply and args.check:
        ap.error("--apply and --check are mutually exclusive")

    _report(migrate(wiki, apply=args.apply, templates=args.templates))
    return 0


def _selftest() -> int:
    # 1. heading rename, exact match only
    out, c = migrate_text("## Answer\nx\n")
    assert out == "## Evidence\nx\n" and c["headings"] == 1, (out, c)
    out, _ = migrate_text("## Answers\n### Answer\n")
    assert out == "## Answers\n### Answer\n", "only the exact `## Answer` heading is renamed"

    # 2. marker dropped AND the synthesis section unquoted — only quotations look like quotations
    out, c = migrate_text("## Context\n\n> [!context]\n> synthesis with $5,555\n")
    assert out == "## Context\n\nsynthesis with $5,555\n", out
    assert c["markers"] == 1 and c["unquoted"] == 1, c
    assert ">" not in out, "Context is the author's own words, not a quotation"

    # a marker carrying text on the same line keeps the text
    out, c = migrate_text("## Gaps\n> [!gap] nothing settles the date\n")
    assert out == "## Gaps\nnothing settles the date\n", out
    assert c["markers"] == 1 and c["unquoted"] == 1, c

    # a `>` OUTSIDE those two sections is a real quotation and is left alone
    out, c = migrate_text("## Evidence\n\n> a verbatim quote — [[src]]\n")
    assert out == "## Evidence\n\n> a verbatim quote — [[src]]\n", out
    assert c["unquoted"] == 0, c

    # a WRAPPED quoted paragraph rejoins into one physical line. Without this the four lines
    # become four stubs in NotePlan, where a hard newline is a line break.
    out, c = migrate_text("## Context\n\n> the allergy is confirmed and it\n"
                          "> spans all **fish** species, so the\n> school note is downstream.\n")
    assert out == ("## Context\n\nthe allergy is confirmed and it spans all **fish** species, "
                   "so the school note is downstream.\n"), repr(out)
    assert c["unquoted"] == 3, c

    # a bare `>` ends the paragraph; a bullet or sub-heading keeps its own line
    out, c = migrate_text("## Gaps\n\n> one\n> more\n>\n> - a bullet\n> - another\n"
                          "### sub\n> two\n\n## Evidence\n> quoted\n")
    assert out == ("## Gaps\n\none more\n- a bullet\n- another\n### sub\ntwo\n\n"
                   "## Evidence\n> quoted\n"), repr(out)
    assert c["unquoted"] == 6, c

    # 3. HTML comments, single and multi-line, with the separating blank line collapsed
    out, c = migrate_text("# T\n\n<!-- one liner -->\n\nbody\n")
    assert out == "# T\n\nbody\n", repr(out)
    assert c["comments"] == 1, c
    out, c = migrate_text("# T\n\n<!-- first\n     second -->\n\nbody\n")
    assert out == "# T\n\nbody\n", repr(out)
    assert c["comments"] == 1, c

    # comments=False leaves them, while still doing the other two
    out, c = migrate_text("<!-- keep -->\n## Answer\n", comments=False)
    assert out == "<!-- keep -->\n## Evidence\n", out
    assert c["comments"] == 0

    # 4. idempotent — running twice changes nothing the second time
    src = "## Answer\n\n## Context\n\n> [!context]\n> s\n\n<!-- c -->\n"
    once, _ = migrate_text(src)
    twice, c2 = migrate_text(once)
    assert once == twice, (once, twice)
    assert c2 == {"headings": 0, "markers": 0, "unquoted": 0, "comments": 0}, c2

    # 5. nothing else moves: a page with none of the four is byte-identical
    plain = "---\ntitle: q\n---\n\n# q\n\n**Short answer.** a\n\n## Evidence\n\n- b — [[s]]\n"
    out, c = migrate_text(plain)
    assert out == plain and c == {"headings": 0, "markers": 0, "unquoted": 0, "comments": 0}

    # 6. the templates folder keeps its comments but is still restructured
    with tempfile.TemporaryDirectory() as td:
        wiki = Path(td)
        page = "<!-- authoring note -->\n## Answer\n\n## Gaps\n\n> [!gap]\n> g\n"
        (wiki / TEMPLATES_DIR).mkdir()
        (wiki / TEMPLATES_DIR / "article.md").write_text(page, encoding="utf-8")
        (wiki / "🌐 General").mkdir()
        (wiki / "🌐 General" / "q.md").write_text(page, encoding="utf-8")

        r = migrate(wiki, apply=True)
        tmpl = (wiki / TEMPLATES_DIR / "article.md").read_text(encoding="utf-8")
        art = (wiki / "🌐 General" / "q.md").read_text(encoding="utf-8")
        assert tmpl == "<!-- authoring note -->\n## Evidence\n\n## Gaps\n\ng\n", repr(tmpl)
        assert art == "## Evidence\n\n## Gaps\n\ng\n", repr(art)
        assert r["totals"] == {"headings": 2, "markers": 2, "unquoted": 2,
                               "comments": 1}, r["totals"]

        # …and a second pass over the migrated tree is a no-op, template included
        r2 = migrate(wiki, apply=True)
        assert r2["files"] == [], r2["files"]

    print("migrate_body_shape selftest: OK "
          "(heading rename + marker drop + synthesis unquoted while a real quotation keeps its "
          f"`>` + comment strip sparing {TEMPLATES_DIR}/ + idempotent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
