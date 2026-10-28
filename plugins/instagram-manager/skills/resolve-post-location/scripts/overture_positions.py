#!/usr/bin/env python3
"""overture_positions.py — a position we may keep for the spots OpenStreetMap does not list (most
small restaurants), from Overture Maps' open places data, matched on this Mac.

    overture_positions.py --pilot NAME --dry-run   the table: each spot, its best row, and the rule
                                                   it failed; nothing written but the download cache
    overture_positions.py --pilot NAME             the same, then the spots that pass every rule move
                                                   from the review list to the pins
    overture_positions.py --all                    every save
    options: --release R (default: the newest one online), --near "Example Town" (one area only)

Reads   $INSTAGRAM_HOME/data/pins-review.yaml     the spots whose `why` is "not found near ..."
        $INSTAGRAM_HOME/data/places.yaml          each area's kind and lat/lon, and its box (the
                                                  same reach resolve_post_location.py searches)
        $INSTAGRAM_HOME/.cache/saves.json         captions, for the warning words and the address
        Overture's public bucket                  s3://overturemaps-us-west-2/release/<R>/theme=places/
                                                  no key and no account; only the area's box is asked
                                                  for, never a venue's name
Writes  $INSTAGRAM_HOME/.cache/overture/<R>/<area>-<box>.parquet   one box per area, never committed
        $INSTAGRAM_HOME/data/pins.yaml            the spots that passed, `by: overture`
        $INSTAGRAM_HOME/data/pins-review.yaml     without those spots

The automatic rule (docs/research/venue-positions/consolidated.md in the data repo). A spot is
pinned with no one looking only when all seven hold:
  1. The row is not closed, is a food or drink place, and has a street address. An empty
     `operating_status` counts as open: most rows leave it empty.
  2. The name matches once filler words, business kinds and the area's own words are dropped, or
     the row carries the caption's handle (instagram.com/<handle>), or a website whose domain is
     the handle.
  3. Only one branch is left: every row that matches sits within 200 m of the first.
  4. The row's town is the spot's town. A park, region or part of a city has no town to compare,
     so its spots are held for a person.
  5. The point is within 300 m of the other rows at the same street address, and fewer than 5
     other rows sit on exactly the same point (a pile at a street's or a postcode's middle).
  6. An address in the caption, if any, has the row's house number and one of its street words.
  7. The caption doesn't warn: no "new", "now open", "opening", "coming", "branch" or "pop-up",
     and no food hall, market, mall, department store or hotel the spot may be inside.
A spot held by any rule stays in review as it was; the table says which rule held it, for the agent
step or a person (`lookup:`, `ok:` with a lat/lon, `by: hand`).

What a pin records: the fields every pin has (`name`, `said`, `near`, `kind`, `lat`, `lon`, `km`,
`found`, `map`), plus `by: overture`, `overture: <row id>`, `overture_release`, and `licence`: the
row's own sources' licences (Foursquare's rows are Apache-2.0, the rest CDLA-Permissive-2.0). The
licence texts sit in the data repo's docs/licences/. `found` is Overture's name and address. The
name is the one the spot was searched under, so its Google id in data/google.yaml still applies.

Releases are monthly, and only the last two stay online. A position is ours once saved, so a box is
downloaded only when a spot in it still waits; a later release changes nothing already pinned.
"""

import argparse
import hashlib
import os
import re
import statistics
import sys
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import resolve_post_location as rpl  # noqa: E402  (it puts shared/scripts on the path)
import geocode  # noqa: E402
from home import cache, read_saves  # noqa: E402
from log import log  # noqa: E402
from pilot import in_pilot  # noqa: E402
from places import load_yaml  # noqa: E402

BUCKET = "s3://overturemaps-us-west-2/release"
BRANCH_M = 200       # two matching rows further apart than this are two branches
ADDRESS_M = 300      # how far a row may sit from the other rows at its street address
PILE = 5             # this many other rows on exactly one point is a pile, not a building
FOOD = {"food_and_drink"}
FOOD_BASIC = {"restaurant", "food_service", "cafe", "coffee_shop", "bakery", "bar", "food_or_drink_retail",
              "dessert_shop", "food_truck", "brewery", "winery", "food_and_drink"}
WARN = re.compile(r"\b(new|now open|opening|coming|branch(es)?|pop[- ]?ups?|food halls?|markets?|malls?|"
                  r"department stores?|grocery|hotels?)\b", re.I)
