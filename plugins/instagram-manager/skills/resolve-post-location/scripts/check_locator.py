#!/usr/bin/env python3
"""check_locator.py — score the post-locator agent on a fixed set of posts whose venues a person
listed by hand, so a change to the agent's instructions or the merge can be measured, before and after.

    check_locator.py --prepare        one batch file of the check posts, for one post-locator agent
    check_locator.py                  score: what the current pins give, and what the agent's answers give

Reads   $INSTAGRAM_HOME/data/locate-checks.yaml      code → {why, spots: [names], not: [names]}: the spots
                                                     the caption names that the map should open, and any
                                                     it must not pin (a place in another city)
        $INSTAGRAM_HOME/data/pins.yaml, pins-review.yaml   the "before" score
        $INSTAGRAM_HOME/.cache/batches/locate-check/batch-001.answers.json   the agent's answers ("now")
        and what resolve_post_location.py reads (saves, tags, places)
Writes  $INSTAGRAM_HOME/.cache/batches/locate-check/batch-001.json (with --prepare); nothing else. The
        agent's answers are looked up on OpenStreetMap exactly as --merge would (cached, one request a
        second), but no pins file changes.

Each listed spot is scored as one of:
  pinned        a pin of its own: OpenStreetMap found it, or the caption's address or coordinates did
  at its town   OpenStreetMap does not list it: the hub shows a dashed pin at its town, and Google Maps
                searches it by name (the same rule as build-hub's placed_spots)
  lost          not named, or named but failed the quote or area check: the post opens only its town
A `not` name the agent pins or places anyway is a wrong spot. Spots the agent names that the list does
not are printed too: either the list is missing them, or the agent made them up.
"""

import argparse
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import resolve_post_location as rpl  # noqa: E402
from home import cache  # noqa: E402
from log import log  # noqa: E402
from places import load_yaml  # noqa: E402

CHECKS = os.path.join("data", "locate-checks.yaml")
# Review reasons where the quote and area checked out and only the map lookup failed: build-hub shows
# these as dashed pins at their town.
LOOKUP_MISSES = (re.compile(r"^not found near "), re.compile(r"^found .*, a different name$"),
                 re.compile(r"^\d+ km from "))
STATUSES = ("pinned", "at its town", "lost")


def check_dir():
    return cache("batches", "locate-check")


def squash(text):
    text = unicodedata.normalize("NFKD", str(text).lower())
    return "".join(c for c in text if c.isalnum() and not unicodedata.combining(c))


def names_of(entry):
    return [entry[k] for k in ("said", "name", "asked", "lookup") if isinstance(entry.get(k), str) and entry[k].strip()]


def own_words(text):
    words = rpl.name_words(text)
    return (words - rpl.PLACE_WORDS - rpl.KIND_WORDS) or words


def match_tier(expected, entry):
    """0 for the same name, 1 for a name that differs by place words or a business kind, 2 for a
    longer name holding all of the listed name's own words ("Example Churro Shop" for "Example"), or a
    handle that runs it together ("@examplecafe_sf" for "Example Cafe"); None for no match. The lower
    tiers are given out first."""
    tiers = []
    for n in names_of(entry):
        n = n.lstrip("@#")
        if squash(n) == squash(expected) or rpl.name_words(n) == rpl.name_words(expected):
            tiers.append(0)
        elif rpl.same_name(expected, n):
            tiers.append(1)
        elif own_words(expected) <= rpl.name_words(n) or (len(squash(expected)) >= 5 and squash(n).startswith(squash(expected))):
            tiers.append(2)
    return min(tiers) if tiers else None


def assign(expected, entries):
    """expected name → the entry that names it, each entry used once; the closest matches first."""
    got, used = {}, set()
    for tier in (0, 1, 2):
        for name in expected:
            if name in got:
                continue
            for i, e in enumerate(entries):
                if i not in used and match_tier(name, e) == tier:
                    got[name] = e
                    used.add(i)
                    break
    return got, [e for i, e in enumerate(entries) if i not in used]


def status(where, entry):
    if entry is None:
        return "lost", "not named"
    if where == "pin":
        kind = entry.get("kind")
        if entry.get("found") == "the caption's coordinates":
            return "pinned", "coordinates"
        how = "address" if kind == "address" else "map"
        return "pinned", f"{how}: {entry['found'][:70]}" if entry.get("found") else how
    why = str(entry.get("why") or "")
    if not entry.get("drop") and any(r.match(why) for r in LOOKUP_MISSES):
        return "at its town", why
    return "lost", why or "dropped"


def score(checks, results):
    """results: code → [(where, entry)]. code → {expected: (status, how)}, wrong spots, extra spots."""
    out, wrong, extra = {}, [], []
    for code, check in checks.items():
        entries = results.get(code, [])
        named = [e for _, e in entries]
        got, rest = assign(check["spots"], named)
        where_of = {id(e): w for w, e in entries}
        out[code] = {n: status(where_of.get(id(got[n])), got[n]) if n in got else status(None, None)
                     for n in check["spots"]}
        bad, rest = assign(check["not"], rest)
        wrong += [(code, n) for n, e in bad.items() if status(where_of.get(id(e)), e)[0] != "lost"]
        extra += [(code, e.get("said")) for e in rest]
    return out, wrong, extra


