"""places.py — the place list the scripts tag with, and which place sits inside which.

    from places import Places
    p = Places.load()                 # reads the data repo's config and data/places.yaml
    p.known                           # every place a save can be tagged with
    p.resolve("Example Town, Example State")   # the listed name, or None
    p.fold({"Example Town"})          # {"Example Town", "Example State"}: a place and what it sits in

The list comes from three files in the data repo:
  config/collections.yaml   each collection's cities
  config/places.yaml        hand-written: names and hashtags to look for; optional `in:` (the place
                            it sits in) and `lookup:` (what to ask OpenStreetMap, when the name alone
                            is ambiguous); and a top-level `aliases:` map, name → listed place,
                            for the names a lookup gets wrong ("East Example" → "Example City")
  data/places.yaml          written by add_places.py from OpenStreetMap: per place its kind, `in`,
                            lat, lon, the name OpenStreetMap found and a Google Maps link; plus
                            `aliases`, the names the agent used that mean a listed place

A tag on a place also tags every place it sits in, so a post about a city shows under its state.
A hand-written `in:` wins over the looked-up one.
"""

import os

import yaml

from home import home


def load_yaml(rel):
    path = os.path.join(home(), rel)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class Places:
    def __init__(self, collections=None, config=None, data=None, aliases=None):
        collections, config, data = collections or {}, config or {}, data or {}
        looked_up = data.get("places") or {}
        self.config, self.data = config, looked_up
        self.known = ({c for rule in collections.values() for c in (rule or {}).get("cities") or []}
                      | set(config) | set(looked_up))
        self.parent = {k: v["in"] for k, v in looked_up.items() if isinstance(v, dict) and v.get("in")}
        self.parent.update({k: v["in"] for k, v in config.items() if isinstance(v, dict) and v.get("in")})
        self.aliases = {**(data.get("aliases") or {}), **(aliases or {})}  # hand-written ones win
        self._lower = {k.lower(): k for k in self.known}

    @classmethod
    def load(cls):
        coll = load_yaml(os.path.join("config", "collections.yaml")).get("collections") or {}
        config = load_yaml(os.path.join("config", "places.yaml"))
        return cls(coll, config.get("places") or {}, load_yaml(os.path.join("data", "places.yaml")),
                   config.get("aliases") or {})

    def resolve(self, name):
        """The listed place a name means, or None."""
        if not isinstance(name, str):
            return None
        if name in self.known:
            return name
        if name in self.aliases and self.aliases[name] in self.known:
            return self.aliases[name]
        found = self._lower.get(name.strip().lower())
        if not found and "," in name:  # "Example Town, Example State": the town, if it is listed
            found = self.resolve(name.split(",")[0])
        return found

    def chain(self, place):
        """The places this one sits in, nearest first."""
        out, seen = [], {place}
        while place in self.parent and self.parent[place] not in seen:
            place = self.parent[place]
            seen.add(place)
            if place in self.known:
                out.append(place)
        return out

    def fold(self, places):
        return set(places) | {p for x in places for p in self.chain(x)}

    def depth(self, place):
        return len(self.chain(place))

    def listing(self):
        """name → the place it sits in ("" for none): what the agent is shown."""
        return {k: (self.chain(k) or [""])[0] for k in sorted(self.known)}
