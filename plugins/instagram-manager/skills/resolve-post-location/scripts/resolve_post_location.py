#!/usr/bin/env python3
"""resolve_post_location.py — turn each saved post into pins for the spots it names (a beach, a café,
a trailhead), each one found on OpenStreetMap near the town or park the save is tagged with. The
reading is done by the post-locator agent in batches; this script never calls a model.

    resolve_post_location.py --prepare --pilot NAME   batch files for the saves the agent must read
    resolve_post_location.py --prepare --all          the same for every save
    resolve_post_location.py --merge                  check the agents' answers, look the spots up,
                                                      write the pins
    resolve_post_location.py --merge --frames         the same for the frame-reader's answers (spots
                                                      read off a reel's video, from read_frames.py)
    options: --redo (read saves that already have an answer), --limit N, --batch-saves N, --batch-chars N

Reads   $INSTAGRAM_HOME/.cache/saves.json            captions and creators (from import-saves)
        $INSTAGRAM_HOME/data/tags.yaml               each save's places (from tag-saves)
        $INSTAGRAM_HOME/data/places.yaml             each place's kind and lat/lon (from add_places.py)
        $INSTAGRAM_HOME/config/collections.yaml      the pilots
Writes  $INSTAGRAM_HOME/data/pins.yaml               code → [{name, said, near, kind, lat, lon, km, osm?,
                                                     wikidata?, found, map, address?}]: the spots that checked out
        $INSTAGRAM_HOME/data/pins-review.yaml        code → [{said, near, why, ...}]: spots for a person
        $INSTAGRAM_HOME/data/no-spot.yaml            code → {areas}: saves whose caption names no spot;
                                                     the "look at the video" list, for when frames are read
        $INSTAGRAM_HOME/.cache/batches/locate/       batch-NNN.json (in), batch-NNN.answers.json (out),
                                                     renamed .answers.merged.json once merged, and
                                                     merged.jsonl (one line per merged batch)
        $INSTAGRAM_HOME/.cache/batches/frames/       the same, for --merge --frames

Spots read off the video (--merge --frames)
  The frame-reader looks at a reel's frames (read_frames.py) and names the spots on screen. Each one
  goes through the same checks, with two changes:
  - The quote check also accepts words either text reader (tesseract or Apple Vision) read on the
    reel's frames ($INSTAGRAM_MEDIA_DIR/<code>/frames/text.json, never the batch), letters and digits
    in order, so OCR's odd spacing still matches. A name both readers missed (a fancy font) goes to
    review, "not in the caption or the video's text", for a person to look at the frame and add a
    `lookup:`.
  - The spots are added to the save's pins and review entries, marked `from: video`, instead of
    replacing them; a spot the save already has is left as it is. A save read from its video leaves
    no-spot.yaml once a spot is found.

Which saves go in
  A save goes in when it is tagged with at least one area more exact than a state or country: a
  town (kind city, or a part of a city), a park, or a region (a valley, a coast, a lake) that has a
  pin in data/places.yaml. The batch gives those areas, each with its kind and lat/lon. A save that
  has an answer already (it is in pins, review or no-spot) is skipped unless --redo.

What the merge checks, per spot
  1. `said` is in the caption word for word (shared/scripts/quote.py), or is the creator's own
     handle (a venue's own post). If not: review. An `address` not in the caption is dropped.
  2. `near` is one of the save's areas. If not: review.
  3. The spot is looked up on OpenStreetMap inside a box around its area (geocode.lookup_near:
     Nominatim's viewbox with bounded=1; cached, one request a second). The box is the area's
     reach plus 25 km, so a place of the same name far away never comes back, while a near miss
     does, with its distance, for a person to judge.
  4. A road for cars is never the answer unless the name asked says it is one ("Example Street",
     "Example Blvd", "Example Bridge", since OpenStreetMap stores a bridge as the road over it) or a
     person wrote the lookup; trails and walkways stay: a venue's name often matches a street nearby (a taco
     stand called Example Moro and a road of that name). The first answer within the area's reach
     is kept: 25 km of the area's pin, or, for a park
     or region, inside its own OpenStreetMap box grown by 10 km. (A park's or region's box is looked
     up once, inside 60 km of its pin, and only an outline counts: a way or relation. OpenStreetMap
     gives a place it stores as a single point a made-up box, a whole degree either side for a
     region, so a point's box is ignored. With no outline the reach is 50 km of its pin for a park
     or region, which a stretch of coast like Example Coast needs.) A spot found out of reach, or
     under a different name (step 5), is tried again for each other area of the save within 60 km
     of what was found, and pinned for the first area where it passes every check, named for it.
     Nothing found, or found only out of reach: review, with why ("not found near Example Town",
     "38 km from Example Town").
  5. The name found matches the name asked: they share a word of their own and differ only by
     place words ("state", "park"), one business kind ("coffee") or the area's name. If not: review
     ("found Example Baguette, a different name"). A person's `lookup:` skips this check.
  Two ways round a name OpenStreetMap does not list (most small restaurants):
  - `lat`/`lon` that appear in the caption are the pin, with no lookup, if within reach.
  - When the name is not found and the caption gives the spot's `address`, the address is looked
    up in the same box. Found within reach: a pin at the address, named for the venue (kind
    "address", no osm id, since the building's id is not the venue's).

Fixing by hand
  - A review entry: add `lookup: "Other Name"`, and the next --merge searches that instead of what
    the caption said (the quote check is skipped, since a person wrote it). `near:` may be changed
    to another area in data/places.yaml. A found spot moves to pins.yaml and keeps its `lookup:`.
  - A spot in the wrong area (a road trip's stop filed under a park in another state; the merge
    lists them, from the agent's `really_in` or a find far away): add the right area to
    config/places.yaml and run add_places.py, then give the entry the new `near:` and a `lookup:`.
    A changed `near:` alone is not searched again, and a re-read puts the agent's area back.
  - A wrong spot: add `drop: true`, to a review entry or to a pin. The next --merge moves a dropped
    pin to review, and the hub leaves it out.
  - A review entry whose find is right ("found Example Mall, a different name", "31 km from
    Example Town" when the spot really is there): add `ok: true`, and the next --merge moves it to
    pins.yaml as found, marked `by: hand`.
  - A pin a person placed or okayed: write it in pins.yaml with `by: hand`.
  - Pins that truly share one place (food trucks on one lot, stalls in a food hall): give each the
    same `building:` text and `by: hand`, so check_data.py accepts the shared map point.
  Each of these survives a re-read (--redo, or the video's spots merged again): it is never
  replaced, and the agent's spots with the same `said` are left out for that save, whatever area
  they are filed under. Deleting a pin or entry is not a fix, since the next re-read brings it back.
  Deleting all of a save's entries sends the save back to the agent on the next round.

Rerunning is safe: a merged batch is never merged twice, a lookup is cached, and the files are
written in a fixed order, so a merge with nothing new changes nothing. A new --prepare refuses to
start while a batch has answers waiting to be merged.

Every pin is a guess until a person has looked at it: run pins_page.py and look.
"""

