#!/usr/bin/env python3
"""One-shot migration: move wiki cross-links from body sections into frontmatter.

The wiki moved to **frontmatter-driven cross-linking**: a page's prerequisite edges live in
`prerequisites:` and its back-links in `leads_to:`, and the `## Builds on` / `## Leads to` body
sections are removed so a reader gets only the answer. This tool performs that migration on an
existing wiki, mechanically (it only moves structured `[[links]]` that are already explicit — it
never interprets prose, per the repo's no-regex-for-intent tenet):

  1. For each `type: wiki-faq` page, read the dependency edges from BOTH the `prerequisites:`
     frontmatter block and the `## Builds on` body section, and merge them (dedup, order-stable)
     into `prerequisites:`.
  2. Derive `leads_to:` for every page GLOBALLY from the union of all `prerequisites` edges
     (X lists Y as a prerequisite  ⇒  Y leads_to X), resolved by basename. This guarantees symmetric
     back-links and repairs pre-existing one-directional edges.
  3. Delete the `## Builds on` and `## Leads to` body sections.
  4. Rewrite the frontmatter (prerequisites + leads_to as flat "[[link]]" lists; empty blocks
     omitted), preserving every other key in place and NotePlan render-safety.

Idempotent: a second run finds no body sections and recomputes the same leads_to → no change.

Usage:
  migrate_frontmatter_links.py --wiki "Notes/📚 Wiki"          # apply
  migrate_frontmatter_links.py --wiki "Notes/📚 Wiki" --check  # dry run (report only)
  migrate_frontmatter_links.py --selftest
Standard library only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
KEY_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:")
REMOVE_SECTIONS = ("Builds on", "Leads to")


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _frontmatter_and_body(text: str) -> tuple[str, str, bool]:
    """Return (frontmatter_text, body_text, had_frontmatter)."""
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            nl = text.find("\n", end + 1)
            return text[4:end], (text[nl + 1:] if nl != -1 else ""), True
    return "", text, False


def _links_in(text: str) -> list[str]:
    return [m.group(1).strip() for m in WIKILINK_RE.finditer(text)]


def _fm_blocks(fm: str) -> list[tuple[str | None, list[str]]]:
    """Split frontmatter into ordered (key, lines) blocks. A block is a top-level
    `key:` line plus its indented continuation lines. Lines before any key (rare) get key=None."""
    blocks: list[tuple[str | None, list[str]]] = []
    cur_key: str | None = None
    cur: list[str] = []
    for line in fm.splitlines():
        m = KEY_RE.match(line)
        if m:
            if cur:
                blocks.append((cur_key, cur))
            cur_key = m.group(1)
            cur = [line]
        else:
            cur.append(line)
    if cur:
        blocks.append((cur_key, cur))
    return blocks


def _list_from_block(lines: list[str]) -> list[str]:
    """The wikilinks declared in a frontmatter list block (`key:` then `  - "[[x]]"`)."""
    out: list[str] = []
    for line in lines:
        out += _links_in(line)
    return out


def _section(body: str, name: str) -> str:
    out: list[str] = []
    capturing = False
    for line in body.splitlines():
        if line.startswith("## "):
            capturing = _normalize(line[3:]).startswith(_normalize(name))
            continue
        if capturing:
            out.append(line)
    return "\n".join(out)


def _strip_sections(body: str, names: tuple[str, ...]) -> str:
    out: list[str] = []
    skipping = False
    for line in body.splitlines():
        if line.startswith("## "):
            head = _normalize(line[3:])
            skipping = any(head.startswith(_normalize(n)) for n in names)
            if skipping:
                continue
        if skipping:
            continue
        out.append(line)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).rstrip("\n")
    return text


def _fm_value(fm: str, key: str) -> str | None:
    for line in fm.splitlines():
        m = re.match(rf"^{re.escape(key)}\s*:\s*(.+?)\s*$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


def _dedup(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _is_faq(fm: str) -> bool:
    return _fm_value(fm, "type") == "wiki-faq"


def _managed_lines(prerequisites: list[str], leads_to: list[str]) -> list[str]:
    lines: list[str] = []
    if prerequisites:
        lines.append("prerequisites:")
        lines += [f'  - "[[{x}]]"' for x in prerequisites]
    if leads_to:
        lines.append("leads_to:")
        lines += [f'  - "[[{x}]]"' for x in leads_to]
    return lines


def _rebuild_fm(fm: str, prerequisites: list[str], leads_to: list[str]) -> str:
    """Re-emit frontmatter with managed prerequisites/leads_to, other keys preserved in place.
    Managed block is placed immediately before `aliases:` if present, else at the end."""
    managed = _managed_lines(prerequisites, leads_to)
    out: list[str] = []
    inserted = False
    for key, lines in _fm_blocks(fm):
        if key in ("prerequisites", "leads_to"):
            continue  # drop originals; managed versions re-placed below
        if key == "aliases" and not inserted:
            out += managed
            inserted = True
        out += lines
    if not inserted:
        out += managed
    return "\n".join(out)


def plan_migration(wiki: Path) -> tuple[dict[Path, str], list[str]]:
    """Return (path -> new_text) for files that change, plus a list of warnings."""
    pages: list[tuple[Path, str, str]] = []  # (path, fm, body)
    stem_to_path: dict[str, Path] = {}
    for p in sorted(wiki.rglob("*.md")):
        if "@References" in p.parts or p.name in ("index.md", "log.md"):
            continue
        rel = p.relative_to(wiki)
        if len(rel.parts) == 2 and p.stem == p.parent.name:
            continue  # folder-note
        text = p.read_text(encoding="utf-8", errors="ignore")
        fm, body, had = _frontmatter_and_body(text)
        if not had or not _is_faq(fm):
            continue
        pages.append((p, fm, body))
        stem_to_path.setdefault(p.stem, p)

    # Pass 1: merged prerequisites per page (frontmatter block + body Builds-on section).
    depends: dict[Path, list[str]] = {}
    warnings: list[str] = []
    for p, fm, body in pages:
        fm_dep: list[str] = []
        for key, lines in _fm_blocks(fm):
            if key == "prerequisites":
                fm_dep = _list_from_block(lines)
        body_dep = _links_in(_section(body, "Builds on"))
        depends[p] = _dedup(fm_dep + body_dep)

    # Pass 2: leads_to per page, derived globally from prerequisites (resolve by stem).
    leads: dict[Path, list[str]] = {p: [] for p, _, _ in pages}
    for p, _, _ in pages:
        for link in depends[p]:
            tgt = stem_to_path.get(link)
            if tgt is not None:
                leads[tgt].append(p.stem)
    for p in leads:
        leads[p] = _dedup(leads[p])

    # Asymmetry warnings: a former `## Leads to` link that the prerequisites graph will NOT re-derive
    # (page P claims "leads to X", but X never declared a Builds-on/prerequisites edge back to P), so
    # the back-link is dropped. prerequisites is the authoritative direction.
    for p, fm, body in pages:
        for lt in _links_in(_section(body, "Leads to")):
            if stem_to_path.get(lt) is None:
                continue
            if lt not in leads[p]:
                warnings.append(
                    f"{p.name}: had 'Leads to [[{lt}]]' but [[{lt}]] does not depend_on it "
                    f"— dropped (add prerequisites on the other page if the edge is real)")

    # Build new text for changed files.
    changes: dict[Path, str] = {}
    for p, fm, body in pages:
        new_fm = _rebuild_fm(fm, depends[p], leads[p])
        new_body = _strip_sections(body, REMOVE_SECTIONS)
        new_text = "---\n" + new_fm + "\n---\n" + new_body + "\n"
        old_text = p.read_text(encoding="utf-8", errors="ignore")
        if new_text != old_text:
            changes[p] = new_text
    return changes, warnings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki", help="wiki directory (Notes/📚 Wiki)")
    ap.add_argument("--check", action="store_true", help="dry run — report, write nothing")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return _selftest()
    if not args.wiki:
        ap.error("--wiki is required")
    wiki = Path(args.wiki)
    if not wiki.is_dir():
        print(f"not a directory: {wiki}", file=sys.stderr)
        return 2
    changes, warnings = plan_migration(wiki)
    for w in warnings:
        print(f"WARN  {w}")
    for p in sorted(changes):
        print(f"{'would change' if args.check else 'changed'}  {p.relative_to(wiki)}")
    if not args.check:
        for p, text in changes.items():
            p.write_text(text, encoding="utf-8")
    print(f"\n{len(changes)} file(s) {'to change' if args.check else 'changed'}, "
          f"{len(warnings)} warning(s).")
    return 0


def _selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        wiki = Path(d) / "📚 Wiki"
        amz = wiki / "📦 Past Work" / "Exp"
        amz.mkdir(parents=True)
        # derived page: edges only in the body Builds-on section, none in frontmatter
        derived = amz / "How do I run an A-B test?.md"
        derived.write_text(
            "---\ntitle: How do I run an A-B test?\ntype: wiki-faq\nspace: 📦 Past Work\n"
            "kind: derived\nupdated: 2026-09-16\n---\n\n"
            "# How do I run an A-B test?\n\n**Short answer.** Stratify then test.\n\n"
            "## Answer\nBecause [[How does stratification help?]] establishes X, do Y.\n\n"
            "## Builds on\n\n- [[How does stratification help?]] — assignment.\n\n"
            "## Leads to\n\n_(none yet)_\n\n## Context\n\n> [!context]\n> Synthesis.\n",
            encoding="utf-8")
        # base page it depends on: has aliases, sources; must GAIN a leads_to back-link
        base = amz / "How does stratification help?.md"
        base.write_text(
            "---\ntitle: How does stratification help?\ntype: wiki-faq\nspace: 📦 Past Work\n"
            "kind: base\nupdated: 2026-09-16\nsources:\n  - \"[[Exp Notes]]\"\n"
            "aliases:\n  - stratification\n---\n\n"
            "# How does stratification help?\n\n**Short answer.** It bins first.\n\n"
            "## Answer\nBins reduce variance. — [[Exp Notes]] (base)\n\n"
            # reciprocated (the A-B page builds on this) → re-derived, no warning
            "## Leads to\n\n- [[How do I run an A-B test?]]\n"
            # NOT reciprocated (the metrics page never builds on this) → dropped, warns
            "- [[Which metric should I pick?]]\n",
            encoding="utf-8")
        orphan = amz / "Which metric should I pick?.md"
        orphan.write_text(
            "---\ntitle: Which metric should I pick?\ntype: wiki-faq\nspace: 📦 Past Work\n"
            "kind: base\nupdated: 2026-09-16\nsources:\n  - \"[[Exp Notes]]\"\n---\n\n"
            "# Which metric should I pick?\n\n**Short answer.** Pick one. — [[Exp Notes]]\n",
            encoding="utf-8")

        changes, warnings = plan_migration(wiki)
        # exactly one asymmetry warning: the non-reciprocated Leads-to, not the reciprocated one
        assert len(warnings) == 1, warnings
        assert "Which metric should I pick?" in warnings[0], warnings
        assert "How do I run an A-B test?" not in warnings[0], (
            "a reciprocated Leads-to is re-derived and must NOT warn")
        assert orphan not in changes, "page with no edges either way should be untouched"
        assert derived in changes, "derived page should change"
        assert base in changes, "base page should gain leads_to"
        dtext = changes[derived]
        btext = changes[base]

        # derived: edge lifted to frontmatter, body sections gone
        assert "prerequisites:\n  - \"[[How does stratification help?]]\"" in dtext, dtext
        assert "## Builds on" not in dtext and "## Leads to" not in dtext, dtext
        assert "## Answer" in dtext and "## Context" in dtext, dtext
        assert "— assignment." not in dtext, "gloss must be dropped"

        # base: leads_to back-link derived globally, placed BEFORE aliases, sources kept
        assert "leads_to:\n  - \"[[How do I run an A-B test?]]\"" in btext, btext
        assert btext.index("leads_to:") < btext.index("aliases:"), "leads_to before aliases"
        assert "sources:" in btext and "[[Exp Notes]]" in btext, "sources preserved"
        assert "aliases:" in btext and "stratification" in btext, "aliases preserved"

        # idempotent: apply, then re-plan → no further changes
        for p, t in changes.items():
            p.write_text(t, encoding="utf-8")
        changes2, _ = plan_migration(wiki)
        assert not changes2, f"second run should be a no-op: {list(changes2)}"

        # render-safety: single frontmatter block, first body line is the H1
        fm, body, had = _frontmatter_and_body(derived.read_text(encoding="utf-8"))
        assert had and body.lstrip().startswith("# How do I run an A-B test?"), body[:40]

        print("migrate_frontmatter_links selftest: OK "
              "(lift edges + global leads_to + strip sections + idempotent + render-safe)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
