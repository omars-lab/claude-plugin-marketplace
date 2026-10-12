#!/usr/bin/env python3
"""Rename the `depends_on:` frontmatter key to `prerequisites:`.

`depends_on` sounded like a claim about where a page's facts came from, so it collided with
`kind:`. The template said a `base` page (grounded directly in raw notes) must "drop depends_on",
and 31 pages quietly ignored that, because on those pages both things are true at once:

    kind: base                                     <- the facts were read off a raw note
    sources:
      - "[[LLM Model consumption]]"
    depends_on:                                    <- and you still need this one first
      - "[[How is model availability and resilience handled on Bedrock?]]"

Nothing was wrong with those pages. The key was named for the wrong question. `kind:` answers
*where the facts come from*; this key answers *what a reader must already understand*. They are
independent, and a name that says so ends the collision without deleting a single real edge:

    prerequisites:
      - "[[How is model availability and resilience handled on Bedrock?]]"

`leads_to:` keeps its name — it is still the mirror ("these questions build on this one"), and it
already reads as prose rather than as schema.

This is a pure key rename inside the frontmatter block. Values, ordering, indentation, body and
every other key are untouched, so it cannot change the graph: the same edges come out, under a
name that describes them. Only the FIRST `---` block is in scope; a `depends_on:` that appears in
body prose or inside a fenced code block is left alone, because there it is being quoted or
explained, not declared.

Usage:
  migrate_prereq_key.py --wiki "Notes/📚 Wiki" --check     # dry run: which files, how many keys
  migrate_prereq_key.py --wiki "Notes/📚 Wiki" --apply
  migrate_prereq_key.py --selftest
Standard library only.
"""
from __future__ import annotations

import argparse
import re
import tempfile
from pathlib import Path

OLD_KEY = "depends_on"
NEW_KEY = "prerequisites"

# Unlike the attribution migration, this one is NOT limited to `wiki-faq`. The key is read by
# check_evidence.py and wiki_map.py from any page that declares it, so any page that declares it
# has to be renamed in the same pass or the edge silently disappears from the graph.
SKIP_DIRS = ("@References",)

# A frontmatter key line: the key at column 0, optional spaces, a colon. Anchored and column-0 so
# a list ITEM mentioning the word, or a nested key, can never match.
_KEY_LINE = re.compile(rf"^{OLD_KEY}(\s*):", re.MULTILINE)


def _split(text: str) -> tuple[str, str]:
    """Return (frontmatter, rest). Frontmatter excludes the `---` fences."""
    if not text.startswith("---"):
        return "", text
    parts = text.split("---", 2)
    return (parts[1], parts[2]) if len(parts) == 3 else ("", text)


def rename_text(text: str) -> tuple[str, int]:
    """Rename the key in the frontmatter block only. Returns (new_text, keys_renamed)."""
    fm, body = _split(text)
    if not fm:
        return text, 0
    new_fm, n = _KEY_LINE.subn(rf"{NEW_KEY}\1:", fm)
    if not n:
        return text, 0
    return f"---{new_fm}---{body}", n


def _pages(wiki: Path):
    for p in sorted(wiki.rglob("*.md")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def migrate(wiki: Path, apply: bool) -> dict:
    files: list[tuple[str, int]] = []
    keys = 0
    for p in _pages(wiki):
        text = p.read_text(encoding="utf-8")
        new, n = rename_text(text)
        if n:
            files.append((str(p.relative_to(wiki)), n))
            keys += n
            if apply:
                p.write_text(new, encoding="utf-8")
    return {"files": files, "keys": keys}


def _report(r: dict, apply: bool) -> None:
    verb = "renamed" if apply else "would rename"
    print(f"{verb} {OLD_KEY}: -> {NEW_KEY}: in {len(r['files'])} file(s), {r['keys']} key(s)")
    for name, n in r["files"]:
        print(f"   · {name}" + (f"  ({n} keys)" if n > 1 else ""))


def _selftest() -> None:
    # 1. the key is renamed, its list items untouched
    src = ('---\ntitle: Q\ntype: wiki-faq\nkind: base\ndepends_on:\n  - "[[A]]"\n  - "[[B]]"\n'
           'leads_to:\n  - "[[C]]"\n---\n\n# Q\n')
    out, n = rename_text(src)
    assert n == 1, n
    assert 'prerequisites:\n  - "[[A]]"\n  - "[[B]]"' in out, out
    assert "depends_on" not in out, out
    assert 'leads_to:\n  - "[[C]]"' in out, out

    # 2. the body is never touched — a page that EXPLAINS the key keeps its prose verbatim
    src = ('---\ntitle: Q\ndepends_on:\n  - "[[A]]"\n---\n\n'
           "# Q\n\nThe `depends_on:` key is how an edge is declared.\n")
    out, n = rename_text(src)
    assert n == 1, n
    assert "The `depends_on:` key is how an edge is declared." in out, out
    assert out.count("depends_on") == 1, out

    # 3. a page without the key is byte-identical (so --apply is safe to run over the whole wiki)
    src = '---\ntitle: Q\nkind: base\nsources:\n  - "[[note]]"\n---\n\n# Q\n'
    out, n = rename_text(src)
    assert out == src and n == 0, (out, n)

    # 4. no frontmatter at all: untouched
    src = "# Just a note\n\ndepends_on: not frontmatter\n"
    out, n = rename_text(src)
    assert out == src and n == 0, (out, n)

    # 5. idempotent — a second pass finds nothing
    src = '---\ntitle: Q\ndepends_on:\n  - "[[A]]"\n---\n\n# Q\n'
    once, _ = rename_text(src)
    twice, n = rename_text(once)
    assert twice == once and n == 0, (twice, n)

    # 6. an empty-list form (`depends_on: []`) renames too — it is still the key
    src = "---\ntitle: Q\ndepends_on: []\n---\n\n# Q\n"
    out, n = rename_text(src)
    assert n == 1 and "prerequisites: []" in out, out

    # 7. a list ITEM that happens to contain the word is not a key
    src = '---\ntitle: Q\nsources:\n  - "[[depends_on explained]]"\n---\n\n# Q\n'
    out, n = rename_text(src)
    assert out == src and n == 0, (out, n)

    # 8. end to end over a directory, @References skipped
    with tempfile.TemporaryDirectory() as td:
        wiki = Path(td)
        (wiki / "🌐 General").mkdir(parents=True)
        (wiki / "@References").mkdir()
        a = wiki / "🌐 General" / "Q.md"
        a.write_text('---\ntitle: Q\ndepends_on:\n  - "[[A]]"\n---\n\n# Q\n', encoding="utf-8")
        ref = wiki / "@References" / "article.md"
        ref_src = '---\ntitle: T\ndepends_on:\n  - "[[X]]"\n---\n'
        ref.write_text(ref_src, encoding="utf-8")
        r = migrate(wiki, apply=False)
        assert r["keys"] == 1 and len(r["files"]) == 1, r
        assert a.read_text(encoding="utf-8").count("depends_on") == 1, "check must not write"
        r = migrate(wiki, apply=True)
        assert "prerequisites:" in a.read_text(encoding="utf-8")
        assert ref.read_text(encoding="utf-8") == ref_src, "@References is out of scope"

    print("selftest OK")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--wiki", type=Path)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
        return 0
    if not a.wiki:
        ap.error("--wiki is required (or use --selftest)")
    if a.apply == a.check:
        ap.error("pass exactly one of --check or --apply")
    _report(migrate(a.wiki, apply=a.apply), apply=a.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
