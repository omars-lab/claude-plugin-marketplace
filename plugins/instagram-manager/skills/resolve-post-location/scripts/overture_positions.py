#!/usr/bin/env python3
"""overture_positions.py — a position we may keep for the spots OpenStreetMap does not list (most
small restaurants), from Overture Maps' open places data, matched on this Mac.

    overture_positions.py --pilot NAME --dry-run   the table: each spot, its best row, and the rule
                                                   it failed; nothing written but the download cache
    overture_positions.py --pilot NAME             the same, then the spots that pass every rule move
                                                   from the review list to the pins
    overture_positions.py --all                    every save
    overture_positions.py --pilot NAME --check-prepare   batch files of the held spots a reader could
                                                   clear, for overture-checker agents (nothing pinned)
    overture_positions.py --check-merge            pin the rows the agents picked
    options: --release R (default: the newest one online), --near "Example Town" (one area only),
             --batch-spots N (most spots in one check batch)

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

The agent step (`--check-prepare`, `--check-merge`): a spot held on a rule the caption can settle (a
looser name, branches, a park or region, another town, a warning word; `SOFT`) goes to a batch file in
$INSTAGRAM_HOME/.cache/batches/overture/ with its caption and the rows it could be, only rows that
pass every other rule (`candidates`). The overture-checker agent writes batch-NNN.answers.json, a row
id or null per spot; the merge pins a pick only if its batch offered it, with `checked: agent`, and
marks a null `overture_checked: <release>` in the review file so the release doesn't offer it again.

What a pin records: the fields every pin has (`name`, `said`, `near`, `kind`, `lat`, `lon`, `km`,
`found`, `map`), plus `by: overture`, `overture: <row id>`, `overture_release`, and `licence`: the
row's own sources' licences (Foursquare's rows are Apache-2.0, the rest CDLA-Permissive-2.0). The
licence texts sit in the data repo's docs/licences/. `found` is Overture's name and address. The
name is the one the spot was searched under, so its Google id in data/google.yaml still applies.

Releases are monthly, and only the last two stay online. A position is ours once saved, so a box is
downloaded only when a spot in it still waits; a later release changes nothing already pinned.
"""

import argparse
import glob
import hashlib
import json
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
    why = placed_badly(best, inside) or off_address(spot, best)
    if why:
        return best, why
    warn = WARN.search(caption or "")
    if warn:
        return best, f"the caption says {warn.group(0)!r}"
    return best, None


def placed_badly(best, inside):
    """Rule 5: why the row's point can't be trusted, or None."""
    same_street = [r for r in inside if r is not best and street_key(r) == street_key(best)]
    if same_street:
        mid = {"lat": statistics.median(r["lat"] for r in same_street),
               "lon": statistics.median(r["lon"] for r in same_street)}
        if km_m(best, mid) > ADDRESS_M:
            return f"more than {ADDRESS_M} m from the other rows at its address"
    pile = sum(1 for r in inside if r is not best and round(r["lat"], 5) == round(best["lat"], 5)
               and round(r["lon"], 5) == round(best["lon"], 5))
    if pile >= PILE:
        return f"{pile} other rows on the same point"
    return None


def off_address(spot, best):
    """Rule 6: "not at the caption's address" when the caption gives one the row doesn't have, or None."""
    address = spot.get("address")
    if isinstance(address, str) and address.strip():
        house = re.match(r"\s*(\d+)\b", address)
        words = rpl.name_words(address) - rpl.STREET_WORDS
        if (house and not re.match(rf"\s*{house.group(1)}\b", best["street"])) or \
                not words & rpl.name_words(best["street"]):
            return "not at the caption's address"
    return None


# --- the agent's check, for the spots a person could clear ------------------------------------------

# The rules a reader of the caption can settle: the name written another way, which of two branches,
# the town next door, a park's café, and a warning word that may not mean what it says ("new menu").
# The rest (no row, closed, not food, no street address, a guessed point, another address) are never
# offered: the agent can't see past them.
SOFT = ("only a looser name", "rows, more than", "the area is a", "the row's town is", "the caption says")
CANDIDATES = 5
CHECK_CAPTION = 2500
BATCH_SPOTS = 15


def soft(why):
    return bool(why) and any(s in why for s in SOFT)


