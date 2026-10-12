"""geocode.py — look a place name up on OpenStreetMap (Nominatim). No key, no login.

    from geocode import lookup, maps_link
    lookup("Example Town, Example State")
      → {"name", "kind", "state", "country", "lat", "lon", "found"} or None
    maps_link("Example Town", "Example State")   # a Google Maps search link; needs no key

kind is what the place is, in our words: city (city, town, village, hamlet), area (a part of a
city: suburb, neighbourhood), park (national park, nature reserve), region (a region, a county or
a natural place people travel to: an island, a lake, falls, a valley, a peak, a beach), state,
country, or other (a road, a building, a business).

Nominatim's first answer is often not the one meant (a famous park's name can first match a suburb of the same name abroad), so
we ask for five and take the best: a city, park, state or country first, then a region, then a
part of a city, the most important one within each (Nominatim's own importance score).

Every answer, misses included, is cached in $INSTAGRAM_HOME/.cache/geocode.json, so a name is
asked once. Nominatim's usage policy allows at most one request a second and needs a
User-Agent that names the app; we wait after every request, misses included (a run of fast
misses is what got the adventures repo an HTTP 429).

Standard library only.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from home import cache
from log import log

NOMINATIM = "https://nominatim.openstreetmap.org/search"
UA = "instagram-manager/0.4 (personal saved-posts organizer; one request a second)"
WAIT = 1.1
CITY = {"city", "town", "village", "hamlet", "municipality"}
AREA = {"suburb", "neighbourhood", "quarter", "city_district", "borough"}
PARK = {"national_park", "nature_reserve", "protected_area"}
REGION = {"region", "county", "state_district", "island", "archipelago", "lake", "waterfall", "valley",
          "peak", "volcano", "beach", "bay", "cape", "glacier"}
RANK = {"city": 0, "park": 0, "state": 0, "country": 0, "region": 1, "area": 2}

_cache, _cache_path = None, None


def _load():
    global _cache, _cache_path
    if _cache is None or _cache_path != cache("geocode.json"):  # INSTAGRAM_HOME can change (tests)
        _cache_path = cache("geocode.json")
        try:
            with open(_cache_path, encoding="utf-8") as fh:
                _cache = json.load(fh)
        except (OSError, ValueError):
            _cache = {}
    return _cache


def _save():
    path = cache("geocode.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(_cache, fh, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)


def kind_of(hit):
    at, typ, cat = hit.get("addresstype"), hit.get("type"), hit.get("category")
    if at in CITY:
        return "city"
    if at in AREA:
        return "area"
    if at == "state":
        return "state"
    if at == "country":
        return "country"
    if typ in PARK or at in PARK:
        return "park"
    if at in REGION or (cat in ("natural", "water", "waterway", "place") and typ in REGION):
        return "region"
    return "other"


def shape(hit):
    """One Nominatim hit in the shape the scripts use."""
    a = hit.get("address") or {}
    return {"name": hit.get("name") or (hit.get("display_name") or "").split(",")[0],
            "kind": kind_of(hit), "city": a.get("city") or a.get("town") or a.get("village"),
            "state": a.get("state"), "country": a.get("country"), "country_code": a.get("country_code"),
            "lat": round(float(hit["lat"]), 5), "lon": round(float(hit["lon"]), 5),
            "found": hit.get("display_name")}


def best(hits):
    """The answer most likely meant: by kind (RANK), then by Nominatim's importance."""
    if not hits:
        return None
    return min(hits, key=lambda h: (RANK.get(kind_of(h), 3), -(h.get("importance") or 0)))


def fetch(query):
    params = urllib.parse.urlencode({"q": query, "format": "jsonv2", "addressdetails": 1, "limit": 5,
                                     "accept-language": "en"})
    req = urllib.request.Request(f"{NOMINATIM}?{params}", headers={"User-Agent": UA})
    log("geocode_call", q=query)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            hits = json.load(r)
    finally:
        time.sleep(WAIT)  # after every request, misses and errors included
    log("geocode_done", q=query, hits=len(hits))
    return hits


def lookup(query, fetcher=None):
    """The best match for a place name, or None. Cached, misses too. fetcher is for tests."""
    c = _load()
    query = query.strip()
    if query in c:
        return c[query]
    try:
        hits = (fetcher or fetch)(query)
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        log("geocode_fail", q=query, msg=str(e)[:150])
        return None  # not cached: a failed call is asked again next run
    c[query] = shape(best(hits)) if hits else None
    _save()
    return c[query]


def maps_link(name, parent=None):
    q = f"{name}, {parent}" if parent else name
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote_plus(q)
