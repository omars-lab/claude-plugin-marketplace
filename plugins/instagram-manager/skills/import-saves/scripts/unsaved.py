#!/usr/bin/env python3
"""unsaved.py — the saves you unsaved: flag them, show them on a page, and remove their data only
when you say so.

    unsaved.py --flag                     after an import: add the saves it found gone to data/unsaved.yaml
    unsaved.py --page [--out PATH]        write $INSTAGRAM_HOME/.cache/hub/unsaved.html
    unsaved.py --forget CODE ... [--dry-run]   take these saves' data out of data/ (only the ones you name)

--flag reads `gone` from .cache/import-diff.json and each save's details from .cache/saves-previous.json
(both written by import_saved.py), because the new saves.json no longer has them. It records each one
that still has data in data/ with the export it went missing in, its creator, collections, save date
and the start of its caption. A save that is back in saves.json comes off the list. Nothing is removed.

--forget removes each named code's whole block as text from data/*.yaml and data/items/*.yaml
(unsaved.yaml too), so the rest of each file keeps its exact layout. Media in the bucket is left
alone; git history keeps what was removed.

The page lists each flagged save with a link to the post (it may be deleted by its creator: the
export cannot tell an unsave from a deleted post), what we hold for it, and a box to tick for the
ones to remove; the ticks build the make line to copy. The page holds captions, so it stays under
.cache, never in git.

Logs ev=unsaved_flag, ev=unsaved_page, ev=forget file=... removed=N and ev=forget_end.
"""
import argparse
import glob
import html
import json
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, os.pardir, "shared", "scripts"))
from home import cache, home  # noqa: E402
from log import log  # noqa: E402

UNSAVED = os.path.join("data", "unsaved.yaml")
SNIPPET = 140   # caption characters kept per save
TOP = re.compile(r"^(['\"]?)([A-Za-z0-9_-]+)\1:")


def data_files(root):
    return sorted(glob.glob(os.path.join(root, "data", "*.yaml")) + glob.glob(os.path.join(root, "data", "items", "*.yaml")))


def top_codes(text):
    """The top-level keys of a YAML map, read as text."""
    return {m.group(2) for m in map(TOP.match, text.splitlines()) if m}


def held(root, codes):
    """code → the data files (relative, unsaved.yaml left out) that hold it."""
    out = {}
    for path in data_files(root):
        rel = os.path.relpath(path, root)
        if rel == UNSAVED:
            continue
        with open(path, encoding="utf-8") as fh:
            for code in top_codes(fh.read()) & set(codes):
                out.setdefault(code, []).append(rel)
    return out


def drop_blocks(text, codes):
    """(text without the top-level blocks keyed by these codes, how many went)."""
    out, removed, skipping = [], 0, False
    for line in text.splitlines(keepends=True):
        m = TOP.match(line)
        if m or (line.strip() and not line[0].isspace() and not line.startswith("-")):
            skipping = bool(m) and m.group(2) in codes
            removed += skipping
        if not skipping:
            out.append(line)
    return "".join(out), removed


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_unsaved(root):
    path = os.path.join(root, UNSAVED)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def write_unsaved(root, flagged):
    path = os.path.join(root, UNSAVED)
    if not flagged:
        if os.path.exists(path):
            os.remove(path)
        return
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(flagged, fh, sort_keys=True, allow_unicode=True, width=1000)


def entry(save, since):
    caption = " ".join((save.get("caption") or "").split())
    e = {"since": since, "owner": (save.get("owner") or {}).get("username") or "",
         "collections": save.get("collections") or [], "saved_at": save.get("saved_at") or "",
         "caption": caption[:SNIPPET] + ("…" if len(caption) > SNIPPET else "")}
    return {k: v for k, v in e.items() if v}


