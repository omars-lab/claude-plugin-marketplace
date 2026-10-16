#!/usr/bin/env python3
"""build_hub.py — the hub as a local site: a map with a pin for each saved post at the places it
names, a page per place listing every saved post that names it, and a page per post.

    build_hub.py --pilot NAME     the pilot's saves (`pilots:` in config/collections.yaml)
    build_hub.py --all            every save
    options: --out DIR            where to write (default $INSTAGRAM_HOME/.cache/hub)

Reads   $INSTAGRAM_HOME/.cache/saves.json          caption, creator, link, saved date, collections
        $INSTAGRAM_HOME/config/topics.yaml         topic labels
        $INSTAGRAM_HOME/config/purposes.yaml       what a post is for, by the kinds of place it names
                                                   (optional: shared/scripts/purposes.py otherwise)
        $INSTAGRAM_HOME/config/collections.yaml    the pilots
        $INSTAGRAM_HOME/data/tags.yaml             code → topics, cities (from tag-saves)
        $INSTAGRAM_HOME/data/places.yaml           each place's kind, pin, the place it sits in
        $INSTAGRAM_HOME/data/pins.yaml             the spots each post names (optional: skipped
                                                   quietly until resolve-post-location has run)
        $INSTAGRAM_HOME/data/pins-review.yaml      spots OpenStreetMap did not place (optional)
        $INSTAGRAM_HOME/data/media.yaml            each post's thumbnail (optional, the same way)
        $INSTAGRAM_MEDIA_DIR/<code>/thumb.jpg      the thumbnails themselves
        $INSTAGRAM_HOME/data/stills.yaml           a still and a 3 s clip per spot a reel names, cut
                                                   where its name, or else its area, is on screen
                                                   (extract-stills; optional, the same way)
Writes  OUT/index.html                             the map, the list of places, a search box
        OUT/places/<slug>.html                     one page per place
        OUT/posts/<code>.html                      one page per post
        OUT/thumbs/<code>.jpg                      copies of the thumbnails media.yaml lists
        OUT/stills/<code>/                         copies of the stills and clips stills.yaml lists
Only places/ and posts/ are cleared on each build; other pages in OUT (the moves page, the pin
review page) are left alone.

Which pin a post gets
  A post's places are its cities in tags.yaml, and every place they sit in. On the map it gets a
  pin at its most exact ones only: a town or park, not the state, when a town is there. A spot
  from pins.yaml (a beach, a café) takes the place of the area it sits in. A post that names only
  a state gets its pin at the state's middle. Every place it names still gets the post on its page,
  so a state's page lists every post in it.
  A spot OpenStreetMap does not list (most small restaurants), or matched only doubtfully, still
  gets its own dashed pin, at its town, and a Google Maps link that searches its name in that town:
  the post opens the venue, not the town. pins-review.yaml stays the list for a person to fix.
  The build ends with a check: of the posts for eating or staying, how many open a spot, a spot
  pinned at its town, or only a town. The codes of the last kind go to the log.

The menus over the map
  State, national attraction, purpose and topic. Each option says how many posts it holds once the
  other menus and the search are applied. A national attraction is a park or spot whose name, or
  the name OpenStreetMap found for it, says National Park, Seashore, Monument and so on. A post's
  purpose comes from the kinds of place it names (a café is "Eat & drink", a park "Adventure &
  outdoors"), plus any `purposes` the tagger gave it; a post that names only towns has none yet.

A spot with a still shows it in place of the post's cover: on the spot's page, in its map popup, and
in the post page's row of places, where the clip plays on hover or with its Play button. Spots cut at
their area's moment (`how: area`) share that one picture: the post page shows it once, titled with
the area, and lists its spots under it.

Spots are grouped across posts by their OpenStreetMap id, else by name and area. A spot with the
same name as its area (a park and its waterfall) is shown on the area's page.

Which saves a pilot holds: the saves in its collections, and any save tagged with one of its
places. That is the same set `tag_saves.py --report` shows.

The pages hold captions and post codes, so they stay under .cache, never in git. The map loads
Leaflet from cdnjs and tiles from OpenStreetMap, with the credit showing; no Instagram script.
"""

import argparse
import ast
import datetime as dt
import html
import json
import os
import re
import shutil
import sys
import unicodedata
from urllib.parse import quote_plus

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, os.pardir, "shared", "scripts"))

import google_places  # noqa: E402
from home import cache  # noqa: E402
from log import log  # noqa: E402
from pilot import in_pilot  # noqa: E402
from places import Places, load_yaml  # noqa: E402
from purposes import NO_PURPOSE, PURPOSES, load as load_purposes  # noqa: E402

MEDIA_DEFAULT = os.path.join("~", "Library", "Mobile Documents", "com~apple~CloudDocs", "CloudDesktop", "data",
                             "instagram")
POPUP_CHARS = 140    # caption shown in a map popup
AROUND = 160         # caption characters shown around the words that name a place
OPENING = 260        # caption shown on a card when no words name the place
WIDE = {"state", "country"}   # kinds that are too big to be a useful pin when a town is there

# A national park, seashore, monument and so on: by its name, or the name OpenStreetMap found for it
# (a place tagged "Example Canyon" can come back as "Example Canyon National Park").
NATIONAL = re.compile(r"\bNational (Park|Seashore|Lakeshore|Monument|Historic|Historical|Forest|Recreation|Preserve|"
                      r"Memorial|Wildlife|Scenic)", re.I)


TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
CREDIT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
CDN = "https://cdnjs.cloudflare.com/ajax/libs"
LEAFLET = (f'<link rel="stylesheet" href="{CDN}/leaflet/1.9.4/leaflet.min.css">'
           f'<script src="{CDN}/leaflet/1.9.4/leaflet.min.js"></script>')
CLUSTER = (f'<link rel="stylesheet" href="{CDN}/leaflet.markercluster/1.5.3/MarkerCluster.css">'
           f'<script src="{CDN}/leaflet.markercluster/1.5.3/leaflet.markercluster.js"></script>')
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@'
         '12..96,600&family=Atkinson+Hyperlegible:wght@400;700&display=swap">')


# ---- reading ----

def literal(v, empty):
    """A field as its real type. Older exports stored some lists and dicts as the text of a Python
    literal ("['a', 'b']"); read those back, and give `empty` for anything else unusable."""
    if isinstance(v, str) and v[:1] in "[{(":
        try:
            v = ast.literal_eval(v)
        except (ValueError, SyntaxError):
            return empty
    if isinstance(empty, list):
        return list(v) if isinstance(v, (list, tuple)) else empty
    return v if isinstance(v, type(empty)) else empty


def load_saves(path):
    with open(path, encoding="utf-8") as fh:
        saves = json.load(fh)["saves"]
    for s in saves:
        s["collections"] = [c for c in literal(s.get("collections"), []) if isinstance(c, str)]
        s["hashtags"] = [h for h in literal(s.get("hashtags"), []) if isinstance(h, str)]
        s["owner"] = literal(s.get("owner"), {})
        s["caption"] = s.get("caption") if isinstance(s.get("caption"), str) else ""
    return saves


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "place"


