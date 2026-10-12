#!/usr/bin/env python3
"""Attach a PlantUML diagram to one wiki article, as a local image NotePlan will actually draw.

`wiki_map.py` already does this for the single `🗺️ Concept Map` note. Tenet 3 ("make meaningful
visual diagrams to explain concepts") wants it for *any* article, so the machinery moves here
where it takes a `--page` and a `--puml` instead of being welded to one note.

What it does, in order:

1. Encodes the PlantUML source and asks the **private** server (`--server`, else
   `$WIKI_PLANTUML_SERVER`) for a PNG. Never a public server: the URL carries the diagram's
   content, and wiki content is compartmented.
2. Writes the PNG into the note's sibling `<page stem>_attachments/` folder — the only image
   form NotePlan draws, because macOS ATS silently blocks a cleartext `http://` image.
3. Inserts (or replaces) the image at the **end of the `## Evidence` section**, so the Short
   answer still comes first.
4. Saves the PlantUML source under `@References/@Diagrams/<page path>/<key>.puml`, so the
   diagram can be re-rendered or edited later without it living in the reader's path.

Step 4 does **not** put the source in the note's `_attachments/` folder, which is the obvious
place and does not work: NotePlan garbage-collects any file there that the note does not
reference, within a few seconds of the note being saved. A `.puml` written beside the PNG is
gone before the next command runs. `@References/@Diagrams/` mirrors where verdicts already
live, and `@`-folders are already excluded from the concept map and the evidence checks.

Step 4 is where this deliberately parts ways with `wiki_map.py`, which keeps a ```plantuml
fence in the note under each image. That fence is right for the map — a generated tooling note
nobody reads top-to-bottom — and wrong for an article: twenty lines of mindmap syntax between
the diagram and `## Context` is precisely the wall of text the lean-body tenet exists to
prevent. The usual argument for the fence ("the page still reads if the fetch fails") does not
apply here either, because the PNG is a committed local attachment, not a remote URL. Pass
`--fence` for the old behaviour when a page genuinely wants its source visible.

Re-running with the same `--key` replaces that block in place, so a diagram can be iterated on
without the note collecting copies.

    python3 bin/wiki_diagram.py --page "<article>.md" --puml <src.puml> --key vocabulary
    python3 bin/wiki_diagram.py --page "<article>.md" --puml <src.puml> --check
    python3 bin/wiki_diagram.py --selftest
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_map import (  # noqa: E402  (path juggling has to come first)
    _image_url,
    _np_link_quote,
    attachments_dirname,
    plantuml_encode,
)

FETCH_TIMEOUT = 60.0

# The markers that bracket a managed block. They are HTML comments, which NotePlan *shows*
# — so they are deliberately not used. The block is found structurally instead: the image
# line whose target ends in `<key>.png`, plus the fence that follows it.
IMG_LINE = "![image]({target})"


def log(ev: str, **kw: object) -> None:
    """One structured line per event, to stderr so stdout stays a clean list of written files."""
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    parts = " ".join(f"{k}={v}" for k, v in kw.items())
    print(f"{stamp} pid={os.getpid()} ev={ev} {parts}".rstrip(), file=sys.stderr)


# ---------------------------------------------------------------------------
# locating the insertion point
# ---------------------------------------------------------------------------
def evidence_bounds(lines: list[str]) -> tuple[int, int]:
    """(start, end) line indices of the `## Evidence` section body.

    `start` is the line after the heading; `end` is the index of the next `## ` heading (or
    len(lines)). Raises if the page has no `## Evidence` — that is a page-shape problem the
    caller should hear about rather than a diagram this tool should silently append.
    """
    start = None
    for i, line in enumerate(lines):
        if re.fullmatch(r"##[ \t]+Evidence[ \t]*", line):
            start = i + 1
            break
    if start is None:
        raise ValueError("page has no `## Evidence` heading — fix the page shape first")
    for j in range(start, len(lines)):
        if re.match(r"^##[ \t]+\S", lines[j]):
            return start, j
    return start, len(lines)


def find_block(lines: list[str], start: int, end: int, key: str) -> tuple[int, int] | None:
    """Locate an existing `<key>.png` image + its trailing ```plantuml fence, if present.

    Returns (first, last_exclusive) over the whole block including the fence, so a re-run
    replaces both the picture and the source it was rendered from.
    """
    needle = f"/{key}.png)"
    for i in range(start, end):
        if lines[i].startswith("![") and lines[i].rstrip().endswith(needle):
            j = i + 1
            # skip blanks, then an optional ```plantuml fence
            while j < end and not lines[j].strip():
                j += 1
            if j < end and lines[j].strip().startswith("```plantuml"):
                j += 1
                while j < end and not lines[j].strip().startswith("```"):
                    j += 1
                j += 1                      # the closing fence itself
                return i, j
            return i, i + 1
    return None


