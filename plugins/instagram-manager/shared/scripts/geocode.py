"""geocode.py — look a place name up on OpenStreetMap (Nominatim). No key, no login.

    from geocode import lookup, maps_link
    lookup("Example Town, Example State")
      → {"name", "kind", "state", "country", "lat", "lon", "found"} or None
    maps_link("Example Town", "Example State")   # a Google Maps search link; needs no key
    lookup_near("Example Beach", (south, west, north, east))
      → every match inside that box: [{"name", "type", "lat", "lon", "found", "osm", "box",
        "wikidata"?}], [] for none. Nominatim's viewbox + bounded=1, so nothing outside the box
        comes back. For a spot (a beach, a café, a trailhead) near a known town or park.

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

A refusal (HTTP 429 "too many requests", or 503) is not a miss. We wait COOL seconds and ask once
more; refused again, lookup() raises Refused and the caller stops its run, so no spot is filed as
"not found" because OpenStreetMap would not answer. Nothing refused is cached. (A merge that kept
going through twelve minutes of refusals filed 269 lookups that way: docs/issues in the data repo,
"osm-refused-lookups".)

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
REFUSED = (429, 503)
COOL = 60  # seconds to wait after a refusal before asking once more
CITY = {"city", "town", "village", "hamlet", "municipality"}
AREA = {"suburb", "neighbourhood", "quarter", "city_district", "borough"}
PARK = {"national_park", "nature_reserve", "protected_area"}
REGION = {"region", "county", "state_district", "island", "archipelago", "lake", "waterfall", "valley",
          "peak", "volcano", "beach", "bay", "cape", "glacier"}
RANK = {"city": 0, "park": 0, "state": 0, "country": 0, "region": 1, "area": 2}

_cache, _cache_path = None, None


class Refused(RuntimeError):
    """OpenStreetMap refused twice in a row (HTTP 429 or 503): stop the run and try again later."""


def _ask(fetcher, arg, query):
    """fetcher(arg), asked once more after COOL seconds if OpenStreetMap refuses; refused again
    raises Refused. Any other error goes to the caller as before."""
    for attempt in (1, 2):
        try:
            return fetcher(arg)
        except urllib.error.HTTPError as e:
            if e.code not in REFUSED:
                raise
            log("geocode_refused", q=query, code=e.code, attempt=attempt)
            if attempt == 2:
                raise Refused(f"OpenStreetMap refused lookups (HTTP {e.code}). Stopped so no spot is filed as "
                              "not found; wait an hour or so, then run it again.") from e
            time.sleep(COOL)


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
        hits = _ask(fetcher or fetch, query, query)
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        log("geocode_fail", q=query, msg=str(e)[:150])
        return None  # not cached: a failed call is asked again next run
    c[query] = shape(best(hits)) if hits else None
    _save()
    return c[query]


def near_params(query, box):
    """The Nominatim query for a name searched only inside a box: box is (south, west, north, east)
    in degrees. Nominatim's viewbox is "west,north,east,south" (longitude first), and bounded=1
    keeps every answer inside it. extratags=1 brings the Wikidata id when there is one."""
    s, w, n, e = (round(float(x), 4) for x in box)
    return {"q": query.strip(), "format": "jsonv2", "addressdetails": 1, "extratags": 1, "limit": 5,
            "accept-language": "en", "viewbox": f"{w},{n},{e},{s}", "bounded": 1}


def fetch_params(params):
    """One paced request with these parameters: the same User-Agent and wait as fetch()."""
    req = urllib.request.Request(f"{NOMINATIM}?{urllib.parse.urlencode(params)}", headers={"User-Agent": UA})
    log("geocode_call", q=params.get("q"), box=params.get("viewbox"))
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            hits = json.load(r)
    finally:
        time.sleep(WAIT)  # after every request, misses and errors included
    log("geocode_done", q=params.get("q"), hits=len(hits))
    return hits


def shape_near(hit):
    """One hit from a bounded search: what it is, where, its box and its ids."""
    out = {"name": hit.get("name") or (hit.get("display_name") or "").split(",")[0],
           "type": hit.get("type"), "category": hit.get("category"),
           "lat": round(float(hit["lat"]), 5), "lon": round(float(hit["lon"]), 5),
           "found": hit.get("display_name"), "importance": hit.get("importance") or 0}
    if hit.get("osm_type") and hit.get("osm_id"):
        out["osm"] = f"{hit['osm_type']}/{hit['osm_id']}"
    if hit.get("boundingbox"):
        s, n, w, e = (round(float(x), 5) for x in hit["boundingbox"])  # Nominatim: south, north, west, east
        out["box"] = [s, w, n, e]
    wikidata = (hit.get("extratags") or {}).get("wikidata")
    if wikidata:
        out["wikidata"] = wikidata
    return out


def lookup_near(query, box, fetcher=None):
    """Every match for a name inside a box (south, west, north, east), in Nominatim's order, or [].
    Cached like lookup(), misses too, under a key that holds the box, so the same name near two
    towns is asked twice. fetcher takes the query parameters; it is for tests."""
    c = _load()
    params = near_params(query, box)
    key = f"near {params['viewbox']} {params['q']}"
    if key in c:
        return c[key]
    try:
        hits = _ask(fetcher or fetch_params, params, params["q"])
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        log("geocode_fail", q=params["q"], msg=str(e)[:150])
        return []  # not cached: a failed call is asked again next run
    c[key] = [shape_near(h) for h in hits or []]
    _save()
    return c[key]


def maps_link(name, parent=None):
    q = f"{name}, {parent}" if parent else name
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote_plus(q)