def number(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def maps_link(name, where=""):
    return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(f"{name}, {where}" if where else name)


# Review entries whose quote and area checked out, and only the map lookup failed or looked doubtful.
# OpenStreetMap is thin on small restaurants and cafés, so these are mostly real venues.
LOOKUP_MISSES = (re.compile(r"^not found near "), re.compile(r"^found .*, a different name$"),
                 re.compile(r"^\d+ km from "))


def placed_spots(review):
    """code → the spots a post names that OpenStreetMap did not place, from pins-review.yaml. Each is
    shown at its town's pin, and its Google Maps link searches the caption's name in that town (or
    at the caption's street address, when it gives one), so the post opens the venue rather than
    the town. A doubtful match's own lat/lon is never used."""
    out = {}
    for code, entries in (review or {}).items():
        for e in entries if isinstance(entries, list) else []:
            if not isinstance(e, dict) or e.get("drop") or not isinstance(e.get("near"), str):
                continue
            if not any(r.match(str(e.get("why") or "")) for r in LOOKUP_MISSES):
                continue
            said = e.get("said") if isinstance(e.get("said"), str) else ""
            # What was searched: a person's lookup, else what the merge asked. Not `name`, which on a
            # doubtful match is the other place OpenStreetMap found.
            name = next((e[k] for k in ("lookup", "asked") if isinstance(e.get(k), str) and e[k].strip()), "")
            name = (name or said.lstrip("@#")).strip()
            if name:
                spot = {"name": name, "said": said, "near": e["near"], "placed": True}
                if isinstance(e.get("address"), str) and e["address"].strip():
                    spot["address"] = e["address"].strip()
                    spot["map"] = maps_link(name, spot["address"])   # the caption's address
                if isinstance(e.get("really_in"), str) and e["really_in"].strip():
                    spot["really_in"] = e["really_in"].strip()   # filed under the wrong area
                out.setdefault(code, []).append(spot)
    return out


def saved_on(save):
    raw = save.get("saved_at")
    if isinstance(raw, str):
        try:
            return dt.datetime.fromisoformat(raw).strftime("%-d %b %Y")
        except ValueError:
            pass
    return save.get("saved_at_text") or ""


# ---- the hub's model: places, posts and pins ----

class Hub:
    """Everything the pages show, worked out once from the data files."""

    def __init__(self, saves, tags, places, pins, media, topics, media_dir, purposes=None, stills=None):
        self.places = {}      # key → place: name, kind, lat, lon, map, parent, spot, posts[], said{}
        self.posts = []       # in-scope saves, newest first, with their places and pins
        self.no_pin = set()   # places with no lat/lon
        self.p = places
        self.topic_label = {k: (v or {}).get("label") or k for k, v in (topics or {}).items()}
        self.purposes = {k: v for k, v in (purposes or PURPOSES).items() if isinstance(v, dict)}
        self.purpose_of = {kind: k for k, v in self.purposes.items() for kind in v.get("kinds") or []}
        aliases = {}
        for said, name in places.aliases.items():
            aliases.setdefault(name, []).append(said)
        self.aliases = aliases
        saves = sorted(saves, key=lambda s: (s.get("saved_at") or "", s["code"]), reverse=True)
        files = self._files([s["code"] for s in saves])
        stills = stills or {}
        for s in saves:
            self._add_post(s, tags.get(s["code"]) or {}, pins.get(s["code"]), media.get(s["code"]),
                           files[s["code"]], media_dir, stills.get(s["code"]))
        self._slugs()
        self.by_code = {p["code"]: p for p in self.posts}
        for p in self.places.values():
            p["inside"] = sorted((k for k, q in self.places.items() if q["parent"] == p["key"]),
                                 key=lambda k: (-len(self.places[k]["posts"]), self.places[k]["name"]))

    @staticmethod
    def _files(codes):
        """A file name per post code. Codes differ by case alone now and then, and a Mac's disk
        does not, so the later one gets a number."""
        seen, out = set(), {}
        for code in sorted(codes):
            name, n = code, 1
            while name.lower() in seen:
                n += 1
                name = f"{code}-{n}"
            seen.add(name.lower())
            out[code] = name
        return out

    def _area(self, name):
        if name not in self.places:
            d = self.p.data.get(name) if isinstance(self.p.data.get(name), dict) else {}
            chain = self.p.chain(name)
            lat, lon = number(d.get("lat")), number(d.get("lon"))
            if lat is None or lon is None:
                lat = lon = None
                self.no_pin.add(name)
            self.places[name] = {"key": name, "name": name, "kind": d.get("kind") or "place", "lat": lat,
                                 "lon": lon, "map": d.get("map") or maps_link(name, chain[0] if chain else ""),
                                 "parent": chain[0] if chain else None, "spot": False, "posts": [], "said": {},
                                 "osm": d.get("osm"), "wikidata": d.get("wikidata"), "notes": d.get("notes"),
                                 "found": d.get("found") if isinstance(d.get("found"), str) else ""}
            for up in chain:
                self._area(up)
        return self.places[name]

    def _spot(self, e, near):
        name = e["name"].strip()
        key = f"osm:{e['osm']}" if isinstance(e.get("osm"), str) and e["osm"] else \
            f"spot:{name.lower()}|{(near or '').lower()}"
        if key not in self.places:
            lat, lon = number(e.get("lat")), number(e.get("lon"))
            if lat is None or lon is None:
                lat = lon = None
                self.no_pin.add(key)
            self.places[key] = {"key": key, "name": name, "kind": e.get("kind") or "spot", "lat": lat, "lon": lon,
                                "map": e.get("map") or maps_link(name, near or ""), "parent": near, "spot": True,
                                "posts": [], "said": {}, "osm": e.get("osm"), "wikidata": e.get("wikidata"),
                                "notes": e.get("notes"), "found": e.get("found") if isinstance(e.get("found"), str) else "",
                                "placed": bool(e.get("placed")), "google_by": e.get("google_by")}
        elif e.get("google_by") and not self.places[key].get("google_by"):   # another post's copy has the id
            self.places[key].update(map=e["map"], google_by=e["google_by"])
        return self.places[key]

    def _name_post(self, place, code, said=None):
        if code not in place["posts"]:
            place["posts"].append(code)
        if said and code not in place["said"]:
            place["said"][code] = said

    def _add_post(self, s, tag, spots, media, file, media_dir, stills=None):
        code = s["code"]
        cut = {r["name"].strip().lower(): r for r in stills if isinstance(r, dict) and isinstance(r.get("name"), str)
               and isinstance(r.get("still"), str)} if isinstance(stills, list) else {}
        shots = []   # a still per spot, in the order the post names them

        def shot(key, name):
            r = cut.get(name.strip().lower())
            if r and all(x["key"] != key for x in shots):
                area = r.get("area") if r.get("how") == "area" and isinstance(r.get("area"), str) else None
                area = (self.p.resolve(area) or area) if area else None
                shots.append({"key": key, "name": name, "t": number(r.get("t")), "area": area,
                              "still_src": os.path.join(media_dir, r["still"]),
                              "clip_src": os.path.join(media_dir, r["clip"]) if isinstance(r.get("clip"), str) else None,
                              "still": None, "clip": None})
        areas = []
        for c in tag.get("cities") or []:
            name = self.p.resolve(c) or c
            if isinstance(name, str) and name not in areas:
                areas.append(name)
        for name in list(areas):
            for up in self.p.chain(name):
                if up not in areas:
                    areas.append(up)
        for name in areas:
            self._name_post(self._area(name), code)

        # Spots: each takes the place of the area it sits in, on the map.
        spot_keys, covered, moved = [], set(), {}
        for e in spots if isinstance(spots, list) else []:
            if not isinstance(e, dict) or not isinstance(e.get("name"), str) or not e["name"].strip():
                continue
            near = self.p.resolve(e.get("near")) or (e.get("near") if isinstance(e.get("near"), str) else None)
            said = e.get("said") if isinstance(e.get("said"), str) else None
            if near:
                for up in [near] + self.p.chain(near):
                    self._name_post(self._area(up), code)
                    if up not in areas:
                        areas.append(up)
                covered.add(near)
            if e.get("placed"):   # not found on OpenStreetMap: shown at its town
                if not near or near not in self.places:
                    continue
                e = {**e, "lat": self.places[near]["lat"], "lon": self.places[near]["lon"]}
            if near and e["name"].strip().lower() == near.lower():   # the spot is the area itself
                self._name_post(self.places[near], code, said)
                shot(near, e["name"])
                lat, lon = number(e.get("lat")), number(e.get("lon"))
                if lat is not None and lon is not None:
                    moved[near] = (lat, lon)
                covered.discard(near)
                continue
            spot = self._spot(e, near)
            self._name_post(spot, code, said)
            shot(spot["key"], e["name"])
            if spot["key"] not in spot_keys:
                spot_keys.append(spot["key"])

        # The most exact areas: the ones no other area of this post sits inside.
        inside = {up for a in areas for up in self.p.chain(a)}
        leaves = [a for a in areas if a not in inside]
        pins = []
        for key in spot_keys:
            sp = self.places[key]
            if sp["lat"] is not None:
                pins.append((key, sp["lat"], sp["lon"], "placed" if sp.get("placed") else "spot"))
            elif sp["parent"]:
                covered.discard(sp["parent"])
        for a in leaves:
            if a in covered:
                continue
            ll = moved.get(a) or (self.places[a]["lat"], self.places[a]["lon"])
            if ll[0] is not None:
                pins.append((a, ll[0], ll[1], "wide" if self.places[a]["kind"] in WIDE else "area"))
        if not pins:   # no exact place has a pin: use the nearest place around them that has one
            for a in leaves:
                up = next((u for u in self.p.chain(a) if self.places.get(u, {}).get("lat") is not None), None)
                if up and all(p[0] != up for p in pins):
                    pins.append((up, self.places[up]["lat"], self.places[up]["lon"], "wide"))

        thumb_src = None
        if isinstance(media, dict) and isinstance(media.get("thumb"), str):
            thumb_src = os.path.join(media_dir, media["thumb"])
        owner = s["owner"]
        self.posts.append({
            "code": code, "file": file, "url": s.get("url") or f"https://www.instagram.com/p/{code}/",
            "kind": s.get("kind") or "post", "user": owner.get("username") or "", "name": owner.get("name") or "",
            "caption": s["caption"], "saved": saved_on(s), "collections": s["collections"],
            "topics": [t for t in tag.get("topics") or [] if isinstance(t, str)],
            "exact": spot_keys + [a for a in leaves if a not in {self.places[k]["parent"] for k in spot_keys}],
            "areas": areas, "pins": pins, "thumb_src": thumb_src, "thumb": None, "shots": shots,
            "tagged_purposes": [t for t in tag.get("purposes") or [] if isinstance(t, str)]})

    def _slugs(self):
        used = set()
        for p in sorted(self.places.values(), key=lambda p: (p["spot"], p["name"].lower(), p["key"])):
            base = slugify(p["name"])
            slug, n = base, 1
            while slug in used:
                n += 1
                slug = f"{base}-{n}"
            used.add(slug)
            p["slug"] = slug

    def post(self, code):
        return self.by_code[code]

    @staticmethod
    def shot(post, key):
        """The post's still of this place, when it has one copied into the site."""
        return next((x for x in post["shots"] if x["key"] == key and x["still"]), None)

    def named(self, post):
        """Every place a post names, exact ones first, each once."""
        return list(dict.fromkeys(post["exact"] + post["areas"]))

    def national(self, place):
        return (place["spot"] or place["kind"] == "park") and bool(
            NATIONAL.search(place["name"]) or NATIONAL.search(place.get("found") or ""))

    def facets(self, post):
        """The menu values a post falls under: its states, national parks, purposes and topics."""
        named = [self.places[k] for k in self.named(post)]
        purposes = [t for t in post["tagged_purposes"] if t in self.purposes]
        for p in named:
            k = self.purpose_of.get(p["kind"])
            if k and k not in purposes:
                purposes.append(k)
        return {"st": [p["key"] for p in named if p["kind"] == "state"],
                "np": [p["key"] for p in named if self.national(p)],
                "pu": purposes or [NO_PURPOSE[0]],
                "tp": list(post["topics"])}

    def within(self, key, cities):
        """True when the place is one of `cities` or sits inside one."""
        while key:
            if key in cities:
                return True
            key = self.places[key]["parent"] if key in self.places else None
        return False

    def words_for(self, place):
        """The words a caption might use for a place: its name, the names that mean it, its hashtag."""
        name = place["name"]
        out = [name] + self.aliases.get(place["key"], [])
        out.append("#" + re.sub(r"[^a-z0-9]", "", name.lower()))
        return [w for w in out if w.strip("#")]


# ---- writing ----

def esc(v):
    return html.escape(str(v), quote=True)


def data_json(obj):
    """JSON safe to sit inside a <script>: a caption may hold "</script>"."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def excerpt(caption, words):
    """The caption around the first of `words` it holds, escaped, with those words marked; or the
    caption's opening when it holds none of them. Returns (html, found)."""
    text = " ".join(caption.split())
    for w in words:
        w = " ".join((w or "").split())
        if not w:
            continue
        m = re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", text, re.I)
        if m:
            a, b = max(0, m.start() - AROUND), min(len(text), m.end() + AROUND)
            if a:   # start and end on whole words
                a = text.find(" ", a, m.start()) + 1 or a
            if b < len(text):
                cut = text.rfind(" ", m.end(), b)
                b = cut if cut > m.end() else b
            return (("…" if a else "") + esc(text[a:m.start()]) + "<mark>" + esc(m.group(0)) + "</mark>"
                    + esc(text[m.end():b]) + ("…" if b < len(text) else "")), True
    cut = text[:OPENING]
    return esc(cut) + ("…" if len(text) > len(cut) else ""), False


def short(text, n):
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n].rstrip() + "…"