def render_block(target: str, source: str, fence: bool = False) -> list[str]:
    """The lines that make up a diagram block: the image, and its source fence only if asked."""
    img = [IMG_LINE.format(target=target)]
    if not fence:
        return img
    return img + ["", "```plantuml", *source.splitlines(), "```"]


def splice(lines: list[str], key: str, target: str, source: str,
           fence: bool = False) -> list[str]:
    """Insert or replace the `<key>` diagram block at the end of `## Evidence`."""
    start, end = evidence_bounds(lines)
    block = render_block(target, source, fence)
    existing = find_block(lines, start, end, key)
    if existing:
        first, last = existing
        return lines[:first] + block + lines[last:]
    tail = end
    while tail > start and not lines[tail - 1].strip():
        tail -= 1                            # append after the last real line, not after blanks
    return lines[:tail] + ["", *block, ""] + lines[tail:]


# ---------------------------------------------------------------------------
# fetching
# ---------------------------------------------------------------------------
def fetch_png(server: str, source: str) -> bytes:
    """Ask the private server to render `source`, returning PNG bytes. Raises on anything else."""
    url = _image_url(server, source)
    log("fetch_start", host=urllib.parse.urlparse(server).netloc, bytes_src=len(source))
    try:
        with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT) as resp:
            if resp.status != 200:
                raise ValueError(f"server returned HTTP {resp.status}")
            data = resp.read()
    except (urllib.error.URLError, OSError) as exc:
        log("fetch_timeout", msg=f'"{exc}"')
        raise ValueError(f"could not reach the PlantUML server: {exc}") from exc
    if not data.startswith(b"\x89PNG"):
        log("fetch_not_png", bytes=len(data))
        raise ValueError("server returned an error page, not a PNG — check the PlantUML source")
    log("fetch_ok", bytes=len(data))
    return data


def source_path(page: Path, key: str) -> Path:
    """Where a diagram's `.puml` lives: `@References/@Diagrams/<page path>/<key>.puml`.

    Not the note's `_attachments/` folder, however natural that looks. NotePlan prunes any file
    there the note does not reference, a few seconds after the note is saved — so a `.puml`
    written beside its PNG is deleted by the very write that attaches the image. The wiki root
    is found by walking up to the folder that holds `@References`; if there is none (a page
    outside a wiki), the source goes in a sibling `<page stem>_diagrams/` instead.
    """
    for parent in page.parents:
        if (parent / "@References").is_dir():
            rel = page.relative_to(parent).with_suffix("")
            return parent / "@References" / "@Diagrams" / rel / f"{key}.puml"
    return page.parent / f"{page.stem}_diagrams" / f"{key}.puml"


def attach(page: Path, key: str, png: bytes, source: str) -> str:
    """Write the PNG next to the note and the source out of the way; return the image link."""
    adir = page.parent / attachments_dirname(page)
    adir.mkdir(parents=True, exist_ok=True)
    (adir / f"{key}.png").write_bytes(png)
    spath = source_path(page, key)
    spath.parent.mkdir(parents=True, exist_ok=True)
    spath.write_text(source + "\n", encoding="utf-8")
    log("source_saved", path=spath.name)
    return f"{_np_link_quote(adir.name)}/{key}.png"


