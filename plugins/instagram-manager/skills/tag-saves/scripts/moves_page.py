#!/usr/bin/env python3
"""moves_page.py — the moves list as a page: each save filed in the wrong collection, where to move
it, and the words in its caption that show it. Instagram has no way to move a save from outside
the app, so the page is a checklist: open the post, move it, tick it off.

    moves_page.py                 writes $INSTAGRAM_HOME/.cache/hub/moves.html
    moves_page.py --out PATH      somewhere else

Reads $INSTAGRAM_HOME/data/moves.yaml (from tag_saves.py --merge) and .cache/saves.json. The
ticks live in the browser only; the next export is what takes a save off the list (the merge sees
it has left the collection). The page holds captions, so it stays under .cache, never in git.
"""

import argparse
import collections as co
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, os.pardir, "shared", "scripts"))

from home import cache, read_saves  # noqa: E402
from log import log  # noqa: E402
from places import load_yaml  # noqa: E402
from tag_saves import MOVES  # noqa: E402

AROUND = 220  # caption characters shown around the quote


def excerpt(caption, quote):
    """The caption near the quote, escaped, with the quote marked."""
    caption = " ".join((caption or "").split())
    m = re.search(re.escape(" ".join(quote.split())), caption, re.I) if quote else None
    if not m:
        cut = caption[:AROUND * 2]
        return html.escape(cut) + ("…" if len(caption) > len(cut) else "")
    a, b = max(0, m.start() - AROUND), min(len(caption), m.end() + AROUND)
    return ("…" if a else "") + html.escape(caption[a:m.start()]) + "<mark>" + html.escape(m.group(0)) + \
        "</mark>" + html.escape(caption[m.end():b]) + ("…" if b < len(caption) else "")


def chips(names, cls):
    return "".join(f'<span class="chip {cls}">{html.escape(n)}</span>' for n in names) or \
        '<span class="none">no better collection yet</span>'


def card(code, move, save):
    owner = (save.get("owner") or {}).get("username") or ""
    url = save.get("url") or f"https://www.instagram.com/p/{code}/"
    return f"""
<article class="move" data-code="{html.escape(code)}">
  <div class="route">
    <div class="leg"><span class="label">In</span>{chips(move.get("collections") or [], "from")}</div>
    <div class="leg"><span class="label">Move to</span>{chips(move.get("to") or [], "to")}</div>
    <div class="leg"><span class="label">Not about</span>{chips(move.get("not") or [], "not")}</div>
  </div>
  <div class="body">
    <p class="caption">{excerpt(save.get("caption"), move.get("quote") or "")}</p>
    <div class="foot">
      <a href="{html.escape(url)}" target="_blank" rel="noopener">Open the post</a>
      <span class="who">{"@" + html.escape(owner) if owner else ""}</span>
      <label class="done"><input type="checkbox" id="done-{html.escape(code)}"> Moved</label>
    </div>
  </div>
</article>"""


def page(moves, saves):
    by_from = co.Counter(c for m in moves.values() for c in (m.get("collections") or ["(none)"]))
    summary = "".join(f'<li><span class="chip from">{html.escape(c)}</span> <b>{n}</b></li>'
                      for c, n in by_from.most_common())
    cards = "".join(card(code, m, saves.get(code, {})) for code, m in
                    sorted(moves.items(), key=lambda kv: ((kv[1].get("collections") or [""])[0], kv[0])))
    empty = '<p class="empty">No saves to move. A save gets here when the tagger shows, with words ' \
            'from its caption, that it sits in the wrong collection.</p>' if not moves else ""
    lede = "1 saved post sits" if len(moves) == 1 else f"{len(moves)} saved posts sit"
    return TEMPLATE.replace("{{LEDE}}", lede).replace("{{COUNT}}", str(len(moves))) \
        .replace("{{SUMMARY}}", summary) \
        .replace("{{CARDS}}", cards + empty)


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Saves to Move</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><path d='M16 2C10.5 2 6 6.3 6 11.8 6 19.3 16 30 16 30s10-10.7 10-18.2C26 6.3 21.5 2 16 2z' fill='%230f6b5c'/><circle cx='16' cy='12' r='4.2' fill='white'/></svg>">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600&family=Atkinson+Hyperlegible:wght@400;700&display=swap">
<style>
@font-face{font-family:"Plain Digits";font-weight:400;unicode-range:U+0030-0039;src:local("AvenirNext-Regular"),local("Helvetica Neue"),local("Arial")}
@font-face{font-family:"Plain Digits";font-weight:700;unicode-range:U+0030-0039;src:local("AvenirNext-Bold"),local("HelveticaNeue-Bold"),local("Arial Bold")}
/* A sorting tray: a short tally of what to move out of each collection, then one slip per save,
   its route (in → move to) on the left and the caption evidence on the right. */