def place_href(p, up=True):
    return ("../" if up else "") + f"places/{p['slug']}.html"


def post_href(post, up=True):
    return ("../" if up else "") + f"posts/{post['file']}.html"


def thumb_html(post, up=True, cls="thumb"):
    if post["thumb"]:
        return f'<img class="{cls}" src="{"../" if up else ""}{esc(post["thumb"])}" alt="" loading="lazy">'
    return f'<span class="{cls} ph" aria-hidden="true">{esc(post["kind"])}</span>'


# OpenStreetMap types that say what a road or building is, not what the place is: a bridge on a main
# road comes back as "primary". These show as "Spot".
NOT_A_KIND = {"yes", "primary", "secondary", "tertiary", "trunk", "motorway", "residential", "unclassified",
              "service", "road", "footway", "house", "building"}


def kind_word(p):
    if p["kind"] in NOT_A_KIND:
        return "Spot"
    return {"city": "Town or city", "park": "Park", "region": "Region", "state": "State", "country": "Country",
            "other": "Place", "place": "Place"}.get(p["kind"], str(p["kind"]).replace("_", " ").capitalize())


def shell(title, content, head="", script="", body=""):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<title>{esc(title)}</title>{FONTS}{head}<style>{CSS}</style></head>'
            + (f'<body class="{body}">' if body else "<body>") + f'{content}{script}</body></html>')


MINI_JS = """<script>(function(){var d=__DATA__;if(!window.L||!d.length)return;
var m=L.map('mini',{scrollWheelZoom:false});
L.tileLayer('__TILES__',{maxZoom:19,attribution:'__CREDIT__'}).addTo(m);
var pts=[];d.forEach(function(p){var mk=L.marker([p[0],p[1]],{title:p[2],alt:p[2],
icon:L.divIcon({className:'',html:'<div class="pin pin-'+p[4]+'"></div>',iconSize:[18,18],iconAnchor:[9,9]})}).addTo(m);
mk.bindTooltip(p[2],{direction:'top',offset:[0,-8]});if(p[3])mk.on('click',function(){location.href=p[3]});pts.push([p[0],p[1]]);});
if(pts.length===1)m.setView(pts[0],__ZOOM__);else m.fitBounds(pts,{padding:[30,30],maxZoom:13});})();</script>"""


def mini_map(points, zoom=11):
    """A small map: points are (lat, lon, label, link or "", style)."""
    if not points:
        return "", ""
    js = (MINI_JS.replace("__DATA__", data_json(points)).replace("__TILES__", TILES)
          .replace("__CREDIT__", CREDIT).replace("__ZOOM__", str(zoom)))
    return '<div id="mini" role="img" aria-label="Map"></div>', js


def topic_chips(hub, topics):
    return "".join(f'<li>{esc(hub.topic_label.get(t, t))}</li>' for t in topics)


def at(t):
    """Seconds into a reel, as 0:07."""
    return f"{int(t) // 60}:{int(t) % 60:02d}" if t is not None else ""


def still_html(post, x, cls, up=True):
    pre = "../" if up else ""
    clip = f' data-clip="{pre}{esc(x["clip"])}"' if x["clip"] else ""
    when = f', {at(x["t"])} into the reel' if x["t"] is not None else ""
    alt = f'The {x["area"]} part of the reel{when}' if x.get("area") else x["name"] + when
    return f'<img class="{cls}" src="{pre}{esc(x["still"])}"{clip} alt="{esc(alt)}" loading="lazy">'


