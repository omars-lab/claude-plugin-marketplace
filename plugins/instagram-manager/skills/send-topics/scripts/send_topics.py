#!/usr/bin/env python3
"""send_topics.py — the files other repos read: one per topic, and for travel one per state or
country, so a trip planner reads only the area it plans. Each repo's own intake takes what it wants
from them. No model is called and nothing is fetched.

    send_topics.py --pilot NAME   the pilot's saves; travel only for the pilot's own areas. A file
                                  another pilot already wrote keeps that pilot's saves: only this
                                  pilot's are replaced, so pilots add up instead of wiping each other
    send_topics.py --all          every tagged save; files no longer written are removed

Reads   $INSTAGRAM_HOME/.cache/saves.json          link, creator, date saved
        $INSTAGRAM_HOME/config/topics.yaml         the topics, and which repos each feeds
        $INSTAGRAM_HOME/config/collections.yaml    the pilots
        $INSTAGRAM_HOME/data/tags.yaml             each save's topics, places and purposes
        $INSTAGRAM_HOME/data/places.yaml           which place sits in which
        $INSTAGRAM_HOME/data/pins.yaml             the spots each save names
        $INSTAGRAM_HOME/data/pins-review.yaml      spots OpenStreetMap did not list (optional)
        $INSTAGRAM_HOME/data/media.yaml            each save's thumbnail (optional)
        $INSTAGRAM_HOME/data/stills.yaml           a still and a clip per spot (optional)
Writes  $INSTAGRAM_HOME/out/travel/<area>.yaml     the travel saves naming a place in that state or
                                                   country, each with its spots there
        $INSTAGRAM_HOME/out/<topic>.yaml           every other topic's saves (items come later, from
                                                   a splitter; for now each save's `items` is empty)

What a save carries
  code, url, creator, saved_at, kind, topics, purposes, the places it is tagged with (the most exact
  ones), its thumbnail, `also_in` (its other topics and travel areas) and `items`. For travel the
  items are its spots: the caption's words for each (`said`), the place it sits in, OpenStreetMap's
  kind, id and lat/lon, a Google Maps link, and its still and clip when it has them. A spot
  OpenStreetMap does not list (many small restaurants) still comes, with `exact: false`, no lat/lon,
  and a map link that searches its name in its town; that is the same set of spots the hub shows.
  No caption goes in: only the short quotes the data repo already keeps.

Travel means tagged `travel`. A save that names a place but is tagged only with another topic (a
recipe post naming four cafés) is left out of the travel files and named in the log
(`ev=send_place_not_travel`), so a person can add `travel` to its tags.

Media paths (thumb, still, clip) are relative to $INSTAGRAM_MEDIA_DIR, a folder outside git; an
intake copies the files it uses. Saves come sorted by code and keys in a fixed order, so a rerun on
the same data writes the same bytes.
"""

import argparse
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.join(HERE, os.pardir, os.pardir)
sys.path.insert(0, os.path.join(SKILLS, os.pardir, "shared", "scripts"))
sys.path.insert(0, os.path.join(SKILLS, "build-hub", "scripts"))
import build_hub as bh  # noqa: E402
import google_places as gp  # noqa: E402
from home import cache, home  # noqa: E402
from log import log  # noqa: E402
from pilot import in_pilot  # noqa: E402
from places import Places, load_yaml  # noqa: E402

HEADER = ("# Written by instagram-manager's send-topics from the data repo. The next run rewrites it, so\n"
          "# fix the data, not this file. thumb, still and clip are paths inside $INSTAGRAM_MEDIA_DIR.\n")
SHOWN = {"on_screen", "area", "hand"}   # stills.yaml `how` values that come with a still


def top(places, name):
    """The state or country a place sits in: the last place up its chain, or itself."""
    chain = places.chain(name)
    return chain[-1] if chain else name


def text(v):
    return v.strip() if isinstance(v, str) and v.strip() else None


def item(e, still):
    """One spot, keys in a fixed order, empty ones left out."""
    exact = not e.get("placed")
    out = {"name": e["name"].strip(), "said": text(e.get("said")), "near": e.get("near"),
           "kind": text(e.get("kind")), "lat": bh.number(e.get("lat")) if exact else None,
           "lon": bh.number(e.get("lon")) if exact else None, "osm": text(e.get("osm")),
           "wikidata": text(e.get("wikidata")),
           "map": text(e.get("map")) or bh.maps_link(e["name"].strip(), e.get("near") or ""),
           "google_id": text(e.get("google_id")),
           "from": "video" if e.get("from") == "video" else "caption", "exact": exact}
    if still:
        out.update({"still": still["still"], "clip": text(still.get("clip")), "t": bh.number(still.get("t")),
                    "still_from": "area" if still.get("how") == "area" else "name"})
        if still.get("how") == "area":
            out["area"] = text(still.get("area"))
    return {k: v for k, v in out.items() if v is not None}