import argparse
import glob
import json
import math
import os
import re
import sys
import time
import unicodedata
from urllib.parse import quote_plus

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, os.pardir, "shared", "scripts"))
import yaml  # noqa: E402

import geocode  # noqa: E402
from home import cache, home, read_saves  # noqa: E402
from log import log  # noqa: E402
from pilot import in_pilot  # noqa: E402
from places import load_yaml  # noqa: E402
from quote import quote_ok  # noqa: E402

PINS = os.path.join("data", "pins.yaml")
REVIEW = os.path.join("data", "pins-review.yaml")
NO_SPOT = os.path.join("data", "no-spot.yaml")
TAGS = os.path.join("data", "tags.yaml")
PLACES = os.path.join("data", "places.yaml")
DEFAULT_MEDIA_DIR = os.path.join("~", "Library", "Mobile Documents", "com~apple~CloudDocs", "CloudDesktop",
                                 "data", "instagram")
EXACT = {"city", "area", "park", "region"}  # more exact than a state or country
BOXED = {"park", "region"}                   # reach is the area's own box, grown
TOWN_KM = 25.0
POINT_AREA_KM = 50.0                         # a park or region OpenStreetMap stores only as a point
BOX_KM = 10.0
AREA_SEARCH_KM = 60.0
MARGIN_KM = 25.0                             # searched past the reach, so a near miss shows its distance
FAR_KM = 60.0                                # a review spot found this far out is most likely in the wrong area
WRONG_SHOWN = 20                             # wrong-area spots printed after a merge; the rest are counted
CAPTION_CHARS = 2500                         # the batch limits are the tagger's
BATCH_SAVES = 40
BATCH_CHARS = 60000


def batch_dir(frames=False):
    return cache("batches", "frames" if frames else "locate")


def media_dir():
    return os.path.abspath(os.path.expanduser(os.environ.get("INSTAGRAM_MEDIA_DIR") or DEFAULT_MEDIA_DIR))


def frame_words(frame):
    """What both text readers read on one frame (read_frames.py): tesseract's lines, then Apple
    Vision's lines tesseract did not have."""
    lines = [ln for ln in (frame.get("text") or "").splitlines() if ln]
    lines += [ln for ln in (frame.get("vision") or "").splitlines() if ln and ln not in lines]
    return "\n".join(lines)


def video_text(code):
    """Everything the text readers read on a reel's frames (read_frames.py), or ""."""
    try:
        with open(os.path.join(media_dir(), code, "frames", "text.json"), encoding="utf-8") as fh:
            info = json.load(fh)
    except (OSError, ValueError):
        return ""
    return "\n".join(frame_words(f) for f in info.get("frames") or [] if isinstance(f, dict))


# --- files ---------------------------------------------------------------------------------------

def write_yaml(rel, data):
    """Codes in order, each entry's keys in the order they were built (said and why near the top),
    so a person can read and edit the file, and a rerun with nothing new leaves git clean."""
    path = os.path.join(home(), rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        yaml.safe_dump({k: data[k] for k in sorted(data)}, fh, sort_keys=False, allow_unicode=True,
                       default_flow_style=False, width=1000)
    os.replace(tmp, path)


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# --- distances and boxes -------------------------------------------------------------------------

def km_between(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(a)))


def degrees(lat, km):
    """km as (degrees of latitude, degrees of longitude) at this latitude."""
    return km / 111.0, km / (111.0 * max(0.05, math.cos(math.radians(lat))))


def box_around(lat, lon, km):
    """(south, west, north, east) of a square km either side of a point."""
    dlat, dlon = degrees(lat, km)
    return (lat - dlat, lon - dlon, lat + dlat, lon + dlon)


def grow(box, km):
    """The box with km added on every side."""
    s, w, n, e = box
    dlat, dlon = degrees((s + n) / 2, km)
    return (s - dlat, w - dlon, n + dlat, e + dlon)


def inside(box, lat, lon):
    s, w, n, e = box
    return s <= lat <= n and w <= lon <= e


