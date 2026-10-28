#!/usr/bin/env python3
"""decisions_page.py — everything waiting on a person, on one page of the hub.

    decisions_page.py --pilot NAME | --all [--out PATH] [--links FILE] [--make]

Writes $INSTAGRAM_HOME/.cache/hub/decisions.html (the hub's map page links it once it is there).
Give it the scope the hub is built with: a post links to its hub page when that build has one,
and to Instagram otherwise.
It gathers:

  - **Google's place to pick**, for each spot find-google-ids left for a person
    (.cache/google-to-pick.json). Each candidate is a numbered "open in Google Maps" link that
    carries only Google's place id, so Google's own name and address show on Google's page, never
    on this one. Choosing one per spot builds a single `google_ids.py --pick … --none … --chain …` line to
    copy (or `make google-ids PICK=… NONE=… CHAIN=…` with --make). --chain is for a chain with several branches, where any of them will do.
  - **Spots to check**: entries in data/pins-review.yaml that are neither settled (`ok`, `drop`,
    `lookup`) nor already shown at their town with a Google search by name, and below them, folded
    away, the ones shown at their town that a better name would pin exactly.
  - **Tags to check** (data/tags-review.yaml): saves the tagger could not tag, places the agents
    named that config/places.yaml does not list, and topics they suggested that config/topics.yaml
    does not (a topic counts once two saves suggest it; one save's suggestion is shown folded).
  - **Items to check** (data/items-review.yaml): items whose words were not in the caption.
  - **Saves to move** (data/moves.yaml), linking to moves.html.
  - **Steps waiting in the terminal**: agents' answers not merged yet, per kind of batch.
  - **Fetch runs waiting on a go-ahead**: reels in .cache/frames/stuck.txt with no video yet.
  - **Elsewhere**: the decisions made outside the hub (a pull request, a choice to make in chat),
    from --links FILE: a YAML list of {label, url, note} the data repo keeps by hand, so nothing of
    them is in this plugin. An entry with `done: true` is left out.

Every step it names is the plugin's own command, which runs from any folder once INSTAGRAM_HOME
is set; --make prints the data repo's make lines instead. Spots shown at their town only work
already, so they are not counted, but the opening line says how many there are.
build_hub.py writes this page too, so the map always links it.

The page holds post codes and caption words, so it stays under .cache, never in git.
"""

import argparse
import glob
import html
import json
import os
import re
import shlex
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, os.pardir, "shared", "scripts"))
sys.path.insert(0, HERE)
import build_hub as bh  # noqa: E402
import google_places as gp  # noqa: E402
from home import PLUGIN, cache  # noqa: E402
from log import log  # noqa: E402
from pilot import in_pilot  # noqa: E402
from places import load_yaml  # noqa: E402

TO_PICK = "google-to-pick.json"   # written by find-google-ids' google_ids.py
BATCH_KINDS = (("tag", "the tags agents read off captions", "tag-merge"),
               ("locate", "the spots agents found in captions", "locate-merge"),
               ("frames", "the spots agents read off videos", "frames-merge"),
               ("split", "the items agents split out of captions", "split-merge"))
TOPIC_MIN = 2   # a topic suggested by fewer saves is shown, folded, but not counted as waiting


def _script(*parts):
    return "python3 " + shlex.quote(os.path.join(PLUGIN, "skills", *parts))


# Each step the page tells a person to run: the data repo's make line (--make), else the plugin's
# own command, which works from any folder once INSTAGRAM_HOME is set.
COMMANDS = {
    "tag-merge": ("make tag-merge", _script("tag-saves", "scripts", "tag_saves.py") + " --merge"),
    "locate-merge": ("make locate-merge",
                     _script("resolve-post-location", "scripts", "resolve_post_location.py") + " --merge"),
    "frames-merge": ("make frames-merge",
                     _script("resolve-post-location", "scripts", "resolve_post_location.py") + " --merge --frames"),
    "split-merge": ("make split-merge", _script("split-saves", "scripts", "split_saves.py") + " --merge"),
    "places": ("make places", _script("tag-saves", "scripts", "add_places.py") + " && "
               + _script("tag-saves", "scripts", "tag_saves.py") + " --merge"),
}
GOOGLE_IDS = os.path.join(PLUGIN, "skills", "find-google-ids", "scripts", "google_ids.py")