class Sender:
    def __init__(self, saves, tags, places, pins, placed, media, stills, topics):
        self.places, self.topics = places, topics or {}
        self.files = {}          # out path → {"topic", "area", "saves": {code: entry}}
        self.not_travel, self.no_place, self.lost = [], [], []
        for t in self.topics:   # every topic gets its file, even with no saves yet
            if t != "travel":
                self.files[t + ".yaml"] = {"topic": t, "area": None, "saves": {}}
        for s in saves:
            tag = tags.get(s["code"])
            if isinstance(tag, dict) and tag.get("topics"):
                self._add(s, tag, (pins.get(s["code"]) or []) + placed.get(s["code"], []),
                          media.get(s["code"]), stills.get(s["code"]))

    def _areas(self, tag):
        areas = []
        for c in tag.get("cities") or []:
            name = self.places.resolve(c) or c
            if isinstance(name, str) and name not in areas:
                areas.append(name)
        return areas

    def _add(self, s, tag, spots, media, stills):
        code = s["code"]
        topics = [t for t in tag["topics"] if isinstance(t, str)]
        areas = self._areas(tag)
        cut = {r["name"].strip().lower(): r for r in stills or [] if isinstance(r, dict)
               and isinstance(r.get("name"), str) and isinstance(r.get("still"), str) and r.get("how") in SHOWN}
        items = []
        for e in spots:
            if not isinstance(e, dict) or not text(e.get("name")):
                continue
            listed = self.places.resolve(e.get("near"))
            items.append((top(self.places, listed) if listed else None,
                          item({**e, "near": listed or text(e.get("near"))}, cut.get(e["name"].strip().lower()))))
        tops = []
        for t in [top(self.places, a) for a in areas] + [t for t, _ in items if t]:
            if t not in tops:
                tops.append(t)
        thumb = text((media or {}).get("thumb")) if isinstance(media, dict) else None
        owner = s.get("owner") or {}
        base = {"code": code, "url": s.get("url") or f"https://www.instagram.com/p/{code}/",
                "creator": owner.get("username") or None, "saved_at": s.get("saved_at") or None,
                "kind": s.get("kind") or None, "topics": topics,
                "purposes": [p for p in tag.get("purposes") or [] if isinstance(p, str)] or None}
        travel_in = [f"travel/{bh.slugify(t)}" for t in tops] if "travel" in topics else []
        if "travel" in topics:
            if not tops:
                self.no_place.append(code)
            if len(tops) > 1:
                self.lost += [(code, i["name"]) for at, i in items if at is None]
            for t in tops:
                mine = [a for a in areas if top(self.places, a) == t]
                # a spot whose area is not on the place list goes with the post's one area, if it has one
                spots_here = [i for at, i in items if at == t or (at is None and len(tops) == 1)]
                also = [x for x in topics if x != "travel"] + [x for x in travel_in if x != f"travel/{bh.slugify(t)}"]
                self._put(os.path.join("travel", bh.slugify(t) + ".yaml"), "travel", t, code,
                          {**base, "places": self._exact(mine) or None, "thumb": thumb, "also_in": also or None,
                           "items": spots_here})
        elif areas or items:
            self.not_travel.append(code)
        for t in topics:
            if t == "travel":
                continue
            # its travel area files, or plain `travel` when it names no place yet
            also = [x for x in topics if x not in (t, "travel")] + (travel_in or [x for x in topics if x == "travel"])
            self._put(t + ".yaml", t, None, code,
                      {**base, "places": self._exact(areas) or None, "thumb": thumb, "also_in": also or None,
                       "items": []})

    def _exact(self, areas):
        """The places no other of them sits inside: a town, not its state."""
        inside = {up for a in areas for up in self.places.chain(a)}
        return [a for a in areas if a not in inside]

    def _put(self, rel, topic, area, code, entry):
        f = self.files.setdefault(rel, {"topic": topic, "area": area, "saves": {}})
        f["saves"][code] = {k: v for k, v in entry.items() if v is not None}

    def document(self, rel, scope):
        f = self.files[rel]
        conf = self.topics.get(f["topic"]) if isinstance(self.topics.get(f["topic"]), dict) else {}
        doc = {"topic": f["topic"]}
        if f["area"]:
            doc["area"] = f["area"]
        doc.update({"feeds": list(conf.get("feeds") or []), "scope": scope, "count": len(f["saves"]),
                    "saves": [f["saves"][c] for c in sorted(f["saves"])]})
        return HEADER + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=10_000)


PILOTS = re.compile(r"^pilots? ([^:]+):")


def merge_old(sender, path, rel, ours, pilot):
    """A pilot run keeps what an earlier run wrote for the saves outside this pilot, and returns the
    scope line naming every pilot now in the file. A save of this pilot that left the file stays out."""
    names = [pilot]
    try:
        with open(path, encoding="utf-8") as fh:
            old = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError):
        return names
    m = PILOTS.match(str(old.get("scope") or ""))
    if not m and old.get("saves"):
        return None                       # an --all file: every save is in it, nothing to add up
    names = sorted(set(names) | {n.strip() for n in (m.group(1).split(",") if m else [])})
    f = sender.files[rel]
    for e in old.get("saves") or []:
        if isinstance(e, dict) and e.get("code") and e["code"] not in ours:
            f["saves"].setdefault(e["code"], e)
    return names


