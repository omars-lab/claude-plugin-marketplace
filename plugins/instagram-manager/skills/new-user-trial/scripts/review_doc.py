#!/usr/bin/env python3
"""review_doc.py — turn a trial's diary and review into docs to read and comment on in Obsidian.

    review_doc.py --sandbox <sandbox> --out <data repo>/docs/user-trials/<date>-<persona> \\
                  --media <media folder>/user-trials/<date>-<persona> --playwright <playwright-core dir>
    review_doc.py ... --no-maps          only the pictures the agents took, no map thumbnails
    review_doc.py ... --max-maps 20      at most this many map thumbnails (default 40)

Writes <out>/diary.md and <out>/review.md, copied from the sandbox with the pictures shown in place:
    - a picture the agents embedded (`![what it shows](shots/x.png)`) points at its copy in the
      media folder;
    - a picture only named in the text (`shots/x.png`, in a sentence or a table row) is shown
      right after that paragraph or table, so nobody has to open a link to see it;
    - review.md ends with "Where each place landed": the small map from every place page in the
      sandbox hub, then from every post page with pins, one map thumbnail each.
The pictures go to <media> (shots/ and maps/), never into git: the docs point at them with
file:/// links, so they show in Obsidian on this Mac. Run it from the main session, not through
the sandbox's `run` (that points the media folder at the sandbox).

Map thumbnails are screenshots of the hub's own small map (Leaflet and OpenStreetMap tiles, the
same as opening the page in a browser), taken with shot.mjs, one browser for all of them.
Prints one ev=review_doc line, then where to open the doc.
"""

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SHOT = os.path.join(HERE, "shot.mjs")
EMBED = re.compile(r"!\[([^\]]*)\]\((shots/[^)\s]+\.(?:png|jpe?g|gif|webp))\)")
NAMED = re.compile(r"(?<![(\w/])(shots/[\w.-]+\.(?:png|jpe?g|gif|webp))")
TITLE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
PINS = re.compile(r"var d=(\[\[.*?\]\]);")


def file_url(path):
    return "file://" + urllib.parse.quote(os.path.abspath(path))


def blocks(text):
    """Paragraphs and tables, with the blank lines between them, so they join back unchanged."""
    return re.split(r"(\n\s*\n)", text)


def show_pictures(text, sandbox, media, copied):
    """Point embedded pictures at the media folder; show named ones after their block."""
    def place(rel):
        src = os.path.join(sandbox, rel)
        if not os.path.isfile(src):
            return None
        dst = os.path.join(media, rel)
        if rel not in copied:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            copied[rel] = dst
        return file_url(dst)

    shown = set(m.group(2) for m in EMBED.finditer(text))
    out = []
    for part in blocks(text):
        if not part.strip():
            out.append(part)
            continue
        part = EMBED.sub(lambda m: f"![{m.group(1)}]({place(m.group(2)) or m.group(2)})", part)
        extra = []
        for line in part.splitlines():
            for rel in NAMED.findall(line):
                if rel in shown:
                    continue
                url = place(rel)
                if not url:
                    continue
                shown.add(rel)
                row = [c.strip() for c in line.strip().strip("|").split("|")] if line.lstrip().startswith("|") else []
                what = f"Finding {row[0]}: " if row and row[0] else ""
                extra.append(f"![{what}{os.path.basename(rel)}|700]({url})")
        out.append(part + ("\n\n" + "\n\n".join(extra) if extra else ""))
    return "".join(out)


