#!/usr/bin/env python3
"""Mechanical grounding + compartment linter for the wiki.

This is a SAFETY NET, not a judge. It does only mechanical, verbatim checks and
reports candidates for a human (or Claude) to review — it never decides what a
note "means" (repo tenet: no regex for intent detection). Claude does the real
grounding read and the real space/tolerance judgment; this catches the obvious
misses cheaply.

Five checks:
  1. link-resolution — every `[[wikilink]]` in an article's `sources:` frontmatter
     (and inline "— [[x]]" citations) resolves to a real .md file in raw or wiki.
  2. orphan-sources  — raw notes referenced by no wiki article at all.
  3. verbatim-grounding — every number, ISO/US date, and "quoted span" in an
     article body appears verbatim (as a substring) in at least one linked source.
     Misses are REPORTED, not failed on — quotation, rounding, and synthesis lines
     produce expected false positives that a human must judge.
  4. compartment (cross-space dependency) — the wiki is split into SPACES (one
     folder under the wiki root per domain, bound to a confidentiality tolerance;
     see references/spaces.md). An answer's `prerequisites:` edges
     may only point into its OWN space or the public floor 🌐 General. An edge into
     a different private space leaks one domain's confidential content into another's
     dependency crawl. NO expected false positives — this is a mechanical boundary.
  5. space-mismatch — an article's `space:` frontmatter must match the folder it
     lives in (the folder is the real compartment boundary).

Usage:
  check_evidence.py --wiki "Notes/📚 Wiki" --raw "Notes/🗑️ Unorganized"
  check_evidence.py --wiki <dir> --raw <dir> --json
  check_evidence.py --selftest

Exit code is 0 unless --strict is passed AND a link fails to resolve, a cross-space
dependency edge exists, or a space frontmatter mismatches its folder (the three
checks with no expected false positives). Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")
# Load-bearing literals: standalone numbers (incl. decimals, $), ISO & US dates,
# and double-quoted spans. Deliberately simple — over-reporting is fine.
NUMBER_RE = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?%?(?![\w.])")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")
QUOTE_RE = re.compile(r"“([^”]{4,})”|\"([^\"]{4,})\"")
# Pure synthesis is exempt from grounding by design — and the exemption belongs to the SECTION,
# not to a line prefix. Everything under `## Context` / `## Gaps` is the author's own words about
# the sources, so there is nothing for it to be verbatim against.
#
# This used to key on a `>` prefix instead, which forced every synthesis paragraph to be written
# as a blockquote. But a blockquote is markdown for "someone else's words", and NotePlan renders
# it as exactly that — grey ground, italic, left rule — so the styling misattributed the author's
# own prose. Only a quotation should look like a quotation. Keying on the section says what was
# always meant and gives `>` back its real job: a `>` block under `## Evidence` IS a quotation,
# and a quotation is grounded like any other claim — it must appear verbatim in a linked source,
# which is the whole point of quoting it.
SYNTHESIS_SECTIONS = ("## Context", "## Gaps")
EXEMPT_PREFIXES = ("<!--",)


def _iter_md(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.md") if p.is_file())


def _stem_index(paths: list[Path]) -> dict[str, Path]:
    # NotePlan/Obsidian wikilinks resolve by basename (minus .md).
    idx: dict[str, Path] = {}
    for p in paths:
        idx.setdefault(p.stem, p)
    return idx


def _frontmatter_and_body(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            nl = text.find("\n", end + 1)
            return text[4:end], text[nl + 1:] if nl != -1 else ""
    return "", text


def _links_in(text: str) -> list[str]:
    return [m.group(1).strip() for m in WIKILINK_RE.finditer(text)]


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _space_of(path: Path, wiki_dir: Path) -> str | None:
    """The space is the FIRST folder under the wiki root — the compartment boundary.
    A file directly under the wiki root (the hub index, the log) has no space."""
    try:
        rel = path.relative_to(wiki_dir)
    except ValueError:
        return None
    parts = rel.parts
    return parts[0] if len(parts) >= 2 else None


def _is_general(space: str | None) -> bool:
    """The public floor: the space whose name ends in 'General' (e.g. '🌐 General')."""
    if not space:
        return False
    toks = _normalize(space).split()
    return bool(toks) and toks[-1] == "general"


def _declared_space(fm: str) -> str | None:
    for line in fm.splitlines():
        m = re.match(r"^space\s*:\s*(.+?)\s*$", line)
        if m:
            val = re.split(r"\s+#", m.group(1), maxsplit=1)[0].strip().strip("\"'")
            return val or None
    return None


def _section(body: str, name: str) -> str:
    """Return the lines under the `## <name>` heading, up to the next `## ` heading."""
    out: list[str] = []
    capturing = False
    for line in body.splitlines():
        if line.startswith("## "):
            capturing = _normalize(line[3:]).startswith(_normalize(name))
            continue
        if capturing:
            out.append(line)
    return "\n".join(out)


def _fm_list_links(fm: str, key: str) -> list[str]:
    """The `[[links]]` in one frontmatter list block (`<key>:` plus its indented items)."""
    links: list[str] = []
    in_block = False
    for line in fm.splitlines():
        if re.match(r"^\s*#", line):
            continue
        if re.match(rf"^{re.escape(key)}\s*:", line):
            in_block = True
            links += _links_in(line)
            continue
        if in_block:
            if line and not line[0].isspace():
                in_block = False  # a new top-level frontmatter key ends the block
            else:
                links += _links_in(line)
    return links


def _fm_list_items(fm: str, key: str) -> list[str] | None:
    """The `- item` lines of one frontmatter list block, as plain strings.

    `None` when the key is absent entirely; `[]` when it is present with no items. Only the
    block's own indented `- ` lines count, so a following top-level key ends it."""
    items: list[str] | None = None
    in_block = False
    for line in fm.splitlines():
        if re.match(r"^\s*#", line):
            continue
        if re.match(rf"^{re.escape(key)}\s*:", line):
            in_block = True
            items = []
            rest = line.split(":", 1)[1].strip()
            if rest and rest not in ("[]", "~", "null"):
                items.append(rest.strip().strip('"').strip("'"))
            continue
        if in_block:
            if line and not line[0].isspace():
                in_block = False  # a new top-level frontmatter key ends the block
            elif line.strip().startswith("- "):
                items.append(line.strip()[2:].strip().strip('"').strip("'"))
    return items