esc = html.escape


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def spot_index(saves, pins, placed):
    """Google key → (spot, [codes]) over every save, as find-google-ids keys them."""
    out = {}
    for s in saves:
        for e in (pins.get(s["code"]) or []) + placed.get(s["code"], []):
            if isinstance(e, dict) and isinstance(e.get("name"), str) and e["name"].strip():
                out.setdefault(gp.spot_key(e), (e, []))[1].append(s["code"])
    return out


def google_rows(to_pick, kept, spots):
    """The spots still to pick: in the to-pick file, still a spot, and not decided since."""
    rows = []
    for k in sorted(to_pick):
        v = to_pick[k]
        if k not in spots or not isinstance(v, dict) or not v.get("ids"):
            continue
        e, codes = spots[k]
        if v.get("query") != gp.query_for(e):
            continue   # the spot's search text changed: its candidates are for another search
        if isinstance(kept.get(k), dict) and kept[k].get("query") == v["query"]:
            continue   # picked, marked none or marked a chain after the search
        rows.append({"key": k, "spot": e, "codes": codes, "query": v["query"],
                     "ids": [i for i in v["ids"] if isinstance(i, str) and i]})
    return rows


def open_review(review):
    """(to check, shown at their town) from pins-review.yaml, as (code, entry) pairs."""
    check, town = [], []
    for code in sorted(review or {}):
        for e in review[code] if isinstance(review[code], list) else []:
            if not isinstance(e, dict) or e.get("drop") or e.get("ok") or e.get("lookup"):
                continue
            why = str(e.get("why") or "")
            # filed under the wrong area: its town-only pin sits in the wrong place, so a person
            # gives it its real town (resolve-post-location, "A spot in the wrong area")
            lookup_miss = any(r.match(why) for r in bh.LOOKUP_MISSES) and not bh.really_elsewhere(e)
            (town if lookup_miss else check).append((code, e))
    return check, town


def tag_review(review):
    """What tags-review.yaml holds for a person: (errors, places, topics).
    errors: [(code, why)] for saves the tagger could not tag; places and topics: name → [codes]
    for the places and topics an agent named that are not on the lists."""
    errors, places, topics = [], {}, {}
    for code in sorted(review or {}):
        r = review[code]
        if not isinstance(r, dict):
            continue
        why = r.get("error")
        if not why and isinstance(r.get("misfiled"), dict):
            why = r["misfiled"].get("error")
        if isinstance(why, str) and why.strip():
            errors.append((code, why.strip()))
        for key, into in (("other_places", places), ("other_topics", topics)):
            for name in r.get(key) or []:
                if isinstance(name, str) and name.strip():
                    into.setdefault(name.strip(), []).append(code)
    return errors, places, topics


def items_review(review):
    """[(code, entry)] from items-review.yaml: items whose quote or topic did not check out."""
    out = []
    for code in sorted(review or {}):
        for e in review[code] if isinstance(review[code], list) else []:
            if isinstance(e, dict):
                out.append((code, e))
    return out


def waiting_answers(batches):
    """kind → answers files not merged yet."""
    return {kind: len(glob.glob(os.path.join(batches, kind, "batch-*.answers.json"))) for kind, _, _ in BATCH_KINDS}


def videos_waiting(stuck_path, media):
    codes = []
    try:
        with open(stuck_path, encoding="utf-8") as fh:
            for line in fh:
                code = line.split("#", 1)[0].strip()
                if code:
                    codes.append(code)
    except OSError:
        return 0
    return sum(1 for c in codes if not (isinstance(media.get(c), dict) and media[c].get("video")))


def load_links(path):
    """The open entries of a hand-kept list: [{label, url, note}]; a url must be http(s) or empty."""
    got = load_yaml(path) if path else []
    out = []
    for x in got if isinstance(got, list) else []:
        if not isinstance(x, dict) or x.get("done") or not str(x.get("label") or "").strip():
            continue
        url = str(x.get("url") or "").strip()
        if url and not re.match(r"^https?://", url):
            sys.exit(f"decisions_page: {path}: {x['label']!r} has a url that is not http(s)")
        out.append({"label": str(x["label"]).strip(), "url": url, "note": str(x.get("note") or "").strip()})
    return out