def page_name(path, sub):
    """A place page's heading; for a post page, its code and the places on its small map."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = TITLE.search(text)
    name = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else os.path.basename(path)
    if sub != "posts":
        return name
    pins = PINS.search(text)
    try:
        spots = [p[2] for p in json.loads(pins.group(1))] if pins else []
    except (ValueError, IndexError, TypeError):
        spots = []
    code = os.path.basename(path)[:-5]
    shown = ", ".join(spots[:4]) + (f" and {len(spots) - 4} more" if len(spots) > 4 else "")
    return f"{code} by {name}" + (f": {shown}" if shown else "")


def map_thumbnails(hub, media, args):
    """The small map from each place page, then each post page, as PNGs in <media>/maps/."""
    jobs, names = [], {}
    for sub in ("places", "posts"):
        folder = os.path.join(hub, sub)
        for fn in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            if not fn.endswith(".html") or len(jobs) >= args.max_maps:
                continue
            with open(os.path.join(folder, fn), encoding="utf-8") as f:
                if 'id="mini"' not in f.read():
                    continue
            out = os.path.join(media, "maps", f"{sub}-{fn[:-5]}.png")
            jobs.append({"page": f"/{sub}/{fn}", "out": out, "clip": "#mini", "width": 900, "height": 900})
            names[out] = (sub, page_name(os.path.join(folder, fn), sub), f"{sub}/{fn}")
    if not jobs:
        return []
    os.makedirs(os.path.join(media, "maps"), exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(jobs, f)
    cmd = ["node", SHOT, "--root", hub, "--list", f.name, "--chrome", args.chrome]
    if args.playwright:
        cmd += ["--playwright", args.playwright]
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=60 + 15 * len(jobs))
    os.unlink(f.name)
    if run.returncode and not any(os.path.isfile(j["out"]) for j in jobs):
        sys.exit(f"review_doc: the map thumbnails failed:\n{run.stdout}{run.stderr}")
    return [(names[j["out"]], j["out"]) for j in jobs if os.path.isfile(j["out"])]


def maps_section(maps):
    lines = ["", "## Where each place landed", "",
             "The small map from each page of the trial's hub, so the pins can be checked here without",
             "opening the pages. Places first, then posts.", ""]
    for sub, title in (("places", "Places"), ("posts", "Posts")):
        rows = [(name, page, out) for (s, name, page), out in maps if s == sub]
        if not rows:
            continue
        lines += [f"### {title}", "", "| Page | Map |", "|---|---|"]
        for name, page, out in rows:
            label = name.replace("|", "\\|")
            alt = os.path.basename(page)[:-5]
            lines.append(f"| {label}<br>`{page}` | ![{alt} map\\|360]({file_url(out)}) |")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sandbox", required=True, help="the trial's sandbox folder")
    ap.add_argument("--out", required=True, help="the folder for diary.md and review.md (in the data repo's docs)")
    ap.add_argument("--media", required=True, help="the folder for the pictures (in the media folder, never git)")
    ap.add_argument("--playwright", default=os.environ.get("PLAYWRIGHT_CORE"), help="playwright-core folder")
    ap.add_argument("--chrome", default="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    ap.add_argument("--no-maps", action="store_true", help="no map thumbnails")
    ap.add_argument("--max-maps", type=int, default=40, help="at most this many map thumbnails")
    args = ap.parse_args(argv)

    sandbox, out, media = (os.path.abspath(os.path.expanduser(p)) for p in (args.sandbox, args.out, args.media))
    os.makedirs(out, exist_ok=True)
    os.makedirs(media, exist_ok=True)
    copied, written = {}, []
    maps = [] if args.no_maps else map_thumbnails(os.path.join(sandbox, "home", ".cache", "hub"), media, args)
    for name in ("diary.md", "review.md"):
        src = os.path.join(sandbox, name)
        if not os.path.isfile(src):
            continue
        with open(src, encoding="utf-8") as f:
            text = show_pictures(f.read(), sandbox, media, copied)
        if name == "review.md" and maps:
            text = text.rstrip("\n") + "\n" + maps_section(maps)
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(text.rstrip("\n") + "\n")
        written.append(name)
    if not written:
        sys.exit(f"review_doc: no diary.md or review.md in {sandbox}")
    print(f"ev=review_doc out={out} docs={','.join(written)} pictures={len(copied)} maps={len(maps)} media={media}")
    doc = os.path.join(out, "review.md" if "review.md" in written else written[0])
    print(f"Open it in Obsidian to read and comment (the pictures show on this Mac):\n"
          f"  obsidian://open?path={urllib.parse.quote(doc)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
