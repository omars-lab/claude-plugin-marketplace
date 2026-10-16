#!/usr/bin/env python3
"""google_ids.py — find Google's own place for each spot a save names, and keep only its place id.

    google_ids.py --pilot NAME [--limit N] [--only KEY,KEY] [--refresh] [--box-km 2] [--dry-run]
    google_ids.py --pilot NAME --pick KEY=PLACE_ID [--pick ...]
    google_ids.py --pilot NAME --none KEY [--none ...]
    google_ids.py --pilot NAME --chain KEY [--chain ...]
    google_ids.py --pilot NAME --prune [--dry-run]

For each spot (data/pins.yaml, and the venues OpenStreetMap lacks from data/pins-review.yaml) it
sends one Google Text Search: our own search text, inside a box round our own pin, or round the
spot's town when the spot has no pin. Google's top 3 are printed on screen with name, address, kind
and "CLOSED FOR GOOD"; none of that is written anywhere (shared/scripts/google_places.py says why).

  - When exactly one of the 3 carries every word of our name, its id is kept (`by: auto`). When the
    caption gives a street address with a house number, that one must also be at that number;
    another branch of a chain carries the name but not the address, so it is left for a person.
    A name taken from a handle is matched too: without a town, hashtag or state code at its end
    ("Example Tacos ETX" is Google's "Example Tacos"), and run together ("Examplecafe" is
    "Example Cafe").
  - A spot with no pin is searched round its town: 8 km for a city, or the town's own `box_km` in
    config/places.yaml for a sprawling one, and at least 30 km when the caption gives a house
    number, since Google's place must then be at that number.
  - Otherwise the spot is printed with a `PICK='KEY=PLACE_ID'` line per candidate for a person.
    `--pick` checks the id with Google's free id-only call and keeps it (`by: hand`, or
    `by: claude` with `--by claude` when Claude chose from the list rather than a person).
  - Nothing in the box is kept as `verdict: none`, so it is not searched again. `--none KEY` lets a
    person say the same of a spot whose candidates are all wrong.
  - `--chain KEY` says the spot is a chain with several branches, so any of them will do. It is kept
    as `verdict: chain` with no id: its map link stays a search for its name in its area, which
    shows every branch there, and it is not searched again.

The spots left for a person also go to .cache/google-to-pick.json with their candidates' place ids
in Google's order, and nothing else of Google's, so build-hub's decisions_page.py can list them as
"open in Google Maps" links to pick from. A spot leaves that file once it is picked, marked none or
kept by name.

data/google.yaml is rewritten after every spot, so a run stopped by the day's cap (HTTP 429 "per
day") keeps what it found; the same command tomorrow carries on. A spot already there with the same
search text is skipped, and so is one whose candidates already wait for a person with the same
search text (--refresh searches either again). An id kept by name before the house number was
checked, for a spot whose caption gives one, is searched once more (`at_address` marks the check).

A spot with no pin that the locator says is really in another town (`really_in`) is not searched:
the box would sit round the wrong town. It is listed to fix its area first. A kept id whose spot
moved (its new pin or town gives it a new key) or was dropped is listed as no longer used, and
--prune drops it, after printing any that a person or Claude picked.

The key comes from GOOGLE_MAPS_API_KEY; `make google-ids` in the data repo runs this through
`dotenvx run`, which decrypts it into this one process. --dry-run needs no key and calls nothing.
"""

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.join(HERE, os.pardir, os.pardir)
sys.path.insert(0, os.path.join(SKILLS, os.pardir, "shared", "scripts"))
sys.path.insert(0, os.path.join(SKILLS, "build-hub", "scripts"))
import build_hub as bh  # noqa: E402
import google_places as gp  # noqa: E402
from home import cache, home, offline, read_saves  # noqa: E402
from log import log  # noqa: E402
from pilot import in_pilot  # noqa: E402
from places import Places, load_yaml  # noqa: E402

OUT = os.path.join("data", "google.yaml")
TO_PICK = "google-to-pick.json"   # in .cache: the spots left for a person, with their candidates' ids
STALE_SHOWN = 20   # how many stale keys to list on screen
HEADER = ("# Google place ids for the spots in data/pins.yaml and data/pins-review.yaml, written by\n"
          "# instagram-manager's find-google-ids. Only the id is kept, with our own search text, the date\n"
          "# and who chose it (auto: the only candidate carrying every word of our name, and at_address when\n"
          "# it is also at the caption's house number; claude: Claude,\n"
          "# from Google's list on screen; hand: a person). verdict: chain means any branch will do, so\n"
          "# its link searches the name in its area and no id is kept.\n"
          "# Nothing else of Google's goes in this file: no name, address or position.\n")