def card(hub, place, post):
    x = hub.shot(post, place["key"])
    words = ([place["said"][post["code"]]] if post["code"] in place["said"] else []) + hub.words_for(place)
    text, found = excerpt(post["caption"], words)
    who = f'@{esc(post["user"])}' if post["user"] else "an unknown creator"
    label = "The caption says" if found else "The caption opens"
    return (f'<article class="card"><a class="tlink" href="{post_href(post)}" tabindex="-1" aria-hidden="true">'
            f'{still_html(post, x, "thumb") if x else thumb_html(post)}</a><div class="cbody">'
            f'<p class="who"><a href="{post_href(post)}">{who}</a>'
            + (f' <span class="muted">· saved {esc(post["saved"])}</span>' if post["saved"] else "") + '</p>'
            f'<p class="said"><span class="label">{label}</span> {text}</p>'
            + (f'<ul class="chips">{topic_chips(hub, post["topics"])}</ul>' if post["topics"] else "")
            + f'<p class="links"><a href="{post_href(post)}">Post page</a>'
            f'<a href="{esc(post["url"])}" target="_blank" rel="noopener">Open on Instagram</a></p>'
            '</div></article>')


def place_page(hub, place):
    parent = hub.places.get(place["parent"]) if place["parent"] else None
    rows = []
    if parent:
        rows.append(("Sits in", f'<a href="{place_href(parent)}">{esc(parent["name"])}</a>'))
    if place["inside"]:
        rows.append((f"Places inside it ({len(place['inside'])})", '<ul class="inline">' + "".join(
            f'<li><a href="{place_href(hub.places[k])}">{esc(hub.places[k]["name"])}</a> '
            f'<span class="muted">{len(hub.places[k]["posts"])}</span></li>' for k in place["inside"]) + "</ul>"))
    where = [f'<a href="{esc(place["map"])}" target="_blank" rel="noopener">Google Maps</a>'
             + {"auto": ' <span class="muted">(this place, matched by its name: check it)</span>',
                "claude": ' <span class="muted">(this place, picked by Claude from Google\'s list: check it)</span>',
                "hand": ' <span class="muted">(this place)</span>'}.get(place.get("google_by"), "")]
    if isinstance(place.get("osm"), str) and re.match(r"^(node|way|relation)/\d+$", place["osm"]):
        where.append(f'<a href="https://www.openstreetmap.org/{esc(place["osm"])}" target="_blank" '
                     f'rel="noopener">OpenStreetMap</a>')
    if isinstance(place.get("wikidata"), str) and re.match(r"^Q\d+$", place["wikidata"]):
        where.append(f'<a href="https://www.wikidata.org/wiki/{esc(place["wikidata"])}" target="_blank" '
                     f'rel="noopener">Wikidata</a>')
    rows.append(("On a map", " · ".join(where)))
    if place["lat"] is None:
        rows.append(("Pin", '<span class="muted">not looked up yet, so it is not on the map</span>'))
    elif place.get("placed"):
        rows.append(("Pin", f'<span class="muted">at {esc(place["parent"])}: OpenStreetMap does not list it, '
                            'so Google Maps searches for it by name</span>'))
    points = []
    if place["lat"] is not None:
        points.append([place["lat"], place["lon"], place["name"], "", "spot" if place["spot"] else "here"])
    for k in place["inside"]:
        q = hub.places[k]
        if q["lat"] is not None:
            points.append([q["lat"], q["lon"], q["name"], q["slug"] + ".html", "inside"])
    box, js = mini_map(points, 13 if place["spot"] else (6 if place["kind"] in WIDE else 10))
    posts = [hub.post(c) for c in place["posts"]]
    n = len(posts)
    notes = f'<p class="notes">{esc(place["notes"])}</p>' if isinstance(place.get("notes"), str) else ""
    sub = esc(kind_word(place)) + (f' in <a href="{place_href(parent)}">{esc(parent["name"])}</a>' if parent else "")
    content = (f'<main class="page"><nav class="top"><a href="../index.html">&larr; The map</a></nav>'
               f'<header><h1>{esc(place["name"])}</h1><p class="sub">{sub} · '
               f'{n} saved post{"" if n == 1 else "s"}</p>{notes}</header>'
               f'<div class="facts{"" if box else " solo"}">{box}<dl>'
               + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows) + '</dl></div>'
               f'<section><h2>Saved posts that name it</h2><div class="cards">'
               + "".join(card(hub, place, p) for p in posts) + '</div></section></main>')
    clips = CLIP_JS if any(hub.shot(p, place["key"]) for p in posts) else ""
    return shell(place["name"], content, LEAFLET if box else "", js + clips)


def post_page(hub, post):
    who = f'@{post["user"]}' if post["user"] else "Unknown creator"
    exact = [hub.places[k] for k in post["exact"]]
    wider = [hub.places[k] for k in post["areas"] if k not in post["exact"]]
    rows = [("Creator", (f'<a href="https://www.instagram.com/{esc(post["user"])}/" target="_blank" rel="noopener">'
                         f'{esc(who)}</a>' if post["user"] else esc(who))
             + (f' <span class="muted">{esc(post["name"])}</span>' if post["name"] else ""))]
    if post["saved"]:
        rows.append(("Saved", esc(post["saved"])))
    if post["topics"]:
        rows.append(("Topics", f'<ul class="chips">{topic_chips(hub, post["topics"])}</ul>'))
    if post["collections"]:
        rows.append(("Collections", esc(", ".join(post["collections"]))))
    if exact:
        rows.append((f"Places it names ({len(exact)})", '<ul class="inline">' + "".join(
            f'<li><a href="{place_href(p)}">{esc(p["name"])}</a> <a class="gmap" href="{esc(p["map"])}" '
            f'target="_blank" rel="noopener" aria-label="{esc(p["name"])} in Google Maps">Google Maps</a></li>'
            for p in exact) + "</ul>"))
    if wider:
        rows.append(("Inside", '<ul class="inline">' + "".join(
            f'<li><a href="{place_href(p)}">{esc(p["name"])}</a></li>' for p in wider) + "</ul>"))
    if not exact and not wider:
        rows.append(("Places", '<span class="muted">none tagged</span>'))
    points = [[lat, lon, hub.places[k]["name"], place_href(hub.places[k]), style] for k, lat, lon, style in post["pins"]]
    zoom = 9 if len(points) == 1 and hub.places[post["pins"][0][0]]["kind"] in ("region", "park") else 11
    box, js = mini_map(points, 6 if points and points[0][4] == "wide" else zoom)
    caption = esc(post["caption"]) if post["caption"].strip() else '<span class="muted">No caption.</span>'
    # In the order they show in the video, not the order the caption lists them.
    shots = sorted((x for x in post["shots"] if x["still"]), key=lambda x: x["t"] if x["t"] is not None else 1e9)
    credit = f"from @{esc(post['user'])}'s {esc(post['kind'])}" if post["user"] else f"from the {esc(post['kind'])}"
    gallery = ""
    if shots:
        # Spots shown by their area's moment share one picture: one figure for the area, its spots under it.
        figures = []
        for x in shots:
            same = next((f for f in figures if x.get("area") and f[0]["still"] == x["still"]), None)
            same.append(x) if same else figures.append([x])

        def figure(group):
            x = group[0]
            link = lambda k: f'<a href="{place_href(hub.places[k])}">{esc(hub.places[k]["name"])}</a>'
            area = hub.places.get(x["area"]) if x.get("area") else None
            first = place_href(area) if area else place_href(hub.places[x["key"]])
            title = (link(x["area"]) if area else f'<b>{esc(x["area"])}</b>') if x.get("area") else link(x["key"])
            spots = ('<span class="muted">' + ("Spot" if len(group) == 1 else "Spots") + " here: "
                     + ", ".join(link(g["key"]) for g in group) + "</span>") if x.get("area") else ""
            return (f'<figure class="shotc"><a href="{first}">{still_html(post, x, "shot")}</a><figcaption>{title}'
                    f'<span class="muted">' + (f'{at(x["t"])} · ' if x["t"] is not None else "") + f'{credit}</span>'
                    + spots + ('<button class="play" type="button" aria-pressed="false">Play 3 s</button>' if x["clip"] else "")
                    + '</figcaption></figure>')
        by_area = any(x.get("area") for x in shots)
        gallery = (f'<section><h2>The places in the video ({len(figures)})</h2>'
                   '<p class="muted hint">Each picture is the moment the place\'s name is on screen'
                   + (", or, for spots the video doesn't name, the moment their area is" if by_area else "")
                   + '. Hover, or press Play, for 3 seconds of the video.</p><div class="shots">'
                   + "".join(figure(g) for g in figures) + '</div></section>')
    content = (f'<main class="page"><nav class="top"><a href="../index.html">&larr; The map</a></nav>'
               f'<header><h1>{esc(who)}</h1><p class="sub">A saved {esc(post["kind"])}'
               + (f' · saved {esc(post["saved"])}' if post["saved"] else "") + '</p></header>'
               + (f'<div class="post">{thumb_html(post, cls="big")}' if post["thumb"] else '<div class="post solo">')
               + '<div class="pbody">'
               f'<p class="cta"><a class="button" href="{esc(post["url"])}" target="_blank" rel="noopener">'
               f'Open on Instagram</a>'
               + (f'<a class="button alt" href="{esc(exact[0]["map"])}" target="_blank" rel="noopener">'
                  f'Open in Google Maps</a>' if len(exact) == 1 else "") + '</p>'
               f'<dl>' + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows) + '</dl></div></div>'
               f'{gallery}{box}<section><h2>Caption</h2><p class="caption">{caption}</p></section></main>')
    return shell(f"{who} · saved post", content, LEAFLET if box else "", js + (CLIP_JS if shots else ""))


