#!/usr/bin/env python3
"""pins_page.py — the spot pins on a map, to look over before anything is built on them. Every pin
is a guess until a person has seen it: a lookup can land on the town centre, or on the sandwich
shop next to the café the post meant.

    pins_page.py                 writes $INSTAGRAM_HOME/.cache/hub/pins.html
    pins_page.py --out PATH      somewhere else

Reads $INSTAGRAM_HOME/data/pins.yaml, pins-review.yaml and no-spot.yaml (from
resolve_post_location.py --merge) and .cache/saves.json (creators and post links). The map is
Leaflet 1.9.4 from cdnjs over OpenStreetMap's tiles, with OpenStreetMap's credit showing, so the
page needs the internet when it is opened. Beside the map, per save: its creator, each spot's words
from the caption, what OpenStreetMap found, how far that is from the save's area, and the post's
link. Review entries are listed after, with why each one needs a look; the ones OpenStreetMap
found somewhere are on the map in another colour. The page holds captions' words and post codes,
so it stays under .cache, never in git.

Each save shows a small preview (extract-stills' previews.py, made here when missing): a 144 x 192
picture, about 5 KB, that loads only as it nears the screen, and for a reel with a video a flipbook
of 12 frames from the whole reel, a few dozen KB. A flipbook loads and plays only while its save is
on screen, at most previews.MAX_PLAYING at once, and turns back into the picture when it scrolls away, so a
page of hundreds of saves stays light. With reduced motion asked for, a flipbook plays only while
the pointer is on it. --no-previews leaves them out.
"""

import argparse
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, os.pardir, "shared", "scripts"))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, "extract-stills", "scripts"))

from home import cache  # noqa: E402
from log import log  # noqa: E402
from places import load_yaml  # noqa: E402
from resolve_post_location import NO_SPOT, PINS, REVIEW  # noqa: E402
import previews  # noqa: E402  extract-stills; ffmpeg and img2webp are needed only for posts not made yet

TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
CREDIT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
CDN = "https://cdnjs.cloudflare.com/ajax/libs"
LEAFLET = (f'<link rel="stylesheet" href="{CDN}/leaflet/1.9.4/leaflet.min.css">\n'
           f'<script src="{CDN}/leaflet/1.9.4/leaflet.min.js"></script>')

esc = html.escape


def post_url(code, save):
    return save.get("url") or f"https://www.instagram.com/p/{code}/"


def spot_row(i, e, review):
    """One spot: the caption's words, what OpenStreetMap found, how far, and links."""
    found = ""
    if e.get("lat") is not None:
        kind = f' <span class="kind">{esc(str(e.get("kind") or ""))}</span>' if e.get("kind") else ""
        where = f'<div class="addr">{esc(e["found"])}</div>' if e.get("found") else ""
        found = f'<div class="found"><b>{esc(str(e.get("name") or ""))}</b>{kind}{where}</div>'
    elif review:
        found = '<div class="found none">OpenStreetMap found nothing</div>'
    dist = (f'<span class="km">{e["km"]:g} km from {esc(str(e.get("near") or ""))}</span>'
            if isinstance(e.get("km"), (int, float)) else f'<span class="km">near {esc(str(e.get("near") or ""))}</span>')
    links = []
    if e.get("lat") is not None:
        links.append(f'<button type="button" class="show" data-i="{i}">Show on map</button>')
    if e.get("osm"):
        links.append(f'<a href="https://www.openstreetmap.org/{esc(e["osm"])}" target="_blank" rel="noopener">OpenStreetMap</a>')
    if e.get("map"):
        links.append(f'<a href="{esc(e["map"])}" target="_blank" rel="noopener">Google Maps</a>')
    why = f'<span class="why">{esc(str(e.get("why") or ""))}</span>' if review else ""
    asked = (f'<div class="asked">searched for “{esc(str(e["asked"]))}”</div>'
             if e.get("asked") and e.get("asked") != e.get("said") else "")
    tip = f'<div class="tip">{"dropped" if e.get("drop") else "lookup: " + esc(str(e["lookup"]))}</div>' \
        if review and (e.get("drop") or e.get("lookup")) else ""
    return (f'<li class="spot{" is-review" if review else ""}" id="spot-{i}">'
            f'<q>{esc(str(e.get("said") or ""))}</q>{why}{asked}{found}'
            f'<div class="meta">{dist}{"".join(links)}</div>{tip}</li>')