def candidates(spot, rows, area, reach):
    """The rows the agent may choose from: any match by name or handle, open, food or drink, with a
    street address, a point that can be trusted and the caption's address if it gives one. Exact
    matches first, then the nearest to the area's pin."""
    name, said = spot["name"], spot["said"]
    inside = [r for r in rows if r.get("lat") is not None and reach.ok(r["lat"], r["lon"])]
    out = []
    for r in inside:
        m = matches(r, name, said, area["name"])
        if not m or closed(r) or not is_food(r) or not r.get("street"):
            continue
        if placed_badly(r, inside) or off_address(spot, r):
            continue
        out.append((m == "close", km_m(r, area), r))
    out.sort(key=lambda t: (t[0], t[1]))
    return [r for _, _, r in out[:CANDIDATES]]


def check_dir():
    return cache("batches", "overture")


def check_key(code, entry):
    return f"{code}|{entry['said']}|{entry['near']}"


def offered(row, area):
    """A row as the batch carries it: what the agent reads, and what the pin is made from."""
    return {"id": row["id"], "name": row.get("name"), "street": row.get("street"), "town": row.get("town"),
            "kind": row.get("basic"), "km_from_area": round(km_m(row, area) / 1000, 1),
            "hierarchy": list(row.get("hierarchy") or []), "licences": list(row.get("licences") or []),
            "lat": row["lat"], "lon": row["lon"]}


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
    creators = {s["code"]: s.get("creator") for s in saves}
    dry = args.dry_run or args.check_prepare
    if args.check_prepare:
        waiting_answers = sorted(glob.glob(os.path.join(check_dir(), "batch-[0-9][0-9][0-9].answers.json")))
        if waiting_answers:
            sys.exit(f"{len(waiting_answers)} answers files are not merged yet "
                     f"({os.path.basename(waiting_answers[0])}...): run --check-merge first")
        todo = [t for t in todo if t[1].get("overture_checked") != release]
    boxes, reaches, rows_of = {}, {}, {}
    table, placed, held, check = [], 0, {}, []
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
            if args.check_prepare and soft(why):
                rows = candidates(spot, rows_of[near], area, reaches[near])
                if rows:
                    check.append({"key": check_key(code, entry), "code": code, "creator": creators.get(code),
                                  "said": entry["said"], "name": spot["name"], "near": near,
                                  "near_kind": area["kind"], "held": why, "address": entry.get("address"),
                                  "caption": captions.get(code, "")[:CHECK_CAPTION],
                                  "rows": [offered(r, area) for r in rows]})
            continue
        placed += 1
        if not dry:
            pins.setdefault(code, []).append(pin_for(spot, entry, row, area, release))
            left = [e for e in review[code] if e is not entry]
            if left:
                review[code] = left
            else:
                del review[code]
    for code, name, near, found, why in table:
        print(f"{code}  {name[:32]:<32}  {near[:18]:<18}  {why[:60]:<60}  {found[:70]}")
    print(f"\n{len(todo)} spots not found on OpenStreetMap; {placed} pass every rule"
          f"{' (dry run: nothing written)' if dry else ' and are pinned'}; release {release}")
    for reason, n in sorted(held.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>4}  held: {reason}")
    if not dry and placed:
        rpl.write_yaml(rpl.PINS, pins)
        rpl.write_yaml(rpl.REVIEW, review)
    log("overture_run", scope=args.pilot or args.near or "all", release=release, spots=len(todo), pinned=placed,
        held=len(todo) - placed, dry_run=bool(dry))
    if args.check_prepare:
        write_check(check, release, args.batch_spots)
        if placed:
            print(f"{placed} spots pass every rule but are not pinned by this step: run it without "
                  f"--check-prepare for them")
    return 0


def write_check(spots, release, size):
    """The batch files for the overture-checker agents; a new round replaces the last one."""
    out = check_dir()
    os.makedirs(out, exist_ok=True)
    for old in glob.glob(os.path.join(out, "batch-*.json")):
        os.remove(old)
    batches = [spots[i:i + size] for i in range(0, len(spots), size)]
    for i, recs in enumerate(batches, 1):
        name = f"batch-{i:03d}"
        with open(os.path.join(out, name + ".json"), "w") as fh:
            json.dump({"batch": name, "answers": os.path.join(out, name + ".answers.json"), "release": release,
                       "spots": recs}, fh, ensure_ascii=False, indent=1)
        log("overture_check_batch", batch=name, spots=len(recs))
    print(f"{len(spots)} held spots a reader could clear, in {len(batches)} batch files in {out}: one "
          f"overture-checker agent per batch, at most 4 at a time, then --check-merge")
    log("overture_check_prepare", spots=len(spots), batches=len(batches), release=release)


