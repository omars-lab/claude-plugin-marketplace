"""google_places.py — Google's own place for a spot, found by search and kept only as its place id.

Shared by find-google-ids (which searches and keeps ids) and build-hub and send-topics (which put a
kept id into each spot's Google Maps link). Google's terms allow keeping a place id for good, and
keeping nothing else of Google's: no name, no address, no position, no distance worked out from them
(the reading this follows was agreed for a sister project, in its docs/research/google-terms/options.md).

  - One Text Search per spot, limited to a box (`locationRestriction`): round our own pin from
    OpenStreetMap, or round the spot's town when OpenStreetMap had no pin for it. Google's own
    coordinates are never asked for.
  - It asks for the top 3 with id, name, address, kind and whether the place is open
    (`businessStatus`). That is "Text Search Pro": 5,000 free a month, then $32 per 1,000
    (Google's price list, read 2026-10-12; businessStatus is on the same tier, read 2026-10-14).
  - Names, addresses, kinds and "closed for good" go to the screen only, never to a file. Only the
    place id is kept, with our own search text, the date and who chose it.

The key comes from GOOGLE_MAPS_API_KEY in the environment (dotenvx run decrypts it into the one
process it starts) and is never printed.
"""

import json
import math
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from urllib.parse import urlencode

SEARCH = "https://places.googleapis.com/v1/places:searchText"
DETAILS = "https://places.googleapis.com/v1/places/"
TIMEOUT_S = 15
CANDIDATE_FIELDS = ("places.id,places.displayName,places.formattedAddress,places.types,"
                    "places.businessStatus")   # Text Search Pro
ID_FIELDS = "id,movedPlaceId"                  # Place Details Essentials (IDs Only): $0, no limit
CANDIDATES = 3
BOX_KM = 2.0            # half the box's width round our own pin
TOWN_BOX_KM = {"city": 8.0, "park": 20.0, "region": 30.0, "other": 10.0}   # round the town, no pin
KM_PER_DEG = 111.32
SHOW_KINDS = 3
CLOSED = "CLOSED_PERMANENTLY"
# Google results that are an area or a stop, not a place to go: a neighbourhood or town named like
# the spot ("Pebble Beach" the beach, and Pebble Beach the neighbourhood), or its bus stop.
NOT_A_PLACE = {"political", "colloquial_area", "neighborhood", "locality", "sublocality",
               "transit_station", "bus_stop"}
RETRY_STATUS = (429, 500, 502, 503, 504)
ATTEMPTS = 6            # waits 1, 2, 4, 8, 16 s
CAP_S = 30.0


def api_key():
    """The key, or "" when it is missing or still encrypted. Never printed."""
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    return "" if key.startswith("encrypted:") else key


# ---- calling Google, with growing waits ----

def error_text(e):
    if not hasattr(e, "_text"):
        try:
            e._text = e.read().decode(errors="replace")
        except Exception:  # noqa: BLE001 — a body we cannot read is just empty
            e._text = ""
    return e._text


def daily_cap(e):
    """A 429 that is the day's cap: no short wait clears it, so the run stops."""
    return getattr(e, "code", None) == 429 and "per day" in error_text(e).lower()


def with_backoff(call, attempts=ATTEMPTS, sleep=time.sleep, on_retry=None):
    """call() until it works, waiting 1, 2, 4 … s after a 429, a 5xx or no answer. Other errors,
    and a daily cap, are raised at once."""
    delay = 1.0
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_STATUS or daily_cap(e) or attempt == attempts:
                raise
            why = f"http_{e.code}"
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == attempts:
                raise
            why = type(e).__name__
        if on_retry:
            on_retry(attempt, delay, why)
        sleep(delay)
        delay = min(delay * 2, CAP_S)


def call(method, url, body, fields, key, on_retry=None, sleep=time.sleep):
    """One call, the key in a header (never in the URL, so it never reaches a log)."""
    def once():
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                     method=method, headers={"Content-Type": "application/json",
                                                             "X-Goog-FieldMask": fields, "X-Goog-Api-Key": key})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.load(r)
    return with_backoff(once, on_retry=on_retry, sleep=sleep)


def search(query, pin, half_km, key, on_retry=None):
    return candidates(call("POST", SEARCH, search_body(query, pin, half_km), CANDIDATE_FIELDS, key, on_retry))


def current_id(place_id, key, on_retry=None):
    """The id Google uses now for this place (free call), or raises on an id Google does not know."""
    got = call("GET", DETAILS + place_id, None, ID_FIELDS, key, on_retry)
    return got.get("movedPlaceId") or got.get("id") or place_id


# ---- the search ----

def box(pin, half_km=BOX_KM):
    """The rectangle for `locationRestriction`, half_km from the pin to each edge. pin: {lat, lon}."""
    dlat = half_km / KM_PER_DEG
    dlon = half_km / (KM_PER_DEG * max(math.cos(math.radians(pin["lat"])), 0.01))
    return {"rectangle": {"low": {"latitude": pin["lat"] - dlat, "longitude": pin["lon"] - dlon},
                          "high": {"latitude": pin["lat"] + dlat, "longitude": pin["lon"] + dlon}}}


def search_body(query, pin, half_km=BOX_KM):
    return {"textQuery": query, "pageSize": CANDIDATES, "locationRestriction": box(pin, half_km)}


