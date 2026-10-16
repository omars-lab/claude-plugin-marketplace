#!/usr/bin/env python3
"""resolve_post_location.py — turn each saved post into pins for the spots it names (a beach, a café,
a trailhead), each one found on OpenStreetMap near the town or park the save is tagged with. The
reading is done by the post-locator agent in batches; this script never calls a model.

    resolve_post_location.py --prepare --pilot NAME   batch files for the saves the agent must read
    resolve_post_location.py --prepare --all          the same for every save
    resolve_post_location.py --merge                  check the agents' answers, look the spots up,
                                                      write the pins
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
  4. The first answer within the area's reach is kept: 25 km of the area's pin, or, for a park
     or region, inside its own OpenStreetMap box grown by 10 km. (A park's or region's box is looked
     up once, inside 60 km of its pin; when none is found, 25 km of its pin is the reach.)
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

Fixing a review entry
  Add `lookup: "Other Name"` to the entry: the next --merge searches that instead of what the caption
  said (the quote check is skipped, since a person wrote it). `near:` may be changed to another
  area in data/places.yaml. A found spot moves to pins.yaml. `drop: true` leaves the entry alone
  for good. Deleting all of a save's entries sends the save back to the agent on the next round.

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
from home import cache, home  # noqa: E402
from log import log  # noqa: E402
from pilot import in_pilot  # noqa: E402
from places import load_yaml  # noqa: E402
from quote import quote_ok  # noqa: E402

PINS = os.path.join("data", "pins.yaml")
REVIEW = os.path.join("data", "pins-review.yaml")
NO_SPOT = os.path.join("data", "no-spot.yaml")
TAGS = os.path.join("data", "tags.yaml")
PLACES = os.path.join("data", "places.yaml")
EXACT = {"city", "area", "park", "region"}  # more exact than a state or country
BOXED = {"park", "region"}                   # reach is the area's own box, grown
TOWN_KM = 25.0
BOX_KM = 10.0
AREA_SEARCH_KM = 60.0
MARGIN_KM = 25.0                             # searched past the reach, so a near miss shows its distance
CAPTION_CHARS = 2500                         # the batch limits are the tagger's
BATCH_SAVES = 40
BATCH_CHARS = 60000


def batch_dir():
    return cache("batches", "locate")


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
    """{name, kind, lat, lon} for a place more exact than a state or country with a pin, else None."""
    p = places.get(name)
    if not isinstance(p, dict) or p.get("kind") not in EXACT or p.get("lat") is None or p.get("lon") is None:
        return None
    return {"name": name, "kind": p["kind"], "lat": p["lat"], "lon": p["lon"]}


def areas_of(tag, places):
    return [a for a in (exact_area(c, places) for c in (tag or {}).get("cities") or []) if a]


class Reach:
    """Where a spot may be for its area: the box to search in, and the test an answer must pass."""

    def __init__(self, area, places, fetcher=None):
        self.area = area
        self.town = box_around(area["lat"], area["lon"], TOWN_KM)
        self.box = None
        if area["kind"] in BOXED:
            own = self.area_box(places.get(area["name"]) or {}, fetcher)
            if own:
                self.box = grow(own, BOX_KM)
        self.search = grow(union(self.town, self.box) if self.box else self.town, MARGIN_KM)

    def area_box(self, place, fetcher):
        """The park's or region's own box on OpenStreetMap: its name searched near its pin."""
        name = (place.get("found") or self.area["name"]).split(",")[0].strip()
        hits = geocode.lookup_near(name, box_around(self.area["lat"], self.area["lon"], AREA_SEARCH_KM), fetcher)
        same = [h for h in hits if (h.get("name") or "").lower() == name.lower() and h.get("box")]
        hit = (same or [h for h in hits if h.get("box")] or [None])[0]
        return tuple(hit["box"]) if hit else None

    def km(self, lat, lon):
        return km_between(self.area["lat"], self.area["lon"], lat, lon)

    def ok(self, lat, lon):
        return self.km(lat, lon) <= TOWN_KM or bool(self.box and inside(self.box, lat, lon))


# --- one spot ------------------------------------------------------------------------------------

def search_text(spot):
    """What to ask OpenStreetMap: a person's `lookup:` first; the agent's plain `name` only when the
    caption said a handle or hashtag (`@examplecafe`); otherwise the caption's own words."""
    said = spot["said"]
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