def spots_in_scope(saves, tags, pins, placed, pilot):
    """key → (spot, [codes]) for every spot of every save in scope, each spot once. When several posts
    name one place, the copy that gives a street address is the one searched: it is the most exact."""
    out = {}
    for s in saves:
        if not in_pilot(s, tags.get(s["code"]), pilot):
            continue
        for e in (pins.get(s["code"]) or []) + placed.get(s["code"], []):
            if isinstance(e, dict) and isinstance(e.get("name"), str) and e["name"].strip():
                k = gp.spot_key(e)
                spot, codes = out.setdefault(k, (e, []))
                codes.append(s["code"])
                if not gp.house_number(spot.get("address")) and gp.house_number(e.get("address")):
                    out[k] = (e, codes)
    return out


def where(e, places, box_km):
    """(pin, half width in km, words for the screen) for the box to search in, or None."""
    lat, lon = bh.number(e.get("lat")), bh.number(e.get("lon"))
    if not e.get("placed") and lat is not None and lon is not None:
        return {"lat": lat, "lon": lon}, box_km, f"inside {box_km:g} km of our pin"
    town = places.resolve(e.get("near"))
    d = places.data.get(town) if town else None
    if not isinstance(d, dict) or bh.number(d.get("lat")) is None or bh.number(d.get("lon")) is None:
        return None
    half = gp.TOWN_BOX_KM.get(d.get("kind"))
    if half is None:   # a state or a country: too wide to tell one café from another
        return None
    own = places.config.get(town)
    if isinstance(own, dict) and bh.number(own.get("box_km")) is not None:   # a sprawling city says how wide
        half = float(own["box_km"])
    if gp.house_number(e.get("address")):   # Google's place must be at the number, so a wide box is safe
        half = max(half, gp.ADDRESS_BOX_KM)
    return {"lat": d["lat"], "lon": d["lon"]}, half, f"inside {half:g} km of {town} (no pin of our own)"


where_words = gp.where_words


def stale_keys(kept, saves, tags, pins, placed):
    """Kept keys that no spot of any save uses any more: the spot moved (a new pin or town gives it a
    new key) or was dropped. Worked out over every save, not only the pilot, so another run's ids
    are never counted stale."""
    used = spots_in_scope(saves, tags, pins, placed, None)
    return sorted(k for k in kept if k not in used)


def load_kept():
    got = load_yaml(OUT)
    return got if isinstance(got, dict) else {}


def write_kept(kept):
    path = os.path.join(home(), OUT)
    body = yaml.safe_dump({k: kept[k] for k in sorted(kept)}, sort_keys=False, allow_unicode=True, width=200)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(HEADER + body)
    os.replace(tmp, path)


