#!/usr/bin/env python3
"""tag_saves.py — give each save its topics and its places: free rules here, the reading done by the
save-tagger subagent in batches. This script never calls a model.

    tag_saves.py --prepare --pilot NAME     rule tags, then batch files for the saves the agent must read
    tag_saves.py --prepare --all            the same for every save
    tag_saves.py --merge                    check the agents' answers and write them into the tags
    tag_saves.py --rules-only --pilot NAME  rule tags only, no batches (sizing a pilot, checking config)
    tag_saves.py --report --pilot NAME      the pilot's tags as a table; tags nothing
    options: --limit N (saves in this round), --retag (read again), --batch-saves N, --batch-chars N

Reads   $INSTAGRAM_HOME/.cache/saves.json (from import-saves)
        $INSTAGRAM_HOME/config/topics.yaml, collections.yaml, places.yaml
Writes  $INSTAGRAM_HOME/data/tags.yaml          code → {topics[], cities[], source, hints[]}
        $INSTAGRAM_HOME/data/tags-review.yaml   code → what the agent named outside the lists, or why
                                                its answer could not be used
        $INSTAGRAM_HOME/.cache/batches/tag/     batch-NNN.json (in), batch-NNN.answers.json (out),
                                                renamed .answers.merged.json once merged
        $INSTAGRAM_HOME/.cache/batches/tag/merged.jsonl   one line per merged batch, for the retro

How a save is tagged
  1. Collections (collections.yaml). A save in a mapped collection gets that entry's topics and
     cities. These are always kept.
  2. Place hints (places.yaml). A listed name in the caption (whole words, any case) or a listed
     hashtag. A hint is not a tag: it pulls a save into a pilot, and it is shown to the agent.
  3. The save-tagger agent (Haiku) reads a batch: caption, hashtags, creator, collections and the
     two above for each save, and answers topics and places from the fixed lists. --merge keeps
     only names on the lists; anything else goes to tags-review.yaml, never into the tags.
  Final tags = collection tags + the agent's. "cities" means places: a city, a state or a country.

Batches are cut by size: saves are added until the next one would pass --batch-chars characters
(about 4 characters a token) or --batch-saves saves. Captions are cut at 2,500 characters, so one
save always fits. Saves are sorted by collection, so a batch holds similar posts.

A save the agent has tagged is not batched again (unless --retag). A save with no usable answer
keeps its rule tags, the reason goes in the review file, and the next --prepare batches it again.

A pilot looks at the saves in its collections plus any save with a hint for one of its cities.
A save outside those collections whose caption names no listed place is not looked at; --all
closes that gap.
"""

import argparse
import glob
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, os.pardir, "shared", "scripts"))
import yaml  # noqa: E402

from home import cache, home  # noqa: E402
from log import log  # noqa: E402

TAGS = os.path.join("data", "tags.yaml")
REVIEW = os.path.join("data", "tags-review.yaml")
CAPTION_CHARS = 2500
BATCH_SAVES = 40
BATCH_CHARS = 60000


def batch_dir():
    return cache("batches", "tag")


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


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
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


def record(save, topics, cities, hints):
    """One save as the agent sees it."""
    owner = save.get("owner") or {}
    return {"code": save["code"], "creator": f"@{owner.get('username', '')} ({owner.get('name', '')})",
            "collections": save.get("collections") or [], "hashtags": save.get("hashtags") or [],
            "already": {"topics": sorted(topics), "cities": sorted(cities)}, "hints": sorted(hints),
            "caption": (save.get("caption") or "")[:CAPTION_CHARS]}


def size(rec):
    return len(json.dumps(rec, ensure_ascii=False))


def chunk(records, max_saves=BATCH_SAVES, max_chars=BATCH_CHARS):
    """Split records into batches of at most max_saves and about max_chars, in order. A record is
    never split, and one bigger than max_chars gets a batch to itself."""
    batches, cur, chars = [], [], 0
    for r in records:
        n = size(r)
        if cur and (len(cur) >= max_saves or chars + n > max_chars):
            batches.append(cur)
            cur, chars = [], 0
        cur.append(r)
        chars += n
    if cur:
        batches.append(cur)
    return batches