def union(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


# --- areas ---------------------------------------------------------------------------------------

def exact_area(name, places):
    """{name, kind, lat, lon} for a place more exact than a state or country with a pin, else None.
    A sprawling city's own width (`box_km`) comes along as `reach_km`."""
    p = places.get(name)
    if not isinstance(p, dict) or p.get("kind") not in EXACT or p.get("lat") is None or p.get("lon") is None:
        return None
    out = {"name": name, "kind": p["kind"], "lat": p["lat"], "lon": p["lon"]}
    if isinstance(p.get("box_km"), (int, float)):
        out["reach_km"] = float(p["box_km"])
    return out


def with_widths(places, config):
    """data/places.yaml's places, each with the `box_km` its config/places.yaml entry sets: how far a
    sprawling city reaches from its middle ("Example City: 35 km out to its suburbs"). A hand-written
    `kind:` wins over the looked-up one: a capital OpenStreetMap files as its municipality ("state")
    or a town it files as its province ("other") is a city to search near."""
    out = dict(places)
    for name, c in (config or {}).items():
        if not isinstance(c, dict) or not isinstance(out.get(name), dict):
            continue
        if isinstance(c.get("box_km"), (int, float)):
            out[name] = {**out[name], "box_km": c["box_km"]}
        if isinstance(c.get("kind"), str) and c["kind"].strip():
            out[name] = {**out[name], "kind": c["kind"].strip()}
    return out


def load_places():
    """The looked-up places, with each sprawling city's own width."""
    return with_widths(load_yaml(PLACES).get("places") or {},
                       load_yaml(os.path.join("config", "places.yaml")).get("places"))


def areas_of(tag, places):
    return [a for a in (exact_area(c, places) for c in (tag or {}).get("cities") or []) if a]


class Reach:
    """Where a spot may be for its area: the box to search in, and the test an answer must pass."""

    def __init__(self, area, places, fetcher=None):
        self.area = area
        self.box = None
        self.radius = max(TOWN_KM, area.get("reach_km") or 0.0)   # a sprawling city sets its own
        if area["kind"] in BOXED:
            own = self.area_box(places.get(area["name"]) or {}, fetcher)
            if own:
                self.box = grow(own, BOX_KM)
            else:
                self.radius = POINT_AREA_KM
        self.town = box_around(area["lat"], area["lon"], self.radius)
        self.search = grow(union(self.town, self.box) if self.box else self.town, MARGIN_KM)

    def area_box(self, place, fetcher):
        """The park's or region's own outline on OpenStreetMap: its name searched near its pin. A
        point's box is made up by OpenStreetMap (a degree either side for a region), so only a way's
        or relation's box counts."""
        name = (place.get("found") or self.area["name"]).split(",")[0].strip()
        hits = geocode.lookup_near(name, box_around(self.area["lat"], self.area["lon"], AREA_SEARCH_KM), fetcher)
        outlines = [h for h in hits if h.get("box") and not str(h.get("osm") or "").startswith("node/")]
        same = [h for h in outlines if (h.get("name") or "").lower() == name.lower()]
        hit = (same or outlines or [None])[0]
        return tuple(hit["box"]) if hit else None

    def km(self, lat, lon):
        return km_between(self.area["lat"], self.area["lon"], lat, lon)

    def ok(self, lat, lon):
        return self.km(lat, lon) <= self.radius or bool(self.box and inside(self.box, lat, lon))


# --- one spot ------------------------------------------------------------------------------------

def search_text(spot):
    """What to ask OpenStreetMap: a person's `lookup:` first; the agent's plain `name` only when the
    caption said a handle or hashtag (`@examplecafe`); otherwise the caption's own words, with styled
    letters ("𝐁𝐞𝐚𝐜𝐡") made plain."""
    said = unicodedata.normalize("NFKC", spot["said"])
    if isinstance(spot.get("lookup"), str) and spot["lookup"].strip():
        return spot["lookup"].strip()
    if said[:1] in "@#" and isinstance(spot.get("name"), str) and spot["name"].strip():
        return spot["name"].strip()
    return said


FILLER = {"the", "a", "an", "and", "of", "at", "in", "on", "by"}


def stem(word):
    """"meadows" and "meadow" as one word; "pass" left alone."""
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def name_words(text):
    """A name's words: lower case, no accents, no punctuation, filler words or bracketed part, plurals
    as singular."""
    text = unicodedata.normalize("NFKD", str(text).lower().replace("’", "").replace("'", ""))
    text = re.sub(r"\(.*?\)", " ", "".join(c for c in text if not unicodedata.combining(c)))
    return {stem(w) for w in re.findall(r"[a-z0-9]+", text)} - FILLER


def area_words(area):
    """The area's words, and its initials when it has two or more: "la" for Los Angeles."""
    words = re.findall(r"[a-z0-9]+", str(area).lower())
    return name_words(area) | ({"".join(w[0] for w in words)} if len(words) > 1 else set())


# Words either name may have that the other lacks, and still be the same place.
PLACE_WORDS = {stem(w) for w in """state national regional county city park beach trail trailhead creek
falls lake river bay cove point island peak mount mt mountain canyon valley spring hot pier harbor harbour
bridge historic historical memorial monument reserve preserve forest wilderness recreation area garden
botanical vista viewpoint overlook lookout fire campground meadow dune sand flat lighthouse light station
steps street st avenue ave road parking north south east west upper lower old association""".split()}
# Kinds of business: one name may add one ("Example" and "Example Coffee"), but two names with different
# kinds ("Example Cafe" and "Example Bakery") are two places.
KIND_WORDS = {stem(w) for w in """coffee co company cafe restaurant bakery eatery kitchen bar ramen craft
hotel inn lodge store shop market creamery food hall sandwiches""".split()}


STREET_WORDS = {w for w in """street st avenue ave boulevard blvd road rd drive dr way lane ln highway hwy
parkway pkwy place pl court ct alley row promenade terrace bridge tunnel pass causeway overpass route
""".split()}   # a road's own words, and what a road carries: a bridge is often stored as the road over it


# OpenStreetMap's road types for cars. Trails and walkways (path, footway, track, steps) are spots.
ROADS = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "service",
         "living_street", "road", "pedestrian"}


def a_street(hit, asked):
    """True when the hit is a road and the name asked does not say it is one."""
    return (hit.get("category") == "highway" and hit.get("type") in ROADS
            and not STREET_WORDS & set(re.findall(r"[a-z]+", asked.lower())))


def same_name(asked, found, area=""):
    """True when the two names share a word of their own, and differ only by place words, business
    kinds or the area's name: "Example Point" and "Example Point State Park", "Example LA" and
    "Example" (near Los Angeles). "Example Bakery" and "Example Baguette" are not, nor are "Example
    Mission" and "Mission Ranch Example": OpenStreetMap's nearest answer to a name it does not know is
    often a different place."""
    a, f = name_words(asked), name_words(found)
    if a and a == f:
        return True
    if not (a & f) - PLACE_WORDS - KIND_WORDS:  # "Example Beach" near Example shares "example"
        return False
    free = PLACE_WORDS | area_words(area)
    if not all(w in free or w in KIND_WORDS or any(c.isdigit() for c in w) for w in a ^ f):
        return False
    return not ((a - f) & KIND_WORDS and (f - a) & KIND_WORDS)


def creator_of(save):
    owner = save.get("owner") if isinstance(save, dict) else None
    return owner.get("username") or "" if isinstance(owner, dict) else ""


def is_creator(said, creator):
    """A business's own post names itself only as its handle: "@examplebakery" when it is the creator."""
    return bool(creator) and said.startswith("@") and said[1:].strip().lower() == creator.strip().lower()


def squash(text):
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", str(text)).lower())


def address_in(address, caption):
    """True when the caption gives this address, letters and digits in order: an address over several
    lines ("1 Example Rd\nExample Town") matches its lines joined with commas."""
    a = squash(address)
    return len(a) >= 6 and a in squash(caption)


