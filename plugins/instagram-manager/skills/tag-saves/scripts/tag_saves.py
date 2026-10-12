#!/usr/bin/env python3
"""tag_saves.py — give each save its topics and its places, free rules first, then the model.

    tag_saves.py --pilot NAME            the pilot's saves (pilots: in config/collections.yaml)
    tag_saves.py --all                   every save
    tag_saves.py --rules-only ...        no model calls: collection tags and place hints only
    tag_saves.py --report --pilot NAME   print the pilot's tags as a table; tags nothing
    options: --limit N (model calls this run), --workers N (default 6), --retag (ask again)

Reads   $INSTAGRAM_HOME/.cache/saves.json (from import-saves)
        $INSTAGRAM_HOME/config/topics.yaml, collections.yaml, places.yaml
Writes  $INSTAGRAM_HOME/data/tags.yaml          code → {topics[], cities[], source, hints[]}
        $INSTAGRAM_HOME/data/tags-review.yaml   code → what the model named outside the lists,
                                                or why its reply could not be used

How a save is tagged
  1. Collections (collections.yaml). A save in a mapped collection gets that entry's topics and
     cities. These are always kept.
  2. Place hints (places.yaml). A listed name in the caption (whole words, any case) or a listed
     hashtag. A hint is not a tag: it pulls a save into a pilot, and it is shown to the model.
  3. The model (Claude Haiku) reads the caption, hashtags, creator, collections and the two
     above, and returns topics and places from the fixed lists. A topic or place outside the
     lists goes to tags-review.yaml, never into the tags.
  Final tags = collection tags + the model's. "cities" means places: a city, a state or a
  country, whatever the lists hold.

A save the model has tagged is skipped on a rerun (unless --retag), so only new saves cost a
call. A failed reply leaves a rules-only entry, and the next run tries that save again.

A pilot looks at the saves in its collections plus any save with a hint for one of its cities.
A save outside those collections whose caption names no listed place is not looked at; --all
closes that gap.
"""

import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, os.pardir, "shared", "scripts"))
import yaml  # noqa: E402

import claude  # noqa: E402
from home import cache, home  # noqa: E402
from log import log  # noqa: E402

TAGS = os.path.join("data", "tags.yaml")
REVIEW = os.path.join("data", "tags-review.yaml")
CAPTION_CHARS = 2500
SAVE_EVERY = 20

SYSTEM = """You sort one person's saved Instagram posts. Answer with the tag tool.

topics: every topic below that the post is about, at least one. Use the slugs exactly.
{topics}

cities: every place below that the post is about; none if it is not about a place. Use the
names exactly. A place inside a listed state or country counts as that state or country.
{places}

other_topics, other_places: a topic or place the post is clearly about that is not listed.
Leave them empty otherwise. Keep everything under "Already tagged"; add to it, never drop it."""

_LIST = {"type": "array", "items": {"type": "string"}}
TOOL = {"name": "tag", "description": "The topics and places of one saved post.",
        "input_schema": {"type": "object", "required": ["topics", "cities"], "properties": {
            "topics": _LIST, "cities": _LIST, "other_topics": _LIST, "other_places": _LIST}}}


def load_yaml(rel):
    path = os.path.join(home(), rel)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def write_yaml(rel, data):
    path = os.path.join(home(), rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=True, allow_unicode=True, default_flow_style=None, width=1000)
    os.replace(tmp, path)


def load_config():
    topics = load_yaml(os.path.join("config", "topics.yaml")).get("topics") or {}
    coll = load_yaml(os.path.join("config", "collections.yaml"))
    places = load_yaml(os.path.join("config", "places.yaml")).get("places") or {}
    return topics, coll.get("collections") or {}, coll.get("pilots") or {}, places


def known_places(collections, places):
    return sorted({c for rule in collections.values() for c in rule.get("cities") or []} | set(places))


def collection_tags(save, collections):
    topics, cities = set(), set()
    for name in save.get("collections") or []:
        rule = collections.get(name) or {}
        topics |= set(rule.get("topics") or [])
        cities |= set(rule.get("cities") or [])
    return topics, cities


def compile_places(places):
    out = []
    for place, p in places.items():
        names = sorted((n for n in p.get("names") or [] if n.strip()), key=len, reverse=True)
        rx = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(n) for n in names) + r")(?!\w)", re.I) if names else None
        out.append((place, rx, {h.lower().lstrip("#") for h in p.get("hashtags") or []}))
    return out