def load_to_pick():
    try:
        with open(cache(TO_PICK), encoding="utf-8") as fh:
            got = json.load(fh)
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def write_to_pick(to_pick):
    """The spots left for a person: key → {query, ids, date}. Only place ids, never a name."""
    path = cache(TO_PICK)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({k: to_pick[k] for k in sorted(to_pick)}, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def entry(query, verdict, by, today, place_id=None):
    out = {"query": query, "verdict": verdict}
    if place_id:
        out["id"] = place_id
    out.update({"by": by, "date": today})
    return out


def unchecked_address(g, e):
    """An id kept by name before the house number was checked: the spot's caption gives a street
    address with a number, and nothing says Google's place was at it. It is searched once more."""
    return g.get("verdict") == "match" and g.get("by") == "auto" and not g.get("at_address") \
        and bool(gp.house_number(e.get("address")))


def pairs(values, flag):
    out = {}
    for v in values or []:
        k, sep, pid = v.partition("=")
        if not sep or not k.strip() or not pid.strip():
            sys.exit(f"google_ids: {flag} wants KEY=PLACE_ID, got {v!r}")
        out[k.strip()] = pid.strip()
    return out


def retry_logger(key):
    return lambda attempt, wait, why: log("google_retry", key=key, attempt=attempt, wait_s=wait, why=why)


def choose(spots, picks, nones, chains, by, today):
    """A person's (or Claude's) choices, kept in data/google.yaml and taken off the to-pick list.
    A pick is checked with Google's id-only call, so only a pick needs the key; none and chain do not
    (the serve-api skill saves those, with no key in its container). ValueError says what is wrong."""
    unknown = [k for k in list(picks) + list(nones) + list(chains) if k not in spots]
    if unknown:
        raise ValueError(f"no spot {', '.join(unknown)} in scope (keys are printed by a search run)")
    key = gp.api_key() if picks else ""
    if picks and not key:
        raise ValueError("no GOOGLE_MAPS_API_KEY (run it through dotenvx: make google-ids)")
    kept, to_pick = load_kept(), load_to_pick()
    for k, pid in picks.items():
        try:
            now = gp.current_id(pid, key, retry_logger(k))
        except urllib.error.HTTPError as e:
            raise ValueError(f"Google does not know {pid} (HTTP {e.code}); copy it again from the list")
        kept[k] = entry(gp.query_for(spots[k][0]), "match", by, today, now)
        log("google_keep", key=k, by=by, moved=str(now != pid).lower())
    for k in nones:
        kept[k] = entry(gp.query_for(spots[k][0]), "none", by, today)
        log("google_none", key=k, by=by)
    for k in chains:
        kept[k] = entry(gp.query_for(spots[k][0]), "chain", by, today)
        log("google_chain", key=k, by=by)
    write_kept(kept)
    for k in list(picks) + list(nones) + list(chains):
        to_pick.pop(k, None)
    write_to_pick(to_pick)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    which = ap.add_mutually_exclusive_group(required=True)
    which.add_argument("--pilot")
    which.add_argument("--all", action="store_true")
    ap.add_argument("--only", help="comma-separated spot keys (as printed) to search")
    ap.add_argument("--limit", type=int, help="search at most this many spots")
    ap.add_argument("--refresh", action="store_true", help="search spots already kept, again")
    ap.add_argument("--box-km", type=float, default=gp.BOX_KM, help="half the box round our pin (default 2)")
    ap.add_argument("--pick", action="append", help="KEY=PLACE_ID: keep this place for this spot")
    ap.add_argument("--none", action="append", help="KEY: none of the candidates is this spot")
    ap.add_argument("--chain", action="append",
                    help="KEY: a chain with several branches, any of them will do; its link searches them all")
    ap.add_argument("--by", choices=("hand", "claude"), default="hand",
                    help="who chose the --pick/--none/--chain: a person (hand, the default) or Claude reading the list")
    ap.add_argument("--dry-run", action="store_true", help="list what would be searched; no key, no calls")
    ap.add_argument("--prune", action="store_true", help="drop kept ids that no spot uses any more")
    args = ap.parse_args(argv)
    if offline() and not args.dry_run and not (args.pick or args.none or args.chain):
        sys.exit("google_ids: INSTAGRAM_OFFLINE is set, so Google is not searched; --dry-run lists what would be")

    saves_path = cache("saves.json")
    if not os.path.exists(saves_path):
        read_saves(saves_path)  # prints how to import, and exits
    tags = load_yaml(os.path.join("data", "tags.yaml"))
    pilot = None
    if args.pilot:
        pilot = (load_yaml(os.path.join("config", "collections.yaml")).get("pilots") or {}).get(args.pilot)
        if not isinstance(pilot, dict):
            sys.exit(f"google_ids: no pilot {args.pilot!r} in config/collections.yaml")
    pins = load_yaml(os.path.join("data", "pins.yaml"))
    placed = bh.placed_spots(load_yaml(os.path.join("data", "pins-review.yaml")))
    spots = spots_in_scope(bh.load_saves(saves_path), tags, pins, placed, pilot)
    places = Places.load()
    kept = load_kept()
    to_pick = load_to_pick()
    today = dt.date.today().isoformat()

    picks, nones = pairs(args.pick, "--pick"), [k.strip() for k in args.none or []]
    chains = [k.strip() for k in args.chain or []]
    if picks or nones or chains:
        try:
            choose(spots, picks, nones, chains, args.by, today)
        except ValueError as e:
            sys.exit(f"google_ids: {e}")
        print(f"kept {len(picks)} picked, {len(nones)} marked none and {len(chains)} marked a chain in {OUT}")
        return

    stale = stale_keys(kept, bh.load_saves(saves_path), tags, pins, placed)
    if args.prune and not args.dry_run:
        for k in stale:
            if kept[k].get("by") in ("hand", "claude"):
                print(f"dropping {k}, picked by {kept[k]['by']} on {kept[k].get('date')}: {kept[k].get('query')!r}")
            del kept[k]
        if stale:
            write_kept(kept)
        gone = stale_keys(to_pick, bh.load_saves(saves_path), tags, pins, placed)
        for k in gone:   # waiting for a person under a key no spot uses any more
            del to_pick[k]
        if gone:
            write_to_pick(to_pick)
        log("google_prune", dropped=len(stale), waiting_dropped=len(gone))
        print(f"dropped {len(stale)} kept ids that no spot uses any more")
        stale = []

    only = {k.strip() for k in (args.only or "").split(",") if k.strip()}
    todo, no_box, wrong, waiting = [], [], [], []
    for k in sorted(spots):
        e, codes = spots[k]
        if only and k not in only:
            continue
        q = gp.query_for(e)
        if not args.refresh and isinstance(kept.get(k), dict) and kept[k].get("query") == q \
                and not unchecked_address(kept[k], e):
            continue
        if not args.refresh and isinstance(to_pick.get(k), dict) and to_pick[k].get("query") == q:
            waiting.append(k)   # searched already: its candidates wait for a person, so no second call
            continue
        if e.get("placed") and e.get("really_in"):
            wrong.append((k, e))   # searching round the wrong town would waste a call
            continue
        box = where(e, places, args.box_km)
        if box is None:
            no_box.append(k)
            log("google_no_box", key=k, code=codes[0], msg="no pin, and its area is a state or unknown")
            continue
        todo.append((k, e, q, box))
    if args.limit is not None:
        todo = todo[:args.limit]
    print(f"{len(spots)} spots in scope; {len(todo)} to search, {len(no_box)} with no box to search in"
          + (f", {len(waiting)} waiting for a person to pick (the hub's decisions page)" if waiting else ""))
    if wrong:
        print(f"{len(wrong)} not searched: filed under the wrong area, fix its area first "
              "(resolve-post-location, \"A spot in the wrong area\"):")
        for k, e in wrong:
            print(f"  {k}: {e['said']!r} under {e['near']}, really in {e['really_in']}")
    if stale:
        print(f"{len(stale)} kept ids no spot uses any more (its spot moved or was dropped); "
              "--prune drops them: " + ", ".join(stale[:STALE_SHOWN]) + (" …" if len(stale) > STALE_SHOWN else ""))
    if args.dry_run or not todo:
        for k, e, q, (_, _, words) in todo:
            print(f"  {k}: {q!r}, {words}")
        return
    key = gp.api_key()
    if not key:
        sys.exit("google_ids: no GOOGLE_MAPS_API_KEY (run it through dotenvx: make google-ids)")

    auto, left, none, closed = 0, [], 0, []
    place_words = where_words(places)
    for n, (k, e, q, (pin, half, words)) in enumerate(todo, 1):
        log("google_search", n=n, of=len(todo), key=k)
        try:
            found = gp.search(q, pin, half, key, retry_logger(k))
        except urllib.error.HTTPError as e2:
            if gp.daily_cap(e2):
                log("google_cap", key=k, done=n - 1, msg="the day's cap is used up; run the same command tomorrow")
                break
            log("google_error", key=k, http=e2.code, msg=gp.error_text(e2)[:200])
            raise
        log("google_found", key=k, candidates=len(found))
        to_pick.pop(k, None)
        if not found:
            kept[k] = entry(q, "none", "auto", today)
            none += 1
            print("\n".join(gp.show(k, q, found, words)))
        else:
            hit = gp.auto_pick(e["name"], found, e.get("address"), place_words)
            if hit:
                kept[k] = entry(q, "match", "auto", today, hit["id"])
                if gp.house_number(e.get("address")):
                    kept[k]["at_address"] = True
                auto += 1
                print(f"kept  {k}: {e['name']!r} = {hit['name']} — {hit['address']}"
                      + ("  CLOSED FOR GOOD" if hit["closed"] else ""))
                if hit["closed"]:
                    closed.append(k)
            else:
                left.append(k)
                to_pick[k] = {"query": q, "ids": [c["id"] for c in found], "date": today}
                print("\n".join(gp.show(k, q, found, words)))
        write_kept(kept)
        write_to_pick(to_pick)
    print(f"\n{auto} kept by name, {len(left)} for a person to pick, {none} with nothing in the box; "
          f"{len(closed)} kept places Google says are closed for good"
          + (f" ({', '.join(closed)})" if closed else ""))
    log("google_ids", searched=len(todo), auto=auto, left=len(left), none=none, closed=len(closed))


if __name__ == "__main__":
    main()
