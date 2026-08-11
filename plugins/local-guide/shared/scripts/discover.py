#!/usr/bin/env python3
"""discover.py — find businesses near a location and detect new-opening signals
from free, no-API-key public data.

Data sources (all free, no key required):
  * Nominatim (OpenStreetMap)  — geocode an address/place to lat/lon.
  * Overpass API (OpenStreetMap) — what businesses physically exist near a point.
  * Socrata Open Data (data.<city>.gov, data.<state>.gov, …) — building permits,
    business licenses, and other "filed to open" records that most US
    cities/counties/states publish. This is the key "did they file?" signal.

Design notes:
  * Standard library only (urllib, json, argparse). No pip installs.
  * Every network call sets a descriptive User-Agent (Nominatim/Overpass require it)
    and honors rate limits with a small sleep.
  * Output is JSON by default (pipe to jq) or a readable table with --table.

Usage examples:
  discover.py geocode "1600 Amphitheatre Pkwy, Mountain View, CA"
  discover.py nearby --address "Ferry Building, San Francisco" --radius 400 --table
  discover.py nearby --lat 37.7955 --lon -122.3937 --category food
  discover.py socrata-search --domain data.sfgov.org --query "coffee" --limit 20
  discover.py permits --domain data.sfgov.org --dataset i98e-djp9 \
      --address-col street_name --near "Valencia St" --since 2024-01-01
  discover.py catalog --domain data.sfgov.org --query "building permits"
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

UA = "claude-discover-places-skill/1.0 (+https://claude.com/claude-code)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = "https://overpass-api.de/api/interpreter"

# OSM tag filters for "nearby" categories. Each maps to Overpass tag selectors.
CATEGORIES = {
    "food": ['amenity~"restaurant|cafe|fast_food|bar|pub|food_court|ice_cream"'],
    "retail": ['shop'],
    "services": ['office', 'amenity~"bank|pharmacy|clinic|dentist|veterinary"'],
    "all": ['shop', 'amenity~"restaurant|cafe|fast_food|bar|pub|bank|pharmacy|'
            'cinema|clinic|dentist|marketplace|fuel|car_rental"', 'office'],
}


def _get(url, headers=None, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _post(url, data, headers=None, timeout=90):
    body = data.encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"User-Agent": UA, **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _die(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------- geocode ----

def geocode(query):
    """Address/place string -> {lat, lon, display_name} via Nominatim."""
    params = urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": 1, "addressdetails": 1}
    )
    try:
        raw = _get(f"{NOMINATIM}?{params}")
    except (HTTPError, URLError) as e:
        _die(f"geocode request failed: {e}")
    hits = json.loads(raw)
    if not hits:
        _die(f"no geocode result for {query!r}")
    h = hits[0]
    time.sleep(1)  # Nominatim usage policy: max 1 req/sec
    return {
        "query": query,
        "lat": float(h["lat"]),
        "lon": float(h["lon"]),
        "display_name": h.get("display_name"),
        "osm_type": h.get("osm_type"),
        "osm_id": h.get("osm_id"),
    }


def _resolve_point(args):
    """Return (lat, lon, label) from --lat/--lon or --address."""
    if args.lat is not None and args.lon is not None:
        return args.lat, args.lon, f"{args.lat},{args.lon}"
    if args.address:
        g = geocode(args.address)
        return g["lat"], g["lon"], g["display_name"]
    _die("provide either --lat/--lon or --address")


# ----------------------------------------------------------------- nearby ----

def overpass_nearby(lat, lon, radius, category):
    selectors = CATEGORIES.get(category, CATEGORIES["all"])
    clauses = []
    for sel in selectors:
        for kind in ("node", "way"):
            clauses.append(f'{kind}(around:{radius},{lat},{lon})[{sel}];')
    query = f"[out:json][timeout:60];({''.join(clauses)});out center tags 200;"
    try:
        raw = _post(OVERPASS, urllib.parse.urlencode({"data": query}),
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    except (HTTPError, URLError) as e:
        _die(f"overpass request failed: {e}")
    data = json.loads(raw)
    out = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        plat = el.get("lat") or (el.get("center") or {}).get("lat")
        plon = el.get("lon") or (el.get("center") or {}).get("lon")
        out.append({
            "name": name,
            "type": tags.get("shop") or tags.get("amenity") or tags.get("office"),
            "brand": tags.get("brand"),
            "address": _osm_addr(tags),
            "website": tags.get("website") or tags.get("contact:website"),
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "opening_hours": tags.get("opening_hours"),
            "lat": plat,
            "lon": plon,
            "osm": f'{el.get("type")}/{el.get("id")}',
        })
    # de-dup by (name, address)
    seen, uniq = set(), []
    for r in out:
        key = (r["name"], r["address"])
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    return sorted(uniq, key=lambda r: r["name"].lower())


def _osm_addr(tags):
    parts = [tags.get("addr:housenumber"), tags.get("addr:street"),
             tags.get("addr:city"), tags.get("addr:postcode")]
    return " ".join(p for p in parts if p) or None


# ---------------------------------------------------------------- Socrata ----

def socrata_catalog(domain, query, limit):
    """Find datasets on a Socrata domain (permits, licenses, etc.)."""
    params = urllib.parse.urlencode({"q": query, "limit": limit})
    url = f"https://{domain}/api/catalog/v1?{params}"
    try:
        raw = _get(url)
    except HTTPError:
        # Fallback to the discovery API (works cross-domain)
        params = urllib.parse.urlencode(
            {"q": query, "domains": domain, "limit": limit})
        url = f"https://api.us.socrata.com/api/catalog/v1?{params}"
        try:
            raw = _get(url)
        except (HTTPError, URLError) as e:
            _die(f"catalog request failed: {e}")
    except URLError as e:
        _die(f"catalog request failed: {e}")
    data = json.loads(raw)
    out = []
    for r in data.get("results", []):
        res = r.get("resource", {})
        out.append({
            "id": res.get("id"),
            "name": res.get("name"),
            "type": res.get("type"),
            "description": (res.get("description") or "")[:160],
            "updated": res.get("updatedAt"),
            "rows": res.get("rows_size"),
        })
    return out


def socrata_query(domain, dataset, where=None, q=None, order=None, limit=50,
                  select=None):
    """Run a SoQL query against a Socrata dataset (the resource endpoint)."""
    params = {"$limit": limit}
    if where:
        params["$where"] = where
    if q:
        params["$q"] = q
    if order:
        params["$order"] = order
    if select:
        params["$select"] = select
    url = f"https://{domain}/resource/{dataset}.json?{urllib.parse.urlencode(params)}"
    try:
        raw = _get(url)
    except HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            pass
        _die(f"socrata query failed ({e.code}): {detail or e}")
    except URLError as e:
        _die(f"socrata query failed: {e}")
    return json.loads(raw)


# ------------------------------------------------------------------ output ----

def emit(obj, table=False, columns=None):
    if not table:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
        return
    rows = obj if isinstance(obj, list) else [obj]
    if not rows:
        print("(no results)")
        return
    cols = columns or list(rows[0].keys())
    widths = {c: max(len(str(c)), *(len(str(r.get(c, "") or "")) for r in rows))
              for c in cols}
    widths = {c: min(w, 48) for c, w in widths.items()}
    line = "  ".join(str(c).ljust(widths[c]) for c in cols)
    print(line)
    print("  ".join("-" * widths[c] for c in cols))
    for r in rows:
        print("  ".join(str(r.get(c, "") or "")[:widths[c]].ljust(widths[c])
                        for c in cols))


# -------------------------------------------------------------------- main ----

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("geocode", help="address/place -> lat/lon")
    g.add_argument("query")

    n = sub.add_parser("nearby", help="businesses physically near a point (OSM)")
    n.add_argument("--address")
    n.add_argument("--lat", type=float)
    n.add_argument("--lon", type=float)
    n.add_argument("--radius", type=int, default=500, help="meters (default 500)")
    n.add_argument("--category", choices=list(CATEGORIES), default="all")
    n.add_argument("--table", action="store_true")

    c = sub.add_parser("catalog", help="find Socrata datasets on a domain")
    c.add_argument("--domain", required=True, help="e.g. data.sfgov.org")
    c.add_argument("--query", default="business license permit")
    c.add_argument("--limit", type=int, default=20)
    c.add_argument("--table", action="store_true")

    s = sub.add_parser("socrata-search", help="full-text search a dataset")
    s.add_argument("--domain", required=True)
    s.add_argument("--dataset", required=True, help="Socrata dataset id, e.g. i98e-djp9")
    s.add_argument("--query", required=True)
    s.add_argument("--limit", type=int, default=50)
    s.add_argument("--order")
    s.add_argument("--table", action="store_true")

    pm = sub.add_parser("permits", help="query a permit/license dataset with filters")
    pm.add_argument("--domain", required=True)
    pm.add_argument("--dataset", required=True)
    pm.add_argument("--where", help="raw SoQL $where clause")
    pm.add_argument("--near", help="text to match in the address column")
    pm.add_argument("--address-col", default="address",
                    help="column name holding the street/address")
    pm.add_argument("--since", help="ISO date; filters --date-col >= this")
    pm.add_argument("--date-col", default="permit_creation_date")
    pm.add_argument("--order")
    pm.add_argument("--limit", type=int, default=50)
    pm.add_argument("--table", action="store_true")

    args = p.parse_args()

    if args.cmd == "geocode":
        emit(geocode(args.query))

    elif args.cmd == "nearby":
        lat, lon, label = _resolve_point(args)
        rows = overpass_nearby(lat, lon, args.radius, args.category)
        print(f"# {len(rows)} places within {args.radius}m of {label}",
              file=sys.stderr)
        emit(rows, table=args.table,
             columns=["name", "type", "address", "website"] if args.table else None)

    elif args.cmd == "catalog":
        rows = socrata_catalog(args.domain, args.query, args.limit)
        emit(rows, table=args.table,
             columns=["id", "name", "type", "rows"] if args.table else None)

    elif args.cmd == "socrata-search":
        rows = socrata_query(args.domain, args.dataset, q=args.query,
                             order=args.order, limit=args.limit)
        emit(rows, table=args.table)

    elif args.cmd == "permits":
        clauses = []
        if args.where:
            clauses.append(f"({args.where})")
        if args.near:
            safe = args.near.replace("'", "''")
            clauses.append(f"upper({args.address_col}) like upper('%{safe}%')")
        if args.since:
            clauses.append(f"{args.date_col} >= '{args.since}'")
        where = " AND ".join(clauses) if clauses else None
        order = args.order or f"{args.date_col} DESC"
        rows = socrata_query(args.domain, args.dataset, where=where,
                             order=order, limit=args.limit)
        emit(rows, table=args.table)


if __name__ == "__main__":
    main()