def hub_pages(saves_list, tags, pilot):
    """The hub's page name per post code, for the saves a build with the same scope puts in the hub.
    Worked out, not looked up on disk: this page is written before build_hub runs, and a post page
    found on a Mac's disk could be another post whose code differs only by case."""
    return bh.Hub._files([s["code"] for s in saves_list if in_pilot(s, tags.get(s["code"]), pilot)])


def post_links(code, saves, pages):
    s = saves.get(code) or {}
    who = (s.get("owner") or {}).get("username")
    url = s.get("url") or f"https://www.instagram.com/p/{code}/"
    out = []
    if code in pages:
        out.append(f'<a href="posts/{esc(pages[code])}.html">{"@" + esc(who) if who else "Post page"}</a>')
    elif who:
        out.append(f'<span>@{esc(who)}</span>')
    out.append(f'<a href="{esc(url)}" target="_blank" rel="noopener">Instagram</a>')
    return " · ".join(out)


def google_card(n, row, saves, pages):
    e, k = row["spot"], row["key"]
    said = e.get("said") if isinstance(e.get("said"), str) and e["said"] != e["name"] else ""
    opts = "".join(
        f'<li><label><input type="radio" name="g{n}" value="pick" data-key="{esc(k)}" data-id="{esc(pid)}"> '
        f'Option {j}</label> <a href="{esc(gp.maps_link(row["query"], pid))}" target="_blank" rel="noopener">'
        f'open in Google Maps</a></li>' for j, pid in enumerate(row["ids"], 1))
    opts += (f'<li><label><input type="radio" name="g{n}" value="chain" data-key="{esc(k)}"> A chain: any branch'
             f' near here</label></li>'
             f'<li><label><input type="radio" name="g{n}" value="none" data-key="{esc(k)}"> None of these</label></li>'
             f'<li><label><input type="radio" name="g{n}" value="" checked> Decide later</label></li>')
    posts = "".join(f'<li>{post_links(c, saves, pages)}</li>' for c in row["codes"])
    where = e.get("address") if isinstance(e.get("address"), str) and e["address"].strip() else e.get("near")
    return (f'<article class="item" id="g-{n}"><header><h3>{esc(e["name"])}</h3>'
            f'<span class="where">{esc(str(where or ""))}</span></header>'
            + (f'<p class="said">The caption says <q>{esc(said)}</q></p>' if said else "")
            + f'<ol class="opts">{opts}</ol><ul class="posts">{posts}</ul></article>')


def review_card(code, e, saves, pages):
    found = (f'<p class="found">OpenStreetMap found <b>{esc(str(e["name"]))}</b>'
             + (f' <span class="muted">{esc(str(e["found"]))}</span>' if e.get("found") else "") + "</p>"
             if e.get("name") and e.get("lat") is not None else "")
    return (f'<article class="item"><header><h3><q>{esc(str(e.get("said") or ""))}</q></h3>'
            f'<span class="where">near {esc(str(e.get("near") or ""))}</span></header>'
            f'<p class="why">{esc(str(e.get("why") or ""))}</p>{found}'
            + (f'<p class="why">The caption puts it in <b>{esc(bh.really_elsewhere(e))}</b>, not near '
               f'{esc(str(e.get("near") or ""))}: say which town, and it is filed and looked up there.</p>'
               if bh.really_elsewhere(e) else "") +
            f'<ul class="posts"><li>{post_links(code, saves, pages)}</li></ul></article>')


def town_row(code, e, saves, pages):
    return (f'<li><q>{esc(str(e.get("said") or ""))}</q> <span class="muted">near {esc(str(e.get("near") or ""))}'
            f' · {esc(str(e.get("why") or ""))}</span> · {post_links(code, saves, pages)}</li>')


def many(n, one, more=None):
    return f"{n:,} {one}" if n == 1 else f"{n:,} {more or one + 's'}"


def cmd_html(cmd):
    return (f'<code class="cmd">{esc(cmd)}</code><button type="button" class="copy" data-copy="{esc(cmd)}">'
            'Copy</button>')


def few_posts(codes, saves, pages, shown=3):
    links = " · ".join(f'<span class="post">{post_links(c, saves, pages)}</span>' for c in codes[:shown])
    return links + (f' <span class="muted">and {len(codes) - shown} more</span>' if len(codes) > shown else "")


def named_rows(named, saves, pages):
    return "".join(f'<li><b>{esc(name)}</b> <span class="muted">{many(len(codes), "save")}</span> · '
                   f'{few_posts(codes, saves, pages)}</li>' for name, codes in named)