def candidates(response):
    """[{id, name, address, types, closed}] in Google's order. For the screen only."""
    return [{"id": g["id"], "name": (g.get("displayName") or {}).get("text", ""),
             "address": g.get("formattedAddress", ""), "types": list(g.get("types") or []),
             "closed": g.get("businessStatus") == CLOSED}
            for g in (response or {}).get("places") or [] if g.get("id")]


# ---- deciding without a person: our name, word for word ----

def plain(w):
    """One word with a plural s dropped, so "Falls" and "Fall" are the same word."""
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def words(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ").replace("'", "").replace("’", "")
    return [plain(w) for w in re.split(r"[^a-z0-9]+", s) if w and w != "the"]


def same_name(ours, theirs):
    """Every word of our name is in Google's ("Example Tacos" → "Example Tacos Downtown"), and our
    name says enough to tell one place from another: two words, or one of five letters or more."""
    mine = words(ours)
    if not mine or (len(mine) == 1 and len(mine[0]) < 5):
        return False
    return set(mine) <= set(words(theirs))


def house_number(address):
    """The house number a street address starts with ("2148 Example Dr" → "2148", "71-100 Example
    Hwy" → "71100"), or None."""
    m = re.match(r"\s*(\d+(?:-\d+)?[a-z]?)\b", address or "", re.I)
    return m.group(1).replace("-", "").lower() if m else None


def at_the_house(number, theirs):
    """Google's address carries our house number as a word of its own, a hyphen inside a number
    ignored. Compared in memory only."""
    theirs = re.sub(r"(?<=\d)-(?=\d)", "", theirs or "")
    return bool(re.search(rf"(?<![\w-]){re.escape(number)}(?![\w-])", theirs, re.I))


def auto_pick(ours, found, address=None):
    """The one candidate whose name is ours, or None when none or more than one is. When several
    carry the name, areas and stops of that name are set aside first (NOT_A_PLACE). When the
    caption gives a street address with a house number, only a candidate at that number counts:
    a chain's other branch carries the name too, but not the address."""
    hits = [c for c in found if same_name(ours, c["name"])]
    number = house_number(address)
    if number:
        hits = [c for c in hits if at_the_house(number, c.get("address"))]
    if len(hits) > 1:
        hits = [c for c in hits if not NOT_A_PLACE & set(c["types"])]
    return hits[0] if len(hits) == 1 else None


# ---- what is kept, and how a spot finds it again ----

def slug(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def spot_key(e):
    """The spot's key in data/google.yaml: its OpenStreetMap id, or its name at its area."""
    if isinstance(e.get("osm"), str) and e["osm"].strip():
        return "osm:" + e["osm"].strip()
    return f"spot:{slug(e.get('name'))}@{slug(e.get('near'))}"


def query_for(e):
    """Our own search text: the spot's name and its street address or area, as on its search link."""
    where = e.get("address") if isinstance(e.get("address"), str) and e["address"].strip() else e.get("near")
    name = (e.get("name") or "").strip()
    return f"{name}, {where.strip()}" if isinstance(where, str) and where.strip() else name


def maps_link(query, place_id):
    """A Google Maps link that opens this exact place: our search text plus the id."""
    return "https://www.google.com/maps/search/?" + urlencode(
        {"api": "1", "query": query, "query_place_id": place_id})


def kept(google, e):
    """The kept entry for this spot, when it is a match for the same search text."""
    g = (google or {}).get(spot_key(e))
    if isinstance(g, dict) and g.get("verdict") == "match" and isinstance(g.get("id"), str) \
            and g.get("query") == query_for(e):
        return g
    return None


def is_chain(google, e):
    """True when a person said this spot is a chain, for the same search text: any branch will do."""
    g = (google or {}).get(spot_key(e))
    return isinstance(g, dict) and g.get("verdict") == "chain" and g.get("query") == query_for(e)


def apply(pins, google):
    """Put each kept id into its spot's Google Maps link, in place. pins: code → [spot]. A chain keeps
    its search link, which shows every branch, and is marked `google_chain`."""
    n = 0
    for spots in (pins or {}).values():
        for e in spots if isinstance(spots, list) else []:
            if isinstance(e, dict) and isinstance(e.get("name"), str) and is_chain(google, e):
                e["google_chain"] = True
                continue
            g = kept(google, e) if isinstance(e, dict) and isinstance(e.get("name"), str) else None
            if g:
                e["map"] = maps_link(g["query"], g["id"])
                by = g.get("by") or "hand"
                e["google_id"], e["google_by"] = g["id"], "auto-address" if by == "auto" and g.get("at_address") else by
                n += 1
    return n


def show(key, query, found, where, kept_id=None):
    """The lines a person reads and picks from. Printed, never written."""
    out = [f"{key}: {query!r}, {where}"]
    if not found:
        out.append("  nothing in the box. Try a wider box (--box-km, GOOGLE_BOX= in make) or put a better name in the data.")
    for n, c in enumerate(found, 1):
        kinds = ", ".join(c["types"][:SHOW_KINDS])
        mark = "  <- kept" if c["id"] == kept_id else ""
        out += [f"  {n}. {c['name']} — {c['address']}" + (f" ({kinds})" if kinds else "")
                + ("  CLOSED FOR GOOD" if c["closed"] else "") + mark,
                f"     {maps_link(query, c['id'])}",
                f"     to keep it: PICK='{key}={c['id']}'"]
    return out
