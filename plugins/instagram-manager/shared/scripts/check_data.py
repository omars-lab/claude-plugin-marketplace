#!/usr/bin/env python3
"""check_data.py — the data repo's files load and fit together. Run by its `make check`.

    python3 shared/scripts/check_data.py          # checks $INSTAGRAM_HOME (default ~/Workspace/git/instagram)

Checks, each one only when its file exists:
  config/topics.yaml       a `topics:` map, each with a label
  config/collections.yaml  every topic is a known topic; every pilot names known collections;
                           with .cache/saves.json present, every collection name is in the export
                           (a typo would silently tag nothing)
  config/places.yaml       a `places:` map, each with names[] and hashtags[] lists
  data/places.yaml         every `in:` and every alias names a known place
  data/tags.yaml           code → {topics[], cities[], purposes[]?}, topics, places and purposes known,
                           codes in the export
  data/moves.yaml          codes in the export, each `to` a collection with an entry
  data/pins.yaml           no two different spots on one map point (the same OpenStreetMap thing, or
                           within about 10 m): a spot given another's pin by mistake. Names that
                           start with the name OpenStreetMap found there are one place ("Example
                           Roastery USA" at Example Roastery). Shops that really share a building (a
                           food hall, a mall) each get the same `building:` value and pass.
  (a known place is a city in collections.yaml or a key in config/ or data/places.yaml)

Prints one ev= line per problem and exits 1 if there is any.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402

from home import cache, home  # noqa: E402
from log import log  # noqa: E402
from purposes import load as load_purposes  # noqa: E402


_OVERRIDES = {}


def load(rel):
    if rel in _OVERRIDES:
        return _OVERRIDES[rel]
    path = os.path.join(home(), rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _words(name):
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def shared_spots(pins):
    """[(where, [names])]: map points that hold two or more different spots, none in a shared building."""
    groups = {}
    for spots in (pins or {}).values():
        for s in spots or []:
            if not isinstance(s, dict) or s.get("lat") is None or s.get("lon") is None:
                continue
            for where in {s.get("osm"), f"{round(float(s['lat']), 4)},{round(float(s['lon']), 4)}"} - {None}:
                groups.setdefault(where, []).append(s)
    out, seen = [], set()
    for where, spots in groups.items():
        if len({s.get("building") for s in spots}) == 1 and spots[0].get("building"):
            continue
        names = {}
        for s in spots:
            found = _words((s.get("found") or "").split(",")[0])
            own = _words(s.get("name"))
            names.setdefault(found if found and own.startswith(found) else own, s.get("name"))
        if len(names) > 1 and tuple(sorted(names.values())) not in seen:
            seen.add(tuple(sorted(names.values())))
            out.append((where, sorted(names.values())))
    return out


def problems(overrides=None, quiet=False):
    """Every problem as {ev, ...}. `overrides` maps a file ("data/tags.yaml") to data not yet
    written, so a change can be checked before it is saved; `quiet` skips the log lines."""
    _OVERRIDES.clear()
    _OVERRIDES.update(overrides or {})
    try:
        return _problems(quiet)
    finally:
        _OVERRIDES.clear()


def _problems(quiet):
    problems = []

    def bad(ev, **kv):
        problems.append({"ev": ev, **{k: str(v) for k, v in kv.items()}})
        if not quiet:
            log(ev, **kv)

    topics = load("config/topics.yaml")
    known = set()
    if topics is not None:
        if not isinstance(topics.get("topics"), dict):
            bad("check_fail", file="config/topics.yaml", msg="needs a topics: map")
        else:
            known = set(topics["topics"])
            for t, v in topics["topics"].items():
                if not isinstance(v, dict) or not v.get("label"):
                    bad("check_fail", file="config/topics.yaml", topic=t, msg="needs a label")

    exported = None
    codes = None
    if os.path.exists(cache("saves.json")):
        with open(cache("saves.json"), encoding="utf-8") as fh:
            saved = json.load(fh)
        exported = {c["name"] for c in saved["collections"]}
        codes = {s["code"] for s in saved["saves"]}

    places = load("config/places.yaml")
    places_known = set()
    if places is not None:
        if not isinstance(places.get("places"), dict):
            bad("check_fail", file="config/places.yaml", msg="needs a places: map")
        else:
            places_known = set(places["places"])
            for place, v in places["places"].items():
                if not isinstance(v, dict) or not all(isinstance(v.get(k) or [], list) for k in ("names", "hashtags")):
                    bad("check_fail", file="config/places.yaml", place=place, msg="needs names[] and hashtags[] lists")

    looked = load("data/places.yaml") or {}
    places_known |= set(looked.get("places") or {})

    cols = load("config/collections.yaml")
    mapping = {}
    if cols is not None:
        mapping = cols.get("collections") or {}
        for name, rule in mapping.items():
            if not isinstance(rule, dict):
                bad("check_fail", file="config/collections.yaml", collection=name, msg="needs {topics, cities}")
                continue
            for t in rule.get("topics") or []:
                if known and t not in known:
                    bad("check_fail", file="config/collections.yaml", collection=name, topic=t, msg="unknown topic")
            if exported is not None and name not in exported:
                bad("check_fail", file="config/collections.yaml", collection=name, msg="not a collection in the export")
            places_known |= {c for c in rule.get("cities") or []}
        for pilot, p in (cols.get("pilots") or {}).items():
            for city in p.get("cities") or []:
                if city not in places_known:
                    bad("check_fail", file="config/collections.yaml", pilot=pilot, city=city, msg="pilot names an unknown place")
            for name in p.get("collections") or []:
                if name not in mapping:
                    bad("check_fail", file="config/collections.yaml", pilot=pilot, collection=name,
                        msg="pilot names a collection with no entry above")

    for place, v in (looked.get("places") or {}).items():
        if isinstance(v, dict) and v.get("in") and v["in"] not in places_known:
            bad("check_fail", file="data/places.yaml", place=place, sits_in=v["in"], msg="sits in an unknown place")
    hand = (places or {}).get("aliases") or {}
    for said, place in {**(looked.get("aliases") or {}), **hand}.items():
        if place not in places_known:
            bad("check_fail", file="data/places.yaml", alias=said, place=place, msg="alias names an unknown place")

    tags = load("data/tags.yaml")
    purposes = load_purposes()
    if tags is not None:
        for code, t in tags.items():
            if not isinstance(t, dict):
                bad("check_fail", file="data/tags.yaml", code=code, msg="needs {topics, cities}")
                continue
            for topic in t.get("topics") or []:
                if known and topic not in known:
                    bad("check_fail", file="data/tags.yaml", code=code, topic=topic, msg="unknown topic")
            for city in t.get("cities") or []:
                if places_known and city not in places_known:
                    bad("check_fail", file="data/tags.yaml", code=code, city=city, msg="unknown place")
            if not isinstance(t.get("purposes", []), list):
                bad("check_fail", file="data/tags.yaml", code=code, msg="purposes needs to be a list")
            for p in t.get("purposes") or []:
                if p not in purposes:
                    bad("check_fail", file="data/tags.yaml", code=code, purpose=p, msg="unknown purpose")
            if codes is not None and code not in codes:
                bad("check_fail", file="data/tags.yaml", code=code, msg="not a save in the export")

    moves = load("data/moves.yaml")
    for code, m in (moves or {}).items():
        if codes is not None and code not in codes:
            bad("check_fail", file="data/moves.yaml", code=code, msg="not a save in the export")
        for name in (m or {}).get("to") or []:
            if mapping and name not in mapping:
                bad("check_fail", file="data/moves.yaml", code=code, collection=name, msg="move to a collection with no entry")

    for where, names in shared_spots(load("data/pins.yaml")):
        bad("check_fail", file="data/pins.yaml", at=where, spots="|".join(names),
            msg="different spots on one map point: fix the wrong pin, or give each the same building: if they share one")

    return problems


def check():
    found = problems()
    log("check", home=home(), problems=len(found))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(check())