def coords_in(caption, lat, lon):
    """True when the caption gives these coordinates ("36.55644, -121.91886"), to 5 decimals."""
    nums = [float(n) for n in re.findall(r"-?\d{1,3}\.\d{3,}", caption or "")]
    return any(abs(n - lat) < 1e-5 for n in nums) and any(abs(n - lon) < 1e-5 for n in nums)


def venue_name(spot):
    return spot.get("name") or spot["said"].lstrip("@#").strip()


def resolve(spot, caption, areas, places, reaches, fetcher=None, creator=""):
    """("pin" or "review", entry) for one spot. areas: the names the spot's `near` may be.

    The spot's name is looked up first. When the caption gives the spot's coordinates, they are the
    pin, if they fall within the area's reach. When the name is not found (most small restaurants
    are not on OpenStreetMap) and the caption gives the spot's street address, the address is looked
    up instead: the pin is at the address, named for the venue."""
    said, near = spot["said"], spot["near"]
    by_person = isinstance(spot.get("lookup"), str) and bool(spot["lookup"].strip())
    base = {"said": said, "near": near}
    keep = {k: spot[k] for k in ("lookup", "name", "address") if spot.get(k)}
    if "address" in keep and not (by_person or quote_ok(keep["address"], caption)):
        del keep["address"]   # an address the caption doesn't give is a guess
    if not by_person and not (quote_ok(said, caption) or is_creator(said, creator)):
        return "review", {**base, "why": "quote not in caption", **keep}
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
    if where == "pin" or not address:
        return where, entry
    hits = geocode.lookup_near(address, reach.search, fetcher)
    hit = next((h for h in hits if reach.ok(h["lat"], h["lon"])), None)
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
    good = [h for h in hits if reach.ok(h["lat"], h["lon"])]
    hit = (good or hits or [None])[0]
    if hit is None:
        return "review", {**base, "why": f"not found near {near}", "asked": asked, **keep}
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


def prepare(args, saves, tags, places, pilot, done):
    out = batch_dir()
    waiting = sorted(glob.glob(os.path.join(out, "batch-[0-9][0-9][0-9].answers.json")))
    if waiting:
        sys.exit(f"{len(waiting)} answers files are not merged yet ({os.path.basename(waiting[0])}...): "
                 "run --merge first, so a new round does not delete them")
    todo, skipped, no_area = [], 0, 0
    for s in saves:
        tag = tags.get(s["code"])
        if pilot and not in_pilot(s, tag, pilot):
            continue
        areas = areas_of(tag, places)
        if not areas:
            no_area += 1
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
        answered_before=skipped, no_exact_area=no_area, dir=out)
    return 0


# --- merge ---------------------------------------------------------------------------------------

def recheck_review(by_code, tags, places, pins, review, reaches, fetcher):
    """Review entries a person gave a `lookup:` are searched again; found ones move to pins."""
    moved = 0
    for code, entries in list(review.items()):
        if not isinstance(entries, list):
            continue
        keep = []
        for e in entries:
            if not (isinstance(e, dict) and isinstance(e.get("lookup"), str) and e["lookup"].strip()
                    and not e.get("drop") and isinstance(e.get("said"), str) and isinstance(e.get("near"), str)):
                keep.append(e)
                continue
            caption = (by_code.get(code) or {}).get("caption") or ""
            areas = [a["name"] for a in areas_of(tags.get(code), places)] + [e["near"]]  # a person may move it
            where, new = resolve(e, caption, areas, places, reaches, fetcher, creator_of(by_code.get(code)))
            if where == "pin":
                pins.setdefault(code, [])
                if not any(p["said"] == new["said"] and p["near"] == new["near"] for p in pins[code]):
                    pins[code].append(new)
                moved += 1
                log("locate_review_fixed", code=code, said=new["said"])
            else:
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
        for k in ("name", "address"):
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