# A still turns into its clip while the pointer is on it, or while its Play button is pressed. With
# reduced motion asked for, only the button plays it.
CLIP_JS = """<script>(function(){var calm=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
document.querySelectorAll('img[data-clip]').forEach(function(img){var s=img.getAttribute('src'),c=img.getAttribute('data-clip'),
f=img.closest('figure'),b=f&&f.querySelector('button.play'),on=false;
function set(v){on=v;img.src=v?c:s;if(b){b.setAttribute('aria-pressed',String(v));b.textContent=v?'Stop':'Play 3 s'}}
if(!calm){img.addEventListener('mouseenter',function(){set(true)});img.addEventListener('mouseleave',function(){set(false)})}
if(b)b.addEventListener('click',function(){set(!on)});});})();</script>"""


MAP_JS = r"""
(function(){
var D=__DATA__, map, layer, marks=[];
var $=function(s){return document.querySelector(s)};
function el(tag,cls,text){var e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e}
function link(href,text,out){var a=el('a',null,text);a.href=href;if(out){a.target='_blank';a.rel='noopener'}return a}
function tidy(s){return String(s).toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g,'').replace(/[’']/g,'')}

function popup(pin){
  var p=D.posts[pin[2]], pl=D.places[pin[3]], box=el('div','pop');
  var th=(p.sp&&p.sp[pin[3]])||p.th;if(th){var img=el('img');img.src=th;img.alt='';box.appendChild(img)}
  box.appendChild(el('p','pwho',p.u?'@'+p.u:'Unknown creator'));
  var where=el('p','pwhere');where.appendChild(link(pl.s,pl.n));box.appendChild(where);
  if(pl.x)box.appendChild(el('p','pnote','Pinned at the town: OpenStreetMap does not list it. Google Maps searches for it by name.'));
  if(p.t)box.appendChild(el('p','ptext',p.t));
  var ln=el('p','plinks');ln.appendChild(link(p.f,'Post page'));ln.appendChild(link(p.i,'Open on Instagram',true));
  ln.appendChild(link(pl.m,'Open in Google Maps',true));
  box.appendChild(ln);return box;
}

function icon(level){return L.divIcon({className:'',html:'<div class="pin pin-'+level+'"></div>',iconSize:[18,18],iconAnchor:[9,9]})}

// A bubble counts posts, not pins: a road-trip post that names 20 places is one post.
function cluster(c){var seen={},n=0;c.getAllChildMarkers().forEach(function(m){if(!seen[m.post]){seen[m.post]=1;n++}});
  var s=n<10?34:n<50?40:48;
  return L.divIcon({html:'<div class="bubble"><span>'+n+'</span></div>',className:'',iconSize:[s,s]})}

function showPins(keep){
  layer.clearLayers();var on=[],fit=[];
  marks.forEach(function(m,i){if(!keep||keep(D.pins[i])){on.push(m);if(keep||D.pins[i][5])fit.push(m.getLatLng())}});
  layer.addLayers(on);
  if(!fit.length)fit=on.map(function(m){return m.getLatLng()});
  if(fit.length){map.fitBounds(L.latLngBounds(fit),{padding:[30,30],maxZoom:12})}
  return on.length;
}

function placesList(rows){
  var ol=el('ol','plist');
  rows.forEach(function(pl){
    var a=link(pl.s,null);a.appendChild(el('span','pname',pl.n));a.appendChild(el('span','pkind',pl.k));
    a.appendChild(el('span','pcount',String(pl.c)));var li=el('li');li.appendChild(a);ol.appendChild(li);
  });
  return ol;
}

function postsList(rows){
  var ol=el('ol','rlist');
  rows.forEach(function(p){
    var a=link(p.f,null);a.appendChild(el('span','rwho',p.u?'@'+p.u:'Unknown creator'));
    a.appendChild(el('span','rtext',p.t||''));var li=el('li');li.appendChild(a);ol.appendChild(li);
  });
  return ol;
}

// The menus: sel[k] is the chosen option of menu k, or -1 for any. A post shows when it falls under
// every chosen option and holds every search word. Each menu counts the posts the other menus and
// the search leave, so a count is what picking that option would show.
var F=D.facets, sel={};
F.forEach(function(f){sel[f.k]=-1});
function fits(p,skip){return F.every(function(f){return f.k===skip||sel[f.k]<0||p.g[f.k].indexOf(sel[f.k])>=0})}
// A place is in a picked state or park when it is that place or sits inside it. A road-trip post
// that names a park also names places far from it; those stay off the map while the park is picked.
function within(pl){return ['st','np'].every(function(k){return sel[k]<0||pl.g[k].indexOf(sel[k])>=0})}

function fill(f,n){
  var s=$('#f-'+f.k);s.textContent='';s.classList.toggle('on',sel[f.k]>=0);
  var any=el('option',null,f.all);any.value='-1';s.appendChild(any);
  var order=f.o.map(function(o,j){return j}).filter(function(j){return j!==f.none&&(n[j]||j===sel[f.k])});
  order.sort(function(a,b){return n[b]-n[a]||a-b});
  if(f.none!=null&&(n[f.none]||f.none===sel[f.k]))order.push(f.none);
  order.forEach(function(j){var o=el('option',null,f.o[j][1]+' ('+n[j]+')');o.value=String(j);s.appendChild(o)});
  s.value=String(sel[f.k]);
}

function remember(q){
  var h=[];if(q)h.push('q='+encodeURIComponent(q));
  F.forEach(function(f){if(sel[f.k]>=0)h.push(f.k+'='+encodeURIComponent(f.o[sel[f.k]][0]))});
  try{history.replaceState(null,'',h.length?'#'+h.join('&'):location.pathname)}catch(e){}
}

function search(){
  var out=$('#out');out.textContent='';var q=tidy($('#q').value.trim());
  var words=q.split(/\s+/).filter(Boolean);
  function hit(text){var t=tidy(text);return words.every(function(w){return t.indexOf(w)>=0})}
  var said=D.posts.map(function(p){return hit(p.q)});
  F.forEach(function(f){
    var n=f.o.map(function(){return 0});
    D.posts.forEach(function(p,i){if(said[i]&&fits(p,f.k))p.g[f.k].forEach(function(j){n[j]++})});
    fill(f,n);
  });
  var chosen=F.some(function(f){return sel[f.k]>=0});
  $('#clear').hidden=!chosen&&!q;
  remember(q);
  if(!q&&!chosen){
    showPins(null);
    out.appendChild(el('h2',null,'Places, most saved first'));
    out.appendChild(placesList(D.places.filter(function(pl){return pl.c})));
    return;
  }
  var ok={}, ps=[], cnt=D.places.map(function(){return 0});
  D.posts.forEach(function(p,i){if(said[i]&&fits(p)){ok[i]=1;ps.push(p);p.pl.forEach(function(j){cnt[j]++})}});
  var pls=[];
  D.places.forEach(function(pl,i){if(cnt[i]&&within(pl)&&(!q||hit(pl.n)))pls.push({n:pl.n,s:pl.s,k:pl.k,c:cnt[i]})});
  pls.sort(function(a,b){return b.c-a.c});
  var n=showPins(function(pin){return ok[pin[2]]&&within(D.places[pin[3]])});
  out.appendChild(el('p','said',ps.length+' post'+(ps.length===1?'':'s')+' at '+pls.length+' place'+(pls.length===1?'':'s')+
    ' match. '+n+' pin'+(n===1?' is':'s are')+' on the map.'));
  if(pls.length){out.appendChild(el('h2',null,'Places'));out.appendChild(placesList(pls))}
  if(ps.length){out.appendChild(el('h2',null,'Posts'));out.appendChild(postsList(ps.slice(0,100)));
    if(ps.length>100)out.appendChild(el('p','said','Showing the first 100.'))}
}

if(!window.L){$('#out').textContent='The map could not load (no connection to cdnjs?). The place pages still work.';return}
map=L.map('map',{worldCopyJump:true}).setView([37,-119],5);
L.tileLayer('__TILES__',{maxZoom:19,attribution:'__CREDIT__'}).addTo(map);
layer=L.markerClusterGroup({showCoverageOnHover:false,maxClusterRadius:45,iconCreateFunction:cluster});
D.pins.forEach(function(pin){
  var p=D.posts[pin[2]],pl=D.places[pin[3]];
  var m=L.marker([pin[0],pin[1]],{icon:icon(pin[4]),title:(p.u?'@'+p.u:'')+' · '+pl.n,alt:pl.n,keyboard:true});
  m.post=pin[2];
  m.bindPopup(function(){return popup(pin)},{maxWidth:260,minWidth:200,autoPanPadding:[20,20]});
  marks.push(m);
});
map.addLayer(layer);
location.hash.slice(1).split('&').forEach(function(kv){
  var i=kv.indexOf('='),k=kv.slice(0,i),v=decodeURIComponent(kv.slice(i+1));if(i<0)return;
  if(k==='q')$('#q').value=v;
  F.forEach(function(f){if(f.k===k)f.o.forEach(function(o,j){if(o[0]===v)sel[k]=j})});
});
F.forEach(function(f){$('#f-'+f.k).addEventListener('change',function(e){sel[f.k]=+e.target.value;search()})});
$('#clear').addEventListener('click',function(){F.forEach(function(f){sel[f.k]=-1});$('#q').value='';search()});
search();
var t;$('#q').addEventListener('input',function(){clearTimeout(t);t=setTimeout(search,180)});
$('form').addEventListener('submit',function(e){e.preventDefault();search()});
})();
"""