def place_hints(save, compiled):
    caption = save.get("caption") or ""
    tags = {h.lower().lstrip("#") for h in save.get("hashtags") or []}
    tags |= {m.lower() for m in re.findall(r"#(\w+)", caption)}  # hashtags written in the caption
    return {place for place, rx, ht in compiled if (rx and rx.search(caption)) or tags & ht}


def system_prompt(topics, places):
    return SYSTEM.format(
        topics="\n".join(f"- {slug}: {t.get('about') or t.get('label', '')}" for slug, t in topics.items()),
        places=", ".join(places))


def user_message(save, topics, cities, hints):
    owner = save.get("owner") or {}
    return "\n".join([
        f"Creator: @{owner.get('username', '')} ({owner.get('name', '')})",
        f"Collections: {', '.join(save.get('collections') or []) or 'none'}",
        f"Hashtags: {' '.join('#' + h for h in save.get('hashtags') or []) or 'none'}",
        f"Already tagged: topics {sorted(topics)}, places {sorted(cities)}",
        f"Place names found in the text: {sorted(hints) or 'none'}",
        "Caption:",
        (save.get("caption") or "(no caption)")[:CAPTION_CHARS],
    ])


def ask_model(key, system, save, topics_known, places_known, rule_topics, rule_cities, hints):
    """(topics, cities, review) from one model call. review is None when nothing needs a look."""
    d = claude.call_tool(key, system, user_message(save, rule_topics, rule_cities, hints), TOOL)
    said_topics = [t for t in d.get("topics") or [] if isinstance(t, str)]
    said_places = [c for c in d.get("cities") or [] if isinstance(c, str)]
    topics = {t for t in said_topics if t in topics_known} | rule_topics
    cities = {c for c in said_places if c in places_known} | rule_cities
    other_topics = sorted({t for t in said_topics if t not in topics_known} | set(d.get("other_topics") or []))
    other_places = sorted({c for c in said_places if c not in places_known} | set(d.get("other_places") or []))
    if not topics:
        topics = {"other"} if "other" in topics_known else set()
    review = {k: v for k, v in (("other_topics", other_topics), ("other_places", other_places)) if v}
    return topics, cities, review or None


def entry(topics, cities, source, hints):
    e = {"topics": sorted(topics), "cities": sorted(cities), "source": source}
    if hints:
        e["hints"] = sorted(hints)
    return e


def in_pilot(save, tag, pilot, hints):
    if set(save.get("collections") or []) & set(pilot.get("collections") or []):
        return True
    cities = set(pilot.get("cities") or [])
    return bool(cities & (hints | set((tag or {}).get("cities") or [])))