def _fm_scalar(fm: str, key: str) -> str | None:
    """The value of a single-line `key: value` frontmatter entry, or None if the key is absent."""
    for line in fm.splitlines():
        m = re.match(rf"^{re.escape(key)}\s*:\s*(.*?)\s*$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


# Fragments that only ever appear in an UNEDITED copy of references/article.md. Matching these is
# a mechanical string test for "the template was never filled in", NOT a judgement about whether
# an entry is a good user story — that judgement belongs to a reader (the review-as-newcomer
# skill's rubric §3), never to a pattern here. See the repo tenet: no regex for intent detection.
FRAMING_PLACEHOLDERS = (
    "<role,", "<a second role", "<task the answer unblocks", "<their task",
    "<what goes wrong if this answer",
)


def _framing_problems(fm: str) -> list[str]:
    """Missing or unfilled `asked_by:` / `matters_because:` — the two keys that say who needs this
    answer and what turns on it. Presence only: whether the stated askers are REAL is a reader's
    call, recorded in the verdict's `framing:` key."""
    problems: list[str] = []

    entries = _fm_list_items(fm, "asked_by")
    if entries is None:
        problems.append("no `asked_by:` — say who needs this answer and what for")
    elif not entries:
        problems.append("`asked_by:` is empty — needs at least one user story")
    else:
        for e in entries:
            if any(ph in e for ph in FRAMING_PLACEHOLDERS):
                problems.append(f"`asked_by` entry is still the template placeholder: {e!r}")

    mb = _fm_scalar(fm, "matters_because")
    if mb is None:
        problems.append("no `matters_because:` — say what goes wrong without this answer")
    elif not mb:
        problems.append("`matters_because:` is empty")
    elif any(ph in mb for ph in FRAMING_PLACEHOLDERS):
        problems.append("`matters_because:` is still the template placeholder")

    return problems


def _prerequisite_links(fm: str) -> list[str]:
    """Prerequisite edges only, read from the `prerequisites:` frontmatter block — the answers a
    reader must already understand. Cross-linking is FRONTMATTER-DRIVEN: the `## Builds on` body
    section is gone (and is flagged as legacy if it reappears). NOT `sources:` (where the facts
    came from, which is a different question and may be set on the same page) and NOT `leads_to:`
    (upward back-links)."""
    return _fm_list_links(fm, "prerequisites")


def _legacy_link_sections(body: str) -> list[str]:
    """Body headings that duplicate what now lives in frontmatter. The lean-body rule: a page is
    Short answer → ## Evidence → ## Context → ## Gaps, and nothing else."""
    found = []
    for line in body.splitlines():
        if line.startswith("## "):
            head = _normalize(line[3:])
            for legacy in ("builds on", "leads to"):
                if head.startswith(legacy) and legacy not in found:
                    found.append(legacy)
    return found


def _is_structural(p: Path, wiki_dir: Path) -> bool:
    """Hub/log/templates and each space's folder-note (`<space>/<space>.md`) are
    structure, not articles — they are not linted for grounding."""
    if p.name in ("index.md", "log.md") or "@References" in p.parts:
        return True
    try:
        rel = p.relative_to(wiki_dir)
    except ValueError:
        return False
    if len(rel.parts) == 1:
        return True  # anything at the wiki root is structure (hub, log, 🗺️ Concept Map)
    return len(rel.parts) == 2 and p.stem == p.parent.name


def check(wiki_dir: Path, raw_dir: Path) -> dict:
    raw_paths = _iter_md(raw_dir)
    wiki_paths = [p for p in _iter_md(wiki_dir) if not _is_structural(p, wiki_dir)]
    resolvable = _stem_index(raw_paths + wiki_paths)

    unresolved = []      # (article, link)
    grounding = []       # (article, kind, literal)
    cross_space = []     # (article, article_space, link, target_space)
    space_mismatch = []  # (article, declared_space, folder_space)
    legacy_sections = [] # (article, heading)
    framing = []         # (article, problem)
    referenced_raw: set[str] = set()
    # stem -> declared edges, for the post-loop leads_to symmetry check
    pre_by_stem: dict[str, list[str]] = {}
    led_by_stem: dict[str, list[str]] = {}

    for art in wiki_paths:
        text = art.read_text(encoding="utf-8", errors="ignore")
        fm, body = _frontmatter_and_body(text)

        links = _links_in(fm) + _links_in(body)
        # A base-fact answer grounds against linked RAW notes; a derived answer
        # grounds against the wiki answers it builds on. So the haystack is every
        # linked note, raw or wiki — following the dependency edges one hop.
        linked_stems = []
        for ln in links:
            if ln not in resolvable:
                unresolved.append((art.name, ln))
                continue
            linked_stems.append(ln)
            if resolvable[ln] in raw_paths:
                referenced_raw.add(resolvable[ln].stem)

        # --- compartment checks (space is the folder; frontmatter must agree) ---
        art_space = _space_of(art, wiki_dir)
        declared = _declared_space(fm)
        if declared and art_space and _normalize(declared) != _normalize(art_space):
            space_mismatch.append((art.name, declared, art_space))

        for heading in _legacy_link_sections(body):
            legacy_sections.append((art.name, heading))

        for problem in _framing_problems(fm):
            framing.append((art.name, problem))

        pre_by_stem[art.stem] = _prerequisite_links(fm)
        led_by_stem[art.stem] = _fm_list_links(fm, "leads_to")

        for ln in _prerequisite_links(fm):
            if ln not in resolvable:
                continue  # already flagged by the link check
            target = resolvable[ln]
            if target in raw_paths or art_space is None:
                continue  # prerequisite→raw is a modeling nit, not a leak; no space to gate
            t_space = _space_of(target, wiki_dir)
            if t_space is None or _normalize(t_space) == _normalize(art_space) or _is_general(t_space):
                continue  # own space or the public floor — allowed
            cross_space.append((art.name, art_space, ln, t_space))

        haystack = ""
        for stem in linked_stems:
            target = resolvable[stem]
            if target == art:
                continue
            haystack += "\n" + target.read_text(encoding="utf-8", errors="ignore")
        norm_hay = _normalize(haystack)

        if not linked_stems:
            continue  # nothing linked to ground against; link check already flagged it

        section = ""
        for raw_line in body.splitlines():
            line = raw_line.strip()
            # A `## ` heading opens a section; a deeper `###` stays inside the one it is under.
            if line.startswith("## "):
                section = line
            if section in SYNTHESIS_SECTIONS:
                continue
            if not line or line.startswith(EXEMPT_PREFIXES) or line.startswith("#"):
                continue
            literals: list[tuple[str, str]] = []
            # Dates first, then blank them out so their digits don't re-match as numbers.
            literals += [("date", m.group(0)) for m in DATE_RE.finditer(line)]
            line_no_dates = DATE_RE.sub(lambda m: " " * len(m.group(0)), line)
            literals += [("number", m.group(0)) for m in NUMBER_RE.finditer(line_no_dates)]
            literals += [("quote", (m.group(1) or m.group(2))) for m in QUOTE_RE.finditer(line)]
            for kind, lit in literals:
                if _normalize(lit) and _normalize(lit) not in norm_hay:
                    grounding.append((art.name, kind, lit))

    # --- leads_to symmetry: every prerequisite edge is wired both directions ---
    # prerequisites is the authoritative direction; leads_to is its mirror. Only edges between two
    # wiki ARTICLES are checked (an edge to a raw note has no page to carry the back-link).
    asymmetric = []  # (article, problem, other)
    for stem, pres in pre_by_stem.items():
        for target in pres:
            if target not in led_by_stem:
                continue  # not a wiki article (raw note, or unresolved — flagged elsewhere)
            if stem not in led_by_stem[target]:
                asymmetric.append((target, "missing leads_to back-link for", stem))
    for stem, leds in led_by_stem.items():
        for source in leds:
            if source not in pre_by_stem:
                continue
            if stem not in pre_by_stem[source]:
                asymmetric.append((stem, "leads_to has no matching prerequisites on", source))

    orphans = sorted(p.stem for p in raw_paths if p.stem not in referenced_raw)

    return {
        "articles": len(wiki_paths),
        "raw_notes": len(raw_paths),
        "unresolved_links": unresolved,
        "ungrounded_literals": grounding,
        "cross_space_deps": cross_space,
        "space_mismatches": space_mismatch,
        "legacy_link_sections": legacy_sections,
        "asymmetric_links": asymmetric,
        "missing_framing": framing,
        "orphan_raw_notes": orphans,
    }


def _print_report(r: dict) -> None:
    print(f"wiki articles: {r['articles']}   raw notes: {r['raw_notes']}")
    print()
    print(f"1. Unresolved [[links]]: {len(r['unresolved_links'])}")
    for art, ln in r["unresolved_links"]:
        print(f"   ✗ {art}: [[{ln}]] → no such note")
    print()
    print(f"2. Ungrounded literals (REVIEW — expect false positives): {len(r['ungrounded_literals'])}")
    for art, kind, lit in r["ungrounded_literals"]:
        print(f"   ? {art}: {kind} {lit!r} not found verbatim in linked sources")
    print()
    print(f"3. Cross-space dependency edges (LEAK — must be 0): {len(r['cross_space_deps'])}")
    for art, art_space, ln, t_space in r["cross_space_deps"]:
        print(f"   ✗ {art} [{art_space}] depends on [[{ln}]] in [{t_space}] — not own space or 🌐 General")
    print()
    print(f"4. Space frontmatter ≠ folder: {len(r['space_mismatches'])}")
    for art, declared, folder in r["space_mismatches"]:
        print(f"   ✗ {art}: space: {declared!r} but lives in {folder!r}")
    print()
    print(f"5. Legacy body link sections (must be 0 — edges live in frontmatter): "
          f"{len(r['legacy_link_sections'])}")
    for art, heading in r["legacy_link_sections"]:
        print(f"   ✗ {art}: has a '## {heading}' body section — move the edges to frontmatter")
    print()
    print(f"6. Asymmetric cross-links (must be 0): {len(r['asymmetric_links'])}")
    for art, problem, other in r["asymmetric_links"]:
        print(f"   ✗ {art}: {problem} [[{other}]]")
    print()
    print(f"7. Missing framing fields (must be 0 — asked_by / matters_because): "
          f"{len(r['missing_framing'])}")
    for art, problem in r["missing_framing"]:
        print(f"   ✗ {art}: {problem}")
    print()
    print(f"8. Orphan raw notes (referenced by no article): {len(r['orphan_raw_notes'])}")
    for stem in r["orphan_raw_notes"]:
        print(f"   · {stem}")


def _selftest() -> int:
    import tempfile

    # Scenario A — grounding / links / orphans (one topic folder, no `space:` declared).
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        raw = base / "raw"
        wiki = base / "wiki"
        raw.mkdir()
        topic = wiki / "Money"
        topic.mkdir(parents=True)
        # anything at the wiki ROOT is structure, never an article — the generated
        # 🗺️ Concept Map lives there and must not be linted for grounding.
        (wiki / "🗺️ Concept Map.md").write_text(
            "# 🗺️ Concept Map\nA bogus $8,888 in generated output. — [[nowhere]]\n",
            encoding="utf-8")
        (raw / "budget note.md").write_text(
            "# Budget note\nWe spent $1,200 on 2026-03-01 with Acme.\n", encoding="utf-8")
        (raw / "lonely.md").write_text("# Lonely\nnobody links me\n", encoding="utf-8")
        (topic / "Budget.md").write_text(
            "---\nsources:\n  - \"[[budget note]]\"\n---\n"
            "# Budget\n## Evidence\n"
            "- We spent $1,200 on 2026-03-01. — [[budget note]]\n"
            "- A made-up figure of $9,999 on 2030-01-01. — [[budget note]]\n"
            "- A dangling ref. — [[does not exist]]\n"
            # a `>` here is a QUOTATION, and a quotation is grounded like any other claim
            "> We also spent $7,777 — [[budget note]]\n"
            "## Context\n"
            "This is synthesis with $5,555, exempt because of the section it is in.\n",
            encoding="utf-8")
        # A DERIVED answer that builds on the base-fact article: its $1,200 must
        # ground against [[Budget]] (crawl through the wiki), not raw directly.
        (topic / "How much runway.md").write_text(
            "---\nsources:\n  - \"[[Budget]]\"\n---\n"
            "# How much runway do we have?\n"
            "- Given we spent $1,200, runway is tight. — [[Budget]]\n",
            encoding="utf-8")
        r = check(wiki, raw)
        assert r["articles"] == 2, r
        assert r["raw_notes"] == 2, r
        assert ("Budget.md", "does not exist") in r["unresolved_links"], r
        lits = {(k, v) for _, k, v in r["ungrounded_literals"]}
        assert ("number", "$9,999") in lits, lits
        assert ("date", "2030-01-01") in lits, lits
        # grounded ones must NOT be flagged
        assert ("number", "$1,200") not in lits, lits
        assert ("date", "2026-03-01") not in lits, lits
        # exemption is by SECTION: plain prose under `## Context` needs no `>` to be exempt
        assert ("number", "$5,555") not in lits, lits
        # …and the freed-up `>` is a real quotation, so it IS grounded now
        assert ("number", "$7,777") in lits, lits
        # derived answer's $1,200 grounds through [[Budget]] — not flagged
        assert not any(art == "How much runway.md" and v == "$1,200"
                       for art, k, v in r["ungrounded_literals"]), r["ungrounded_literals"]
        assert "lonely" in r["orphan_raw_notes"], r
        assert "budget note" not in r["orphan_raw_notes"], r
        # the root-level concept map is structure: neither counted nor linted
        assert not any(art.startswith("🗺️") for art, *_ in r["ungrounded_literals"]), r
        assert not any(art.startswith("🗺️") for art, _ in r["unresolved_links"]), r
        # no `space:` frontmatter anywhere → no compartment findings
        assert r["cross_space_deps"] == [], r
        assert r["space_mismatches"] == [], r

    # Scenario B — spaces: the compartment (cross-space) + space-mismatch checks.
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        raw = base / "raw"
        wiki = base / "wiki"
        raw.mkdir()
        wiki.mkdir()
        (raw / "mission.md").write_text("# Mission\nWe help people ship.\n", encoding="utf-8")
        for space in ("🌐 General", "🏢 Work", "📦 Past Work"):
            (wiki / space).mkdir()
            # each space's folder-note (`<space>/<space>.md`) is structure, not an article
            (wiki / space / f"{space}.md").write_text(
                f"---\ntitle: {space}\ntype: wiki-space-index\nspace: {space}\n---\n# {space}\n",
                encoding="utf-8")

        # Public-floor base answer. Carries the symmetric back-link in frontmatter.
        (wiki / "🌐 General" / "What is the mission.md").write_text(
            "---\nspace: 🌐 General\nkind: base\nsources:\n  - \"[[mission]]\"\n"
            "leads_to:\n  - \"[[How does work advance the mission]]\"\n---\n"
            "# What is the mission?\n- We help people ship. — [[mission]]\n",
            encoding="utf-8")
        # ALLOWED: a private space building on the public floor. Edge is frontmatter-only and
        # symmetric, and the body carries no link section — this page must produce NO findings.
        (wiki / "🏢 Work" / "How does work advance the mission.md").write_text(
            "---\nspace: 🏢 Work\nkind: derived\nprerequisites:\n"
            "  - \"[[What is the mission]]\"\n---\n"
            "# How does work advance the mission?\n"
            "Because [[What is the mission]] establishes the goal, the work follows.\n",
            encoding="utf-8")
        # VIOLATION: a legacy `## Builds on` body section (edges belong in frontmatter).
        (wiki / "🌐 General" / "Legacy page.md").write_text(
            "---\nspace: 🌐 General\nkind: base\nsources:\n  - \"[[mission]]\"\n---\n"
            "# Legacy page?\n- We help people ship. — [[mission]]\n"
            "## Builds on\n- [[What is the mission]] — stale scaffolding.\n",
            encoding="utf-8")
        # VIOLATION: a leads_to back-link the target never declared a prerequisite for.
        (wiki / "🌐 General" / "Dangling backlink.md").write_text(
            "---\nspace: 🌐 General\nkind: base\nsources:\n  - \"[[mission]]\"\n"
            "leads_to:\n  - \"[[What is the mission]]\"\n---\n"
            "# Dangling backlink?\n- We help people ship. — [[mission]]\n",
            encoding="utf-8")
        # VIOLATION: a private space building on ANOTHER private space.
        (wiki / "📦 Past Work" / "A past-work-only answer.md").write_text(
            "---\nspace: 📦 Past Work\nkind: base\nsources:\n  - \"[[mission]]\"\n---\n"
            "# A past-work-only answer?\n- Confidential detail. — [[mission]]\n",
            encoding="utf-8")
        (wiki / "🏢 Work" / "Cross leak.md").write_text(
            "---\nspace: 🏢 Work\nkind: derived\nprerequisites:\n"
            "  - \"[[A past-work-only answer]]\"\n---\n"
            "# Cross leak?\nBecause [[A past-work-only answer]] says so — leaks across compartments.\n",
            encoding="utf-8")
        # VIOLATION: frontmatter space ≠ folder.
        (wiki / "🏢 Work" / "Misfiled.md").write_text(
            "---\nspace: 📦 Past Work\nkind: base\nsources:\n  - \"[[mission]]\"\n---\n"
            "# Misfiled?\n- x. — [[mission]]\n",
            encoding="utf-8")
        r = check(wiki, raw)
        # folder-notes are structural — only the 7 real articles are linted
        assert r["articles"] == 7, r
        cross = {(art, ln) for art, _, ln, _ in r["cross_space_deps"]}
        # the cross-compartment edge is flagged, with the target space named
        assert ("Cross leak.md", "A past-work-only answer") in cross, r["cross_space_deps"]
        assert any(t == "📦 Past Work" for _, _, _, t in r["cross_space_deps"]), r["cross_space_deps"]
        # the legal own→General edge is NOT flagged
        assert not any(art == "How does work advance the mission.md"
                       for art, _, _, _ in r["cross_space_deps"]), r["cross_space_deps"]
        # space mismatch caught, correctly-filed articles are not
        mis = {(a, decl, folder) for a, decl, folder in r["space_mismatches"]}
        assert ("Misfiled.md", "📦 Past Work", "🏢 Work") in mis, r["space_mismatches"]
        assert not any(a == "Cross leak.md" for a, _, _ in r["space_mismatches"]), r["space_mismatches"]

        # --- lean body: a legacy `## Builds on` / `## Leads to` section is flagged ---
        legacy = {(a, h) for a, h in r["legacy_link_sections"]}
        assert ("Legacy page.md", "builds on") in legacy, r["legacy_link_sections"]
        # a page whose edges live only in frontmatter is clean
        assert not any(a == "How does work advance the mission.md"
                       for a, _ in r["legacy_link_sections"]), r["legacy_link_sections"]

        # --- leads_to symmetry, both directions ---
        asym = {(a, other) for a, _, other in r["asymmetric_links"]}
        # a prerequisite with no matching back-link on the target
        assert ("A past-work-only answer", "Cross leak") in asym, r["asymmetric_links"]
        # leads_to with no matching prerequisites on the named source
        assert ("Dangling backlink", "What is the mission") in asym, r["asymmetric_links"]
        # the properly-wired pair is NOT flagged in either direction
        assert not any(a in ("What is the mission", "How does work advance the mission")
                       and other in ("What is the mission", "How does work advance the mission")
                       for a, other in asym), r["asymmetric_links"]

    # Scenario C — the framing fields (`asked_by:` / `matters_because:`).
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        raw = base / "raw"
        wiki = base / "wiki"
        raw.mkdir()
        space = wiki / "🌐 General"
        space.mkdir(parents=True)
        (raw / "src.md").write_text("# Src\nA fact.\n", encoding="utf-8")
        (space / "🌐 General.md").write_text("# 🌐 General\n", encoding="utf-8")
        # PASSES: both keys filled in, two askers.
        (space / "Framed.md").write_text(
            "---\ntype: wiki-faq\nspace: 🌐 General\nkind: base\n"
            "asked_by:\n"
            "  - as someone wiring a new hook, I need this to know which event can deny a call\n"
            "  - as someone debugging a rejected edit, I need this to find which check fired\n"
            "matters_because: a hook that cannot deny is detection, and calling it a guard misleads\n"
            "sources:\n  - \"[[src]]\"\n---\n"
            "# Framed?\n**Short answer.** Yes.\n## Evidence\n- A fact. — [[src]]\n",
            encoding="utf-8")
        # FAILS: no asked_by at all, and matters_because left as the template placeholder.
        (space / "Unframed.md").write_text(
            "---\ntype: wiki-faq\nspace: 🌐 General\nkind: base\n"
            "matters_because: <what goes wrong if this answer is absent or wrong — one line>\n"
            "sources:\n  - \"[[src]]\"\n---\n"
            "# Unframed?\n**Short answer.** No.\n## Evidence\n- A fact. — [[src]]\n",
            encoding="utf-8")
        # FAILS: the key is there but the list is empty.
        (space / "Empty.md").write_text(
            "---\ntype: wiki-faq\nspace: 🌐 General\nkind: base\n"
            "asked_by: []\n"
            "matters_because: something real is at stake here\n"
            "sources:\n  - \"[[src]]\"\n---\n"
            "# Empty?\n**Short answer.** No.\n## Evidence\n- A fact. — [[src]]\n",
            encoding="utf-8")
        r = check(wiki, raw)
        flagged = {a for a, _ in r["missing_framing"]}
        assert "Unframed.md" in flagged, r["missing_framing"]
        assert "Empty.md" in flagged, r["missing_framing"]
        assert "Framed.md" not in flagged, r["missing_framing"]
        # the placeholder is caught even though the key is present and non-empty
        assert any(a == "Unframed.md" and "placeholder" in why
                   for a, why in r["missing_framing"]), r["missing_framing"]
        # a good page passes the pre-commit path; a bad one fails it
        assert _framing_only([str(space / "Framed.md")]) == 0
        assert _framing_only([str(space / "Unframed.md")]) == 1
        # non-articles and vanished paths are skipped in silence, not failed
        assert _framing_only([str(space / "🌐 General.md"), str(space / "gone.md")]) == 0

    print("check_evidence selftest: OK "
          "(grounding + compartments + lean body + leads_to symmetry + framing fields)")
    return 0


def _framing_only(paths: list[str]) -> int:
    """Check just the framing fields on the named files — the pre-commit path.

    Only files that declare `type: wiki-faq` are checked; a folder-note, the log, a verdict or a
    deleted path is skipped in silence, so the hook can hand over every staged path it saw."""
    problems: list[tuple[str, str]] = []
    checked = 0
    for raw_path in paths:
        p = Path(raw_path)
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        fm, _ = _frontmatter_and_body(text)
        if _fm_scalar(fm, "type") != "wiki-faq":
            continue
        checked += 1
        for problem in _framing_problems(fm):
            problems.append((p.name, problem))

    if problems:
        print(f"✗ {len(problems)} framing problem(s) in {checked} wiki article(s):")
        for name, problem in problems:
            print(f"   ✗ {name}: {problem}")
        print()
        print("Every FAQ page says who needs the answer and what turns on it. `asked_by:` is a")
        print("flat list of user stories — \"as a <role doing something specific>, I need this to")
        print("<task the answer unblocks>\" — and `matters_because:` is one line on what goes wrong")
        print("when the answer is absent or wrong. See references/article.md.")
        return 1

    print(f"✓ framing fields present on {checked} wiki article(s)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wiki", help="wiki directory (Notes/📚 Wiki)")
    ap.add_argument("--raw", help="raw sources directory (Notes/🗑️ Unorganized)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a report")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on an unresolved link, a cross-space dependency, a space "
                         "mismatch, a legacy body link section, an asymmetric cross-link, or a "
                         "missing framing field")
    ap.add_argument("--framing", nargs="+", metavar="FILE",
                    help="check ONLY `asked_by:` / `matters_because:` on the named article files "
                         "and exit 1 on any problem. No wiki scan — this is the pre-commit path, "
                         "which sees only the files being committed.")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()
    if args.framing:
        return _framing_only(args.framing)
    if not args.wiki or not args.raw:
        ap.error("--wiki and --raw are required (or use --selftest)")

    r = check(Path(args.wiki), Path(args.raw))
    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        _print_report(r)
    if args.strict and (r["unresolved_links"] or r["cross_space_deps"] or r["space_mismatches"]
                        or r["legacy_link_sections"] or r["asymmetric_links"]
                        or r["missing_framing"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