MENUS = (("st", "State", "All states"), ("np", "National attraction", "All national parks and sites"),
         ("pu", "Purpose", "All purposes"), ("tp", "Topic", "All topics"))


def menus(hub, places):
    """The menus over the map, each post's options in them, and each place's state and national
    attraction (itself or what it sits in). An option is [id for the link, label, posts under it];
    options run most posts first, and "not worked out yet" last."""
    per = [hub.facets(p) for p in hub.posts]
    label = {"st": lambda v: hub.places[v]["name"], "np": lambda v: hub.places[v]["name"],
             "pu": lambda v: hub.purposes[v]["label"] if v in hub.purposes else NO_PURPOSE[1],
             "tp": lambda v: hub.topic_label.get(v, v)}
    out, picks, ats = [], [{} for _ in per], {}
    for key, name, every in MENUS:
        n = {}
        for f in per:
            for v in f[key]:
                n[v] = n.get(v, 0) + 1
        values = sorted(n, key=lambda v: (v == NO_PURPOSE[0], -n[v], label[key](v)))
        at = {v: i for i, v in enumerate(values)}
        menu = {"k": key, "n": name, "all": every, "o": [[slugify(label[key](v)), label[key](v), n[v]] for v in values]}
        if NO_PURPOSE[0] in at:
            menu["none"] = at[NO_PURPOSE[0]]
        out.append(menu)
        for i, f in enumerate(per):
            picks[i][key] = [at[v] for v in f[key]]
        ats[key] = at
    inside = []
    for p in places:
        up, chain = p["key"], []
        while up in hub.places and up not in chain:
            chain.append(up)
            up = hub.places[up]["parent"]
        inside.append({k: [ats[k][u] for u in chain if u in ats[k]] for k in ("st", "np")})
    return out, picks, inside


def index_page(hub, title, extra_links, home=()):
    """The map page. It opens on the pins inside `home` (the pilot's places), else on every pin."""
    places = sorted((p for p in hub.places.values()), key=lambda p: (-len(p["posts"]), p["name"]))
    pidx = {p["key"]: i for i, p in enumerate(places)}
    posts = hub.posts
    facets, picks, inside = menus(hub, places)
    data = {
        "places": [{"n": p["name"], "s": place_href(p, up=False), "c": len(p["posts"]), "m": p["map"],
                    "k": ("spot" if p["spot"] else kind_word(p).lower()), "g": inside[i],
                    **({"x": 1} if p.get("placed") else {})} for i, p in enumerate(places)],
        "posts": [{"c": p["code"], "u": p["user"], "f": post_href(p, up=False), "i": p["url"], "th": p["thumb"],
                   "t": short(p["caption"], POPUP_CHARS), "g": picks[i], "pl": [pidx[k] for k in hub.named(p)],
                   "q": " ".join([p["user"], p["name"], p["caption"]] + [hub.places[k]["name"] for k in hub.named(p)]),
                   **({"sp": {str(pidx[x["key"]]): x["still"] for x in p["shots"] if x["still"]}}
                      if any(x["still"] for x in p["shots"]) else {})}
                   for i, p in enumerate(posts)],
        "facets": facets,
        "pins": [[lat, lon, i, pidx[k], style, 1 if hub.within(k, set(home)) else 0]
                 for i, p in enumerate(posts) for k, lat, lon, style in p["pins"]],
    }
    pinned = sum(1 for p in posts if p["pins"])
    n_places = len({k for p in posts for k, *_ in p["pins"]})
    links = "".join(f'<a href="{esc(h)}">{esc(t)}</a>' for h, t in extra_links)
    content = (f'<header class="bar"><div><h1>{esc(title)}</h1>'
               f'<p class="sub">{pinned} of {len(posts)} saved posts on the map, at {n_places} places</p></div>'
               f'<nav class="links">{links}</nav>'
               '<nav class="facets" aria-label="Narrow the map">'
               + "".join(f'<label><span>{esc(name)}</span><select id="f-{key}"></select></label>' for key, name, _ in MENUS)
               + '<button id="clear" type="button" hidden>Clear</button></nav></header>'
               '<div class="panes"><aside><form role="search"><input id="q" type="search" autocomplete="off" '
               'placeholder="Search captions, creators and places" aria-label="Search captions, creators and places">'
               '</form><div class="legend"><span><i class="pin pin-spot"></i>a spot the post names</span>'
               '<span><i class="pin pin-placed"></i>a spot not on OpenStreetMap, at its town</span>'
               '<span><i class="pin pin-area"></i>a town, park or region</span>'
               '<span><i class="pin pin-wide"></i>only the state or country</span></div>'
               '<div id="out" aria-live="polite"></div></aside><div id="map"></div></div>')
    js = MAP_JS.replace("__DATA__", data_json(data)).replace("__TILES__", TILES).replace("__CREDIT__", CREDIT)
    return shell(title, content, LEAFLET + CLUSTER, f"<script>{js}</script>", body="hub")