KIND = {"restaurant": "restaurant", "cafe": "cafe", "coffee_shop": "cafe", "bakery": "bakery", "bar": "bar"}


def km_m(a, b):
    return rpl.km_between(a["lat"], a["lon"], b["lat"], b["lon"]) * 1000


# --- the download ---------------------------------------------------------------------------------

def connect():
    import duckdb
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2'; SET enable_progress_bar=false;")
    return con


def newest_release(con):
    rows = con.execute(f"SELECT DISTINCT regexp_extract(file, 'release/([^/]+)/', 1) AS r "
                       f"FROM glob('{BUCKET}/*/theme=places/type=place/*') ORDER BY r DESC").fetchall()
    if not rows:
        sys.exit("no Overture release found online")
    return rows[0][0]


def box_path(release, area, box):
    slug = re.sub(r"[^a-z0-9]+", "-", area.lower()).strip("-")
    tag = hashlib.sha1(",".join(f"{v:.4f}" for v in box).encode()).hexdigest()[:8]
    return cache("overture", release, f"{slug}-{tag}.parquet")


COLUMNS = """id, names.primary AS name, basic_category AS basic, taxonomy.hierarchy AS hierarchy,
  operating_status AS status, addresses[1].freeform AS street, addresses[1].locality AS town,
  websites, socials, [s.dataset FOR s IN sources] AS datasets, [s.license FOR s IN sources] AS licences,
  bbox.ymin AS lat, bbox.xmin AS lon"""


def fetch(con, release, area, box):
    """The box's rows, from the cache or the bucket. Only the box is in the request."""
    path = box_path(release, area, box)
    if not os.path.exists(path):
        s, w, n, e = box
        os.makedirs(os.path.dirname(path), exist_ok=True)
        log("overture_fetch", area=area, release=release, box=f"{s:.4f},{w:.4f},{n:.4f},{e:.4f}")
        con.execute(f"COPY (SELECT {COLUMNS} FROM read_parquet('{BUCKET}/{release}/theme=places/type=place/*') "
                    f"WHERE bbox.xmin BETWEEN {w} AND {e} AND bbox.ymin BETWEEN {s} AND {n}) "
                    f"TO '{path}.tmp' (FORMAT parquet)")
        os.replace(path + ".tmp", path)
    cur = con.execute(f"SELECT * FROM read_parquet('{path}')")
    names = [d[0] for d in cur.description]
    rows = [dict(zip(names, r)) for r in cur.fetchall()]
    log("overture_box", area=area, rows=len(rows), file=os.path.basename(path))
    return rows


# --- the rule -------------------------------------------------------------------------------------

def core(name, area):
    return rpl.name_words(name) - rpl.KIND_WORDS - rpl.area_words(area)


def lead(name):
    """The name's first word, past a "the"."""
    words = [w for w in re.split(r"\s+", name.strip()) if w]
    if len(words) > 1 and words[0].lower() == "the":
        words = words[1:]
    return rpl.squash(words[0]) if words else ""


def handle_of(said):
    return said[1:].strip().lower() if said.startswith("@") else ""


def carries_handle(row, handle):
    """The row's own links name the handle: its Instagram page, or a website whose domain is the handle
    ("@examplecafe" and examplecafe.com)."""
    if not handle:
        return False
    for s in row.get("socials") or []:
        m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)", s or "")
        if m and m.group(1).lower().rstrip(".") == handle:
            return True
    for w in row.get("websites") or []:
        host = (urlparse(w if "//" in (w or "") else "//" + (w or "")).hostname or "").lower()
        host = host[4:] if host.startswith("www.") else host
        if host and rpl.squash(host.rsplit(".", 1)[0]) == rpl.squash(handle):
            return True
    return False


def matches(row, name, said, area):
    """How the row matches the spot: "name", "handle", "close" (a looser match, for the table only)
    or None."""
    if carries_handle(row, handle_of(said)):
        return "handle"
    a, f = core(name, area), core(row.get("name") or "", area)
    # The same words in another order can be another place ("Examples Tacos" and "Tacos Example"),
    # so the names must also start with the same word.
    if a and a == f and lead(name) == lead(row.get("name") or ""):
        return "name"
    if a and a == f:
        return "close"
    if rpl.same_name(name, row.get("name") or "", area) or (len(rpl.squash(name)) >= 5
                                                             and rpl.squash(name) in rpl.squash(row.get("name") or "")):
        return "close"
    if len(f) >= 2 and f < a:   # the row's name is the start of ours: "Example Fish" for "Example Fish N Chips"
        return "close"
    return None


