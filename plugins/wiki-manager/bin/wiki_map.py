#!/usr/bin/env python3
"""Render the wiki as PlantUML — a hybrid of a hierarchy mindmap and a concept graph.

This is a MECHANICAL projection of structure that already exists in the notes, not a
judge of meaning (repo tenet: no regex for intent detection). It reads only structured
frontmatter and folder layout — `type:`, `space:`, `kind:`, `prerequisites:` — and emits
two PlantUML blocks:

  1. HIERARCHY (@startmindmap) — the full table of contents as a tree:
        📚 Wiki → <space> → <topic subfolder> → <article question>
     A mindmap is a strict tree, so it shows how articles are *grouped*, not how they
     depend on each other. This is the dense view today (every article appears once).

  2. INTERCONNECTION (@startuml) — the real concept graph: one arrow per `prerequisites:`
     edge (derived answer → the prerequisite it builds on), grouped into `package`s by
     space. Only articles that participate in an edge appear here. This is sparse now
     and grows as more derived answers are written.

The default output is a complete, render-safe NotePlan note (frontmatter title == H1,
an auto-generated banner, both blocks in ```plantuml fences) so a hook can overwrite it
wholesale on every wiki write. Use --stdout to preview, --selftest to self-check.

Usage:
  wiki_map.py --wiki "Notes/📚 Wiki" --out "Notes/📚 Wiki/🗺️ Concept Map.md"
  wiki_map.py --wiki "Notes/📚 Wiki" --stdout
  wiki_map.py --wiki "Notes/📚 Wiki" --scope "🌐 General" --stdout
  wiki_map.py --selftest

Standard library only.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")


# ---------------------------------------------------------------------------
# PlantUML text encoding (deflate + PlantUML's base64 variant)
# ---------------------------------------------------------------------------
# Lets a PlantUML *server* render a diagram from a GET URL: /png/<encoded>. Used
# only to point `![](…)` at a server the user controls (e.g. a private studio
# host on their own Tailscale/LAN) — never at a public one — so the diagram
# content (article titles across spaces) stays on the user's own infrastructure.
def _encode6bit(b: int) -> str:
    if b < 10:
        return chr(48 + b)          # 0-9
    b -= 10
    if b < 26:
        return chr(65 + b)          # A-Z
    b -= 26
    if b < 26:
        return chr(97 + b)          # a-z
    b -= 26
    if b == 0:
        return "-"
    if b == 1:
        return "_"
    return "?"


def _append3bytes(b1: int, b2: int, b3: int) -> str:
    c1 = b1 >> 2
    c2 = ((b1 & 0x3) << 4) | (b2 >> 4)
    c3 = ((b2 & 0xF) << 2) | (b3 >> 6)
    c4 = b3 & 0x3F
    return (_encode6bit(c1 & 0x3F) + _encode6bit(c2 & 0x3F)
            + _encode6bit(c3 & 0x3F) + _encode6bit(c4 & 0x3F))


def plantuml_encode(text: str) -> str:
    """Encode PlantUML source the way a PlantUML server expects in /png/<x>."""
    comp = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)  # raw deflate
    data = comp.compress(text.encode("utf-8")) + comp.flush()
    out: list[str] = []
    for i in range(0, len(data), 3):
        b1 = data[i]
        b2 = data[i + 1] if i + 1 < len(data) else 0
        b3 = data[i + 2] if i + 2 < len(data) else 0
        out.append(_append3bytes(b1, b2, b3))
    return "".join(out)


def _image_url(server: str, source: str, fmt: str = "png") -> str:
    """Build a `<server>/<fmt>/<encoded>` URL. `server` may include the context
    path (e.g. http://host:8080/plantuml); a trailing slash is tolerated."""
    return f"{server.rstrip('/')}/{fmt}/{plantuml_encode(source)}"


# ---------------------------------------------------------------------------
# small, self-contained readers (same idioms as check_evidence.py)
# ---------------------------------------------------------------------------
def _iter_md(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.md") if p.is_file())


def _frontmatter_and_body(text: str) -> tuple[str, str]:
    """Split a leading `---`-fenced frontmatter block from the body. Lenient:
    if there is no closing fence the whole text is treated as body."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    return "", text


def _fm_value(fm: str, key: str) -> str | None:
    for line in fm.splitlines():
        m = re.match(rf"^{re.escape(key)}\s*:\s*(.+?)\s*$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


def _space_of(path: Path, wiki_dir: Path) -> str | None:
    """The space is the FIRST folder under the wiki root — the compartment boundary."""
    try:
        rel = path.relative_to(wiki_dir)
    except ValueError:
        return None
    parts = rel.parts
    return parts[0] if len(parts) > 1 else None


def _topic_of(path: Path, wiki_dir: Path) -> str | None:
    """The topic is the subfolder under the space, if any (space/<topic>/article.md)."""
    try:
        rel = path.relative_to(wiki_dir)
    except ValueError:
        return None
    parts = rel.parts
    return parts[1] if len(parts) > 2 else None


def _prerequisite_targets(fm: str) -> list[str]:
    """The prerequisite titles named in the `prerequisites:` frontmatter block."""
    targets: list[str] = []
    in_dep = False
    for line in fm.splitlines():
        if re.match(r"^prerequisites\s*:", line):
            in_dep = True
            continue
        if in_dep:
            if line and not line[0].isspace():
                break  # a new top-level key ends the block
            for m in WIKILINK_RE.finditer(line):
                targets.append(m.group(1).strip())
    return targets


# ---------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------
class Article:
    __slots__ = ("title", "space", "topic", "kind", "deps")

    def __init__(self, title, space, topic, kind, deps):
        self.title = title
        self.space = space
        self.topic = topic
        self.kind = kind
        self.deps = deps  # list of prerequisite titles (raw)


def _general_first(space: str) -> tuple[int, str]:
    """Sort key: the public floor (name ends in 'General') sorts first, rest alpha."""
    toks = _normalize(space).split()
    return (0 if toks and toks[-1] == "general" else 1, _normalize(space))


def collect(wiki_dir: Path, scope: str | None = None) -> list[Article]:
    arts: list[Article] = []
    for p in _iter_md(wiki_dir):
        fm, _ = _frontmatter_and_body(p.read_text(encoding="utf-8", errors="replace"))
        if not fm or _fm_value(fm, "type") != "wiki-faq":
            continue  # only question articles; skips hub/log/indexes/templates
        space = _space_of(p, wiki_dir)
        if space is None:
            continue
        if space.startswith("@"):
            continue  # @References/@Archive/… are structural (templates), not spaces
        if scope and _normalize(space) != _normalize(scope):
            continue
        title = _fm_value(fm, "title") or p.stem
        arts.append(Article(
            title=title,
            space=space,
            topic=_topic_of(p, wiki_dir),
            kind=(_fm_value(fm, "kind") or "base").strip(),
            deps=_prerequisite_targets(fm),
        ))
    return arts


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------
def _is_emoji_cp(cp: int) -> bool:
    """Codepoints a PlantUML server's default font can't draw (shows tofu). Kept
    off the ASCII/text-punctuation ranges so only real pictographs are rewritten."""
    return (
        0x1F000 <= cp <= 0x1FAFF        # the SMP emoji/pictograph blocks
        or 0x2600 <= cp <= 0x27BF       # misc symbols + dingbats (☕ ⚙ ♻ …)
        or 0x2B00 <= cp <= 0x2BFF       # misc symbols and arrows (⭐ …)
        or 0x1F1E6 <= cp <= 0x1F1FF     # regional indicators (flags)
    )


def _emojify(text: str) -> str:
    """Rewrite emoji to PlantUML's native `<:HEX:>` syntax so a server renders them
    as color OpenMoji glyphs instead of tofu boxes (its font lacks the glyph, and
    Java2D can't reliably draw a color-emoji font even if one is installed). Variation
    selectors / ZWJ / skin-tone modifiers are dropped — the wiki's labels use simple
    single emoji; a ZWJ sequence would degrade to its base glyph, not crash."""
    skip = {0xFE0F, 0xFE0E, 0x200D}
    out: list[str] = []
    for ch in text:
        cp = ord(ch)
        if cp in skip or 0x1F3FB <= cp <= 0x1F3FF:  # selector / ZWJ / skin tone
            continue
        out.append(f"<:{cp:X}:>" if _is_emoji_cp(cp) else ch)
    return "".join(out)


def render_mindmap(arts: list[Article], emoji: bool = False) -> str:
    """The hierarchy: 📚 Wiki → space → topic → article, as an OrgMode mindmap.

    `emoji=True` rewrites emoji to PlantUML `<:HEX:>` (for server rendering); leave
    it False for the raw source fence, where `<:HEX:>` would show as literal text."""
    e = _emojify if emoji else (lambda s: s)
    lines = ["@startmindmap", f"* {e('📚 Wiki')}"]
    by_space: dict[str, list[Article]] = {}
    for a in arts:
        by_space.setdefault(a.space, []).append(a)
    for space in sorted(by_space, key=_general_first):
        lines.append(f"** {e(space)}")
        group = by_space[space]
        by_topic: dict[str, list[Article]] = {}
        for a in group:
            by_topic.setdefault(a.topic or "", []).append(a)
        # topics (named subfolders) first, then any ungrouped articles at the space level
        for topic in sorted((t for t in by_topic if t), key=_normalize):
            lines.append(f"*** {e(topic)}")
            for a in sorted(by_topic[topic], key=lambda a: _normalize(a.title)):
                lines.append(f"**** {_mm_label(a.title, emoji)}")
        for a in sorted(by_topic.get("", []), key=lambda a: _normalize(a.title)):
            lines.append(f"*** {_mm_label(a.title, emoji)}")
    lines.append("@endmindmap")
    return "\n".join(lines)


def _mm_label(title: str, emoji: bool = False) -> str:
    """A mindmap node label: keep the full question, but neutralize a leading `*`/`+`/`-`
    (OrgMode depth/side markers) and collapse whitespace."""
    t = re.sub(r"\s+", " ", title).strip()
    t = ("=" + t) if t[:1] in "*+-" else t
    return _emojify(t) if emoji else t


def _wrap(text: str, width: int = 30) -> str:
    """Word-wrap for a graph node label using PlantUML's `\\n`."""
    out, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return "\\n".join(out)


def render_graph(arts: list[Article], emoji: bool = False) -> str:
    """The interconnection: one arrow per prerequisite edge, grouped by space package.

    `emoji=True` rewrites emoji to PlantUML `<:HEX:>` (for server rendering)."""
    e = _emojify if emoji else (lambda s: s)
    by_title = {_normalize(a.title): a for a in arts}
    # Build edges (derived -> prerequisite); collect the nodes that participate.
    edges: list[tuple[str, str]] = []
    participating: set[str] = set()
    dangling: list[tuple[str, str]] = []  # (source title, unresolved target text)
    for a in arts:
        for dep in a.deps:
            tgt = by_title.get(_normalize(dep))
            if tgt is None:
                dangling.append((a.title, dep))
                continue
            edges.append((a.title, tgt.title))
            participating.add(_normalize(a.title))
            participating.add(_normalize(tgt.title))

    lines = ["@startuml", "left to right direction", "skinparam componentStyle rectangle",
             "skinparam rectangle {", "  BackgroundColor #FEFEFE", "  BorderColor #888",
             "}", ""]
    if not edges:
        lines.append("' No prerequisite edges yet — every article stands on its own.")
        lines.append("' The concept graph appears here as derived answers are written.")
        lines.append("@enduml")
        return "\n".join(lines)

    # stable alias per participating article
    alias: dict[str, str] = {}
    for i, norm in enumerate(sorted(participating)):
        alias[norm] = f"n{i}"

    # group nodes into space packages
    node_space: dict[str, str] = {}
    for a in arts:
        if _normalize(a.title) in participating:
            node_space[_normalize(a.title)] = a.space
    by_pkg: dict[str, list[str]] = {}
    for norm, space in node_space.items():
        by_pkg.setdefault(space, []).append(norm)
    label = {_normalize(a.title): a.title for a in arts}
    for space in sorted(by_pkg, key=_general_first):
        lines.append(f'package "{e(space)}" {{')
        for norm in sorted(by_pkg[space], key=lambda n: label[n].casefold()):
            lines.append(f'  rectangle "{e(_wrap(label[norm]))}" as {alias[norm]}')
        lines.append("}")
    lines.append("")
    for src, tgt in sorted(edges):
        lines.append(f"{alias[_normalize(src)]} --> {alias[_normalize(tgt)]} : builds on")
    if dangling:
        lines.append("")
        for src, tgt in dangling:
            lines.append(f"' unresolved prerequisite: {src!r} -> {tgt!r}")
    lines.append("@enduml")
    return "\n".join(lines)


TITLE = "🗺️ Concept Map"


def _np_link_quote(s: str) -> str:
    """Percent-encode an attachment path the way NotePlan itself writes one.

    Full UTF-8 percent-encoding, emoji included: `🗺️ Concept Map_attachments` becomes
    `%F0%9F%97%BA%EF%B8%8F%20Concept%20Map_attachments`.

    A path with the emoji left literal *does* render — but NotePlan rewrites the note into
    this canonical form within seconds of the generator writing it, which would make every
    regeneration produce a spurious diff and a stale-map nudge for a map that did not change.
    Emitting the canonical form directly leaves the app nothing to rewrite.
    """
    return urllib.parse.quote(s, safe="/")


def attachments_dirname(out: Path) -> str:
    """NotePlan keeps a note's embedded files in a sibling `<note stem>_attachments/`."""
    return f"{out.stem}_attachments"


def fetch_local_images(server: str, out: Path, sources: dict[str, str]) -> dict[str, str] | None:
    """Download each PlantUML render into the note's `_attachments/` folder.

    Returns {key: relative markdown link}, or None if any fetch failed.

    NotePlan does **not** display a remote `http://` image: macOS App Transport Security
    blocks cleartext loads, so a note pointing at the private studio server renders as an
    empty gap no matter that the URL is valid (`curl` returns the PNG happily). Embedding
    the bytes as a local attachment is the only form the app actually draws — and it has
    the side benefit that the map keeps rendering when the studio box is off the network.
    The ```plantuml source fences stay in the note either way, so nothing is lost if this
    download fails and we fall back to remote URLs.
    """
    adir = out.parent / attachments_dirname(out)
    links: dict[str, str] = {}
    try:
        adir.mkdir(parents=True, exist_ok=True)
        for key, src in sources.items():
            url = _image_url(server, src)
            with urllib.request.urlopen(url, timeout=60) as resp:
                if resp.status != 200:
                    return None
                data = resp.read()
            if not data.startswith(b"\x89PNG"):
                return None            # an error page, not an image
            (adir / f"{key}.png").write_bytes(data)
            links[key] = f"{_np_link_quote(adir.name)}/{key}.png"
    except (urllib.error.URLError, OSError, ValueError):
        return None
    return links


def _img(key: str, alt: str, server: str | None, source: str,
         image_links: dict[str, str] | None) -> str:
    """One `![alt](target)` line — a local attachment when we have one, else the server URL.

    A local attachment is written as `![image](…)`, not with the descriptive `alt`, because
    NotePlan rewrites an embedded image's alt text to the literal word `image` when it
    canonicalizes the note. Keeping the description here would mean the app edits the file
    after every regeneration. The heading directly above each image carries the description
    for a reader, so nothing is actually lost.
    """
    target = (image_links or {}).get(key)
    if target:
        return f"![image]({target})"
    return f"![{alt}]({_image_url(server, source)})"


def render_note(arts: list[Article], scope: str | None = None,
                server: str | None = None,
                image_links: dict[str, str] | None = None) -> str:
    """A complete, render-safe NotePlan note embedding both PlantUML views.

    Without `server`: two ```plantuml source fences (NotePlan shows them as code
    unless a PlantUML renderer is installed). With `server`: the diagrams render
    inline as `![](…)` PNGs served by that PlantUML server, and the source is kept
    below under `## Source` so the note still degrades to text if the server is
    unreachable. `server` should be a host the user controls (see plantuml_encode).

    `image_links` (from `fetch_local_images`) points the `![](…)` at downloaded local
    attachments instead of the server URL — the only form NotePlan actually renders."""
    title = f"{TITLE}" + (f" — {scope}" if scope else "")
    n_edges = sum(len(a.deps) for a in arts)
    # Raw-emoji source for the fences (human-readable fallback); a separate
    # <:HEX:>-emojified source drives the server image so it renders in color.
    mindmap = render_mindmap(arts)
    graph = render_graph(arts)
    mindmap_img = render_mindmap(arts, emoji=True) if server else mindmap
    graph_img = render_graph(arts, emoji=True) if server else graph
    parts = [
        "---",
        f"title: {title}",
        "type: wiki-map",
        "---",
        "",
        f"# {title}",
        "",
        "*Generated by `wiki_map.py` from article frontmatter — edits here are overwritten.*",
        "",
        f"A picture of the wiki: **{len(arts)} articles** across the spaces, with "
        f"**{n_edges} prerequisite edge{'s' if n_edges != 1 else ''}** of interconnection. "
        "The hierarchy mindmap is the table of contents; the graph below it is the "
        "concept map — how derived answers build on their prerequisites.",
        "",
    ]
    if server:
        parts += [
            "## Hierarchy",
            "",
            _img("hierarchy", "Wiki hierarchy — space to topic to article",
                 server, mindmap_img, image_links),
            "",
            "## Interconnection",
            "",
            _img("graph", "Wiki prerequisite graph — what to read first",
                 server, graph_img, image_links),
            "",
            "## Source",
            "",
            "The PlantUML behind both diagrams, so the map still reads as text if the "
            "render server is down.",
            "",
            "```plantuml",
            mindmap,
            "```",
            "",
            "```plantuml",
            graph,
            "```",
            "",
        ]
    else:
        parts += [
            "## Hierarchy",
            "",
            "```plantuml",
            mindmap,
            "```",
            "",
            "## Interconnection",
            "",
            "```plantuml",
            graph,
            "```",
            "",
        ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------
def _selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        wiki = Path(d) / "📚 Wiki"
        (wiki / "🌐 General" / "Debugging").mkdir(parents=True)
        (wiki / "🏢 Work").mkdir(parents=True)

        def w(rel, fm_lines):
            p = wiki / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("---\n" + "\n".join(fm_lines) + "\n---\n\n# x\n", encoding="utf-8")

        w("🌐 General/Debugging/base.md",
          ["title: Why does nginx -t pass but fail?", "type: wiki-faq", "kind: base"])
        w("🌐 General/Debugging/derived.md",
          ["title: Why does .local upstream fail?", "type: wiki-faq", "kind: derived",
           "prerequisites:", '  - "[[Why does nginx -t pass but fail?]]"'])
        w("🌐 General/index.md", ["title: 🌐 General", "type: wiki-space-index"])
        w("🏢 Work/lonely.md", ["title: A standalone work fact?", "type: wiki-faq", "kind: base"])
        # a template in @References carries type: wiki-faq but is NOT a real article
        w("@References/article.md",
          ["title: <The question, phrased as a question?>", "type: wiki-faq", "kind: base"])

        arts = collect(wiki)
        assert len(arts) == 3, f"expected 3 faq articles, got {len(arts)}"
        titles = {a.title for a in arts}
        assert "🌐 General" not in titles, "space index leaked in"
        assert not any(a.space.startswith("@") for a in arts), "@References template leaked in"

        mm = render_mindmap(arts)
        assert mm.startswith("@startmindmap") and mm.endswith("@endmindmap")
        assert "*** Debugging" in mm, "topic subfolder missing"
        assert "**** Why does .local upstream fail?" in mm, "article under topic missing"
        assert "*** A standalone work fact?" in mm, "ungrouped article should sit at space level"
        assert "** 🌐 General" in mm and "** 🏢 Work" in mm

        g = render_graph(arts)
        assert "-->" in g and "builds on" in g, "edge missing from graph"
        assert 'package "🌐 General"' in g, "space package missing"
        # the lonely work fact has no edge -> must NOT appear as a node
        assert "standalone work fact" not in g, "non-participating node leaked into graph"

        # emoji rewriting: raw emoji in source mode, <:HEX:> in server/image mode
        assert "📚 Wiki" in render_mindmap(arts), "source mindmap keeps raw emoji"
        mm_e = render_mindmap(arts, emoji=True)
        assert "<:1F310:>" in mm_e and "📚" not in mm_e, "mindmap emoji not rewritten"
        assert "<:1F310:> General" in mm_e, "space emoji should keep its trailing text"
        g_e = render_graph(arts, emoji=True)
        assert 'package "<:1F310:> General"' in g_e, "graph package emoji not rewritten"
        # text-only labels are untouched; em dash / apostrophes are not emoji
        assert _emojify("t-test or Wilcoxon — really?") == "t-test or Wilcoxon — really?"

        # a wiki with no edges renders the empty-graph note
        w2 = Path(d) / "empty"
        (w2 / "🌐 General").mkdir(parents=True)
        (w2 / "🌐 General" / "a.md").write_text(
            "---\ntitle: A base fact?\ntype: wiki-faq\nkind: base\n---\n\n# x\n", encoding="utf-8")
        g2 = render_graph(collect(w2))
        assert "No prerequisite edges yet" in g2, "empty-graph message missing"

        note = render_note(arts)
        assert note.startswith("---\ntitle: 🗺️ Concept Map\n")
        assert "# 🗺️ Concept Map" in note
        assert "```plantuml" in note
        assert "![" not in note, "no images without a render server"
        # render-safety: title line == H1 text (the vault golden rule)
        assert "3 articles" in note and "1 prerequisite edge" in note

        # PlantUML encoding: a known source round-trips to the documented encoding
        enc = plantuml_encode("@startuml\nBob -> Alice : hello\n@enduml")
        assert enc and all(c.isalnum() or c in "-_" for c in enc), "bad encode alphabet"

        # server mode: images primary, source retained under ## Source
        snote = render_note(arts, server="http://host:8080/plantuml")
        assert "![Wiki hierarchy" in snote and "![Wiki prerequisite graph" in snote
        assert "http://host:8080/plantuml/png/" in snote
        assert "## Source" in snote and "```plantuml" in snote, "source must survive"

        # Local attachments: the only image form NotePlan actually draws. `image_links`
        # must win over the server URL, or the note regresses to an invisible diagram.
        lnote = render_note(arts, server="http://host:8080/plantuml", image_links={
            "hierarchy": "%F0%9F%97%BA%20Map_attachments/hierarchy.png",
            "graph": "%F0%9F%97%BA%20Map_attachments/graph.png",
        })
        assert "_attachments/hierarchy.png)" in lnote, lnote[:400]
        assert "_attachments/graph.png)" in lnote
        assert "http://host:8080/plantuml/png/" not in lnote, \
            "a local attachment must replace the server URL, not sit beside it"
        assert "```plantuml" in lnote, "source fences must survive local images too"

        # Emit NotePlan's canonical form exactly, or the app rewrites the note after every
        # regeneration: alt text is the literal word `image`, path fully percent-encoded.
        assert "![image](%F0%9F%97%BA%20Map_attachments/hierarchy.png)" in lnote, lnote[:400]
        assert "![Wiki hierarchy" not in lnote, "NotePlan replaces a descriptive alt with `image`"
        assert (_np_link_quote("🗺️ Concept Map_attachments")
                == "%F0%9F%97%BA%EF%B8%8F%20Concept%20Map_attachments")
        assert attachments_dirname(Path("/w/🗺️ Concept Map.md")) == "🗺️ Concept Map_attachments"
        # Without local images the descriptive alt still applies (not a NotePlan attachment).
        assert "![Wiki hierarchy — space to topic to article](http://" in snote
        assert "/png//png/" not in snote, "double context path"
        # server mode's ## Source keeps raw emoji (the rendered image carries <:HEX:>)
        assert "* 📚 Wiki" in snote, "source fence under ## Source should stay human-readable"

        print("selftest: PASS (3 articles, mindmap + graph + note + encode + emoji + server all OK)")
        return 0


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Render the wiki as hybrid PlantUML (mindmap + graph).")
    ap.add_argument("--wiki", help="path to the wiki root (the folder holding the spaces)")
    ap.add_argument("--out", help="write a complete render-safe note to this path")
    ap.add_argument("--scope", help="limit to one space (e.g. '🌐 General')")
    ap.add_argument("--render-server", metavar="URL",
                    help="a PlantUML server you control (e.g. http://host:8080/plantuml) — "
                         "render diagrams inline as ![](…) PNGs instead of source fences. "
                         "Falls back to $WIKI_PLANTUML_SERVER. NEVER point this at a public "
                         "server: the URL carries the diagram content (article titles).")
    ap.add_argument("--stdout", action="store_true", help="print the note to stdout instead of writing")
    ap.add_argument("--remote-images", action="store_true",
                    help="point ![](…) at the render server instead of downloading the PNGs "
                         "into <note>_attachments/. NotePlan will NOT display the result "
                         "(App Transport Security blocks cleartext http), so this is for "
                         "publishing the note somewhere other than NotePlan.")
    ap.add_argument("--selftest", action="store_true", help="run built-in tests and exit")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    if not args.wiki:
        ap.error("--wiki is required (or use --selftest)")
    wiki = Path(args.wiki)
    if not wiki.is_dir():
        ap.error(f"wiki root not found: {wiki}")

    server = args.render_server or os.environ.get("WIKI_PLANTUML_SERVER") or None
    arts = collect(wiki, scope=args.scope)

    # Local attachments are the default whenever we are writing a real note, because a
    # remote http image is invisible in NotePlan. Needs `--out`: the attachments folder is
    # named after the note file, so there is nowhere to put the PNGs when printing to stdout.
    image_links = None
    if server and args.out and not args.stdout and not args.remote_images:
        image_links = fetch_local_images(server, Path(args.out), {
            "hierarchy": render_mindmap(arts, emoji=True),
            "graph": render_graph(arts, emoji=True),
        })
        if image_links is None:
            print(f"warning: could not fetch diagrams from {server} — falling back to "
                  f"remote image URLs, which NotePlan will not display. The ```plantuml "
                  f"source fences in the note are unaffected.", file=sys.stderr)

    note = render_note(arts, scope=args.scope, server=server, image_links=image_links)

    if args.out and not args.stdout:
        Path(args.out).write_text(note, encoding="utf-8")
        n_edges = sum(len(a.deps) for a in arts)
        where = "local attachments" if image_links else "remote URLs" if server else "source fences"
        print(f"wrote {args.out} — {len(arts)} articles, {n_edges} edges ({where})")
    else:
        sys.stdout.write(note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