UNIT = re.compile(r",?\s+(?:suite|ste\.?|unit|apt\.?|#)\s*[\w-]+(?=\W|$)", re.I)
UNIT_LETTER = re.compile(r"\b(rd|dr|st|ave|blvd|ln|pkwy|hwy|cir|way|ct|pl)\.?\s+[a-z]\d?(?=,|$)", re.I)


def street_only(address):
    """The address without its suite or unit ("1 Example Rd Suite 5, Example Town" → "1 Example Rd,
    Example Town"; "1 Example Dr B" → "1 Example Dr"): OpenStreetMap knows the building, not the
    unit, and finds nothing with it."""
    return " ".join(UNIT_LETTER.sub(r"\1", UNIT.sub("", address)).split()).strip(", ")


def at_the_house(found, address):
    """True when what OpenStreetMap found carries the address's house number ("12, Example Road, …"
    for "12 Example Rd"). A hit without it is the whole street, and its point can be kilometres off.
    An address with no house number passes."""
    m = re.match(r"\s*(\d+)\b", address or "")
    if not m:
        return True
    return m.group(1) in [t.strip() for t in str(found or "").split(",")]


def on_screen(said, seen):
    """True when tesseract read these words on the video, letters and digits in order ("EXAMPLE
    CAFE" read as "EXAMPLECAFE" or "Example  Cafe")."""
    a = squash(said.lstrip("@#"))
    return bool(seen) and len(a) >= 4 and a in squash(seen)


def coords_in(caption, lat, lon):
    """True when the caption gives these coordinates ("36.55644, -121.91886"), to 5 decimals."""
    nums = [float(n) for n in re.findall(r"-?\d{1,3}\.\d{3,}", caption or "")]
    return any(abs(n - lat) < 1e-5 for n in nums) and any(abs(n - lon) < 1e-5 for n in nums)


def venue_name(spot):
    return spot.get("name") or spot["said"].lstrip("@#").strip()


RETRY = re.compile(r"\d+ km from |found .*, a different name$")   # found something, near another area
ANOTHER_BRANCH = re.compile(r"^found .* by name, but not at the caption's address$")
OTHER_AREA_KM = 60.0   # how far another of the save's areas may be from a spot to be tried for it


def resolve(spot, caption, areas, places, reaches, fetcher=None, creator="", seen=None):
    """("pin" or "review", entry) for one spot. areas: the names the spot's `near` may be. seen: the
    text read on the post's video (None for a caption answer), which the quote and address checks
    also accept.

    A spot found out of its `near`'s reach, or found under a different name, is tried again for
    each other area of the save close enough to what was found: the agent picks one area, and a
    trip tagged with a town and its stretch of coast, or a chain in two cities, may have it in the
    wrong one. The pin then names the area it is in."""
    where, entry = resolve_near(spot, caption, areas, places, reaches, fetcher, creator, seen)
    if where != "review" or not RETRY.match(entry.get("why", "")) or "lat" not in entry:
        return where, entry
    for other in areas:
        area = exact_area(other, places)
        if other == spot["near"] or area is None:
            continue
        if km_between(area["lat"], area["lon"], entry["lat"], entry["lon"]) > OTHER_AREA_KM:
            continue
        again = resolve_near({**spot, "near": other}, caption, areas, places, reaches, fetcher, creator, seen)
        if again[0] == "pin":
            return again
    return where, entry


def resolve_near(spot, caption, areas, places, reaches, fetcher=None, creator="", seen=None):
    """resolve() for the spot's own `near` only.

    The spot's name is looked up first. When the caption gives the spot's coordinates, they are the
    pin, if they fall within the area's reach. When the name is not found (most small restaurants
    are not on OpenStreetMap) and the caption gives the spot's street address, the address is looked
    up instead: the pin is at the address, named for the venue. So it is when the name is found but
    not at the caption's address (the house number is not in what was found): a name like a chain's
    finds another branch. If the address is not found either, the spot goes to review."""
    said, near = spot["said"], spot["near"]
    by_person = isinstance(spot.get("lookup"), str) and bool(spot["lookup"].strip())
    base = {"said": said, "near": near}
    keep = {k: spot[k] for k in ("lookup", "name", "address", "really_in") if spot.get(k)}
    if isinstance(keep.get("address"), str):
        keep["address"] = " ".join(keep["address"].split())   # one line, as copied across line breaks
    if "address" in keep and not (by_person or address_in(keep["address"], caption)
                                  or (seen and address_in(keep["address"], seen))):
        del keep["address"]   # an address the caption doesn't give is a guess
    if not by_person and not (quote_ok(said, caption) or is_creator(said, creator) or on_screen(said, seen)):
        why = "quote not in caption" if seen is None else "not in the caption or the video's text"
        return "review", {**base, "why": why, **keep}
    area = exact_area(near, places)
    if near not in areas or area is None:
        why = (f"near {near}, which is not one of the save's areas" if near not in areas
               else f"{near} has no pin, or is a state or country")
        return "review", {**base, "why": why, **keep}
    if near not in reaches:
        reaches[near] = Reach(area, places, fetcher)
    reach = reaches[near]
    lat, lon = spot.get("lat"), spot.get("lon")
    if isinstance(lat, float) and isinstance(lon, float) and coords_in(caption, lat, lon):
        km = round(reach.km(lat, lon), 1)
        if not reach.ok(lat, lon):
            return "review", {**base, "why": f"{km:.0f} km from {near}", "lat": lat, "lon": lon, **keep}
        return "pin", {"name": venue_name(spot), **base, "kind": "spot", "lat": lat, "lon": lon, "km": km,
                       "found": "the caption's coordinates",
                       "map": "https://www.google.com/maps/search/?api=1&query=" + quote_plus(f"{lat},{lon}")}
    where, entry = lookup_name(spot, reach, near, base, keep, by_person, fetcher)
    address = keep.get("address")
    if not address:
        return where, entry
    elsewhere = where == "pin" and not by_person and not at_the_house(entry.get("found"), address)
    if where == "pin" and not elsewhere:
        return where, entry
    hits = geocode.lookup_near(street_only(address), reach.search, fetcher)
    hit = next((h for h in hits if reach.ok(h["lat"], h["lon"]) and at_the_house(h.get("found"), address)), None)
    if hit is None and elsewhere:
        log("locate_other_branch", said=said, near=near)
        return "review", {**base, "why": f"found {entry['name']} by name, but not at the caption's address",
                          **({"asked": entry["asked"]} if entry.get("asked") else {}), **keep,
                          "address_tried": True}
    if hit is None:
        return where, entry
    name = venue_name(spot)
    return "pin", {"name": name, **base, "kind": "address", "lat": hit["lat"], "lon": hit["lon"],
                   "km": round(reach.km(hit["lat"], hit["lon"]), 1), "address": address,
                   "found": hit.get("found"), "map": geocode.maps_link(name, address)}