def is_food(row):
    return (row.get("hierarchy") or [None])[0] in FOOD or row.get("basic") in FOOD_BASIC


def closed(row):
    return str(row.get("status") or "").lower() not in ("", "open")


def street_key(row):
    return (rpl.squash(row.get("street") or ""), (row.get("town") or "").lower())


def judge(spot, rows, area, reach, caption):
    """(row, None) for a spot that passes every rule, else (best row or None, the rule that held it)."""
    name, said = spot["name"], spot["said"]
    inside = [r for r in rows if r.get("lat") is not None and reach.ok(r["lat"], r["lon"])]
    hits = [(matches(r, name, said, area["name"]), r) for r in inside]
    hits = [(m, r) for m, r in hits if m]
    strong = [r for m, r in hits if m in ("name", "handle") and not closed(r)]
    best = (strong or [r for _, r in hits] or [None])[0]
    if not strong:
        return best, "no row by that name" if not hits else f"only a looser name ({best.get('name')})"
    if any(km_m(r, strong[0]) > BRANCH_M for r in strong[1:]):
        return best, f"{len(strong)} rows, more than {BRANCH_M} m apart (branches)"
    best = max(strong, key=lambda r: (bool(r.get("street")), is_food(r), len(r.get("datasets") or [])))
    if not is_food(best):
        return best, f"not a food or drink place ({best.get('basic')})"
    if not best.get("street"):
        return best, "no street address"
    if area["kind"] != "city":
        return best, f"the area is a {area['kind']}, not a town, so the row's town can't be compared"
    if (best.get("town") or "").lower() != area["name"].lower():
        return best, f"the row's town is {best.get('town') or 'not given'}"
    same_street = [r for r in inside if r is not best and street_key(r) == street_key(best)]
    if same_street:
        mid = {"lat": statistics.median(r["lat"] for r in same_street),
               "lon": statistics.median(r["lon"] for r in same_street)}
        if km_m(best, mid) > ADDRESS_M:
            return best, f"more than {ADDRESS_M} m from the other rows at its address"
    pile = sum(1 for r in inside if r is not best and round(r["lat"], 5) == round(best["lat"], 5)
               and round(r["lon"], 5) == round(best["lon"], 5))
    if pile >= PILE:
        return best, f"{pile} other rows on the same point"
    address = spot.get("address")
    if isinstance(address, str) and address.strip():
        house = re.match(r"\s*(\d+)\b", address)
        words = rpl.name_words(address) - rpl.STREET_WORDS
        if (house and not re.match(rf"\s*{house.group(1)}\b", best["street"])) or \
                not words & rpl.name_words(best["street"]):
            return best, "not at the caption's address"
    warn = WARN.search(caption or "")
    if warn:
        return best, f"the caption says {warn.group(0)!r}"
    return best, None


def licence(row):
    return ", ".join(sorted({str(x) for x in row.get("licences") or [] if x})) or "CDLA-Permissive-2.0"


def pin_for(spot, entry, row, area, release):
    pin = {"name": spot["name"], "said": entry["said"], "near": entry["near"],
           "kind": KIND.get(row.get("basic") or "", "restaurant" if is_food(row) else row.get("basic") or "place"),
           "lat": round(row["lat"], 6), "lon": round(row["lon"], 6),
           "km": round(rpl.km_between(area["lat"], area["lon"], row["lat"], row["lon"]), 1),
           "found": ", ".join(x for x in (row.get("name"), row.get("street"), row.get("town")) if x),
           "map": geocode.maps_link(spot["name"], entry["near"])}
    for k in ("asked", "lookup", "address", "from"):
        if k in entry:
            pin[k] = entry[k]
    pin.update({"by": "overture", "overture": row["id"], "overture_release": release, "licence": licence(row)})
    return pin


# --- the run --------------------------------------------------------------------------------------

