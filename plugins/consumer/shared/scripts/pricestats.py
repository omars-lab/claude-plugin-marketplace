#!/usr/bin/env python3
"""
pricestats.py — statistics for a used-market listing set.

Usage:
    python3 pricestats.py listings.csv
    python3 pricestats.py listings.csv --local "Austin"
    python3 pricestats.py listings.json          # JSON array still accepted

Input: listings.csv as written by record.sh, or a JSON array of the same records.
       Schema: shared/references/record-format.md
Output: a summary keyed to the sample-size thresholds in
        skills/research-used-market/references/analysis.md, so the reported
        confidence matches what the data can actually support.

The n>=8 quartile threshold below is coupled to the same threshold in the
artifact spec (shared/references/artifact-design.md). If you change one,
change the other -- a confident band drawn over 5 points is the main way
this tooling could mislead someone.
"""

import csv
import json
import sys
from statistics import median


def load(path):
    """Read listings.csv (the record.sh format) or a JSON array of the same records."""
    if path.lower().endswith(".csv"):
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    else:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)

    # CSV gives every field back as a string, and empty cells as "". Coerce price
    # and drop the blanks, so a missing price reads as missing rather than as 0.
    out = []
    for r in rows:
        r = {k: v for k, v in r.items() if k is not None}
        raw = str(r.get("price", "")).strip().replace(",", "").lstrip("$")
        try:
            r["price"] = float(raw) if raw else None
        except ValueError:
            r["price"] = None
        for k, v in list(r.items()):
            if isinstance(v, str) and not v.strip():
                r[k] = None
        out.append(r)
    return out


def quantile(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    i = (len(s) - 1) * p
    lo, hi = int(i), min(int(i) + 1, len(s) - 1)
    return s[lo] if lo == hi else s[lo] + (s[hi] - s[lo]) * (i - lo)


def confidence(n):
    if n <= 3:
        return "ANECDOTE", "Report listings individually. Do not compute statistics."
    if n <= 7:
        return "ROUGH", "Midpoint only, wide caveat. No quartiles."
    if n <= 14:
        return "PROVISIONAL", "Median and range usable, flag as provisional."
    if n <= 30:
        return "SOLID", "Distribution is meaningful. Quartiles valid."
    return "CONFIDENT", "Large enough to read condition and regional effects."


def money(v):
    return "-" if v is None else f"${v:,.0f}"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    try:
        rows = load(sys.argv[1])
    except FileNotFoundError:
        sys.exit(f"pricestats.py: no such file: {sys.argv[1]}")
    except (json.JSONDecodeError, csv.Error, UnicodeDecodeError) as e:
        sys.exit(f"pricestats.py: could not read {sys.argv[1]}: {e}")

    local_filter = None
    if "--local" in sys.argv:
        local_filter = sys.argv[sys.argv.index("--local") + 1].lower()

    # Junk and parts units never enter the headline number.
    usable = [r for r in rows if r.get("price") and r.get("condition") != "parts"]
    parts = [r for r in rows if r.get("condition") == "parts"]

    sold = [r for r in usable if r.get("status") in ("sold", "auction_end")]
    asking = [r for r in usable if r.get("status") == "asking"]

    sp = [r["price"] for r in sold]
    ap = [r["price"] for r in asking]

    label, guidance = confidence(len(sp))

    print(f"\n{'=' * 58}")
    print(f"  SOLD  n={len(sp)}   [{label}]")
    print(f"  {guidance}")
    print(f"{'=' * 58}")
    if sp:
        q1, q3 = quantile(sp, 0.25), quantile(sp, 0.75)
        print(f"  median            {money(median(sp))}")
        if len(sp) >= 8:
            print(f"  fair range        {money(q1)} - {money(q3)}   (25th-75th)")
            print(f"  buyer target      {money(q1)}   (25th pct)")
            print(f"  seller target     {money(quantile(sp, 0.60))}   (60th pct)")
        else:
            print("  quartiles         withheld - needs n>=8")
        print(f"  observed low      {money(min(sp))}")
        print(f"  observed high     {money(max(sp))}")

        # Flag rather than silently drop.
        med = median(sp)
        outliers = [r for r in sold if r["price"] > med * 2 or r["price"] < med * 0.4]
        if outliers:
            print(f"\n  OUTLIERS TO INVESTIGATE ({len(outliers)}) - check for bundles,")
            print("  variant mismatch, or a listing that never actually sold:")
            for r in outliers:
                print(f"    {money(r['price'])}  {r.get('title', '')[:44]}")
    else:
        print("  No sold data. Any analysis below is asking-price based and reads HIGH.")

    if ap:
        print(f"\n  ASKING  n={len(ap)}  median {money(median(ap))}")
        if sp:
            gap = (median(ap) / median(sp) - 1) * 100
            print(f"  Asking runs {gap:+.0f}% vs sold. Never quote asking as market.")

    # Local vs shipped are different markets, not noise.
    loc = [r["price"] for r in sold if r.get("shipping") == "local"]
    shp = [r["price"] for r in sold if r.get("shipping") == "shipped"]
    if loc and shp:
        d = (median(loc) / median(shp) - 1) * 100
        print(f"\n  LOCAL {money(median(loc))} (n={len(loc)}) vs "
              f"SHIPPED {money(median(shp))} (n={len(shp)})   {d:+.0f}%")

    if local_filter:
        near = [r for r in sold if local_filter in str(r.get("location", "")).lower()]
        print(f"\n  IN '{local_filter}': n={len(near)}"
              + (f"  median {money(median([r['price'] for r in near]))}" if near else
                 "  - none found; widen the radius"))

    if parts:
        pp = [r["price"] for r in parts]
        print(f"\n  PARTS/BROKEN floor  n={len(pp)}  median {money(median(pp))}"
              "  (excluded from headline)")

    print()


if __name__ == "__main__":
    main()