def lookup_name(spot, reach, near, base, keep, by_person, fetcher):
    """The spot's name looked up near its area: ("pin" or "review", entry)."""
    asked = search_text(spot)
    hits = geocode.lookup_near(asked, reach.search, fetcher)
    streets = [] if by_person else [h for h in hits if a_street(h, asked)]
    hits = [h for h in hits if h not in streets]
    good = [h for h in hits if reach.ok(h["lat"], h["lon"])]
    hit = (good or hits or [None])[0]
    if hit is None:
        why = f"not found near {near}" + (" (only a street of that name)" if streets else "")
        return "review", {**base, "why": why, "asked": asked, **keep}
    km = round(reach.km(hit["lat"], hit["lon"]), 1)
    found = {"name": hit["name"], "kind": hit.get("type") or hit.get("category") or "place",
             "lat": hit["lat"], "lon": hit["lon"], "km": km}
    for k in ("osm", "wikidata"):
        if hit.get(k):
            found[k] = hit[k]
    found["found"] = hit.get("found")
    found["map"] = geocode.maps_link(hit["name"], near)
    if not good:
        return "review", {**base, "why": f"{km:.0f} km from {near}", "asked": asked, **found, **keep}
    if not by_person and not same_name(asked, found["name"], near):
        return "review", {**base, "why": f"found {found['name']}, a different name", "asked": asked,
                          **found, **keep}
    pin = {"name": found.pop("name"), **base, **found}
    if asked != base["said"]:
        pin["asked"] = asked
    if keep.get("address"):
        pin["address"] = keep["address"]
    return "pin", pin


# --- prepare -------------------------------------------------------------------------------------


def record(save, areas):
    """One save as the agent sees it."""
    owner = save.get("owner") or {}
    return {"code": save["code"], "creator": f"@{owner.get('username', '')} ({owner.get('name', '')})",
            "areas": [{"name": a["name"], "kind": a["kind"], "lat": a["lat"], "lon": a["lon"]} for a in areas],
            "caption": (save.get("caption") or "")[:CAPTION_CHARS]}


def size(rec):
    return len(json.dumps(rec, ensure_ascii=False))


def chunk(records, max_saves=BATCH_SAVES, max_chars=BATCH_CHARS):
    """Batches of at most max_saves and about max_chars, in order; a record is never split."""
    batches, cur, chars = [], [], 0
    for r in records:
        n = size(r)
        if cur and (len(cur) >= max_saves or chars + n > max_chars):
            batches.append(cur)
            cur, chars = [], 0
        cur.append(r)
        chars += n
    if cur:
        batches.append(cur)
    return batches


NO_AREA_SHOWN = 10  # codes named when saves are skipped for having no town or park


def prepare(args, saves, tags, places, pilot, done):
    out = batch_dir()
    waiting = sorted(glob.glob(os.path.join(out, "batch-[0-9][0-9][0-9].answers.json")))
    if waiting:
        sys.exit(f"{len(waiting)} answers files are not merged yet ({os.path.basename(waiting[0])}...): "
                 "run --merge first, so a new round does not delete them")
    todo, skipped, no_area = [], 0, []
    for s in saves:
        tag = tags.get(s["code"])
        if pilot and not in_pilot(s, tag, pilot):
            continue
        areas = areas_of(tag, places)
        if not areas:
            if (tag or {}).get("cities"):  # a place, but only a state or country; untagged saves are not counted
                no_area.append(s["code"])
            continue
        if s["code"] in done and not args.redo:
            skipped += 1
            continue
        todo.append(record(s, areas))
    todo.sort(key=lambda r: (r["areas"][0]["name"], r["code"]))  # saves about one area sit together
    if args.limit:
        todo = todo[:args.limit]
    batches = chunk(todo, args.batch_saves, args.batch_chars)
    os.makedirs(out, exist_ok=True)
    for old in glob.glob(os.path.join(out, "batch-*.json")):  # a new round replaces the last one
        os.remove(old)
    for i, recs in enumerate(batches, 1):
        name = f"batch-{i:03d}"
        path = os.path.join(out, name + ".json")
        write_json(path, {"batch": name, "answers": os.path.join(out, name + ".answers.json"), "saves": recs})
        log("locate_batch", batch=name, saves=len(recs), chars=sum(size(r) for r in recs))
        print(path)
    log("locate_prepare", scope=args.pilot or "all", saves=len(todo), batches=len(batches),
        answered_before=skipped, no_exact_area=len(no_area), dir=out)
    if no_area:
        shown = ", ".join(no_area[:NO_AREA_SHOWN]) + (f" and {len(no_area) - NO_AREA_SHOWN} more" if len(no_area) > NO_AREA_SHOWN else "")
        print(f"Skipped {len(no_area)} saves tagged only with a state or country, so there is no town or park "
              f"to search near: {shown}.\nTo place one, give it a town in data/tags.yaml (tag-saves, "
              f"\"Fixing by hand\"); a reel whose place is only on screen can go to read-frames.", file=sys.stderr)
    return 0


# --- merge ---------------------------------------------------------------------------------------

PIN_KEYS = ("name", "said", "near", "kind", "lat", "lon", "km", "osm", "wikidata", "found", "map", "asked",
            "address", "from")