# ---------------------------------------------------------------------------
def selftest() -> int:
    page = [
        "---", "title: Q?", "---", "",
        "# Q?", "",
        "**Short answer.** Yes.", "",
        "## Evidence", "",
        "A point.", "",
        "## Context", "",
        "Background.", "",
    ]
    start, end = evidence_bounds(page)
    assert page[start - 1] == "## Evidence" and page[end] == "## Context", (start, end)

    out = splice(page, "shape", "X_attachments/shape.png", "@startuml\nA -> B\n@enduml")
    text = "\n".join(out)
    assert "![image](X_attachments/shape.png)" in text
    # The default is the picture alone: the source is a file beside the PNG, not body text a
    # reader has to scroll past. This is the whole difference from wiki_map.py.
    assert "```plantuml" not in text and "A -> B" not in text, \
        "the source must stay out of the article body unless --fence"
    # The diagram belongs to Evidence, not to Context.
    assert text.index("shape.png") < text.index("## Context"), "diagram escaped the section"
    # And it goes *after* the evidence prose, so the answer still reads first.
    assert text.index("A point.") < text.index("shape.png"), "diagram jumped the evidence"

    again = splice(out, "shape", "X_attachments/shape.png", "@startuml\nA -> C\n@enduml")
    assert "\n".join(again).count("shape.png") == 1, \
        "a re-run must replace the block, not duplicate it"

    fenced = splice(page, "shape", "X_attachments/shape.png", "@startuml\nA -> B\n@enduml",
                    fence=True)
    tf = "\n".join(fenced)
    assert "```plantuml" in tf and "A -> B" in tf, "--fence must still print the source"
    # Dropping --fence on a re-run has to take the old fence with it, or the body keeps a
    # stale copy of source that no longer matches the picture.
    unfenced = "\n".join(splice(fenced, "shape", "X_attachments/shape.png",
                                "@startuml\nA -> C\n@enduml"))
    assert "```plantuml" not in unfenced and "A -> B" not in unfenced, \
        "re-running without --fence must remove the previous fence"
    assert unfenced.count("shape.png") == 1

    other = splice(out, "second", "X_attachments/second.png", "@startuml\nD\n@enduml")
    t3 = "\n".join(other)
    assert t3.count("shape.png") == 1 and t3.count("second.png") == 1, \
        "a different key is a second diagram, not a replacement"

    try:
        evidence_bounds(["# Q?", "", "no evidence heading"])
    except ValueError:
        pass
    else:
        raise AssertionError("a page without ## Evidence must be refused, not appended to")

    # An Evidence section that runs to the end of the file still gets a diagram.
    trailing = ["# Q?", "", "## Evidence", "", "Only this.", ""]
    t4 = "\n".join(splice(trailing, "k", "A/k.png", "@startuml\nE\n@enduml"))
    assert "A/k.png" in t4 and t4.rstrip().endswith("A/k.png)")

    enc = plantuml_encode("@startuml\nBob -> Alice : hello\n@enduml")
    assert enc and " " not in enc, "the encoded source must be URL-safe"

    # The source must not land in _attachments/ — NotePlan deletes unreferenced files there
    # within seconds of the note being saved, so a .puml beside the PNG never survives.
    with tempfile.TemporaryDirectory() as tmp:
        wiki = Path(tmp) / "📚 Wiki"
        (wiki / "@References").mkdir(parents=True)
        art = wiki / "🌐 General" / "Q?.md"
        art.parent.mkdir(parents=True)
        art.touch()
        sp = source_path(art, "shape")
        assert sp == wiki / "@References" / "@Diagrams" / "🌐 General" / "Q?" / "shape.puml", sp
        assert "_attachments" not in str(sp), "the source must not go where NotePlan prunes"
        # A page outside any wiki still gets its source somewhere predictable.
        loose = Path(tmp) / "loose.md"
        loose.touch()
        assert source_path(loose, "k") == Path(tmp) / "loose_diagrams" / "k.puml"

    print("selftest ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", help="the article .md to attach the diagram to")
    ap.add_argument("--puml", help="file holding the PlantUML source (`-` for stdin)")
    ap.add_argument("--key", default="diagram",
                    help="attachment basename; re-running with the same key replaces the block")
    ap.add_argument("--server", default=os.environ.get("WIKI_PLANTUML_SERVER"),
                    help="a PlantUML server you control. NEVER a public one — the URL carries "
                         "the diagram's content. Falls back to $WIKI_PLANTUML_SERVER.")
    ap.add_argument("--fence", action="store_true",
                    help="also print the PlantUML source in the note under the image. Off by "
                         "default: on a reader-facing article that is a wall of syntax, and "
                         "the source is saved under @References/@Diagrams either way.")
    ap.add_argument("--check", action="store_true",
                    help="render and report, but write nothing")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.page or not args.puml:
        ap.error("--page and --puml are required")
    if not args.server:
        ap.error("no PlantUML server: pass --server or set $WIKI_PLANTUML_SERVER")

    page = Path(args.page).expanduser()
    if not page.is_file():
        ap.error(f"no such page: {page}")
    source = (sys.stdin.read() if args.puml == "-"
              else Path(args.puml).expanduser().read_text(encoding="utf-8")).strip()

    lines = page.read_text(encoding="utf-8").split("\n")
    evidence_bounds(lines)                   # fail before fetching if the page shape is wrong

    png = fetch_png(args.server, source)
    if args.check:
        log("check_only", page=page.name, key=args.key, png_bytes=len(png))
        print(f"would attach {args.key}.png ({len(png)} bytes) to {page.name}")
        return 0

    target = attach(page, args.key, png, source)
    page.write_text("\n".join(splice(lines, args.key, target, source, args.fence)),
                    encoding="utf-8")
    log("attached", key=args.key, target=target, fence=args.fence)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
