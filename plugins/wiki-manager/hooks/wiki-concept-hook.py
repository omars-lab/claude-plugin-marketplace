#!/usr/bin/env python3
"""Stop hook: link concepts to wiki articles, and keep the concept map fresh.

Advisory, mechanical, tenet-clean (no regex for intent detection). It NEVER
decides what a note *means* and never mutates a note — it surfaces two things and
lets Claude do the real work:

  1. CONCEPT LINKS — a wiki article can declare `aliases:` in its frontmatter: the
     short surface terms by which its concept is mentioned in prose (e.g. an article
     titled "How should RAG be implemented on Bedrock?" declares alias "RAG"). This
     hook builds a registry {alias|title -> article} from the live wiki, then scans
     the plain-text notes Claude wrote this turn for any registry term that appears
     VERBATIM but is not already inside a `[[wikilink]]`. Each hit is reported as a
     candidate link. Claude judges whether the mention really is that concept and
     adds `[[the article title]]` — the intent call stays with Claude. Matching is a
     mechanical word-boundary match of a Claude-authored vocabulary, nothing more.

  2. STALE MAP — if any wiki article changed this turn, the generated concept map
     (🗺️ Concept Map.md) is now out of date. The hook reports the exact command to
     regenerate it (wiki_map.py). It does not run it.

Both are reported via a single `{"decision":"block","reason":...}` nudge, deduped by
content hash within a TTL so an unchanged nudge never re-fires (no Stop loop).

Safe everywhere: no-op unless the cwd is a NotePlan vault with a Notes/📚 Wiki/.
Opt out per repo with .claude/hooks/wiki-inbox.conf → CONCEPT_LINKS=0.
Standard library only. Always exits 0.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(os.path.dirname(os.path.abspath(__file__))).parent / "bin"))
from check_verdicts import is_article  # noqa: E402  (shared "what counts as an article" rule)

WIKI_REL = "Notes/📚 Wiki"
MAP_REL = "Notes/📚 Wiki/🗺️ Concept Map.md"
CONF_REL = ".claude/hooks/wiki-inbox.conf"
DEDUP_TTL_SECS = 3600.0
MAX_CANDIDATES = 12
WIKILINK_RE = re.compile(r"\[\[[^\]]*\]\]")

WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}


# ---------------------------------------------------------------------------
# vault / config / transcript
# ---------------------------------------------------------------------------
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
    """Collect file_paths of Write/Edit/MultiEdit tool_use blocks in the transcript."""
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


# ---------------------------------------------------------------------------
# concept registry (built from the live wiki)
# ---------------------------------------------------------------------------
def _frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return ""
    lines = text.splitlines()
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i])
    return ""


def _fm_value(fm: str, key: str) -> str | None:
    for line in fm.splitlines():
        m = re.match(rf"^{re.escape(key)}\s*:\s*(.+?)\s*$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


def _fm_list(fm: str, key: str) -> list[str]:
    """Read a simple YAML list: `key:` then `  - item` lines (item may be quoted)."""
    items: list[str] = []
    in_block = False
    for line in fm.splitlines():
        if re.match(rf"^{re.escape(key)}\s*:\s*$", line):
            in_block = True
            continue
        if in_block:
            if line and not line[0].isspace():
                break
            m = re.match(r"^\s*-\s*(.+?)\s*$", line)
            if m:
                items.append(m.group(1).strip().strip('"').strip("'"))
    return items


def build_registry(wiki: Path) -> dict[str, str]:
    """Map a lowercased surface term -> the article title it links to.

    Terms are each article's declared `aliases:` plus its full title. Aliases are the
    workhorse (a bare full-question title rarely appears verbatim in prose); the title
    is included so an exact quote of the question still links. @-folders (templates)
    and structural notes (map/index/log/space-index) are skipped."""
    reg: dict[str, str] = {}
    for p in sorted(wiki.rglob("*.md")):
        rel = p.relative_to(wiki).parts
        if len(rel) < 2 or rel[0].startswith("@"):
            continue  # hub/log/map at root, or template folders
        text = p.read_text(encoding="utf-8", errors="replace")
        fm = _frontmatter(text)
        if _fm_value(fm, "type") != "wiki-faq":
            continue
        title = _fm_value(fm, "title") or p.stem
        terms = _fm_list(fm, "aliases") + [title]
        for t in terms:
            t = t.strip()
            if len(t) >= 3:  # skip noise-length terms
                reg.setdefault(t.casefold(), title)
    return reg


def _body(text: str) -> str:
    return text[len(_frontmatter(text)) + 8:] if text.startswith("---") else text


def find_candidates(note_text: str, registry: dict[str, str]) -> list[tuple[str, str]]:
    """Registry terms appearing verbatim in the note body but NOT already wikilinked.
    Returns [(matched term, target article title)]. Mechanical word-boundary match."""
    stripped = WIKILINK_RE.sub(" ", _body(note_text))  # remove existing links first
    low = stripped.casefold()
    hits: list[tuple[str, str]] = []
    seen: set[str] = set()
    for term, target in registry.items():
        if term in seen:
            continue
        # word-boundary exact match of the literal term (case-insensitive)
        if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", low):
            hits.append((term, target))
            seen.add(term)
    return hits


# ---------------------------------------------------------------------------
# dedup (content-hash TTL, like the vault's noteplan-check)
# ---------------------------------------------------------------------------
def _dedup_path() -> Path:
    return Path(os.path.dirname(os.path.abspath(__file__))) / "concept-hook-triggers.jsonl"


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


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def _mtime(path: str) -> float:
    try:
        return os.stat(path).st_mtime
    except OSError:
        return 0.0


def _build_reason(vault: Path, written: set[str]) -> str | None:
    wiki = vault / WIKI_REL
    parts: list[str] = []

    # (2) stale map — a wiki ARTICLE was written AND is newer than the map itself.
    # `written` is cumulative over the whole transcript, so a bare "was it written?"
    # test stays true for the rest of a session once any article is edited and would
    # re-fire this nudge on every Stop. The mtime guard scopes it to genuine staleness:
    # once the map is regenerated it becomes the newest file, so no written article
    # outranks it and the nudge stops — while a fresh edit after regeneration (newer
    # than the map) correctly re-triggers it.
    #
    # "Article" is `is_article` from bin/check_verdicts.py — the same `type: wiki-faq` test
    # wiki_map.py projects — and NOT a list of filename suffixes. The suffix version excluded
    # only the map, index.md and log.md, so writing a template, a space folder-note or (fatally,
    # once verdicts became the main workflow) a VERDICT nudged about a map those files cannot
    # affect. Sharing the predicate means the hook can only fire on a write that could really
    # have changed the graph.
    map_mtime = _mtime(str(vault / MAP_REL))
    wiki = vault / WIKI_REL
    wiki_changed = any(
        WIKI_REL in p and _mtime(p) > map_mtime and is_article(Path(p), wiki)
        for p in written
    )
    if wiki_changed:
        parts.append(
            "Wiki articles changed — the 🗺️ Concept Map is now stale. Regenerate it: "
            "python3 \"${CLAUDE_PLUGIN_ROOT}/bin/wiki_map.py\" --wiki \"Notes/📚 Wiki\" "
            "--out \"Notes/📚 Wiki/🗺️ Concept Map.md\" "
            "(renders inline images when $WIKI_PLANTUML_SERVER is set to a PlantUML "
            "server you control; source fences otherwise)"
        )

    # (1) concept links — scan written NON-wiki notes for verbatim concept mentions
    note_paths = [
        p for p in written
        if p.endswith(".md") and "/Notes/" in p and WIKI_REL not in p
        and "/@Templates/" not in p and "/@Trash/" not in p and "/@Archive/" not in p
    ]
    if note_paths:
        registry = build_registry(wiki)
        if registry:
            candidates: list[str] = []
            for p in note_paths:
                try:
                    text = Path(p).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for term, target in find_candidates(text, registry):
                    candidates.append(f"{os.path.basename(p)}: “{term}” → [[{target}]]")
            if candidates:
                shown = candidates[:MAX_CANDIDATES]
                more = len(candidates) - len(shown)
                tail = f" (+{more} more)" if more > 0 else ""
                parts.append(
                    "Notes mention wiki concepts that aren't linked yet — consider adding "
                    "the [[wikilink]] where the mention really is that concept: "
                    + "; ".join(shown) + tail
                )

    return " | ".join(parts) if parts else None


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
    if _conf(vault).get("CONCEPT_LINKS", "1") == "0":
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
        wiki = Path(d) / "📚 Wiki"
        (wiki / "📦 Past Work").mkdir(parents=True)
        (wiki / "📦 Past Work" / "rag.md").write_text(
            "---\ntitle: How should RAG be implemented on Bedrock?\n"
            "type: wiki-faq\naliases:\n  - RAG\n  - retrieval-augmented generation\n---\n\n# x\n",
            encoding="utf-8")
        (wiki / "📦 Past Work" / "guard.md").write_text(
            "---\ntitle: How do Bedrock Guardrails protect an LLM application?\n"
            "type: wiki-faq\naliases:\n  - Bedrock Guardrails\n---\n\n# x\n", encoding="utf-8")
        (wiki / "index.md").write_text("---\ntitle: 📚 Wiki\ntype: wiki-hub\n---\n\n# x\n", encoding="utf-8")

        reg = build_registry(wiki)
        assert "rag" in reg and reg["rag"] == "How should RAG be implemented on Bedrock?", reg
        assert "bedrock guardrails" in reg, reg
        assert "📚 wiki" not in reg, "hub leaked into registry"

        # a note that mentions RAG (unlinked) and Bedrock Guardrails (already linked)
        note = ("We set up a RAG pipeline today. Storage was fine. "
                "See [[How do Bedrock Guardrails protect an LLM application?]] for guardrails.")
        cands = dict(find_candidates(note, reg))
        assert "rag" in cands, f"RAG should be a candidate: {cands}"
        # 'Bedrock Guardrails' appears only inside a wikilink -> must NOT be a candidate
        assert "bedrock guardrails" not in cands, f"already-linked term leaked: {cands}"
        # word-boundary: 'RAG' must not match inside 'storage'
        assert not find_candidates("storage only, no acronym here", reg), "substring false match"

        # stale-map detection
        r = _build_reason(Path("/nope"), set())  # no writes -> no reason path exercised below
        assert r is None

        # stale-map mtime guard: a written article only counts as stale-making when it
        # is newer than the map. Build a vault-shaped tree so vault/WIKI_REL resolves.
        vault = Path(d) / "vault"
        vwiki = vault / WIKI_REL
        (vwiki / "📦 Past Work").mkdir(parents=True)
        art = vwiki / "📦 Past Work" / "rag.md"
        art.write_text("---\ntitle: q\ntype: wiki-faq\n---\n\n# x\n", encoding="utf-8")
        vmap = vault / MAP_REL
        vmap.write_text("# 🗺️ Concept Map\n", encoding="utf-8")
        written = {str(art)}
        # article older than map -> NOT stale (this is the post-regeneration case)
        os.utime(art, (1000, 1000))
        os.utime(vmap, (2000, 2000))
        assert _build_reason(vault, written) is None, "map newer than article must not flag stale"
        # article newer than map -> stale (a fresh edit after the last regeneration)
        os.utime(vmap, (1000, 1000))
        os.utime(art, (2000, 2000))
        r2 = _build_reason(vault, written)
        assert r2 is not None and "Concept Map is now stale" in r2, r2

        # REGRESSION: only a real ARTICLE may flag the map stale. These four are all under the
        # wiki, all newer than the map, and none of them can change the graph — the map projects
        # `type: wiki-faq` pages. The pre-0.6.1 suffix test excluded only the map, index.md and
        # log.md, so every one of these nudged; the verdict especially, which made writing a
        # verdict (the main workflow now) always fire a spurious map nudge.
        verdict = vwiki / "@References" / "@Verdicts" / "📦 Past Work" / "rag.md"
        verdict.parent.mkdir(parents=True)
        verdict.write_text("---\nof_page: \"[[q]]\"\npage_hash: abc\n---\n\n# v\n", encoding="utf-8")
        template = vwiki / "@References" / "article.md"
        template.write_text("---\ntitle: t\ntype: wiki-faq\n---\n\n# t\n", encoding="utf-8")
        folder_note = vwiki / "📦 Past Work" / "📦 Past Work.md"
        folder_note.write_text("---\ntitle: 📦 Past Work\ntype: wiki-space-index\n---\n\n# a\n", encoding="utf-8")
        raw_note = vwiki / "📦 Past Work" / "scratch.md"      # under the wiki but not an FAQ page
        raw_note.write_text("# just a note\n", encoding="utf-8")
        for p in (verdict, template, folder_note, raw_note):
            os.utime(p, (3000, 3000))                       # newer than BOTH map and article
            assert _build_reason(vault, {str(p)}) is None, f"non-article flagged the map stale: {p}"
        # and a real article among them still does flag it
        assert _build_reason(vault, {str(verdict), str(art)}) is not None, "article missed"

        print("wiki-concept-hook selftest: OK (registry + candidate match + boundaries + "
              "stale mtime guard + article-only map nudge)")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    raise SystemExit(main())