def preview_html(code, save, pv):
    """The post's picture, and its flipbook to swap in while it is on screen; empty with neither."""
    if not pv or not pv.get("poster"):
        return ""
    anim = f' data-anim="previews/{esc(pv["anim"])}"' if pv.get("anim") else ""
    return (f'<a class="pv" href="{esc(post_url(code, save))}" target="_blank" rel="noopener" tabindex="-1">'
            f'<img src="previews/{esc(pv["poster"])}" data-poster="previews/{esc(pv["poster"])}"{anim} '
            f'width="72" height="96" alt="" loading="lazy" decoding="async"></a>')


def save_card(code, entries, save, start, review, pv=None):
    owner = (save.get("owner") or {}).get("username") or ""
    who = f'<span class="who">@{esc(owner)}</span>' if owner else '<span class="who">unknown creator</span>'
    rows = "".join(spot_row(start + j, e, review) for j, e in enumerate(entries))
    fig = preview_html(code, save, pv)
    return (f'<article class="save{" has-pv" if fig else ""}">{fig}<div class="body"><header>{who}'
            f'<a href="{esc(post_url(code, save))}" target="_blank" rel="noopener">Open the post</a></header>'
            f'<ul class="spots">{rows}</ul></div></article>')


def codes_shown(pins, review):
    """The saves that get a card: those with at least one spot entry."""
    return sorted(c for group in (pins, review) for c in group
                  if any(isinstance(e, dict) for e in group[c] or []))


def build(pins, review, no_spot, saves, shown=None):
    """The page, and the number of map markers. `shown` is {code: {"poster", "anim"}}."""
    shown = shown or {}
    markers, cards, review_cards, i = [], [], [], 0
    for group, out, is_review in ((pins, cards, False), (review, review_cards, True)):
        for code in sorted(group):
            entries = [e for e in group[code] or [] if isinstance(e, dict)]
            if not entries:
                continue
            save = saves.get(code) or {}
            out.append(save_card(code, entries, save, i, is_review, shown.get(code)))
            for e in entries:
                if e.get("lat") is not None and e.get("lon") is not None and not e.get("drop"):
                    markers.append({"i": i, "lat": e["lat"], "lon": e["lon"], "review": is_review,
                                    "label": f'{e.get("name") or e.get("said")} ({e.get("said")})'})
                i += 1
    n_pins = sum(len(v or []) for v in pins.values())
    n_review = sum(len(v or []) for v in review.values())
    def many(n, word):
        return f"{n} {word}" if n == 1 else f"{n} {word}s"

    n_none = len(no_spot)
    lede = (f"{many(n_pins, 'spot')} from {many(len(pins), 'save')} pinned, and {n_review} from "
            f"{many(len(review), 'save')} need a look. {many(n_none, 'save')} "
            f"{'names' if n_none == 1 else 'name'} no spot in the caption; "
            f"{'it waits' if n_none == 1 else 'they wait'} for the video to be read.")
    empty = '<p class="empty">No pins yet. Run the post-locator agents and the merge first.</p>'
    data = json.dumps(markers, ensure_ascii=False).replace("</", "<\\/")
    page = (TEMPLATE.replace("{{LEAFLET}}", LEAFLET).replace("{{LEDE}}", esc(lede))
            .replace("{{PINS}}", "".join(cards) or empty)
            .replace("{{REVIEW}}", "".join(review_cards) or '<p class="empty">Nothing to review.</p>')
            .replace("{{N_REVIEW}}", str(n_review))
            .replace("{{PLAYER}}", previews.player_js() if any((v or {}).get("anim") for v in shown.values()) else "")
            .replace("{{TILES}}", TILES).replace("{{CREDIT}}", CREDIT).replace("{{DATA}}", data))
    return page, len(markers)


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Spot Pins</title>
{{LEAFLET}}
<style>
/* A checking desk: the map holds still on the left, the list of spots scrolls on the right. Each
   row puts the caption's words beside what OpenStreetMap found, so a wrong match stands out. */