def pilot_scope(names):
    who = f"pilot {names[0]}" if len(names) == 1 else "pilots " + ", ".join(names)
    return (f"{who}: only {'its' if len(names) == 1 else 'their'} saves are here; the rest are not tagged yet, and the other travel areas "
            "named in also_in are not written yet")


def write_all(sender, out_dir, keep, scope, prune, ours=None, pilot=None):
    written = []
    for rel in sorted(sender.files):
        if not keep(rel):
            continue
        path = os.path.join(out_dir, rel)
        if pilot is not None:
            names = merge_old(sender, path, rel, ours, pilot)
            if names is None:
                log("send_kept_full_file", file=rel, msg="written by --all; a pilot run leaves it alone")
                continue
            scope = pilot_scope(names)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(sender.document(rel, scope))
        written.append(rel)
    removed = []
    if prune:
        for folder in (out_dir, os.path.join(out_dir, "travel")):
            for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
                rel = os.path.relpath(os.path.join(folder, name), out_dir)
                if name.endswith(".yaml") and rel not in written:
                    os.remove(os.path.join(folder, name))
                    removed.append(rel)
    return written, removed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    which = ap.add_mutually_exclusive_group(required=True)
    which.add_argument("--pilot")
    which.add_argument("--all", action="store_true")
    ap.add_argument("--out", help="where to write (default $INSTAGRAM_HOME/out)")
    args = ap.parse_args(argv)

    saves_path = cache("saves.json")
    if not os.path.exists(saves_path):
        sys.exit(f"send_topics: no {saves_path}; run import-saves first")
    places = Places.load()
    tags = load_yaml(os.path.join("data", "tags.yaml"))
    pilot = None
    if args.pilot:
        pilot = (load_yaml(os.path.join("config", "collections.yaml")).get("pilots") or {}).get(args.pilot)
        if not isinstance(pilot, dict):
            sys.exit(f"send_topics: no pilot {args.pilot!r} in config/collections.yaml")
    saves = [s for s in bh.load_saves(saves_path) if in_pilot(s, tags.get(s["code"]), pilot)]
    stills = load_yaml(os.path.join("data", "stills.yaml"))
    pins = load_yaml(os.path.join("data", "pins.yaml"))
    placed = bh.placed_spots(load_yaml(os.path.join("data", "pins-review.yaml")))
    google = load_yaml(os.path.join("data", "google.yaml"))
    gp.apply(pins, google)     # a kept Google place id: the map link opens that exact place
    gp.apply(placed, google)
    sender = Sender(saves, tags, places, pins, placed,
                    load_yaml(os.path.join("data", "media.yaml")), stills,
                    load_yaml(os.path.join("config", "topics.yaml")).get("topics") or {})

    if pilot is not None:
        mine = {bh.slugify(top(places, places.resolve(c) or c)) for c in pilot.get("cities") or []}
        scope = pilot_scope([args.pilot])

        def keep(rel):
            return not rel.startswith("travel/") or os.path.splitext(os.path.basename(rel))[0] in mine
    else:
        scope = "every tagged save"

        def keep(rel):
            return True
    out_dir = os.path.abspath(args.out or os.path.join(home(), "out"))
    written, removed = write_all(sender, out_dir, keep, scope, prune=pilot is None,
                                 ours={s["code"] for s in saves}, pilot=args.pilot)

    for code in sender.not_travel:
        log("send_place_not_travel", code=code, msg="names a place but is not tagged travel")
    for code in sender.no_place:
        log("send_travel_no_place", code=code, msg="tagged travel but names no place")
    for code, name in sender.lost:
        log("send_spot_no_area", code=code, spot=name, msg="its near is not on the place list and the post spans areas")
    parts = []
    for rel in written:
        f = sender.files[rel]
        n_items = sum(len(e.get("items") or []) for e in f["saves"].values())
        n_still = sum(1 for e in f["saves"].values() for i in e.get("items") or [] if i.get("still"))
        log("send", file=rel, saves=len(f["saves"]), items=n_items, stills=n_still)
        parts.append(f"{os.path.splitext(rel)[0]} {len(f['saves'])} saves"
                     + (f", {n_items} spots ({n_still} with a still)" if f["topic"] == "travel" else ""))
    print(f"wrote {len(written)} files in {out_dir}: " + "; ".join(parts))
    if removed:
        print(f"removed {len(removed)} no longer written: {', '.join(removed)}")
    if sender.not_travel:
        print(f"{len(sender.not_travel)} saves name a place but are not tagged travel, so no travel file has "
              f"them (codes in the log, ev=send_place_not_travel)")
    if sender.no_place:
        print(f"{len(sender.no_place)} travel saves name no place yet (ev=send_travel_no_place)")


if __name__ == "__main__":
    main()