def merge(saves, tags, places, fetcher=None):
    by_code = {s["code"]: s for s in saves}
    pins, review, no_spot = load_yaml(PINS), load_yaml(REVIEW), load_yaml(NO_SPOT)
    reaches = {}
    fixed = recheck_review(by_code, tags, places, pins, review, reaches, fetcher)
    out = batch_dir()
    counts = {"pins": 0, "review": 0, "no_spot": 0, "unanswered": 0}
    pending = before = 0
    for path in sorted(glob.glob(os.path.join(out, "batch-[0-9][0-9][0-9].json"))):
        with open(path, encoding="utf-8") as fh:
            batch = json.load(fh)
        ans_path = batch["answers"]
        merged_path = ans_path.replace(".answers.json", ".answers.merged.json")
        if os.path.exists(merged_path):
            before += 1
            continue
        if not os.path.exists(ans_path):  # its agent has not run yet
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
            areas = [a["name"] for a in rec["areas"]]
            old = {(e.get("said"), e.get("near")): e for e in review.get(code) or [] if isinstance(e, dict)}
            new_pins, new_review = [], []
            for spot in spots:
                prior = old.get((spot["said"], spot["near"])) or {}
                if prior.get("drop"):  # a person dropped it before: keep it dropped
                    new_review.append(prior)
                    continue
                if prior.get("lookup"):  # a person's fix carries over a re-read
                    spot["lookup"] = prior["lookup"]
                where, entry = resolve(spot, caption, areas, places, reaches, fetcher, creator_of(by_code[code]))
                (new_pins if where == "pin" else new_review).append(entry)
            for d, v in ((pins, new_pins), (review, new_review)):  # a save's answer replaces its last one
                if v:
                    d[code] = v
                else:
                    d.pop(code, None)
            if spots:
                no_spot.pop(code, None)
            else:
                no_spot[code] = {"areas": areas}
                got["no_spot"] += 1
            got["pins"] += len(new_pins)
            got["review"] += len(new_review)
        for k in counts:
            counts[k] += got[k]
        log("locate_merge_batch", batch=batch["batch"], saves=len(batch["saves"]), **got)
        with open(os.path.join(out, "merged.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "batch": batch["batch"],
                                 "saves": len(batch["saves"]), **got, **({"error": bad} if bad else {})}) + "\n")
        os.replace(ans_path, merged_path)
    write_yaml(PINS, pins)
    write_yaml(REVIEW, review)
    write_yaml(NO_SPOT, no_spot)
    log("locate_merge", **counts, review_fixed=fixed, batches_waiting=pending, batches_merged_before=before,
        saves_with_pins=len(pins), saves_in_review=len(review), saves_no_spot=len(no_spot))
    print(f"{counts['pins']} spots pinned, {counts['review']} for review, {counts['no_spot']} saves name no spot, "
          f"{counts['unanswered']} saves with no usable answer; {pending} batches still waiting for their agent")
    if fixed:
        print(f"{fixed} review entries found with their lookup text and moved to the pins")
    return 0


def main(argv=None, fetcher=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    action = ap.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true", help="batch files for the post-locator agents")
    action.add_argument("--merge", action="store_true", help="check the answers, look the spots up, write the pins")
    scope = ap.add_mutually_exclusive_group()
    scope.add_argument("--pilot", help="a pilot name from config/collections.yaml")
    scope.add_argument("--all", action="store_true", help="every save")
    ap.add_argument("--redo", action="store_true", help="batch saves that already have an answer")
    ap.add_argument("--limit", type=int, default=0, help="at most this many saves this round (0 = no limit)")
    ap.add_argument("--batch-saves", type=int, default=BATCH_SAVES, help="most saves in one batch")
    ap.add_argument("--batch-chars", type=int, default=BATCH_CHARS, help="about the most characters in one batch")
    ap.add_argument("--saved", default=None, help="saves.json (default: the data repo's .cache)")
    args = ap.parse_args(argv)
    if args.prepare and not (args.pilot or args.all):
        ap.error("--prepare needs --pilot NAME or --all")

    with open(args.saved or cache("saves.json"), encoding="utf-8") as fh:
        saves = json.load(fh)["saves"]
    tags = load_yaml(TAGS)
    places = load_yaml(PLACES).get("places") or {}
    if args.merge:
        return merge(saves, tags, places, fetcher)
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