:root {
  --bg: #f4f3ef; --card: #ffffff; --fg: #1f2320; --muted: #5f675f; --line: #dcdcd3;
  --accent: #1f6f50; --warn: #9a5b00; --warn-bg: #fdf0d8; --quote-bg: #eef5ef;
  --body: system-ui, -apple-system, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #151816; --card: #1d211e; --fg: #e5e9e5; --muted: #9ca59d; --line: #2f3530;
  --accent: #6cc79f; --warn: #f0b860; --warn-bg: #3a2c14; --quote-bg: #1f2c24; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #151816; --card: #1d211e; --fg: #e5e9e5; --muted: #9ca59d; --line: #2f3530;
  --accent: #6cc79f; --warn: #f0b860; --warn-bg: #3a2c14; --quote-bg: #1f2c24; color-scheme: dark }
* { box-sizing: border-box }
body { margin: 0; background: var(--bg); color: var(--fg); font: 15px/1.5 var(--body) }
.top { padding: 1.2rem 16px .6rem; max-width: 90rem; margin: 0 auto }
h1 { margin: 0; font-size: clamp(1.6rem, 4vw, 2.2rem); line-height: 1.1 }
.lede { margin: .3rem 0 0; color: var(--muted); max-width: 70ch }
.desk { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); gap: 1rem;
        padding: 0 16px 3rem; max-width: 90rem; margin: 0 auto }
#map { position: sticky; top: 1rem; height: calc(100vh - 2rem); border-radius: 10px; border: 1px solid var(--line) }
#map.off { display: grid; place-items: center; color: var(--muted); background: var(--card) }
.list { display: grid; gap: .8rem; align-content: start; min-width: 0 }
h2 { margin: .8rem 0 0; font-size: 1.15rem }
.save { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: .7rem .9rem }
.save.has-pv { display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: .8rem; align-items: start }
.body { min-width: 0 }
.pv { position: sticky; top: .7rem; display: block; line-height: 0 }
.pv img { width: 72px; height: 96px; object-fit: cover; border-radius: 6px; background: var(--line) }
.save header { display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap; align-items: baseline }
.who { font-weight: 700 }
a, .show { color: var(--accent); font-weight: 600 }
.show { background: none; border: 0; padding: 0; font: inherit; cursor: pointer; text-decoration: underline }
a:focus-visible, .show:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px }
.spots { list-style: none; margin: .5rem 0 0; padding: 0; display: grid; gap: .6rem }
.spot { border-top: 1px solid var(--line); padding-top: .55rem; overflow-wrap: anywhere }
.spot.is-on { outline: 2px solid var(--accent); outline-offset: 4px; border-radius: 4px }
q { display: inline-block; background: var(--quote-bg); padding: .05rem .4rem; border-radius: 4px; font-weight: 600 }
.why { display: inline-block; margin-left: .5rem; padding: .05rem .5rem; border-radius: 999px;
       background: var(--warn-bg); color: var(--warn); font-size: .85rem; font-weight: 700 }