def apply_answer(d, topics_known, places_known, rule_topics, rule_cities):
    """(topics, cities, review) from one answer. review is None when nothing needs a look."""
    if not isinstance(d, dict) or not isinstance(d.get("topics"), list) or not isinstance(d.get("cities", []), list):
        raise ValueError("answer is not {topics: [...], cities: [...]}")
    said_topics = [t for t in d.get("topics") or [] if isinstance(t, str)]
    said_places = [c for c in d.get("cities") or [] if isinstance(c, str)]
    topics = {t for t in said_topics if t in topics_known} | rule_topics
    cities = {c for c in said_places if c in places_known} | rule_cities
    other_topics = sorted({t for t in said_topics if t not in topics_known}
                          | {t for t in d.get("other_topics") or [] if isinstance(t, str)})
    other_places = sorted({c for c in said_places if c not in places_known}
                          | {c for c in d.get("other_places") or [] if isinstance(c, str)})
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
        print("\nA place name matched, but the agent did not put these in the pilot's places:")
        for s, tag in rejected:
            print(f"- {s['code']} hints {', '.join(tag.get('hints') or [])} → {', '.join(tag['topics'])} "
                  f"/ {', '.join(tag['cities']) or 'no place'}: {(s.get('caption') or '')[:90]!r}")
    multi = sum(1 for r in rows if "2+ topics or places" in r[2])
    outside = sum(1 for r in rows if "found outside the collections" in r[2])
    print(f"\n{len(rows)} saves in the pilot: {outside} found outside the collections, {multi} with 2+ "
          f"topics or places, {len(rejected)} place matches the agent turned down.")


def prepare(args, saves, topics_known, collections, places, places_known, compiled, pilot, tags):
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
        if not old or old.get("source") != "model":  # a retag keeps the old tags until an answer lands
            tags[s["code"]] = entry(rule_topics, rule_cities, "rules", hints)
        todo.append((s, rule_topics, rule_cities, hints))
    write_yaml(TAGS, tags)
    if args.rules_only:
        log("tag_rules", scope=args.pilot or "all", already_tagged=kept, rule_tagged=len(todo))
        return 0
    if args.limit:
        todo = todo[:args.limit]
    todo.sort(key=lambda t: ((t[0].get("collections") or ["~"])[0], t[0]["code"]))
    batches = chunk([record(*t) for t in todo], args.batch_saves, args.batch_chars)

    out = batch_dir()
    os.makedirs(out, exist_ok=True)
    for old in glob.glob(os.path.join(out, "batch-*.json")):  # a new round replaces the last one
        os.remove(old)
    lists = {"topics": {slug: t.get("about") or t.get("label", "") for slug, t in topics_known.items()},
             "places": places_known}
    for i, recs in enumerate(batches, 1):
        name = f"batch-{i:03d}"
        path = os.path.join(out, name + ".json")
        write_json(path, {"batch": name, "answers": os.path.join(out, name + ".answers.json"), **lists,
                          "saves": recs})
        log("tag_batch", batch=name, saves=len(recs), chars=sum(size(r) for r in recs))
        print(path)
    log("tag_prepare", scope=args.pilot or "all", already_tagged=kept, saves=len(todo), batches=len(batches),
        batch_saves=args.batch_saves, batch_chars=args.batch_chars, dir=out)
    return 0