def report(saves, tags, pilot, compiled):
    """The pilot's saves as a table, with what to spot-check called out."""
    rows, rejected = [], []
    pilot_colls, pilot_cities = set(pilot.get("collections") or []), set(pilot.get("cities") or [])
    for s in saves:
        hints = place_hints(s, compiled)
        tag = tags.get(s["code"])
        if not in_pilot(s, tag, pilot, hints):
            continue
        tag = tag or {"topics": [], "cities": [], "source": "untagged"}
        in_coll = bool(set(s.get("collections") or []) & pilot_colls)
        took = bool(set(tag["cities"]) & pilot_cities)
        if not in_coll and not took:
            if tag["source"] == "model":
                rejected.append((s, tag))
            continue
        notes = []
        if not in_coll:
            notes.append("found outside the collections")
        if len(tag["topics"]) > 1 or len(tag["cities"]) > 1:
            notes.append("2+ topics or places")
        rows.append((s, tag, notes))
    print("| code | collections | topics | places | by | look at |")
    print("|---|---|---|---|---|---|")
    for s, tag, notes in sorted(rows, key=lambda r: (not r[2], r[0]["code"])):
        print(f"| {s['code']} | {', '.join(s.get('collections') or []) or '-'} | {', '.join(tag['topics'])} "
              f"| {', '.join(tag['cities'])} | {tag['source']} | {'; '.join(notes)} |")
    if rejected:
        print("\nA place name matched, but the model did not put these in the pilot's places:")
        for s, tag in rejected:
            print(f"- {s['code']} hints {', '.join(tag.get('hints') or [])} → {', '.join(tag['topics'])} "
                  f"/ {', '.join(tag['cities']) or 'no place'}: {(s.get('caption') or '')[:90]!r}")
    multi = sum(1 for r in rows if "2+ topics or places" in r[2])
    outside = sum(1 for r in rows if "found outside the collections" in r[2])
    print(f"\n{len(rows)} saves in the pilot: {outside} found outside the collections, {multi} with 2+ "
          f"topics or places, {len(rejected)} place matches the model turned down.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument("--pilot", help="a pilot name from config/collections.yaml")
    scope.add_argument("--all", action="store_true", help="every save")
    ap.add_argument("--rules-only", action="store_true", help="no model calls")
    ap.add_argument("--report", action="store_true", help="print the pilot's tags; tag nothing")
    ap.add_argument("--retag", action="store_true", help="ask the model again for saves it already tagged")
    ap.add_argument("--limit", type=int, default=0, help="at most this many model calls (0 = no limit)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--saved", default=None, help="saves.json (default: the data repo's .cache)")
    args = ap.parse_args(argv)

    with open(args.saved or cache("saves.json"), encoding="utf-8") as fh:
        saves = json.load(fh)["saves"]
    topics_known, collections, pilots, places = load_config()
    places_known = known_places(collections, places)
    compiled = compile_places(places)
    pilot = None
    if args.pilot:
        if args.pilot not in pilots:
            sys.exit(f"no pilot {args.pilot!r} in config/collections.yaml (have: {', '.join(pilots) or 'none'})")
        pilot = pilots[args.pilot]
    tags = load_yaml(TAGS)
    review = load_yaml(REVIEW)

    if args.report:
        if not pilot:
            sys.exit("--report needs --pilot")
        report(saves, tags, pilot, compiled)
        return 0

    todo, kept = [], 0
    for s in saves:
        hints = place_hints(s, compiled)
        if pilot and not in_pilot(s, None, pilot, hints):
            continue
        rule_topics, rule_cities = collection_tags(s, collections)
        old = tags.get(s["code"])
        if old and old.get("source") == "model" and not args.retag:
            tags[s["code"]] = entry(set(old["topics"]) | rule_topics, set(old["cities"]) | rule_cities, "model", hints)
            kept += 1
            continue
        if not old or old.get("source") != "model":  # a retag keeps the old tags until a reply lands
            tags[s["code"]] = entry(rule_topics, rule_cities, "rules", hints)
        if not args.rules_only:
            todo.append((s, rule_topics, rule_cities, hints))
    if args.limit:
        todo = todo[:args.limit]
    log("tag_start", scope=args.pilot or "all", already_tagged=kept, to_ask=len(todo), rules_only=args.rules_only)

    asked = failed = 0
    refused = None
    if todo:
        key = claude.load_key()
        system = system_prompt(topics_known, places_known)
        stop = threading.Event()

        def ask(*a):  # after one refusal no new call starts; only those already in flight finish
            if stop.is_set():
                raise claude.Refused("stopped after an earlier refusal")
            try:
                return ask_model(*a)
            except claude.Refused:
                stop.set()
                raise

        with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(ask, key, system, s, set(topics_known), set(places_known),
                                   rt, rc, h): (s, h) for s, rt, rc, h in todo}
            for i, fut in enumerate(cf.as_completed(futures), 1):
                s, hints = futures[fut]
                code = s["code"]
                try:
                    topics, cities, extra = fut.result()
                except claude.Refused as e:  # no credit or a bad key: every other call would fail too
                    refused = refused or e
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
                except Exception as e:  # a bad reply must not stop the run
                    failed += 1
                    review[code] = {"error": f"{type(e).__name__}: {e}"[:200]}
                    log("tag_review", code=code, reason="reply_unusable", err=type(e).__name__)
                else:
                    asked += 1
                    tags[code] = entry(topics, cities, "model", hints)
                    if extra:
                        review[code] = extra
                        log("tag_review", code=code, reason="outside_lists")
                    else:
                        review.pop(code, None)
                    log("tag", code=code, topics=",".join(sorted(topics)), cities=",".join(sorted(cities)) or "-")
                if i % SAVE_EVERY == 0:
                    write_yaml(TAGS, tags)
                    write_yaml(REVIEW, review)
    write_yaml(TAGS, tags)
    write_yaml(REVIEW, review)
    u = claude.USAGE
    log("tag_done", tagged=asked, failed=failed, already_tagged=kept, calls=u["calls"],
        tokens_in=u["tokens_in"], tokens_out=u["tokens_out"], review=len(review), out=os.path.join(home(), TAGS))
    if refused:
        log("tag_stopped", reason="refused", msg=str(refused))
        sys.exit(f"stopped: the API refused the account ({refused}). What was tagged is saved; rerun to go on.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