CSS = """
:root{
  --bg:#f3f5f4; --card:#ffffff; --fg:#1d2421; --muted:#5d6a64; --line:#d9e0dc;
  --accent:#0f6b5c; --accent-soft:#dcf1ea; --spot:#c2410c; --wide:#8a948f; --mark:#fde9a8; --ring:#ffffff;
  --display:"Bricolage Grotesque","Avenir Next",system-ui,sans-serif;
  --body:"Atkinson Hyperlegible",system-ui,-apple-system,sans-serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#141917; --card:#1c2320; --fg:#e4ebe7; --muted:#9aa8a1; --line:#2e3833;
  --accent:#5fc9b3; --accent-soft:#173a31; --spot:#fb923c; --wide:#7b8681; --mark:#5a4a12; --ring:#141917;
  color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#141917; --card:#1c2320; --fg:#e4ebe7; --muted:#9aa8a1; --line:#2e3833;
  --accent:#5fc9b3; --accent-soft:#173a31; --spot:#fb923c; --wide:#7b8681; --mark:#5a4a12; --ring:#141917;
  color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 var(--body)}
a{color:var(--accent)}
a:focus-visible,input:focus-visible,select:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
h1{font:600 clamp(1.5rem,4vw,2.3rem)/1.1 var(--display);margin:0;text-wrap:balance}
h2{font:600 1.15rem/1.2 var(--display);margin:0 0 .6rem}
.sub{margin:.3rem 0 0;color:var(--muted)}
.muted{color:var(--muted)}
mark{background:var(--mark);color:inherit;padding:0 .15em;border-radius:3px}
.pin{display:inline-block;width:18px;height:18px;border-radius:50%;background:var(--accent);
  border:3px solid var(--ring);box-shadow:0 1px 4px rgba(0,0,0,.4)}
.pin-spot{background:var(--spot)}
.pin-wide{background:var(--wide)}
.pin-placed{background:var(--card);border-color:var(--spot);border-style:dashed}
.pin-here{background:var(--spot);width:20px;height:20px}
.pin-inside{width:14px;height:14px;border-width:2px}
.bubble{width:100%;height:100%;border-radius:50%;background:var(--accent);color:#fff;display:grid;place-items:center;
  font:700 .85rem var(--body);border:3px solid var(--ring);box-shadow:0 1px 5px rgba(0,0,0,.35)}
@media (prefers-color-scheme:dark){.bubble{color:#0b1512}}
.leaflet-container{font:14px/1.4 var(--body)}
.leaflet-popup-content{margin:12px 14px}
.leaflet-popup-content-wrapper,.leaflet-popup-tip{background:var(--card);color:var(--fg)}
.leaflet-container a{color:var(--accent)}
.leaflet-container a.leaflet-popup-close-button{color:var(--muted)}
.pop img{width:100%;max-height:150px;object-fit:cover;border-radius:6px;display:block;margin-bottom:6px}
.pop p{margin:0 0 4px}
.pwho{font-weight:700}
.pwhere a{color:var(--muted);font-size:.85rem}
.ptext{font-size:.9rem;overflow-wrap:anywhere}
.pnote{font-size:.8rem;color:var(--muted);margin:.2rem 0}
.plinks{display:flex;gap:12px;flex-wrap:wrap;font-weight:700;margin-top:6px!important}

/* The map page: a bar on top, the list beside the map; the map on top on a phone. */
body.hub{height:100dvh;display:grid;grid-template-rows:auto 1fr}
.bar{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:end;gap:8px 16px;padding:14px 16px;
  background:var(--card);border-bottom:1px solid var(--line)}
.bar .links{display:flex;gap:16px;font-weight:700;font-size:.95rem}
.facets{flex-basis:100%;display:flex;flex-wrap:wrap;align-items:end;gap:8px 12px}
.facets label{flex:0 1 13rem;min-width:0;display:grid;grid-template-columns:minmax(0,1fr);gap:2px;font-size:.72rem;letter-spacing:.08em;
  text-transform:uppercase;color:var(--muted)}
.facets select{width:100%;min-width:0;font:inherit;font-size:.92rem;letter-spacing:normal;text-transform:none;color:var(--fg);
  padding:7px 12px;border:1px solid var(--line);border-radius:10px;background:var(--bg)}
.facets select.on{border-color:var(--accent);background:var(--accent-soft);color:var(--accent);font-weight:700}
#clear{font:700 .92rem var(--body);padding:7px 14px;border-radius:10px;border:1px solid var(--line);
  background:transparent;color:var(--accent);cursor:pointer}
.panes{display:grid;grid-template-columns:minmax(17rem,24rem) 1fr;min-height:0}
aside{overflow:auto;padding:14px 16px;border-right:1px solid var(--line);display:grid;gap:12px;align-content:start;
  background:var(--bg)}
#map{min-height:0}
form{display:flex}
input{flex:1;width:0;min-width:0;font:inherit;padding:9px 14px;border:1px solid var(--line);border-radius:999px;
  background:var(--card);color:var(--fg)}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:.82rem;color:var(--muted)}
.legend span{display:flex;align-items:center;gap:6px}
.legend .pin{width:12px;height:12px;border-width:2px;box-shadow:none}
.said{margin:0;color:var(--muted)}
#out h2{margin-top:6px}
ol{list-style:none;margin:0;padding:0}
.plist a{display:grid;grid-template-columns:1fr auto;gap:0 10px;padding:7px 10px;border-radius:8px;
  text-decoration:none;color:var(--fg)}
.plist a:hover,.rlist a:hover{background:var(--accent-soft)}
.pname{font-weight:700}
.pkind{grid-column:1;color:var(--muted);font-size:.82rem}
.pcount{grid-row:1/3;grid-column:2;align-self:center;font-variant-numeric:tabular-nums;color:var(--muted);font-weight:700}
.rlist a{display:grid;padding:7px 10px;border-radius:8px;text-decoration:none;color:var(--fg)}
.rwho{font-weight:700}
.rtext{color:var(--muted);font-size:.88rem;overflow-wrap:anywhere}

/* Place and post pages: one column. */
.page{max-width:56rem;margin:0 auto;padding-inline:16px;padding-block:18px 56px;display:grid;gap:22px}
.top{font-weight:700}
.notes{margin:.6rem 0 0;max-width:65ch}
.facts{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:16px;align-items:start}
.facts.solo{grid-template-columns:1fr}
#mini{height:280px;border-radius:12px;border:1px solid var(--line)}
dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:8px 16px;background:var(--card);
  border:1px solid var(--line);border-radius:12px;padding:14px 16px}
dt{color:var(--muted);font-size:.9rem}
dd{margin:0;min-width:0;overflow-wrap:anywhere}
ul.inline{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:4px 14px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:0;padding:0;list-style:none}
.chips li{font-size:.82rem;padding:1px 10px;border-radius:999px;background:var(--accent-soft);color:var(--accent)}
.cards{display:grid;gap:12px}
.card{display:grid;grid-template-columns:96px minmax(0,1fr);gap:14px;background:var(--card);
  border:1px solid var(--line);border-radius:12px;padding:12px}
.thumb{width:96px;height:120px;border-radius:8px;object-fit:cover;display:block}
.ph{display:grid;place-items:center;background:var(--bg);border:1px dashed var(--line);color:var(--muted);
  font-size:.75rem;text-transform:uppercase;letter-spacing:.08em}
.cbody{display:grid;gap:6px;align-content:start;min-width:0}
.cbody p{margin:0}
.who{font-weight:700}
.who .muted{font-weight:400}
.tlink{text-decoration:none}
.said .label{display:block;font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);
  font-weight:400}
.said{overflow-wrap:anywhere;max-width:70ch}
.links{display:flex;flex-wrap:wrap;gap:4px 16px;font-weight:700;font-size:.92rem}
.post{display:grid;grid-template-columns:minmax(0,16rem) minmax(0,1fr);gap:18px;align-items:start}
.post.solo{grid-template-columns:minmax(0,1fr)}
.big{width:100%;aspect-ratio:4/5;border-radius:12px;object-fit:cover;display:block}
.pbody{display:grid;gap:12px;min-width:0}
.cta{margin:0;display:flex;flex-wrap:wrap;gap:8px}
.button.alt{background:transparent;color:var(--accent);border:1px solid var(--accent)}
.gmap{font-size:.82rem;font-weight:400;color:var(--muted)}
.button{display:inline-block;padding:9px 18px;border-radius:999px;background:var(--accent);color:var(--card);
  font-weight:700;text-decoration:none}
.hint{margin:-.3rem 0 .7rem;font-size:.9rem}
.shots{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,10.5rem),1fr));gap:12px}
.shotc{margin:0;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px;display:grid;gap:6px;
  align-content:start;min-width:0}
.shot{width:100%;aspect-ratio:9/16;object-fit:cover;border-radius:8px;display:block;background:var(--bg)}
.shotc figcaption{display:grid;gap:2px;font-size:.9rem;min-width:0;overflow-wrap:anywhere}
.shotc figcaption a{font-weight:700}
.shotc figcaption .muted{font-size:.8rem}
.shotc figcaption .muted a{font-weight:400}
.play{justify-self:start;margin-top:2px;font:700 .8rem var(--body);padding:4px 12px;border-radius:999px;cursor:pointer;
  border:1px solid var(--accent);background:transparent;color:var(--accent)}
.play[aria-pressed="true"]{background:var(--accent);color:var(--card)}
.caption{white-space:pre-wrap;overflow-wrap:anywhere;margin:0;max-width:70ch;background:var(--card);
  border:1px solid var(--line);border-radius:12px;padding:14px 16px}
@media (prefers-color-scheme:dark){.leaflet-tile-pane{filter:brightness(.82) contrast(1.05)}}
@media (max-width:760px){
  body.hub{height:auto;display:block}
  .panes{display:flex;flex-direction:column}
  #map{height:58vh;order:-1}
  aside{border-right:0;overflow:visible}
  .facts,.post{grid-template-columns:minmax(0,1fr)}
  .post .big{max-width:16rem}
  .card{grid-template-columns:72px minmax(0,1fr);gap:12px}
  .facets label{flex:1 1 9rem}
  .thumb{width:72px;height:90px}
  dl{grid-template-columns:1fr;gap:2px}
  dd{margin-bottom:8px}
}
"""