.found { margin-top: .3rem }
.found.none, .asked, .tip { color: var(--muted); font-size: .9rem }
.kind { color: var(--muted); font-size: .85rem; margin-left: .3rem }
.addr { color: var(--muted); font-size: .85rem }
.meta { display: flex; flex-wrap: wrap; gap: .3rem 1rem; margin-top: .3rem; font-size: .9rem }
.km { font-variant-numeric: tabular-nums }
.empty { color: var(--muted) }
.dot { width: 14px; height: 14px; border-radius: 50%; border: 2px solid #fff; box-shadow: 0 0 0 1px #0006 }
.dot.pin { background: #1f6f50 } .dot.review { background: #c77700 }
.leaflet-container { font: 13px/1.4 var(--body) }
@media (max-width: 800px) {
  .desk { grid-template-columns: minmax(0, 1fr) }
  #map { position: relative; top: 0; height: 55vh }
}
</style>
</head>
<body>
<header class="top">
  <h1>Spot Pins</h1>
  <p class="lede">{{LEDE}} Green pins checked out; orange ones were found, but too far from the save's area or under a different name.</p>
</header>
<div class="desk">
  <div id="map" role="region" aria-label="Map of the spot pins"></div>
  <div class="list">
    <h2>Pinned</h2>
    {{PINS}}
    <h2>To review ({{N_REVIEW}})</h2>
    <p class="lede">Add <code>lookup: "Other Name"</code> to an entry in data/pins-review.yaml to search
    for that instead, <code>ok: true</code> when the find is right as it is, or <code>drop: true</code> to
    leave it out (on a wrong pin too), then merge again.
    These fixes survive a re-read; deleting an entry does not.</p>
    {{REVIEW}}
  </div>
</div>
<script>
(function () {
  var pts = {{DATA}}, el = document.getElementById("map");
  if (!window.L) { el.classList.add("off"); el.textContent = "The map needs the internet to load."; return; }
  var map = L.map(el, {scrollWheelZoom: true});
  L.tileLayer('{{TILES}}', {maxZoom: 19, attribution: '{{CREDIT}}'}).addTo(map);
  var marks = {};
  pts.forEach(function (p) {
    var icon = L.divIcon({className: "", html: '<div class="dot ' + (p.review ? "review" : "pin") + '"></div>',
                          iconSize: [14, 14], iconAnchor: [7, 7]});
    var m = L.marker([p.lat, p.lon], {icon: icon, title: p.label, alt: p.label}).addTo(map);
    m.bindTooltip(p.label);
    m.on("click", function () { on(p.i, false); });
    marks[p.i] = m;
  });
  if (pts.length) { map.fitBounds(pts.map(function (p) { return [p.lat, p.lon]; }), {padding: [30, 30], maxZoom: 13}); }
  else { map.setView([20, 0], 2); }
  function on(i, fly) {
    document.querySelectorAll(".spot.is-on").forEach(function (x) { x.classList.remove("is-on"); });
    var row = document.getElementById("spot-" + i);
    if (row) { row.classList.add("is-on"); if (!fly) row.scrollIntoView({block: "nearest", behavior: "smooth"}); }
    if (fly && marks[i]) { map.flyTo(marks[i].getLatLng(), 15); marks[i].openTooltip(); }
  }
  document.querySelectorAll(".show").forEach(function (b) {
    b.addEventListener("click", function () { on(+b.dataset.i, true); });
  });
})();
</script>
{{PLAYER}}
</body>
</html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=None, help="where to write the page (default .cache/hub/pins.html)")
    ap.add_argument("--no-previews", action="store_true", help="leave out each save's picture and flipbook")
    args = ap.parse_args(argv)
    pins, review, no_spot = load_yaml(PINS), load_yaml(REVIEW), load_yaml(NO_SPOT)
    try:
        with open(cache("saves.json"), encoding="utf-8") as fh:
            saves = {s["code"]: s for s in json.load(fh)["saves"]}
    except OSError:
        saves = {}
    out = args.out or cache(os.path.join("hub", "pins.html"))
    shown = {}
    if not args.no_previews:
        shown = previews.make_all(codes_shown(pins, review), os.path.join(os.path.dirname(out), "previews"))
    page, n = build(pins, review, no_spot, saves, shown)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    log("pins_page", saves_with_pins=len(pins), saves_in_review=len(review), markers=n,
        previews=sum(1 for v in shown.values() if v.get("poster")),
        flipbooks=sum(1 for v in shown.values() if v.get("anim")), out=out)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