def waiting(review, saves, tags, pilot, only):
    """[(code, entry, spot)]: review spots not found on OpenStreetMap, in scope."""
    by_code = {s["code"]: s for s in saves}
    out = []
    for code, entries in sorted(review.items()):
        if pilot and (code not in by_code or not in_pilot(by_code[code], tags.get(code), pilot)):
            continue
        for e in entries if isinstance(entries, list) else []:
            if not isinstance(e, dict) or e.get("drop") or not str(e.get("why") or "").startswith("not found near"):
                continue
            if not isinstance(e.get("said"), str) or not isinstance(e.get("near"), str) or (only and e["near"] != only):
                continue
            name = next((e[k] for k in ("lookup", "asked") if isinstance(e.get(k), str) and e[k].strip()),
                        e["said"].lstrip("@#")).strip()
            out.append((code, e, {"name": name, "said": e["said"], "address": e.get("address")}))
    return out


def run(args, con=None, fetcher=None):
    saves = read_saves(args.saved)["saves"]
    captions = {s["code"]: s.get("caption") or "" for s in saves}
    tags, places = load_yaml(rpl.TAGS), rpl.load_places()
    pins, review = load_yaml(rpl.PINS), load_yaml(rpl.REVIEW)
    pilot = None
    if args.pilot:
        pilots = load_yaml(os.path.join("config", "collections.yaml")).get("pilots") or {}
        if args.pilot not in pilots:
            sys.exit(f"no pilot {args.pilot!r} in config/collections.yaml (have: {', '.join(pilots) or 'none'})")
        pilot = pilots[args.pilot]
    todo = waiting(review, saves, tags, pilot, args.near)
    con = con or connect()
    release = args.release or newest_release(con)
    boxes, reaches, rows_of = {}, {}, {}
    table, placed, held = [], 0, {}
    for code, entry, spot in todo:
        near = entry["near"]
        area = rpl.exact_area(near, places)
        if not area:
            table.append((code, spot["name"], near, "", "the area has no pin to search near"))
            held["no area"] = held.get("no area", 0) + 1
            continue
        if near not in reaches:
            r = rpl.Reach(area, places, fetcher)
            reaches[near] = r
            boxes[near] = rpl.union(r.town, r.box) if r.box else r.town
            rows_of[near] = fetch(con, release, near, boxes[near])
        row, why = judge(spot, rows_of[near], area, reaches[near], captions.get(code, ""))
        found = f"{row.get('name')}, {row.get('street') or '?'}, {row.get('town') or '?'}" if row else ""
        table.append((code, spot["name"], near, found, why or "PIN"))
        log("overture_spot", code=code, near=near, said=entry["said"], result="pin" if not why else "held",
            why=why or "")
        if why:
            reason = why.split(" (")[0].split(",")[0]
            reason = re.sub(r"\d+", "N", reason)
            held[reason] = held.get(reason, 0) + 1
            continue
        placed += 1
        if not args.dry_run:
            pins.setdefault(code, []).append(pin_for(spot, entry, row, area, release))
            left = [e for e in review[code] if e is not entry]
            if left:
                review[code] = left
            else:
                del review[code]
    for code, name, near, found, why in table:
        print(f"{code}  {name[:32]:<32}  {near[:18]:<18}  {why[:60]:<60}  {found[:70]}")
    print(f"\n{len(todo)} spots not found on OpenStreetMap; {placed} pass every rule"
          f"{' (dry run: nothing written)' if args.dry_run else ' and are pinned'}; release {release}")
    for reason, n in sorted(held.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>4}  held: {reason}")
    if not args.dry_run and placed:
        rpl.write_yaml(rpl.PINS, pins)
        rpl.write_yaml(rpl.REVIEW, review)
    log("overture_run", scope=args.pilot or args.near or "all", release=release, spots=len(todo), pinned=placed,
        held=len(todo) - placed, dry_run=bool(args.dry_run))
    return 0


def main(argv=None, con=None, fetcher=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument("--pilot", help="a pilot name from config/collections.yaml")
    scope.add_argument("--all", action="store_true", help="every save")
    scope.add_argument("--near", help="only the spots filed under this area")
    ap.add_argument("--dry-run", action="store_true", help="print the table, write no data file")
    ap.add_argument("--release", help="an Overture release, such as 2026-09-23.1 (default: the newest online)")
    ap.add_argument("--saved", default=None, help="saves.json (default: the data repo's .cache)")
    return run(ap.parse_args(argv), con, fetcher)


if __name__ == "__main__":
    sys.exit(main())