def copy_file(src, dest):
    """Copy src to dest unless dest is already the same file. True when dest is there after."""
    if os.path.isfile(src):
        st = os.stat(src)
        if not os.path.isfile(dest) or os.path.getsize(dest) != st.st_size or os.path.getmtime(dest) < st.st_mtime:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
    return os.path.isfile(dest)


def copy_stills(hub, out):
    """Copy each spot's still and clip into OUT/stills/<post file>/, when the files are there.
    Returns how many spots have a still."""
    have = 0
    for post in hub.posts:
        for x in post["shots"]:
            base = "stills/" + post["file"] + "/"
            if copy_file(x["still_src"], os.path.join(out, base + os.path.basename(x["still_src"]))):
                x["still"] = base + os.path.basename(x["still_src"])
                have += 1
                if x["clip_src"] and copy_file(x["clip_src"], os.path.join(out, base + os.path.basename(x["clip_src"]))):
                    x["clip"] = base + os.path.basename(x["clip_src"])
    return have


def copy_thumbs(hub, out):
    """Copy each post's thumbnail into OUT/thumbs, when the file is there. Returns how many posts
    have one."""
    folder = os.path.join(out, "thumbs")
    have = 0
    for post in hub.posts:
        src = post["thumb_src"]
        if not src:
            continue
        dest = os.path.join(folder, post["file"] + (os.path.splitext(src)[1].lower() or ".jpg"))
        if copy_file(src, dest):
            post["thumb"] = "thumbs/" + os.path.basename(dest)
            have += 1
    return have


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def build(hub, out, title, home=()):
    os.makedirs(out, exist_ok=True)
    thumbs = copy_thumbs(hub, out)
    hub.stills = copy_stills(hub, out)
    for sub in ("places", "posts"):   # only our own folders: other pages live in OUT too
        shutil.rmtree(os.path.join(out, sub), ignore_errors=True)
    for place in hub.places.values():
        write(os.path.join(out, "places", place["slug"] + ".html"), place_page(hub, place))
    for post in hub.posts:
        write(os.path.join(out, "posts", post["file"] + ".html"), post_page(hub, post))
    extra = [(f, t) for f, t in (("moves.html", "Saves to move"), ("pins.html", "Pins to check"))
             if os.path.exists(os.path.join(out, f))]
    write(os.path.join(out, "index.html"), index_page(hub, title, extra, home))
    return thumbs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument("--pilot", help="a pilot name from config/collections.yaml")
    scope.add_argument("--all", action="store_true", help="every save")
    ap.add_argument("--out", default=None, help="where to write the site (default .cache/hub)")
    ap.add_argument("--saved", default=None, help="saves.json (default: the data repo's .cache)")
    args = ap.parse_args(argv)

    pilots = load_yaml(os.path.join("config", "collections.yaml")).get("pilots") or {}
    pilot = None
    if args.pilot:
        if args.pilot not in pilots:
            sys.exit(f"no pilot {args.pilot!r} in config/collections.yaml (have: {', '.join(pilots) or 'none'})")
        pilot = pilots[args.pilot] or {}
    saved = args.saved or cache("saves.json")
    if not os.path.exists(saved):
        sys.exit(f"no saves at {saved}: run the import first (make import)")
    saves = load_saves(saved)
    tags = load_yaml(os.path.join("data", "tags.yaml"))
    if not tags:
        print("note: data/tags.yaml is empty or missing, so no save has a place yet (run the tagger)",
              file=sys.stderr)
    pins = load_yaml(os.path.join("data", "pins.yaml"))
    placed = placed_spots(load_yaml(os.path.join("data", "pins-review.yaml")))
    pins = {c: (pins.get(c) if isinstance(pins.get(c), list) else []) + placed.get(c, [])
            for c in set(pins) | set(placed)}
    google_places.apply(pins, load_yaml(os.path.join("data", "google.yaml")))   # exact Google links
    media = load_yaml(os.path.join("data", "media.yaml"))
    stills = load_yaml(os.path.join("data", "stills.yaml"))
    topics = load_yaml(os.path.join("config", "topics.yaml")).get("topics") or {}
    purposes = load_purposes()
    media_dir = os.path.expanduser(os.environ.get("INSTAGRAM_MEDIA_DIR") or MEDIA_DEFAULT)
    scoped = [s for s in saves if in_pilot(s, tags.get(s["code"]), pilot)]

    hub = Hub(scoped, tags, Places.load(), pins, media, topics, media_dir, purposes, stills)
    out = os.path.abspath(args.out or cache("hub"))
    title = f"Saved places: {args.pilot.replace('-', ' ').title()}" if args.pilot else "Saved places"
    thumbs = build(hub, out, title, (pilot or {}).get("cities") or ())

    pinned = sum(1 for p in hub.posts if p["pins"])
    exact = sum(1 for p in hub.posts if any(style != "wide" for *_, style in p["pins"]))
    spots = sum(1 for p in hub.places.values() if p["spot"])
    n_pins = sum(len(p["pins"]) for p in hub.posts)   # a post that names 5 places has 5 pins
    multi = sum(1 for p in hub.posts if len(p["pins"]) > 1)
    if hub.no_pin:
        log("hub_no_pin", places=len(hub.no_pin), names=",".join(sorted(hub.no_pin))[:300])
    log("hub", scope=args.pilot or "all", saves=len(hub.posts), pinned=pinned, pins=n_pins,
        posts_with_2plus_pins=multi, more_exact_than_state=exact, place_pages=len(hub.places), spots=spots, thumbs=thumbs, stills=hub.stills, pins_file=bool(pins), media_file=bool(media),
        out=out)
    print(f"{len(hub.posts)} saves: {pinned} on the map ({exact} at a town, park or spot) "
          f"with {n_pins} pins, one per place a post names ({multi} posts have 2 or more); "
          f"{len(hub.places)} place pages ({spots} spots); {thumbs} thumbnails; {hub.stills} spot stills")
    venues = venue_check(hub)
    log("hub_venues", **{k: len(v) for k, v in venues.items()}, town_only_codes=",".join(venues["town"]))
    print(f"eat or stay posts: {len(venues['spot'])} open a spot OpenStreetMap placed, {len(venues['placed'])} "
          f"one it doesn't list (pinned at its town), {len(venues['town'])} only a town")
    print(os.path.join(out, "index.html"))
    return 0


def venue_check(hub, purposes=("eat", "stay")):
    """The posts for eating or staying, by what their Google Maps links open: a spot OpenStreetMap
    placed, a spot it does not list (searched by name in its town), or only a town. A "town" post
    either names no venue in its caption or lost it before the lookup: those are the ones to read."""
    out = {"spot": [], "placed": [], "town": []}
    for p in hub.posts:
        if not set(p["tagged_purposes"]) & set(purposes):
            continue
        styles = {style for *_, style in p["pins"]}
        out["spot" if "spot" in styles else "placed" if "placed" in styles else "town"].append(p["code"])
    return out


if __name__ == "__main__":
    sys.exit(main())
