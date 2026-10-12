#!/usr/bin/env python3
"""Open a wiki page in NotePlan and screenshot what a reader actually sees.

WHY THIS EXISTS
---------------
Reviewing a page from its markdown source is guessing. NotePlan is an *editor*, not a preview:
it prints `**` and backtick markers in grey while also applying the formatting, it has no callout
syntax, it shows HTML comments, and inline markup that spans a wrapped line renders as literal
text. None of that is visible in the source. So the newcomer review looks at the render.

Doing that by hand is three fiddly commands per shot and roughly 200 shots across the wiki, which
is exactly the shape the repo rule says to push into a tool: the difference (which page, which
section, how many screens) becomes a parameter, and the call site stays one stable command.

THE PIPELINE, AND WHY EACH STEP IS THERE
----------------------------------------
1. `open -a NotePlan` — activate. Without this another app's window floats over the capture; a
   GeoGebra window landed in the middle of one probe shot.
2. `toggleSidebar?forceCollapse=yes` — collapse the left sidebar, which is otherwise dead pixels.
3. `openNote?...&highlightStart=<offset>` — scroll straight to the section under review.
   The offset is counted from the START OF THE FILE, frontmatter included. This is the part that
   is easy to get wrong: `highlightStart=0` does NOT land on the body, it lands on the top of the
   frontmatter, so the shot is a screenful of PROPERTIES panel. Passing the real character offset
   of the heading is what skips it.
4. `screencapture -R <region>` — crop to the editor column. NotePlan keeps a right-hand
   calendar/Timeline panel open that no x-callback closes, so cropping is how it is excluded.
   Cropping also roughly halves the pixels per shot.
5. `key code 121` (page down) via System Events for each additional screen. System Events is a
   DIFFERENT Apple-events target from NotePlan, which is why this works while direct NotePlan
   automation fails with -1743 (errAEEventNotPermitted) until Automation permission is granted.

Every subprocess gets a timeout and logs `ev=` lines, so a sweep that stalls is bracketed rather
than silently frozen.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.parse

# Verified against a 3024x1964 capture on this machine: the editor text column with the left
# sidebar collapsed. Override with --region when the window moves or the display changes.
DEFAULT_REGION = "310,80,640,900"

# screencapture and osascript can both block indefinitely (a modal dialog, a wedged WindowServer).
# A sweep of 73 pages cannot afford one of them hanging the whole run.
CMD_TIMEOUT = 20.0

# How long NotePlan needs to navigate and settle before the pixels are worth capturing. Measured,
# not guessed: below ~0.6s the capture catches the previous note still on screen.
SETTLE = 1.2


def log(ev: str, **kw: object) -> None:
    """One structured line per event, to stderr so stdout stays a clean list of written files."""
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    parts = " ".join(f"{k}={v}" for k, v in kw.items())
    print(f"{stamp} pid={os.getpid()} ev={ev} {parts}".rstrip(), file=sys.stderr)


def run(cmd: list[str], what: str) -> bool:
    """Run a command with a timeout, logging before and after so a stall is bracketed."""
    log(f"{what}_start")
    try:
        subprocess.run(cmd, timeout=CMD_TIMEOUT, check=True)
    except subprocess.TimeoutExpired:
        log(f"{what}_timeout", timeout=CMD_TIMEOUT)
        return False
    except subprocess.CalledProcessError as exc:
        log(f"{what}_failed", rc=exc.returncode)
        return False
    log(f"{what}_ok")
    return True


def note_title(text: str, path: pathlib.Path) -> str:
    """The title NotePlan matches on: the H1, falling back to the filename.

    The vault's golden rule is that filename minus `.md` equals heading minus `# `, so these agree
    on a well-formed page. Reading the H1 first means a page that has drifted still opens.
    """
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return path.stem


def section_offset(text: str, section: str | None) -> tuple[int, int]:
    """Character offset and length of the heading to scroll to, counted from the file start.

    Counting from the file start — frontmatter included — is what NotePlan's `highlightStart`
    expects. Returns the H1 when no section is named, so `--top` still skips the PROPERTIES panel.
    """
    if section is None:
        match = re.search(r"^#\s+.+$", text, re.MULTILINE)
    else:
        # `[ \t]*$` and not `\s*$`: under MULTILINE, `\s*` happily eats the trailing newline and
        # the highlight then spills onto the blank line below the heading.
        match = re.search(rf"^#{{1,6}}[ \t]+{re.escape(section)}[ \t]*$", text, re.MULTILINE)
    if not match:
        return 0, 1
    return match.start(), len(match.group(0))


def build_url(title: str, offset: int, length: int) -> str:
    """The openNote x-callback URL. Every component is encoded — titles are questions, so they
    carry `?` and `'` that would otherwise terminate or corrupt the query string."""
    query = urllib.parse.urlencode(
        {"noteTitle": title, "highlightStart": offset, "highlightLength": length},
        quote_via=urllib.parse.quote,
    )
    return f"noteplan://x-callback-url/openNote?{query}"


def capture(page: pathlib.Path, section: str | None, screens: int,
            out_dir: pathlib.Path, region: str, collapse: bool) -> list[pathlib.Path]:
    text = page.read_text(encoding="utf-8")
    title = note_title(text, page)
    offset, length = section_offset(text, section)
    log("page", title=repr(title), section=section or "TOP", offset=offset, screens=screens)

    run(["open", "-a", "NotePlan"], "activate")
    if collapse:
        run(["open", "noteplan://x-callback-url/toggleSidebar?forceCollapse=yes&animated=no"],
            "collapse")
    run(["open", build_url(title, offset, length)], "open_note")
    time.sleep(SETTLE)

    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", page.stem).strip("-").lower()[:60]
    written: list[pathlib.Path] = []
    for index in range(screens):
        if index:
            # 121 = page down. Sent to System Events, not to NotePlan, because System Events is a
            # separately authorized Apple-events target.
            run(["osascript", "-e",
                 'tell application "System Events" to key code 121'], "page_down")
            time.sleep(SETTLE)
        shot = out_dir / f"{slug}-{index + 1}.png"
        if run(["screencapture", "-x", "-o", "-R", region, str(shot)], "capture"):
            written.append(shot)
            log("wrote", path=str(shot))
    return written


def _selftest() -> int:
    """Covers the parts that are testable without a screen: offset maths and URL building.

    The capture itself is not asserted here — it needs a live NotePlan and a display, and a test
    that mocked all of that would only prove the mock works.
    """
    page = (
        "---\ntitle: What is X?\nkind: base\nprerequisites:\n  - \"[[Y]]\"\n---\n\n"
        "# What is X?\n\n**Short answer.** A thing.\n\n## Evidence\n\n- a fact\n\n## Context\n\np\n"
    )
    path = pathlib.Path("What is X?.md")

    assert note_title(page, path) == "What is X?", "H1 is the title"
    assert note_title("no heading here", path) == "What is X?", "falls back to the filename"

    top_off, top_len = section_offset(page, None)
    assert page[top_off:top_off + top_len] == "# What is X?", "top lands on the H1"
    assert top_off > 0, "the H1 is NOT at offset 0 — offset 0 is the frontmatter, which is the "\
                        "whole reason a computed offset is needed"

    ev_off, ev_len = section_offset(page, "Evidence")
    assert page[ev_off:ev_off + ev_len] == "## Evidence", "section lands on the heading"

    ctx_off, _ = section_offset(page, "Context")
    assert ctx_off > ev_off, "later section has a later offset"

    missing_off, missing_len = section_offset(page, "Nope")
    assert (missing_off, missing_len) == (0, 1), "a missing section degrades to the file top"

    url = build_url("How do I test A/B & C?", 431, 12)
    assert "%2F" in url and "%26" in url, "slash and ampersand are encoded, not left to split "\
                                          "the query string"
    assert "highlightStart=431" in url, "offset is passed through"

    # A question mark in a title is the common case here — every page is a question.
    assert "%3F" in build_url("What is X?", 0, 1), "question mark is encoded"

    print("wiki_render selftest: 9 checks passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--page", type=pathlib.Path, help="the .md file to render")
    parser.add_argument("--section", help="heading to scroll to, e.g. Evidence (default: the H1)")
    parser.add_argument("--screens", type=int, default=1,
                        help="how many screens to capture, paging down between (default 1)")
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("."),
                        help="directory to write PNGs into")
    parser.add_argument("--region", default=DEFAULT_REGION,
                        help=f"screencapture -R region x,y,w,h (default {DEFAULT_REGION})")
    parser.add_argument("--no-collapse", action="store_true",
                        help="skip the sidebar collapse (it is already collapsed)")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        return _selftest()
    if not args.page:
        parser.error("--page is required (or use --selftest)")
    if not args.page.is_file():
        log("missing_page", path=str(args.page))
        return 1

    written = capture(args.page, args.section, max(1, args.screens),
                      args.out, args.region, not args.no_collapse)
    for shot in written:
        print(shot)
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())