def find_entry(review, key):
    code = key.split("|", 1)[0]
    for e in review.get(code) or []:
        if isinstance(e, dict) and not e.get("drop") and isinstance(e.get("said"), str) \
                and isinstance(e.get("near"), str) and check_key(code, e) == key \
                and str(e.get("why") or "").startswith("not found near"):
            return code, e
    return code, None


def check_merge(args):
    """Pin the rows the agents picked. A pick must be one of the rows its batch offered; a spot the agent
    found no row for stays in review, marked so the same release doesn't offer it again."""
    places = rpl.load_places()
    pins, review = load_yaml(rpl.PINS), load_yaml(rpl.REVIEW)
    counts = {"pinned": 0, "none": 0, "gone": 0, "bad": 0, "unanswered": 0}
    waiting_batches, merged = 0, 0
    for path in sorted(glob.glob(os.path.join(check_dir(), "batch-[0-9][0-9][0-9].json"))):
        with open(path) as fh:
            batch = json.load(fh)
        ans_path = batch["answers"]
        if not os.path.exists(ans_path):
            waiting_batches += 1
            continue
        try:
            with open(ans_path) as fh:
                answers = json.load(fh)
            answers = answers.get("answers", answers) if isinstance(answers, dict) else {}
        except ValueError as e:
            log("overture_check_bad_file", batch=batch["batch"], msg=str(e)[:200])
            print(f"{batch['batch']}: the answers file is not JSON ({e}); ask its agent again")
            continue
        for s in batch["spots"]:
            a = answers.get(s["key"])
            code, entry = find_entry(review, s["key"])
            if not isinstance(a, dict) or "row" not in a:
                counts["unanswered"] += 1
                continue
            if entry is None:   # pinned or changed since the batch was written
                counts["gone"] += 1
                continue
            offered_rows = {r["id"]: r for r in s["rows"]}
            pick = a.get("row")
            if pick is None:
                entry["overture_checked"] = batch["release"]
                counts["none"] += 1
                log("overture_check_spot", code=code, said=s["said"], result="none")
                continue
            if pick not in offered_rows:
                counts["bad"] += 1
                log("overture_check_spot", code=code, said=s["said"], result="bad", row=str(pick)[:60])
                continue
            o = offered_rows[pick]
            row = {**o, "basic": o.get("kind")}
            area = rpl.exact_area(entry["near"], places)
            pin = pin_for({"name": s["name"]}, entry, row, area, batch["release"])
            pin["checked"] = "agent"
            pins.setdefault(code, []).append(pin)
            left = [e for e in review[code] if e is not entry]
            if left:
                review[code] = left
            else:
                del review[code]
            counts["pinned"] += 1
            log("overture_check_spot", code=code, said=s["said"], result="pin", row=pick)
        os.replace(ans_path, ans_path.replace(".answers.json", ".answers.merged.json"))
        merged += 1
    if counts["pinned"] or counts["none"]:
        rpl.write_yaml(rpl.PINS, pins)
        rpl.write_yaml(rpl.REVIEW, review)
    print(f"{merged} batches merged: {counts['pinned']} spots pinned, {counts['none']} with no row that is the "
          f"spot, {counts['gone']} already moved on, {counts['bad']} picks not among the rows offered, "
          f"{counts['unanswered']} unanswered; {waiting_batches} batches still waiting for their agent")
    log("overture_check_merge", batches=merged, waiting=waiting_batches, **counts)
    return 0


def main(argv=None, con=None, fetcher=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    scope = ap.add_mutually_exclusive_group()
    scope.add_argument("--pilot", help="a pilot name from config/collections.yaml")
    scope.add_argument("--all", action="store_true", help="every save")
    scope.add_argument("--near", help="only the spots filed under this area")
    action = ap.add_mutually_exclusive_group()
    action.add_argument("--dry-run", action="store_true", help="print the table, write no data file")
    action.add_argument("--check-prepare", action="store_true",
                        help="batch files of the held spots a reader could clear, for overture-checker agents")
    action.add_argument("--check-merge", action="store_true", help="pin the rows the agents picked")
    ap.add_argument("--batch-spots", type=int, default=BATCH_SPOTS, help="most spots in one check batch")
    ap.add_argument("--release", help="an Overture release, such as 2026-09-23.1 (default: the newest online)")
    ap.add_argument("--saved", default=None, help="saves.json (default: the data repo's .cache)")
    args = ap.parse_args(argv)
    if args.check_merge:
        return check_merge(args)
    if not (args.pilot or args.all or args.near):
        ap.error("one of --pilot, --all or --near is needed")
    return run(args, con, fetcher)


if __name__ == "__main__":
    sys.exit(main())