def merge(saves, topics_known, collections, places_known, compiled, tags, review):
    by_code = {s["code"]: s for s in saves}
    out = batch_dir()
    answered = missing = pending = done = 0
    for path in sorted(glob.glob(os.path.join(out, "batch-[0-9][0-9][0-9].json"))):
        with open(path, encoding="utf-8") as fh:
            batch = json.load(fh)
        ans_path = batch["answers"]
        merged_path = ans_path.replace(".answers.json", ".answers.merged.json")
        if os.path.exists(merged_path):  # merged after an earlier wave
            done += 1
            continue
        if not os.path.exists(ans_path):  # its agent has not run yet: wait, don't blame the saves
            pending += 1
            continue
        try:
            with open(ans_path, encoding="utf-8") as fh:
                answers = json.load(fh)
            answers = answers.get("answers", answers) if isinstance(answers, dict) else {}
            why = "no answer for this save"
        except ValueError as e:
            answers, why = {}, f"the answers file is not JSON: {e}"[:200]
        got = miss = 0
        for rec in batch["saves"]:
            code = rec["code"]
            s = by_code.get(code)
            if s is None:
                continue
            hints = place_hints(s, compiled)
            rule_topics, rule_cities = collection_tags(s, collections)
            try:
                if code not in answers:
                    raise ValueError(why)
                topics, cities, extra = apply_answer(answers[code], set(topics_known), set(places_known),
                                                     rule_topics, rule_cities)
            except ValueError as e:
                miss += 1
                review[code] = {"error": str(e)[:200]}
                log("tag_review", code=code, reason="answer_unusable")
                continue
            got += 1
            tags[code] = entry(topics, cities, "model", hints)
            if extra:
                review[code] = extra
                log("tag_review", code=code, reason="outside_lists")
            else:
                review.pop(code, None)
        answered += got
        missing += miss
        log("tag_merge_batch", batch=batch["batch"], saves=len(batch["saves"]), answered=got, missing=miss,
            chars=sum(size(r) for r in batch["saves"]))
        with open(os.path.join(out, "merged.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "batch": batch["batch"],
                                 "batch_file": path, "saves": len(batch["saves"]), "answered": got,
                                 "missing": miss, "chars": sum(size(r) for r in batch["saves"])}) + "\n")
        os.replace(ans_path, merged_path)
    write_yaml(TAGS, tags)
    write_yaml(REVIEW, review)
    log("tag_merge", answered=answered, missing=missing, batches_waiting=pending, batches_merged_before=done,
        review=len(review), out=os.path.join(home(), TAGS))
    print(f"merged {answered} answers ({missing} unusable); {pending} batches still waiting for their agent")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    action = ap.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true", help="rule tags, then batch files for the agent")
    action.add_argument("--merge", action="store_true", help="check the agents' answers into the tags")
    action.add_argument("--rules-only", action="store_true", help="rule tags only, no batches")
    action.add_argument("--report", action="store_true", help="print the pilot's tags; tag nothing")
    scope = ap.add_mutually_exclusive_group()
    scope.add_argument("--pilot", help="a pilot name from config/collections.yaml")
    scope.add_argument("--all", action="store_true", help="every save")
    ap.add_argument("--retag", action="store_true", help="batch saves the agent already tagged")
    ap.add_argument("--limit", type=int, default=0, help="at most this many saves this round (0 = no limit)")
    ap.add_argument("--batch-saves", type=int, default=BATCH_SAVES, help="most saves in one batch")
    ap.add_argument("--batch-chars", type=int, default=BATCH_CHARS, help="about the most characters in one batch")
    ap.add_argument("--saved", default=None, help="saves.json (default: the data repo's .cache)")
    args = ap.parse_args(argv)
    if (args.prepare or args.rules_only or args.report) and not (args.pilot or args.all):
        ap.error("--prepare, --rules-only and --report need --pilot NAME or --all")
    if args.report and not args.pilot:
        ap.error("--report needs --pilot")

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
        report(saves, tags, pilot, compiled)
        return 0
    if args.merge:
        return merge(saves, topics_known, collections, places_known, compiled, tags, review)
    return prepare(args, saves, topics_known, collections, places, places_known, compiled, pilot, tags)


if __name__ == "__main__":
    sys.exit(main())
