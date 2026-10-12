#!/usr/bin/env python3
"""add_places.py — look places up on OpenStreetMap and add the missing ones to the place list.

    add_places.py              look up every listed place not looked up yet, and every place the
                               agent suggested (other_places in data/tags-review.yaml); add the
                               cities, parks, regions, states and countries to data/places.yaml
    add_places.py --dry-run    print the table, write nothing
    add_places.py --listed     only the listed places, not the agent's suggestions

What it writes, per place, in $INSTAGRAM_HOME/data/places.yaml:
    kind   city, park, region (a region, county, lake, falls, valley), state, country
    in     the place it sits in: a US city's state, any other city's country
    lat, lon, found (the name OpenStreetMap matched), map (a Google Maps link; needs no key)
and `aliases`: a name the agent used → the listed place it means ("Example Peak" → "Example Peak
National Park", "West Example City" → "Example City"). The place a new one sits in is added too, so the chain is whole.

What it leaves in review: a road, a venue or a region OpenStreetMap does not know as a city, park,
state or country ("Example Highway"), and names it cannot find. Run `tag_saves.py --merge` after it: the
merge moves every suggestion that now has a listed place out of review and into the tags.

Every lookup is a guess until someone looks at it (the adventures repo once had three spots land
on one town centre). Read the printed table. To fix a wrong match: for a listed place, add
`lookup: "Name, State"` or `in:` to it in config/places.yaml; for a name the agent used, add it to
the `aliases:` map there (name → listed place). Delete the place from data/places.yaml and run
again.
"""

import argparse
import collections as co
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, os.pardir, "shared", "scripts"))

import geocode  # noqa: E402
from log import log  # noqa: E402
from places import Places, load_yaml  # noqa: E402
from tag_saves import REVIEW, write_yaml  # noqa: E402

DATA = os.path.join("data", "places.yaml")
TAKE = {"city", "park", "region", "state", "country"}


def parent_of(hit):
    """The place a looked-up place sits in: a US city's state, any other place's country."""
    if hit["kind"] == "country":
        return None
    if hit["kind"] == "state":
        return None if hit.get("country_code") == "us" else hit.get("country")
    if hit.get("country_code") == "us" and hit.get("state"):
        return hit["state"]
    return hit.get("country")


class Adder:
    def __init__(self, places, data, fetcher=None):
        self.p, self.fetcher = places, fetcher
        self.places = dict(data.get("places") or {})
        self.aliases = dict(data.get("aliases") or {})
        self.rows = []

    def look(self, query):
        return geocode.lookup(query, self.fetcher)

    def known(self, name):
        return name in self.p.known or name in self.places

    def add(self, key, hit, parent=None):
        """Write one place, and the place it sits in if that is new."""
        parent = parent if parent is not None else parent_of(hit)
        if parent == key:
            parent = None
        e = {"kind": hit["kind"], "lat": hit["lat"], "lon": hit["lon"], "found": hit["found"],
             "map": geocode.maps_link(key, parent)}
        if parent:
            e["in"] = parent
            if not self.known(parent):
                where = hit.get("country") if parent != hit.get("country") else None
                up = self.look(f"{parent}, {where}" if where else parent)
                if up and up["kind"] in ("state", "country"):
                    self.add(parent, up)
                    self.rows.append((parent, 0, up, parent))
                else:
                    self.places[parent] = {"kind": "country" if parent == hit.get("country") else "state",
                                           "map": geocode.maps_link(parent)}
        self.places[key] = e

    def listed(self):
        """Every listed place gets its map entry; cities and parks get the place they sit in."""
        for name in sorted(self.p.known):
            if name in self.places:
                continue
            cfg = self.p.config.get(name) or {}
            hit = self.look(cfg.get("lookup") or name)
            if not hit:
                self.rows.append((name, 0, None, "not found"))
                continue
            self.add(name, hit, cfg.get("in"))
            self.rows.append((name, 0, hit, name))

    def suggestion(self, said, count):
        if self.p.resolve(said) or said in self.aliases or said in self.p.aliases:
            return
        hit = self.look(said)
        if not hit:
            self.rows.append((said, count, None, "not found"))
            return
        key, kind = hit["name"], hit["kind"]
        if kind == "area" and hit.get("city"):  # a part of a city counts as the city
            key = hit["city"]
            if not (self.p.resolve(key) or key in self.places):
                city = self.look(f"{key}, {hit.get('state') or hit.get('country')}")
                if not city or city["kind"] != "city":
                    self.rows.append((said, count, hit, "left in review"))
                    return
                self.add(key, city)
        elif kind not in TAKE:
            self.rows.append((said, count, hit, "left in review"))
            return
        else:
            have = self.p.resolve(key) or (key if key in self.places else None)
            if not have:
                self.add(key, hit)
            key = have or key
        if said != key:
            self.aliases[said] = key
        self.rows.append((said, count, hit, key))

    def table(self):
        print("| asked | saves | OpenStreetMap found | kind | listed as | sits in |")
        print("|---|---|---|---|---|---|")
        for said, n, hit, result in self.rows:
            found = (hit or {}).get("found") or "-"
            sits = (self.places.get(result) or {}).get("in", "") if result in self.places else ""
            print(f"| {said} | {n or ''} | {found[:70]} | {(hit or {}).get('kind', '-')} | {result} | {sits} |")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print the table, write nothing")
    ap.add_argument("--listed", action="store_true", help="only the listed places, not the agent's suggestions")
    args = ap.parse_args(argv)

    data = load_yaml(DATA)
    adder = Adder(Places.load(), data)
    adder.listed()
    if not args.listed:
        said = co.Counter(p for r in load_yaml(REVIEW).values() if isinstance(r, dict)
                          for p in r.get("other_places") or [])
        for name, n in said.most_common():
            adder.suggestion(name, n)
    adder.table()
    added = len(adder.places) - len(data.get("places") or {})
    log("places_add", added=added, aliases=len(adder.aliases), asked=len(adder.rows), dry_run=args.dry_run)
    if not args.dry_run:
        write_yaml(DATA, {"places": adder.places, "aliases": adder.aliases})
    print(f"\n{added} places added, {len(adder.aliases)} names mapped to a listed place"
          f"{' (dry run: nothing written)' if args.dry_run else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