def okayed(e):
    """A review entry a person marked `ok: true` that holds a find to pin, else None."""
    if not (isinstance(e, dict) and e.get("ok") is True and not e.get("drop") and isinstance(e.get("said"), str)
            and isinstance(e.get("near"), str) and isinstance(e.get("name"), str)):
        return None
    try:
        float(e["lat"]), float(e["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    return {**{k: e[k] for k in PIN_KEYS if k in e}, "by": "hand"}


def by_hand(entry):
    """A pin or review entry a person made or fixed: `by: hand`, `ok: true`, a `lookup:` or `drop: true`.
    A re-read never replaces it, and the agent's spots of the same name are left out for that save."""
    return isinstance(entry, dict) and (entry.get("by") == "hand" or entry.get("drop") is True
                                        or entry.get("ok") is True
                                        or (isinstance(entry.get("lookup"), str) and bool(entry["lookup"].strip())))


def said_key(entry):
    return " ".join(str(entry.get("said") or "").lower().split())


def move_dropped(pins, review):
    """Pins a person marked `drop: true` move to review, where they stay dropped."""
    moved = 0
    for code, entries in list(pins.items()):
        if not isinstance(entries, list):
            continue
        gone = [e for e in entries if isinstance(e, dict) and e.get("drop") is True]
        if not gone:
            continue
        review[code] = (review.get(code) or []) + gone
        keep = [e for e in entries if e not in gone]
        if keep:
            pins[code] = keep
        else:
            del pins[code]
        moved += len(gone)
        for e in gone:
            log("locate_pin_dropped", code=code, said=e.get("said"))
    return moved


def move_street_pins(pins, review):
    """Address pins whose find is only the street, not the house (made before at_the_house()), move
    to review. A person's pin stays."""
    moved = 0
    for code, entries in list(pins.items()):
        if not isinstance(entries, list):
            continue
        gone = [e for e in entries if isinstance(e, dict) and e.get("kind") == "address" and not by_hand(e)
                and not at_the_house(e.get("found"), e.get("address"))]
        if not gone:
            continue
        review[code] = (review.get(code) or []) + [
            {**{k: e[k] for k in ("said", "near", "name", "address", "map", "from") if k in e},
             "why": f"only the street was found near {e.get('near')}, not the house", "street_tried": True}
            for e in gone]
        keep = [e for e in entries if e not in gone]
        if keep:
            pins[code] = keep
        else:
            del pins[code]
        moved += len(gone)
        for e in gone:
            log("locate_street_pin_moved", code=code, said=e.get("said"))
    return moved


def move_branch_pins(pins, review):
    """Pins found by name whose caption gives an address they are not at (made before the address
    check in resolve_near()) move to review; recheck_review() then looks the address up once. A
    person's pin stays."""
    moved = 0
    for code, entries in list(pins.items()):
        if not isinstance(entries, list):
            continue
        gone = [e for e in entries if isinstance(e, dict) and e.get("kind") != "address" and e.get("osm")
                and isinstance(e.get("address"), str) and not by_hand(e)
                and not at_the_house(e.get("found"), e["address"])]
        if not gone:
            continue
        review[code] = (review.get(code) or []) + [
            {**{k: e[k] for k in ("said", "near", "asked", "address", "from") if k in e},
             "name": e.get("name"), "why": f"found {e.get('name')} by name, but not at the caption's address"}
            for e in gone]
        keep = [e for e in entries if e not in gone]
        if keep:
            pins[code] = keep
        else:
            del pins[code]
        moved += len(gone)
        for e in gone:
            log("locate_branch_pin_moved", code=code, said=e.get("said"))
    return moved


FAR = re.compile(r"^\d+ km from ")
STREET_ONLY = re.compile(r"^only the street was found near ")


def box_key(box):
    """A search box as Nominatim's viewbox text, the way the lookup cache keys it."""
    return geocode.near_params(".", box)["viewbox"]


def street_box_changed(e, places, reaches, fetcher):
    """The search box for a review entry that found only the street, when it is not the box the
    address was last searched in (None otherwise): a city given its own width (`box_km`) since then
    may now find the house. An entry with no box noted was searched before boxes were noted."""
    if not (isinstance(e, dict) and STREET_ONLY.match(str(e.get("why") or ""))
            and isinstance(e.get("near"), str) and isinstance(e.get("address"), str)):
        return None
    area = exact_area(e["near"], places)
    if area is None:
        return None
    if e["near"] not in reaches:
        reaches[e["near"]] = Reach(area, places, fetcher)
    key = box_key(reaches[e["near"]].search)
    return key if e.get("searched_in") != key else None


def same_spot(a, b):
    """Two pins for one post at one place: the same words near the same area, or two address pins
    at the same point (a reel's sign and its caption's fuller name for one shop)."""
    if a.get("said") == b.get("said") and a.get("near") == b.get("near"):
        return True
    return (a.get("kind") == b.get("kind") == "address"
            and (a.get("lat"), a.get("lon")) == (b.get("lat"), b.get("lon")))


def now_in_reach(e, places):
    """A review entry held back only for its distance, which its area's own width (`box_km`, a
    sprawling city's) now covers: "31 km from Example City" when the city reaches 35 km."""
    if not (isinstance(e, dict) and FAR.match(str(e.get("why") or "")) and isinstance(e.get("near"), str)
            and isinstance(e.get("km"), (int, float))):
        return False
    area = exact_area(e["near"], places)
    return bool(area and area.get("reach_km") and e["km"] <= area["reach_km"])


def now_exact(e, places):
    """A review entry held back because its area had no pin or was a state, which now has one, or
    which config/places.yaml's `kind:` now calls a city."""
    return bool(isinstance(e, dict) and isinstance(e.get("near"), str)
                and str(e.get("why") or "") == f"{e['near']} has no pin, or is a state or country"
                and exact_area(e["near"], places))


def recheck_review(by_code, tags, places, pins, review, reaches, fetcher):
    """Review entries a person marked `ok: true` move to pins as found. Ones a person gave a `lookup:`
    are searched again; found ones move to pins. So is, once, one whose address has a suite or unit,
    looked up before street_only() dropped it, one found by name but not at its address, one
    held back for its distance that its city's own width now covers, and one whose area had no pin
    or was a state and now is a city (a `kind:` in config/places.yaml)."""
    moved = 0
    for code, entries in list(review.items()):
        if not isinstance(entries, list):
            continue
        keep = []
        for e in entries:
            pin = okayed(e)
            if pin:
                pins.setdefault(code, [])
                if not any(p["said"] == pin["said"] and p["near"] == pin["near"] for p in pins[code]):
                    pins[code].append(pin)
                moved += 1
                log("locate_review_ok", code=code, said=pin["said"])
                continue
            by_person = isinstance(e, dict) and isinstance(e.get("lookup"), str) and e["lookup"].strip()
            unit = (isinstance(e, dict) and isinstance(e.get("address"), str) and not e.get("street_tried")
                    and street_only(e["address"]) != " ".join(e["address"].split()))
            branch = (isinstance(e, dict) and ANOTHER_BRANCH.match(str(e.get("why") or ""))
                      and not e.get("address_tried"))
            street = street_box_changed(e, places, reaches, fetcher)
            if not ((by_person or unit or branch or street or now_in_reach(e, places) or now_exact(e, places))
                    and not e.get("drop")
                    and isinstance(e.get("said"), str) and isinstance(e.get("near"), str)):
                keep.append(e)
                continue
            caption = (by_code.get(code) or {}).get("caption") or ""
            areas = [a["name"] for a in areas_of(tags.get(code), places)] + [e["near"]]  # a person may move it
            where, new = resolve(e, caption, areas, places, reaches, fetcher, creator_of(by_code.get(code)))
            if e.get("from"):
                new["from"] = e["from"]
            if where == "pin":
                if by_person:
                    new["lookup"] = e["lookup"]  # still a person's fix once pinned, so a re-read keeps it
                pins.setdefault(code, [])
                if not any(same_spot(p, new) for p in pins[code]):
                    pins[code].append(new)
                moved += 1
                log("locate_review_fixed", code=code, said=new["said"])
            elif street and not (by_person or unit or branch):
                keep.append({**e, "searched_in": street})   # still only the street; not again in this box
            else:
                if unit and not by_person:
                    new["street_tried"] = True   # tried without the unit; not again each merge
                if branch and not by_person:
                    new["address_tried"] = True   # its address looked up once; not again each merge
                keep.append(new)
        if keep:
            review[code] = keep
        else:
            del review[code]
    return moved


def read_answers(path):
    """code → list of spots, and why the file could not be used (or None)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except ValueError as e:
        return {}, f"the answers file is not JSON: {e}"[:200]
    data = data.get("answers", data) if isinstance(data, dict) else {}
    return (data if isinstance(data, dict) else {}), None


def clean_spots(answer):
    """The usable spots of one answer, each once, or None when the answer is not a list."""
    if isinstance(answer, dict) and isinstance(answer.get("spots"), list):
        answer = answer["spots"]
    if not isinstance(answer, list):
        return None
    out, seen = [], set()
    for s in answer:
        if not (isinstance(s, dict) and isinstance(s.get("said"), str) and s["said"].strip()
                and isinstance(s.get("near"), str) and s["near"].strip()):
            continue
        spot = {"said": s["said"].strip(), "near": s["near"].strip()}
        for k in ("name", "address", "really_in"):
            if isinstance(s.get(k), str) and s[k].strip():
                spot[k] = s[k].strip()
        try:
            spot["lat"], spot["lon"] = float(s["lat"]), float(s["lon"])
        except (KeyError, TypeError, ValueError):
            spot.pop("lat", None)
        if (spot["said"].lower(), spot["near"]) not in seen:
            seen.add((spot["said"].lower(), spot["near"]))
            out.append(spot)
    return out


def merge(saves, tags, places, fetcher=None, frames=False):
    by_code = {s["code"]: s for s in saves}
    pins, review, no_spot = load_yaml(PINS), load_yaml(REVIEW), load_yaml(NO_SPOT)
    reaches = {}
    dropped = move_dropped(pins, review)
    streets = move_street_pins(pins, review)
    branches = move_branch_pins(pins, review)
    # OpenStreetMap refusing (geocode.Refused) stops the run: the batches already done are kept and
    # written, the one under way stays unmerged (its answers file is not renamed), and the next run
    # takes it again. Its saves already redone keep their new answers; the rerun replaces them.
    stopped = None
    try:
        fixed = recheck_review(by_code, tags, places, pins, review, reaches, fetcher)
    except geocode.Refused as e:
        fixed, stopped = 0, e
    out = batch_dir(frames)
    counts = {"pins": 0, "review": 0, "no_spot": 0, "unanswered": 0}
    pending = before = 0
    for path in sorted(glob.glob(os.path.join(out, "batch-[0-9][0-9][0-9].json"))):
        with open(path, encoding="utf-8") as fh:
            batch = json.load(fh)
        ans_path = batch["answers"]
        merged_path = ans_path.replace(".answers.json", ".answers.merged.json")
        if os.path.exists(merged_path):
            if not os.path.exists(ans_path):  # merged after an earlier wave
                before += 1
                continue
            # its agent wrote the answers again after they were merged: the new file wins
            log("locate_merge_rewritten", batch=batch["batch"])
        if not os.path.exists(ans_path) or stopped:  # its agent has not run yet, or the run stopped
            pending += 1
            continue
        answers, bad = read_answers(ans_path)
        got = {"pins": 0, "review": 0, "no_spot": 0, "unanswered": 0}
        for rec in batch["saves"]:
            code = rec["code"]
            spots = clean_spots(answers.get(code))
            if spots is None or code not in by_code:
                got["unanswered"] += 1
                log("locate_unanswered", code=code, reason="bad_file" if bad else "no_answer")
                continue
            caption = by_code[code].get("caption") or ""
            seen = video_text(code) if frames else None
            areas = [a["name"] for a in rec["areas"]]
            key = lambda e: (e.get("said"), e.get("near"))  # noqa: E731
            pinned = {key(e) for e in pins.get(code) or [] if isinstance(e, dict)}
            # A name a person settled (pinned by hand, given a lookup, or dropped) stays as they left
            # it, whichever area the agent files it under this time.
            settled = {said_key(e) for e in (pins.get(code) or []) + (review.get(code) or []) if by_hand(e)}
            new_pins, new_review, redone = [], [], set()
            for spot in spots:
                if frames and key(spot) in pinned:  # the caption already gave it
                    continue
                if said_key(spot) in settled:
                    continue
                redone.add(key(spot))
                try:
                    where, entry = resolve(spot, caption, areas, places, reaches, fetcher, creator_of(by_code[code]),
                                           seen)
                except geocode.Refused as e:
                    stopped = e
                    break
                if frames:
                    entry["from"] = "video"
                (new_pins if where == "pin" else new_review).append(entry)
            if stopped:  # this save keeps what it had; the batch is merged again next run
                break
            got["pins"] += len(new_pins)
            got["review"] += len(new_review)
            if frames:  # spots read off the video add to what the caption gave
                new_pins = (pins.get(code) or []) + new_pins
                new_review = [e for e in review.get(code) or [] if key(e) not in redone] + new_review
            else:  # a caption answer replaces the caption's last one; the video's spots and a person's stay
                given = {key(e) for e in new_pins + new_review}
                stays = lambda e: (isinstance(e, dict) and (e.get("from") == "video" or by_hand(e))  # noqa: E731
                                   and key(e) not in given)
                new_pins += [e for e in pins.get(code) or [] if stays(e)]
                new_review += [e for e in review.get(code) or [] if stays(e)]
            for d, v in ((pins, new_pins), (review, new_review)):
                if v:
                    d[code] = v
                else:
                    d.pop(code, None)
            if spots or new_pins or new_review:
                no_spot.pop(code, None)
            elif not frames:
                no_spot[code] = {"areas": areas}
            got["no_spot"] += not spots
        if stopped:  # not renamed, not counted: the next run merges this batch again
            log("locate_merge_stopped", batch=batch["batch"], msg=str(stopped))
            pending += 1
            continue
        for k in counts:
            counts[k] += got[k]
        log("locate_merge_batch", batch=batch["batch"], saves=len(batch["saves"]), source="video" if frames else "caption",
            **got)
        with open(os.path.join(out, "merged.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "batch": batch["batch"],
                                 "saves": len(batch["saves"]), "chars": sum(size(r) for r in batch["saves"]),
                                 **got, **({"error": bad} if bad else {})}) + "\n")
        os.replace(ans_path, merged_path)
    write_yaml(PINS, pins)
    write_yaml(REVIEW, review)
    write_yaml(NO_SPOT, no_spot)
    log("locate_merge", **counts, review_fixed=fixed, pins_dropped=dropped, street_pins_moved=streets,
        branch_pins_moved=branches, batches_waiting=pending,
        batches_merged_before=before,
        saves_with_pins=len(pins), saves_in_review=len(review), saves_no_spot=len(no_spot))
    print(f"{counts['pins']} spots pinned, {counts['review']} for review, {counts['no_spot']} saves "
          f"{'show' if frames else 'name'} no spot, "
          f"{counts['unanswered']} saves with no usable answer; {pending} batches still waiting for their agent"
          f"{' or for the next run' if stopped else ''}")
    if stopped:
        print(f"STOPPED: {stopped}")
    if fixed:
        print(f"{fixed} review entries moved to the pins (a person fixed them with ok: true or a lookup, or the "
              "address was found once its suite or unit was dropped, or once looked up on its own)")
    if dropped:
        print(f"{dropped} pins marked drop: true moved to review, and stay out of the pins")
    if streets:
        print(f"{streets} address pins moved to review: OpenStreetMap found only the street, not the house")
    if branches:
        print(f"{branches} pins found by name moved to review: they are not at the address the caption gives "
              "(another branch); the address alone was then looked up")
    wrong = wrong_area(review)
    log("locate_wrong_area", spots=len(wrong))
    if wrong:
        print(f"{len(wrong)} spots in review look filed under the wrong area, or matched a namesake far off "
              "(for the first, add the area, then give the spot `near:` and `lookup:`; for the second, a "
              "`lookup:` alone; see the skill's \"A spot in the wrong area\"):")
        for code, said, near, hint in wrong[:WRONG_SHOWN]:
            print(f"  {code}  {said!r} under {near}: {hint}")
        if len(wrong) > WRONG_SHOWN:
            print(f"  ... and {len(wrong) - WRONG_SHOWN} more (ev=locate_wrong_area)")
    return 3 if stopped else 0


def wrong_area(review):
    """(code, said, near, hint) for the review spots most likely filed under the wrong area: the agent
    said the spot is really somewhere else (`really_in`), or OpenStreetMap found it far from its area.
    A road-trip reel names stops in towns the save is not tagged with, and the agent can only file a
    spot under one of the save's areas, so such a stop lands under the nearest one, often in another
    state. Its Google search then looks in the wrong place too."""
    out = []
    for code, entries in sorted(review.items()):
        for e in entries if isinstance(entries, list) else []:
            if not isinstance(e, dict) or e.get("drop") or not isinstance(e.get("near"), str):
                continue
            said = str(e.get("said") or "")
            really = e["really_in"].strip() if isinstance(e.get("really_in"), str) else ""
            # "really in Example Town, Example State" under Example Town is the same town: not misfiled
            if really and really.split(",")[0].strip().lower() != e["near"].strip().lower():
                out.append((code, said, e["near"], f"really in {really}"))
                continue
            km = e.get("km")
            if isinstance(km, (int, float)) and km > FAR_KM:
                out.append((code, said, e["near"], f"found {km:.0f} km away ({str(e.get('found') or '')[:60]})"))
    return out


def main(argv=None, fetcher=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    action = ap.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true", help="batch files for the post-locator agents")
    action.add_argument("--merge", action="store_true", help="check the answers, look the spots up, write the pins")
    scope = ap.add_mutually_exclusive_group()
    scope.add_argument("--pilot", help="a pilot name from config/collections.yaml")
    scope.add_argument("--all", action="store_true", help="every save")
    ap.add_argument("--frames", action="store_true", help="with --merge: the frame-reader's answers")
    ap.add_argument("--redo", action="store_true", help="batch saves that already have an answer")
    ap.add_argument("--limit", type=int, default=0, help="at most this many saves this round (0 = no limit)")
    ap.add_argument("--batch-saves", type=int, default=BATCH_SAVES, help="most saves in one batch")
    ap.add_argument("--batch-chars", type=int, default=BATCH_CHARS, help="about the most characters in one batch")
    ap.add_argument("--saved", default=None, help="saves.json (default: the data repo's .cache)")
    args = ap.parse_args(argv)
    if args.prepare and not (args.pilot or args.all):
        ap.error("--prepare needs --pilot NAME or --all")
    if args.frames and not args.merge:
        ap.error("--frames goes with --merge; read_frames.py --prepare makes the frame batches")

    saves = read_saves(args.saved)["saves"]
    tags = load_yaml(TAGS)
    places = load_places()
    if args.merge:
        return merge(saves, tags, places, fetcher, args.frames)
    pilot = None
    if args.pilot:
        pilots = load_yaml(os.path.join("config", "collections.yaml")).get("pilots") or {}
        if args.pilot not in pilots:
            sys.exit(f"no pilot {args.pilot!r} in config/collections.yaml (have: {', '.join(pilots) or 'none'})")
        pilot = pilots[args.pilot]
    done = set(load_yaml(PINS)) | set(load_yaml(REVIEW)) | set(load_yaml(NO_SPOT))
    return prepare(args, saves, tags, places, pilot, done)


if __name__ == "__main__":
    sys.exit(main())