def flag(root):
    diff = load_json(cache("import-diff.json"))
    if diff is None:
        log("unsaved_missing", msg="run make import first; it writes the diff")
        return 1
    now = load_json(cache("saves.json")) or {"saves": []}
    before = {s["code"]: s for s in (load_json(cache("saves-previous.json")) or {}).get("saves", [])}
    saved = {s["code"] for s in now["saves"]}
    since = now.get("exported") or ""
    flagged = load_unsaved(root)
    back = sorted(set(flagged) & saved)
    for code in back:
        del flagged[code]
    gone = [c for c in diff.get("gone") or [] if c not in saved]
    holds = held(root, gone)
    added = [c for c in gone if c in holds and c not in flagged]
    for code in added:
        flagged[code] = entry(before.get(code, {}), since)
    write_unsaved(root, flagged)
    log("unsaved_flag", gone=len(gone), added=len(added), back=len(back), flagged=len(flagged))
    print(f"{len(gone)} saves are no longer saved; {len(added)} newly flagged in {UNSAVED} "
          f"({len(flagged)} in all), {len(back)} saved again. Nothing was removed: see make unsaved-page.")
    return 0


def forget(root, codes, dry_run):
    codes = set(codes)
    total = 0
    for path in data_files(root):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        new, removed = drop_blocks(text, codes)
        if not removed:
            continue
        total += removed
        log("forget", file=os.path.relpath(path, root), removed=removed, dry_run="yes" if dry_run else "no")
        if not dry_run:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new)
    log("forget_end", codes=len(codes), removed=total, dry_run="yes" if dry_run else "no")
    print(f"{'Would remove' if dry_run else 'Removed'} {total} entries for {len(codes)} saves from data/.")
    return 0


def export_date(name):
    """2026-01-02 from an export's file name, else the name."""
    m = re.search(r"\d{4}-\d{2}-\d{2}", name)
    return m.group(0) if m else name


def card(code, e, files):
    owner = e.get("owner") or ""
    cols = "".join(f'<span class="chip">{html.escape(c)}</span>' for c in e.get("collections") or []) or \
        '<span class="muted">no collection</span>'
    holds = ", ".join(html.escape(os.path.relpath(f, "data")) for f in files) or "nothing any more"
    return f"""
<article class="save" data-code="{html.escape(code)}">
  <header><a href="https://www.instagram.com/p/{html.escape(code)}/" target="_blank" rel="noopener">Open the post</a>
  <span class="muted">{"@" + html.escape(owner) if owner else ""}</span>
  <span class="muted">saved {html.escape((e.get("saved_at") or "")[:10])}</span></header>
  <div class="cols">{cols}</div>
  <p class="caption">{html.escape(e.get("caption") or "")}</p>
  <p class="muted">Not in the export of {html.escape(export_date(e.get("since") or ""))}. We hold: {holds}</p>
  <label class="pick"><input type="checkbox" value="{html.escape(code)}"> Remove its data</label>
</article>"""