def tags_html(errors, places, topics, saves, pages, cmd):
    """The tags section: saves the tagger could not tag, places and topics not on the lists."""
    parts = []
    if errors:
        rows = "".join(f'<li>{post_links(code, saves, pages)} <span class="why">{esc(why)}</span></li>'
                       for code, why in errors)
        parts.append(f'<h3>{many(len(errors), "save")} the tagger could not tag</h3>'
                     '<p class="how">The next tagging round sends each one back to the agents. To settle one now, '
                     'give it its tags in <code>data/tags.yaml</code> with <code>by: hand</code> (the tag-saves skill, '
                     '"Fixing by hand").</p>'
                     f'<ul class="towns">{rows}</ul>')
    if places:
        named = sorted(places.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        parts.append(f'<h3>{many(len(places), "place")} not on your list</h3>'
                     '<p class="how">An agent named these, but <code>config/places.yaml</code> does not list them, so '
                     'those saves have no pin for them yet. This looks each one up on OpenStreetMap, adds the ones it '
                     f'finds and tags the saves again: {cmd("places")}. One it cannot find needs a line in '
                     '<code>config/places.yaml</code> by hand.</p>'
                     f'<ul class="towns">{named_rows(named, saves, pages)}</ul>')
    if topics:
        named = sorted(topics.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        often = [x for x in named if len(x[1]) >= TOPIC_MIN]
        once = [x for x in named if len(x[1]) < TOPIC_MIN]
        parts.append(f'<h3>{many(len(often), "topic")} the agents keep suggesting</h3>'
                     '<p class="how">Not on your topic list in <code>config/topics.yaml</code>. Add the ones you want '
                     'there, then tag again with <code>--retag</code> so those saves get them (the tag-saves skill says '
                     'how). One you do not want: delete it from those saves in <code>data/tags-review.yaml</code>.</p>'
                     + (f'<ul class="towns">{named_rows(often, saves, pages)}</ul>' if often else "")
                     + (f'<details><summary>{many(len(once), "topic")} suggested by one save only (not counted)'
                        f'</summary><ul class="towns">{named_rows(once, saves, pages)}</ul></details>' if once else ""))
    return "".join(parts) or '<p class="empty">Nothing to check: every place and topic the agents named is on your lists.</p>'


def item_card(code, e, saves, pages):
    what = " · ".join(esc(str(e[k])) for k in ("topic", "kind") if e.get(k))
    return (f'<article class="item"><header><h3>{esc(str(e.get("name") or "No usable answer"))}</h3>'
            f'<span class="where">{what}</span></header>'
            + (f'<p class="said">The agent quoted <q>{esc(str(e["quote"]))}</q></p>' if e.get("quote") else "")
            + f'<p class="why">{esc(str(e.get("why") or ""))}</p>'
            f'<ul class="posts"><li>{post_links(code, saves, pages)}</li></ul></article>')


def build(rows, check, town, moves, answers, videos, links, saves, pages, tags=((), {}, {}), items=(),
          make=False):
    cmd = (lambda k: cmd_html(COMMANDS[k][0 if make else 1]))
    errors, places, topics = tags
    n_topics = sum(1 for codes in topics.values() if len(codes) >= TOPIC_MIN)
    counts = {"google": len(rows), "check": len(check), "tags": len(errors) + len(places) + n_topics,
              "items": len(items), "moves": len(moves), "merge": sum(answers.values()),
              "fetch": 1 if videos else 0, "links": len(links)}
    total = sum(counts.values())
    toc = [("#google", "Google's place to pick", counts["google"]), ("#check", "Spots to check", counts["check"]),
           ("#tags", "Tags to check", counts["tags"]), ("#items", "Items to check", counts["items"]),
           ("#moves", "Saves to move", counts["moves"]), ("#terminal", "Steps in the terminal", counts["merge"]),
           ("#chat", "Go-aheads in chat", counts["fetch"]), ("#elsewhere", "Elsewhere", counts["links"])]
    nav = "".join(f'<li><a href="{h}">{esc(t)}</a> <span class="n{" zero" if not c else ""}">{c:,}</span></li>'
                  for h, t, c in toc)

    g = ("".join(google_card(n, r, saves, pages) for n, r in enumerate(rows, 1))
         or '<p class="empty">Nothing to pick: every spot has its place, or none of Google\'s fits.</p>')
    c = ("".join(review_card(code, e, saves, pages) for code, e in check)
         or '<p class="empty">Nothing to check.</p>')
    t = (f'<details id="town"><summary>{many(len(town), "spot")} shown at {"its" if len(town) == 1 else "their"} town only</summary>'
         '<p class="how">These work already: the map shows them at their town and Google Maps searches their '
         'name there. To pin one exactly, give it a better name with <code>lookup: "Other Name"</code>.</p>'
         f'<ul class="towns">{"".join(town_row(code, e, saves, pages) for code, e in town)}</ul></details>'
         if town else "")
    it = ("".join(item_card(code, e, saves, pages) for code, e in items)
          or '<p class="empty">Nothing to check: every item\'s words were found in its caption.</p>')
    m = (f'<p>{many(len(moves), "save")} {"is" if len(moves) == 1 else "are"} filed in a collection that does not fit. '
         '<a href="moves.html">See where each one goes</a>, then move them in Instagram.</p>'
         if moves else '<p class="empty">No saves to move.</p>')
    merge = [f'<li><b>{many(answers[kind], "batch", "batches")}</b> of {esc(what)} are ready. Run {cmd(key)}</li>'
             for kind, what, key in BATCH_KINDS if answers.get(kind)]
    term = (f'<ul class="steps">{"".join(merge)}</ul>' if merge
            else '<p class="empty">Nothing waiting in the terminal.</p>')
    chat = (f'<p>{many(videos, "reel")} still {"needs its" if videos == 1 else "need their"} video to be read. '
            'Each fetch run (at most 100 reels, 3 runs a day) waits for your go-ahead in chat: say '
            '<q>fetch the next videos</q>.</p>' if videos else '<p class="empty">No fetch run waiting.</p>')
    else_ = ("".join((f'<li><a href="{esc(x["url"])}" target="_blank" rel="noopener">{esc(x["label"])}</a>'
                      if x["url"] else f'<li><b>{esc(x["label"])}</b>')
                     + (f' <span class="muted">{esc(x["note"])}</span>' if x["note"] else "") + "</li>" for x in links))
    else_ = f'<ul class="steps">{else_}</ul>' if links else '<p class="empty">Nothing listed.</p>'

    lede = (f"{many(total, 'thing')} {'waits' if total == 1 else 'wait'} on you." if total
            else "Nothing needs a decision right now.")
    if town:   # they work, so they are not counted, but the lede never hides them
        lede += (f" {many(len(town), 'more spot')} {'is' if len(town) == 1 else 'are'} shown at {'its' if len(town) == 1 else 'their'}"
                 " town only, under Spots to check; a better name would pin "
                 f"{'it' if len(town) == 1 else 'them'} exactly.")
    where = ("Run it in the data repo" if make
             else "Run it with INSTAGRAM_HOME set to your saves folder")
    return (TEMPLATE.replace("{{ICON}}", bh.ICON).replace("{{LEDE}}", esc(lede)).replace("{{NAV}}", nav)
            .replace("{{N_GOOGLE}}", str(counts["google"])).replace("{{GOOGLE}}", g)
            .replace("{{N_CHECK}}", str(counts["check"])).replace("{{CHECK}}", c + t)
            .replace("{{LOCATE_MERGE}}", cmd("locate-merge"))
            .replace("{{N_TAGS}}", f'{counts["tags"]:,}').replace("{{TAGS}}", tags_html(errors, places, topics, saves, pages, cmd))
            .replace("{{N_ITEMS}}", str(counts["items"])).replace("{{ITEMS}}", it)
            .replace("{{MOVES}}", m).replace("{{TERMINAL}}", term).replace("{{CHAT}}", chat)
            .replace("{{ELSEWHERE}}", else_).replace("{{WHERE}}", esc(where))
            .replace("{{GOOGLE_MODE}}", "make" if make else "plugin")
            .replace("{{GOOGLE_SCRIPT}}", esc(shlex.quote(GOOGLE_IDS)))), counts


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Your Decisions</title>
{{ICON}}
<style>
/* An in-tray: one column of what waits on a person, each kind under its own heading, with the
   Google picks first because they are the only ones made on this page. */
:root {
  --bg: #f4f3ef; --card: #ffffff; --fg: #1f2320; --muted: #5f675f; --line: #dcdcd3;
  --accent: #1f6f50; --accent-soft: #e2f1e8; --warn: #9a5b00; --warn-bg: #fdf0d8; --quote-bg: #eef5ef;
  --body: system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #151816; --card: #1d211e; --fg: #e5e9e5; --muted: #9ca59d; --line: #2f3530;
  --accent: #6cc79f; --accent-soft: #1d3428; --warn: #f0b860; --warn-bg: #3a2c14; --quote-bg: #1f2c24; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #151816; --card: #1d211e; --fg: #e5e9e5; --muted: #9ca59d; --line: #2f3530;
  --accent: #6cc79f; --accent-soft: #1d3428; --warn: #f0b860; --warn-bg: #3a2c14; --quote-bg: #1f2c24; color-scheme: dark }
* { box-sizing: border-box }
body { margin: 0; background: var(--bg); color: var(--fg); font: 15px/1.5 var(--body) }
.page { max-width: 52rem; margin: 0 auto; padding-inline: 16px; padding-block: 1.2rem 7rem }
h1 { margin: 0; font-size: clamp(1.6rem, 4vw, 2.2rem); line-height: 1.1; text-wrap: balance }
h2 { margin: 2rem 0 .6rem; font-size: 1.2rem; text-wrap: balance }
h3 { margin: 0; font-size: 1rem }
.page > h3 { margin: 1.1rem 0 0 }
.lede, .how { color: var(--muted); max-width: 65ch; margin: .3rem 0 0 }
.back { font-weight: 600 }
a { color: var(--accent); font-weight: 600 }
a:focus-visible, button:focus-visible, input:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px }
.toc { list-style: none; padding: 0; margin: 1rem 0 0; display: flex; flex-wrap: wrap; gap: .4rem .9rem }
.n { display: inline-block; min-width: 1.6em; padding: 0 .4em; border-radius: 999px; text-align: center;
     background: var(--warn-bg); color: var(--warn); font-weight: 700; font-size: .85rem; font-variant-numeric: tabular-nums }
.n.zero { background: var(--line); color: var(--muted) }
.list { display: grid; gap: .7rem }
.item { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: .75rem .9rem; min-width: 0;
        overflow-wrap: anywhere }
.item:has(input[value="pick"]:checked), .item:has(input[value="chain"]:checked),
.item:has(input[value="none"]:checked) { border-color: var(--accent) }
.item header { display: flex; flex-wrap: wrap; gap: .2rem .8rem; align-items: baseline }
.where, .muted { color: var(--muted); font-size: .9rem }
.said, .why, .found { margin: .35rem 0 0 }
.why { display: inline-block; padding: .05rem .5rem; border-radius: 999px; background: var(--warn-bg); color: var(--warn);
       font-size: .85rem; font-weight: 700 }
q { background: var(--quote-bg); padding: .05rem .35rem; border-radius: 4px; font-weight: 600 }
.opts { list-style: none; padding: 0; margin: .5rem 0 0; display: flex; flex-wrap: wrap; gap: .35rem 1.1rem }
.opts label { cursor: pointer }
.posts { list-style: none; padding: 0; margin: .5rem 0 0; display: flex; flex-wrap: wrap; gap: .2rem 1rem; font-size: .9rem }
.steps { padding-left: 1.2rem; display: grid; gap: .5rem }
.towns { padding-left: 1.2rem; display: grid; gap: .35rem; font-size: .92rem }
details { margin-top: .8rem } summary { cursor: pointer; font-weight: 600 }
code { font-family: var(--mono); font-size: .88em; background: var(--quote-bg); padding: .05rem .3rem; border-radius: 4px }
.copy { margin-left: .5rem; font: 600 .85rem var(--body); padding: .2rem .7rem; border-radius: 8px;
        border: 1px solid var(--accent); background: transparent; color: var(--accent); cursor: pointer }
.empty { color: var(--muted) }
.tray { position: fixed; left: 0; right: 0; bottom: 0; padding: .7rem 16px calc(.7rem + env(safe-area-inset-bottom, 0px));
        background: var(--card); border-top: 1px solid var(--line); box-shadow: 0 -4px 14px #0002 }
.tray .in { max-width: 52rem; margin: 0 auto; display: grid; gap: .4rem }
.tray p { margin: 0 }
.tray pre { margin: 0; font-family: var(--mono); font-size: .85rem; white-space: pre-wrap; overflow-wrap: anywhere;
            max-height: 6.5rem; overflow: auto; background: var(--accent-soft); padding: .45rem .6rem; border-radius: 8px }
.tray .row { display: flex; flex-wrap: wrap; gap: .5rem 1rem; align-items: center }
.tray .copy { margin: 0 }
</style>
</head>
<body>
<main class="page">
  <a class="back" href="index.html">← The map</a>
  <h1>Your Decisions</h1>
  <p class="lede">{{LEDE}} Your answers to the Google picks are remembered in this browser until you run
  them.</p>
  <ul class="toc">{{NAV}}</ul>

  <h2 id="google">Google's place to pick ({{N_GOOGLE}})</h2>
  <p class="how">Google gave more than one place for each of these, so it needs you to choose. Open each option to see
  which place it is, then pick it here. Pick <b>A chain</b> when it has several branches and any of them will do: its
  map link then searches every branch nearby. Pick <b>None of these</b> when no option is the place. Your choices build one
  command at the bottom of the page. {{WHERE}}, and the map links open the exact place.</p>
  <div class="list">{{GOOGLE}}</div>

  <h2 id="check">Spots to check ({{N_CHECK}})</h2>
  <p class="how">OpenStreetMap found something, but not clearly the place the post meant. In
  <code>data/pins-review.yaml</code>, add <code>ok: true</code> when the find is right,
  <code>drop: true</code> to leave the spot out, or <code>lookup: "Other Name"</code> to search for another
  name. Then run {{LOCATE_MERGE}}. <a href="pins.html">See them on the map</a>.</p>
  <div class="list">{{CHECK}}</div>

  <h2 id="tags">Tags to check ({{N_TAGS}})</h2>
  <p class="how">What the tagging agents could not settle on their own, from <code>data/tags-review.yaml</code>.</p>
  {{TAGS}}

  <h2 id="items">Items to check ({{N_ITEMS}})</h2>
  <p class="how">Dishes, ideas and tips an agent named whose words are not in the caption, so they were left out, from
  <code>data/items-review.yaml</code>. Add one that is right to <code>data/items/&lt;topic&gt;.yaml</code> by hand with
  <code>by: hand</code> (the split-saves skill), then delete its entry from the review file; delete the entry alone when it
  is wrong.</p>
  <div class="list">{{ITEMS}}</div>

  <h2 id="moves">Saves to move</h2>
  {{MOVES}}

  <h2 id="terminal">Steps waiting in the terminal</h2>
  {{TERMINAL}}

  <h2 id="chat">Go-aheads in chat</h2>
  {{CHAT}}

  <h2 id="elsewhere">Elsewhere</h2>
  {{ELSEWHERE}}
</main>
<div class="tray" id="tray" hidden data-mode="{{GOOGLE_MODE}}" data-script="{{GOOGLE_SCRIPT}}" data-where="{{WHERE}}">
  <div class="in">
    <p id="tally"></p>
    <pre id="cmd"></pre>
    <div class="row"><button type="button" class="copy" id="copy-cmd">Copy the command</button>
    <span class="muted" id="copied" aria-live="polite"></span></div>
  </div>
</div>
<script>
(function () {
  var KEY = "decisions-google-picks", saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { saved = {}; }
  var radios = Array.prototype.slice.call(document.querySelectorAll('.opts input[type="radio"]'));
  radios.forEach(function (r) {
    var s = r.dataset.key && saved[r.dataset.key];   // by spot, so a list that changed keeps each answer
    if (s && r.value === s.value && (r.dataset.id || "") === (s.id || "")) r.checked = true;
    r.addEventListener("change", update);
  });
  function q(s) { return "'" + s.replace(/'/g, "'\\\\''") + "'"; }
  function update() {
    var picks = [], nones = [], chains = [], keep = {};
    radios.forEach(function (r) {
      if (!r.checked || !r.value) return;
      keep[r.dataset.key] = {value: r.value, id: r.dataset.id || ""};
      if (r.value === "pick") picks.push(r.dataset.key + "=" + r.dataset.id);
      else if (r.value === "chain") chains.push(r.dataset.key);
      else nones.push(r.dataset.key);
    });
    try { localStorage.setItem(KEY, JSON.stringify(keep)); } catch (e) {}
    var tray = document.getElementById("tray"), n = picks.length + nones.length + chains.length;
    tray.hidden = !n;
    if (!n) return;
    var said = [];
    if (picks.length) said.push(picks.length + " picked");
    if (chains.length) said.push(chains.length + (chains.length === 1 ? " chain" : " chains"));
    if (nones.length) said.push(nones.length + " with none that fits");
    document.getElementById("tally").textContent = said.join(", ") + ". " + tray.dataset.where + ":";
    var each = function (flag, keys) { return keys.map(function (k) { return " " + flag + " " + q(k); }).join(""); };
    document.getElementById("cmd").textContent = tray.dataset.mode === "make"
      ? "make google-ids PILOT=" + (picks.length ? " PICK=" + q(picks.join(" ")) : "") +
        (nones.length ? " NONE=" + q(nones.join(" ")) : "") + (chains.length ? " CHAIN=" + q(chains.join(" ")) : "")
      : "python3 " + tray.dataset.script + " --all" + each("--pick", picks) + each("--none", nones) +
        each("--chain", chains);
  }
  function copy(text, done) {
    var ok = function () { done("Copied."); };
    try { navigator.clipboard.writeText(text).then(ok, function () { done("Select the text and copy it."); }); }
    catch (e) { done("Select the text and copy it."); }
  }
  document.getElementById("copy-cmd").addEventListener("click", function () {
    copy(document.getElementById("cmd").textContent, function (m) { document.getElementById("copied").textContent = m; });
  });
  document.querySelectorAll("button.copy[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () { copy(b.dataset.copy, function (m) { b.textContent = m === "Copied." ? "Copied" : "Copy"; }); });
  });
  update();
})();
</script>
</body>
</html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument("--pilot", help="the pilot the hub is built for, so posts link to their hub page")
    scope.add_argument("--all", action="store_true", help="the hub is built for every save")
    ap.add_argument("--out", default=None, help="where to write the page (default .cache/hub/decisions.html)")
    ap.add_argument("--links", default=None,
                    help="a YAML list of {label, url, note}: decisions made outside the hub")
    ap.add_argument("--make", action="store_true",
                    help="print the data repo's make lines (make tag-merge) instead of the plugin's commands")
    args = ap.parse_args(argv)
    pilot = None
    if args.pilot:
        pilots = load_yaml(os.path.join("config", "collections.yaml")).get("pilots") or {}
        if args.pilot not in pilots:
            sys.exit(f"no pilot {args.pilot!r} in config/collections.yaml (have: {', '.join(pilots) or 'none'})")
        pilot = pilots[args.pilot] or {}
    links = load_links(args.links)
    saves_path = cache("saves.json")
    saves_list = bh.load_saves(saves_path) if os.path.exists(saves_path) else []
    saves = {s["code"]: s for s in saves_list}
    pages = hub_pages(saves_list, load_yaml(os.path.join("data", "tags.yaml")), pilot)
    pins = load_yaml(os.path.join("data", "pins.yaml"))
    review = load_yaml(os.path.join("data", "pins-review.yaml"))
    placed = bh.placed_spots(review)
    rows = google_rows(load_json(cache(TO_PICK)), load_yaml(os.path.join("data", "google.yaml")),
                       spot_index(saves_list, pins, placed))
    check, town = open_review(review)
    tags = tag_review(load_yaml(os.path.join("data", "tags-review.yaml")))
    items = items_review(load_yaml(os.path.join("data", "items-review.yaml")))
    moves = load_yaml(os.path.join("data", "moves.yaml"))
    moves = moves if isinstance(moves, dict) else {}
    answers = waiting_answers(cache("batches"))
    videos = videos_waiting(cache(os.path.join("frames", "stuck.txt")), load_yaml(os.path.join("data", "media.yaml")))
    out = args.out or cache(os.path.join("hub", "decisions.html"))
    page, counts = build(rows, check, town, moves, answers, videos, links, saves, pages, tags, items, args.make)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    log("decisions_page", **counts, town_only=len(town), out=out)
    print(f"{many(counts['google'], 'Google pick')}, {many(counts['check'], 'spot')} to check "
          f"({many(len(town), 'more spot')} shown at their town only), {many(counts['tags'], 'tag')} to check, "
          f"{many(counts['items'], 'item')} to check, {many(counts['moves'], 'save')} to move, {many(counts['merge'], 'answer file')} to merge, "
          f"{many(videos, 'reel')} waiting for a video, {many(len(links), 'link')}")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