def load_checks():
    raw = load_yaml(CHECKS)
    checks = {}
    for code, c in (raw or {}).items():
        if not isinstance(c, dict):
            continue
        listed = lambda k: [str(s) for s in (c.get(k) or []) if str(s).strip()]  # noqa: E731
        checks[str(code)] = {"why": str(c.get("why") or ""), "spots": listed("spots"), "not": listed("not")}
    if not checks:
        sys.exit(f"no checks in {CHECKS}: write code → {{why, spots: [...]}} first")
    return checks


def before(checks):
    pins, review = load_yaml(rpl.PINS), load_yaml(rpl.REVIEW)
    res = {}
    for code in checks:
        res[code] = ([("pin", e) for e in pins.get(code) or [] if isinstance(e, dict)]
                     + [("review", e) for e in review.get(code) or [] if isinstance(e, dict)])
    return res


def now(checks, by_code, tags, places, fetcher=None):
    path = os.path.join(check_dir(), "batch-001.answers.json")
    if not os.path.exists(path):
        return None
    answers, bad = rpl.read_answers(path)
    if bad:
        sys.exit(f"{path}: {bad}")
    res, reaches = {}, {}
    for code in checks:
        save = by_code.get(code) or {}
        areas = [a["name"] for a in rpl.areas_of(tags.get(code), places)]
        res[code] = [rpl.resolve(s, save.get("caption") or "", areas, places, reaches, fetcher, rpl.creator_of(save))
                     for s in rpl.clean_spots(answers.get(code)) or []]
    return res


def totals(scored):
    t = {k: 0 for k in STATUSES}
    for spots in scored.values():
        for st, _ in spots.values():
            t[st] += 1
    return t


def prepare(checks, by_code, tags, places):
    recs, skipped = [], []
    for code in checks:
        areas = rpl.areas_of(tags.get(code), places)
        if code not in by_code or not areas:
            skipped.append(code)
            continue
        recs.append(rpl.record(by_code[code], areas))
    out = check_dir()
    os.makedirs(out, exist_ok=True)
    answers = os.path.join(out, "batch-001.answers.json")
    if os.path.exists(answers):  # the last run's answers make way for the next
        os.replace(answers, answers.replace(".answers.json", ".answers.prev.json"))
    path = os.path.join(out, "batch-001.json")
    rpl.write_json(path, {"batch": "check-001", "answers": answers, "saves": recs})
    log("locate_check_prepare", saves=len(recs), skipped=",".join(skipped) or "none")
    if skipped:
        print(f"left out (no save, or no area more exact than a state): {', '.join(skipped)}")
    print(path)
    return 0


def report(checks, was, is_now):
    for code, spots in was.items():
        print(f"{code}  {checks[code]['why']}")
        for name, (st, how) in spots.items():
            line = f"    {name:<34} before: {st:<11}"
            if is_now is not None:
                nst, nhow = is_now[code][name]
                line += f"  now: {nst:<11} ({nhow})" if nst != "lost" else f"  now: lost ({nhow})"
            print(line)


def main(argv=None, fetcher=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--prepare", action="store_true", help="write the check batch for one post-locator agent")
    ap.add_argument("--saved", default=None, help="saves.json (default: the data repo's .cache)")
    args = ap.parse_args(argv)
    checks = load_checks()
    with open(args.saved or cache("saves.json"), encoding="utf-8") as fh:
        by_code = {s["code"]: s for s in json.load(fh)["saves"]}
    tags = load_yaml(rpl.TAGS)
    places = load_yaml(rpl.PLACES).get("places") or {}
    if args.prepare:
        return prepare(checks, by_code, tags, places)
    was, wrong_was, _ = score(checks, before(checks))
    res = now(checks, by_code, tags, places, fetcher)
    is_now, wrong_now, extra = score(checks, res) if res is not None else (None, [], [])
    report(checks, was, is_now)
    n = sum(len(c["spots"]) for c in checks.values())
    tb = totals(was)
    print(f"\n{n} listed spots in {len(checks)} posts.")
    print(f"before: {tb['pinned']} pinned, {tb['at its town']} at their town, {tb['lost']} lost; "
          f"{len(wrong_was)} wrong spots")
    log("locate_check", run="before", spots=n, **{k.replace(" ", "_"): v for k, v in tb.items()}, wrong=len(wrong_was))
    if is_now is None:
        print("now: no answers yet. Run --prepare, then one post-locator agent on the batch it prints.")
        return 0
    tn = totals(is_now)
    print(f"now:    {tn['pinned']} pinned, {tn['at its town']} at their town, {tn['lost']} lost; "
          f"{len(wrong_now)} wrong spots")
    log("locate_check", run="now", spots=n, **{k.replace(" ", "_"): v for k, v in tn.items()}, wrong=len(wrong_now))
    for code, name in wrong_now:
        print(f"wrong: {code} {name}")
    if extra:
        print(f"{len(extra)} more spots the agent named, not on the list (add them, or they were made up):")
        for code, said in extra:
            print(f"    {code} {said}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