def page(flagged, holds, make=True):
    cmd = "make forget-unsaved CODES=" if make else \
        f"python3 {os.path.abspath(__file__)} --forget "
    cards = "".join(card(c, e, holds.get(c, [])) for c, e in
                    sorted(flagged.items(), key=lambda kv: (kv[1].get("saved_at") or "", kv[0]), reverse=True))
    empty = '<p class="muted">Nothing here: every save in data/ is still saved.</p>' if not flagged else ""
    lede = "1 post you" if len(flagged) == 1 else f"{len(flagged)} posts you"
    return TEMPLATE.replace("{{LEDE}}", lede).replace("{{CARDS}}", cards + empty).replace("{{CMD}}", html.escape(cmd))


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Saves You Unsaved</title>
<style>
:root { --bg: #f4f5f3; --card: #fff; --fg: #1e2420; --muted: #5f6a63; --line: #d9dfdb; --accent: #0f6b5c;
        --chip: #fbf0dc; --chip-fg: #8a5a12; --soft: #e3f1ec }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #151816; --card: #1d211e; --fg: #e5e9e5; --muted: #9ca59d; --line: #2f3530; --accent: #6cc79f;
  --chip: #3a2c14; --chip-fg: #f0b860; --soft: #1d3428; color-scheme: dark } }
:root[data-theme="dark"] { --bg: #151816; --card: #1d211e; --fg: #e5e9e5; --muted: #9ca59d; --line: #2f3530;
  --accent: #6cc79f; --chip: #3a2c14; --chip-fg: #f0b860; --soft: #1d3428; color-scheme: dark }
* { box-sizing: border-box }
body { margin: 0; background: var(--bg); color: var(--fg); font: 15px/1.5 system-ui, -apple-system, sans-serif }
main { max-width: 52rem; margin: 0 auto; padding: 1.2rem 16px 9rem; display: grid; gap: 1rem }
h1 { margin: 0; font-size: clamp(1.6rem, 4vw, 2.2rem); line-height: 1.1 }
a { color: var(--accent); font-weight: 600 }
a:focus-visible, input:focus-visible, button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px }
.lede, .muted { color: var(--muted) }
.lede { margin: .3rem 0 0; max-width: 65ch }
.list { display: grid; gap: .7rem }
.save { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: .75rem .9rem; overflow-wrap: anywhere }
.save:has(input:checked) { border-color: var(--accent) }
.save header { display: flex; flex-wrap: wrap; gap: .2rem .9rem; align-items: baseline }
.save p { margin: .35rem 0 0 }
.cols { display: flex; flex-wrap: wrap; gap: .3rem; margin-top: .35rem }
.chip { padding: .05rem .55rem; border-radius: 999px; background: var(--chip); color: var(--chip-fg); font-size: .85rem }
.pick { display: inline-flex; gap: .4rem; margin-top: .45rem; cursor: pointer }
.tray { position: fixed; left: 0; right: 0; bottom: 0; padding: .7rem 16px calc(.7rem + env(safe-area-inset-bottom, 0px));
        background: var(--card); border-top: 1px solid var(--line) }
.tray .in { max-width: 52rem; margin: 0 auto; display: grid; gap: .4rem }
.tray p { margin: 0 }
pre { margin: 0; font-size: .85rem; white-space: pre-wrap; overflow-wrap: anywhere; max-height: 6rem; overflow: auto;
      background: var(--soft); padding: .45rem .6rem; border-radius: 8px }
button { justify-self: start; font: 600 .85rem system-ui; padding: .2rem .7rem; border-radius: 8px;
         border: 1px solid var(--accent); background: transparent; color: var(--accent); cursor: pointer }
</style>
</head>
<body>
<main>
  <a href="decisions.html">← Your decisions</a>
  <h1>Saves You Unsaved</h1>
  <p class="lede">{{LEDE}} saved before are not in your newest export. Some you unsaved; some may have
  been deleted by the person who posted them, and the export cannot tell which. Their tags and items are
  kept, so nothing is lost. Tick the ones whose data you want gone, then run the line below; leave the
  rest, and a post you save again comes off this list at the next import.</p>
  <section class="list">{{CARDS}}</section>
</main>
<div class="tray" id="tray" hidden>
  <div class="in">
    <p id="tally"></p>
    <pre id="cmd"></pre>
    <button type="button" id="copy">Copy the command</button>
  </div>
</div>
<script>
(function () {
  var base = "{{CMD}}", boxes = document.querySelectorAll(".pick input");
  function update() {
    var codes = Array.prototype.filter.call(boxes, function (b) { return b.checked; }).map(function (b) { return b.value; });
    document.getElementById("tray").hidden = !codes.length;
    document.getElementById("tally").textContent = codes.length + (codes.length === 1 ? " save" : " saves") + " to remove";
    document.getElementById("cmd").textContent = base.indexOf("CODES=") >= 0 ? base + '"' + codes.join(" ") + '"' : base + codes.join(" ");
  }
  boxes.forEach(function (b) { b.addEventListener("change", update); });
  document.getElementById("copy").addEventListener("click", function () {
    try { navigator.clipboard.writeText(document.getElementById("cmd").textContent); } catch (e) {}
  });
  update();
})();
</script>
</body>
</html>
"""


def write_page(root, out, make):
    flagged = load_unsaved(root)
    out = out or cache(os.path.join("hub", "unsaved.html"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page(flagged, held(root, flagged), make))
    log("unsaved_page", flagged=len(flagged), out=out)
    print(out)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--flag", action="store_true", help="flag the saves the last import found gone")
    mode.add_argument("--page", action="store_true", help="write the page of flagged saves")
    mode.add_argument("--forget", nargs="+", metavar="CODE", help="take these saves' data out of data/")
    ap.add_argument("--dry-run", action="store_true", help="with --forget: count what would go; change nothing")
    ap.add_argument("--out", default=None, help="with --page: where to write it (default .cache/hub/unsaved.html)")
    ap.add_argument("--make", action="store_true", help="with --page: show the data repo's make line")
    a = ap.parse_args(argv)
    root = home()
    if a.flag:
        return flag(root)
    if a.page:
        return write_page(root, a.out, a.make)
    return forget(root, a.forget, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