:root {
  --bg: #f3f5f4; --card: #ffffff; --fg: #1d2421; --muted: #5d6a64; --line: #d9e0dc;
  --accent: #0f6b5c; --from: #8a5a12; --from-bg: #fbf0dc; --to-bg: #dcf1ea; --mark: #fde9a8;
  --display: "Bricolage Grotesque", "Avenir Next", system-ui, sans-serif;
  --body: "Plain Digits", "Atkinson Hyperlegible", system-ui, -apple-system, sans-serif;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #141917; --card: #1c2320; --fg: #e4ebe7; --muted: #9aa8a1; --line: #2e3833;
  --accent: #5fc9b3; --from: #e7b766; --from-bg: #3a2e18; --to-bg: #173a31; --mark: #5a4a12; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #141917; --card: #1c2320; --fg: #e4ebe7; --muted: #9aa8a1; --line: #2e3833;
  --accent: #5fc9b3; --from: #e7b766; --from-bg: #3a2e18; --to-bg: #173a31; --mark: #5a4a12; color-scheme: dark }
* { box-sizing: border-box }
body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.5 var(--body); }
main { max-width: 60rem; margin: 0 auto; padding-inline: 16px; padding-block: 2rem 4rem; display: grid; gap: 1.5rem }
h1 { font: 600 clamp(1.8rem, 5vw, 2.6rem)/1.1 var(--display); margin: 0; text-wrap: balance }
.lede { margin: .4rem 0 0; color: var(--muted); max-width: 62ch }
.tally { display: flex; flex-wrap: wrap; gap: .5rem 1rem; list-style: none; padding: 0; margin: 0 }
.tally li { display: flex; align-items: center; gap: .35rem; font-variant-numeric: tabular-nums }
.bar { display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; justify-content: space-between;
       border-block: 1px solid var(--line); padding-block: .6rem }
.bar label { color: var(--muted); display: flex; gap: .4rem; align-items: center }
.left { font-variant-numeric: tabular-nums }
.list { display: grid; gap: .9rem }
.move { display: grid; grid-template-columns: minmax(0, 15rem) minmax(0, 1fr); gap: 1rem 1.5rem;
        background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 1rem 1.1rem }
.move.is-done { opacity: .5 }
.route { display: grid; gap: .55rem; align-content: start }
.leg { display: flex; flex-wrap: wrap; gap: .3rem; align-items: center }
.label { width: 100%; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted) }
.chip { display: inline-block; padding: .1rem .55rem; border-radius: 999px; font-size: .88rem; border: 1px solid var(--line) }
.chip.from { background: var(--from-bg); color: var(--from); border-color: transparent }
.chip.to { background: var(--to-bg); color: var(--accent); border-color: transparent; font-weight: 700 }
.chip.not { text-decoration: line-through; color: var(--muted) }
.none { color: var(--muted); font-size: .88rem }
.body { min-width: 0; display: grid; gap: .7rem; align-content: start }
.caption { margin: 0; overflow-wrap: anywhere; max-width: 65ch }
mark { background: var(--mark); color: inherit; padding: 0 .15em; border-radius: 3px }
.foot { display: flex; flex-wrap: wrap; gap: .5rem 1.2rem; align-items: center }
.foot a { color: var(--accent); font-weight: 700 }
.foot a:focus-visible, input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px }
.who { color: var(--muted); font-size: .9rem }
.done { margin-left: auto; display: flex; gap: .4rem; align-items: center; cursor: pointer }
.empty { color: var(--muted) }
body.hide-done .move.is-done { display: none }
@media (max-width: 640px) { .move { grid-template-columns: minmax(0, 1fr) } .done { margin-left: 0 } }
</style>
</head>
<body>
<main>
  <header>
    <h1>Saves to Move</h1>
    <p class="lede">{{LEDE}} in a collection they do not belong to. Open each one in
    Instagram, move it to the suggested collection, and tick it off. The next export takes it off
    this list for good.</p>
  </header>
  <ul class="tally" aria-label="Saves to move, by the collection they are in now">{{SUMMARY}}</ul>
  <div class="bar">
    <span class="left"><b id="left">{{COUNT}}</b> left to move</span>
    <label><input type="checkbox" id="hide-done"> Hide the ones I moved</label>
  </div>
  <section class="list">{{CARDS}}</section>
</main>
<script>
(function () {
  var KEY = "moves-done", done = {};
  try { done = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) {}
  function save() { try { localStorage.setItem(KEY, JSON.stringify(done)); } catch (e) {} }
  function count() {
    document.getElementById("left").textContent =
      document.querySelectorAll(".move:not(.is-done)").length;
  }
  document.querySelectorAll(".move").forEach(function (card) {
    var code = card.dataset.code, box = card.querySelector(".done input");
    box.checked = !!done[code];
    card.classList.toggle("is-done", box.checked);
    box.addEventListener("change", function () {
      if (box.checked) done[code] = true; else delete done[code];
      card.classList.toggle("is-done", box.checked);
      save(); count();
    });
  });
  var hide = document.getElementById("hide-done");
  try { hide.checked = localStorage.getItem(KEY + "-hide") === "1"; } catch (e) {}
  document.body.classList.toggle("hide-done", hide.checked);
  hide.addEventListener("change", function () {
    document.body.classList.toggle("hide-done", hide.checked);
    try { localStorage.setItem(KEY + "-hide", hide.checked ? "1" : "0"); } catch (e) {}
  });
  count();
})();
</script>
</body>
</html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=None, help="where to write the page (default .cache/hub/moves.html)")
    args = ap.parse_args(argv)
    moves = load_yaml(MOVES)
    saves = {s["code"]: s for s in read_saves()["saves"]}
    out = args.out or cache(os.path.join("hub", "moves.html"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page(moves, saves))
    log("moves_page", moves=len(moves), out=out)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
