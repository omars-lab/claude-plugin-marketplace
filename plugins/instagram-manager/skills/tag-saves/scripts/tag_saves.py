#!/usr/bin/env python3
"""tag_saves.py — give each save its topics and its places: free rules here, the reading done by the
save-tagger subagent in batches. This script never calls a model.

    tag_saves.py --prepare --pilot NAME     rule tags, then batch files for the saves the agent must read
    tag_saves.py --prepare --all            the same for every save
    tag_saves.py --merge                    check the agents' answers and write them into the tags
    tag_saves.py --rules-only --pilot NAME  rule tags only, no batches (sizing a pilot, checking config)
    tag_saves.py --report --pilot NAME      the pilot's tags as a table; tags nothing
    tag_saves.py --moves                    the saves filed in the wrong collection, as a table
    options: --limit N (saves in this round), --retag (read again), --retag-topic SLUG (read again
             only the saves with that topic), --batch-saves N, --batch-chars N

Reads   $INSTAGRAM_HOME/.cache/saves.json (from import-saves)
        $INSTAGRAM_HOME/config/topics.yaml, collections.yaml, places.yaml
        $INSTAGRAM_HOME/data/places.yaml        looked-up places and aliases (from add_places.py)
        $INSTAGRAM_HOME/config/purposes.yaml    what a post is for (optional: shared/scripts/purposes.py)
Writes  $INSTAGRAM_HOME/data/tags.yaml          code → {topics[], cities[], purposes[], source, hints[]}
        $INSTAGRAM_HOME/data/tags-review.yaml   code → what the agent named outside the lists, or why
                                                its answer could not be used
        $INSTAGRAM_HOME/data/moves.yaml         code → {collections, not[], quote, fits, to[]}: saves the
                                                agent says sit in the wrong collection
        $INSTAGRAM_HOME/.cache/batches/tag/     batch-NNN.json (in), batch-NNN.answers.json (out),
                                                renamed .answers.merged.json once merged
        $INSTAGRAM_HOME/.cache/batches/tag/merged.jsonl   one line per merged batch, for the retro

How a save is tagged
  1. Collections (collections.yaml). A save in a mapped collection gets that entry's topics and
     cities. These are kept unless the agent says the save is misfiled (see Moves).
  2. Place hints (places.yaml). A listed name in the caption (whole words, any case) or a listed
     hashtag; and for every known place, its name run together as a hashtag (#examplefalls).
     A hint is not a tag: it pulls a save into a pilot, and it is shown to the agent.
  3. The save-tagger agent (Haiku) reads a batch: caption, hashtags, creator, collections and the
     two above for each save, and answers topics, places and purposes (what the post is for: eat,
     stay, get outdoors, see something) from the fixed lists. --merge keeps only names on the
     lists; anything else goes to tags-review.yaml, never into the tags.
  Final tags = collection tags + the agent's, plus every place each one sits in (a city brings
  its state: places.py). "cities" means places: a city, a park, a state or a country. A name the
  agent gives that is not listed yet goes to review; add_places.py looks it up, and the next
  --merge moves it into the tags.

Moves
  The agent may say a collection's tags are wrong for a save ("misfiled": the tags, and words
  copied from the caption that show it). With a real quote, the save goes on data/moves.yaml with
  up to three collections that fit better. Both tags stay until a new export shows the save has
  left the flagged collection; then the wrong tags are dropped and the move comes off the list.
  Without a real quote, the claim goes to review and nothing changes.

Batches are cut by size: saves are added until the next one would pass --batch-chars characters
(about 4 characters a token) or --batch-saves saves. Captions are cut at 2,500 characters, so one
save always fits. Saves are sorted by collection, so a batch holds similar posts.

A save the agent has tagged is not batched again (unless --retag). One it tagged before it was asked
for purposes (no `purposes` in its tags) is read once more, keeping the topics and places it has:
they go to the agent under `already`, and the merge keeps everything under `already`. So is one that
now has a place hint it was not read with (a place added to the list since, say). A --retag
sends only the collection's tags as `already`, so a fresh answer can drop a wrong place.
--retag-topic SLUG does the same for only the saves tagged SLUG: after new topics are added, the
saves under `other` are read again with the longer list.
A save with no usable answer
keeps its rule tags, the reason goes in the review file, and the next --prepare batches it again.

Fixing by hand
  A person who corrects a save's tags in data/tags.yaml adds `by: hand` to the entry. That entry is
  final: no round batches it again (--retag included), the merge ignores any answer for it, the
  collection's tags are not added back, the review list adds no place to it, and a finished move
  leaves its tags as they are. Without the mark, the next round can undo the fix.

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

from home import cache, home, read_saves, need_topics  # noqa: E402
from log import log  # noqa: E402
from pilot import in_pilot  # noqa: E402
from places import Places  # noqa: E402
from purposes import load as load_purposes  # noqa: E402
from quote import quote_ok  # noqa: E402

TAGS = os.path.join("data", "tags.yaml")
REVIEW = os.path.join("data", "tags-review.yaml")
MOVES = os.path.join("data", "moves.yaml")
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
    return topics, coll.get("collections") or {}, coll.get("pilots") or {}, Places.load()


def collection_tags(save, collections):
    topics, cities = set(), set()
    for name in save.get("collections") or []:
        rule = collections.get(name) or {}
        topics |= set(rule.get("topics") or [])
        cities |= set(rule.get("cities") or [])
    return topics, cities


def by_hand(t):
    """True for a tags entry a person wrote or corrected (`by: hand`); no round changes it."""
    return isinstance(t, dict) and t.get("by") == "hand"


def run_together(name):
    """A name as a hashtag would write it: "Example Falls" → "examplefalls"."""
    return re.sub(r"[\W_]+", "", name).lower()


def compile_places(places):
    """Per place: a caption pattern and the hashtags that hint at it. A hand-listed place
    (config/places.yaml) matches its names in the caption and its hashtags. Every place, looked-up
    ones and aliases too, also matches its name run together as a hashtag (#examplefalls), and a
    looked-up name of two words or more matches the caption. One-word looked-up names do not match
    the caption: too many are also common words. A hand-listed place marked `common_word: true` (a
    town named like an everyday word) is not a hashtag on its own name either, only on the
    `hashtags` it lists."""
    config, extra = places.config, {}
    for name in places.known:
        extra.setdefault(name, set()).add(name)
    for name, to in places.aliases.items():
        if to in places.known and "," not in name:
            extra.setdefault(to, set()).add(name)
    out = []
    for place in sorted(set(config) | set(extra)):
        p = config.get(place) if isinstance(config.get(place), dict) else {}
        names = set(n for n in p.get("names") or [] if n.strip())
        if place not in config:
            names |= {n for n in extra.get(place, ()) if len(n.split()) > 1}
        names = sorted(names, key=len, reverse=True)
        rx = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(n) for n in names) + r")(?!\w)", re.I) if names else None
        tags = {h.lower().lstrip("#") for h in p.get("hashtags") or []}
        tags |= {run_together(n) for n in extra.get(place, ()) | set(p.get("names") or [])} - {""}
        if p.get("common_word"):
            tags = {h.lower().lstrip("#") for h in p.get("hashtags") or []}
        out.append((place, rx, tags))
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


def apply_answer(d, topics_known, places, rule_topics, rule_cities, purposes_known=None):
    """(topics, cities, purposes, review) from one answer. review is None when nothing needs a look.
    A place the agent named that means a listed place counts as it; every place brings the places
    it sits in. purposes is None when the agent was not asked (purposes_known is None); asked, an
    answer without any is an empty list."""
    if not isinstance(d, dict) or not isinstance(d.get("topics"), list) or not isinstance(d.get("cities", []), list):
        raise ValueError("answer is not {topics: [...], cities: [...]}")
    said_topics = [t for t in d.get("topics") or [] if isinstance(t, str)]
    said_places = [c for c in (d.get("cities") or []) + (d.get("other_places") or []) if isinstance(c, str)]
    topics = {t for t in said_topics if t in topics_known} | rule_topics
    cities = places.fold({places.resolve(c) for c in said_places if places.resolve(c)} | rule_cities)
    other_topics = sorted({t for t in said_topics if t not in topics_known}
                          | {t for t in d.get("other_topics") or [] if isinstance(t, str)})
    other_places = sorted({c for c in said_places if not places.resolve(c)})
    if not topics:
        topics = {"other"} if "other" in topics_known else set()
    elif len(topics) > 1:
        topics.discard("other")  # an older "other" kept under `already` gives way to a real topic
    purposes = None
    if purposes_known is not None:
        said = d.get("purposes") if isinstance(d.get("purposes"), list) else []
        purposes = {x for x in said if isinstance(x, str) and x in purposes_known}
    review = {k: v for k, v in (("other_topics", other_topics), ("other_places", other_places)) if v}
    return topics, cities, purposes, review or None


def misfiled(d, save, rule_topics, rule_cities, topics, cities):
    """A move from one answer, or None. The agent may say a tag that came from the save's collection
    is wrong for it ("not"), with words copied from the caption that show it. The tag stays until the
    save is moved in the app; the move goes on the moves list for the owner to do or ignore."""
    m = d.get("misfiled") if isinstance(d, dict) else None
    if not isinstance(m, dict):
        return None
    wrong = sorted({x for x in m.get("not") or [] if isinstance(x, str) and x in rule_topics | rule_cities})
    quote = m.get("quote") if isinstance(m.get("quote"), str) else ""
    if not wrong:
        return None
    if not quote_ok(quote, save.get("caption") or ""):
        return {"error": "misfiled, but its quote is not in the caption", "not": wrong}
    return {"collections": save.get("collections") or [], "not": wrong, "quote": quote.strip()[:300],
            "fits": {"topics": sorted(topics - set(wrong)), "cities": sorted(cities - set(wrong))}}


def suggest(move, collections, places, current):
    """Up to three collections the save fits better: a collection whose city it is about, the most
    specific first; with no city, a collection whose topic it is about and that names no city."""
    fit_cities, fit_topics = set(move["fits"]["cities"]), set(move["fits"]["topics"])
    scored = []
    for name, rule in collections.items():
        if name in current:
            continue
        rc, rt = set(rule.get("cities") or []), set(rule.get("topics") or [])
        if rc & fit_cities:
            scored.append((-max(places.depth(c) for c in rc & fit_cities), name))
        elif not rc and not fit_cities and rt & fit_topics:
            scored.append((0, name))
    return [name for _, name in sorted(scored)[:3]]


def settle_moves(by_code, tags, moves, collections, places):
    """A save that has left a collection it was flagged in has been moved: drop the tags that came
    only from that collection, and take it off the list."""
    done = 0
    for code, m in list(moves.items()):
        s = by_code.get(code)
        if s is None or not set(m["collections"]) - set(s.get("collections") or []):
            continue
        rule_topics, rule_cities = collection_tags(s, collections)
        t = tags.get(code)
        if t and not by_hand(t):
            gone = {x for x in m["not"] if x not in rule_topics | rule_cities}
            topics = set(t["topics"]) - gone
            base = set(t["cities"]) - places.fold(gone & set(t["cities"]))
            cities = places.fold(base | rule_cities)
            tags[code] = entry(topics or {"other"}, cities, t["source"], t.get("hints"), t.get("purposes"))
        del moves[code]
        done += 1
        log("move_done", code=code)
    return done


def recheck_review(tags, review, places):
    """Suggested places that are listed now (add_places.py added them) move into the tags."""
    moved = 0
    for code, r in list(review.items()):
        said = r.get("other_places") if isinstance(r, dict) else None
        if not said or code not in tags or by_hand(tags[code]):
            continue
        hit = {places.resolve(p) for p in said} - {None}
        if not hit:
            continue
        t = tags[code]
        tags[code] = entry(set(t["topics"]), places.fold(set(t["cities"]) | hit), t["source"], t.get("hints"),
                           t.get("purposes"))
        rest = [p for p in said if not places.resolve(p)]
        if rest:
            r["other_places"] = rest
        else:
            r.pop("other_places")
        if not r:
            del review[code]
        moved += 1
    return moved


def entry(topics, cities, source, hints, purposes=None):
    """One save's tags. purposes None (never asked) leaves the key out; [] means asked, none fit."""
    e = {"topics": sorted(topics), "cities": sorted(cities), "source": source}
    if purposes is not None:
        e["purposes"] = sorted(purposes)
    if hints:
        e["hints"] = sorted(hints)
    return e


def most_specific(cities, places):
    """The places that hold no other place in the list: a town and its state count as one."""
    inside = {p for c in cities for p in places.chain(c)}
    return [c for c in cities if c not in inside]


def report(saves, tags, pilot, compiled, places):
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
        if len(tag["topics"]) > 1 or len(most_specific(tag["cities"], places)) > 1:
            notes.append("2+ topics or places")
        rows.append((s, tag, notes))
    print("| code | collections | topics | places | by | look at |")
    print("|---|---|---|---|---|---|")
    for s, tag, notes in sorted(rows, key=lambda r: (not r[2], r[0]["code"])):
        print(f"| {s['code']} | {', '.join(s.get('collections') or []) or '-'} | {', '.join(tag['topics'])} "
              f"| {', '.join(tag['cities'])} | {tag.get('by') or tag['source']} | {'; '.join(notes)} |")
    if rejected:
        print("\nA place name matched, but the agent did not put these in the pilot's places:")
        for s, tag in rejected:
            print(f"- {s['code']} hints {', '.join(tag.get('hints') or [])} → {', '.join(tag['topics'])} "
                  f"/ {', '.join(tag['cities']) or 'no place'}: {(s.get('caption') or '')[:90]!r}")
    multi = sum(1 for r in rows if "2+ topics or places" in r[2])
    outside = sum(1 for r in rows if "found outside the collections" in r[2])
    print(f"\n{len(rows)} saves in the pilot: {outside} found outside the collections, {multi} with 2+ "
          f"topics or places, {len(rejected)} place matches the agent turned down.")


def print_moves(saves, moves):
    """The moves list as a table: where each save is, where it fits, and the words that show it."""
    by_code = {s["code"]: s for s in saves}
    print("| post | in collection | not about | move to | the caption says |")
    print("|---|---|---|---|---|")
    for code, m in sorted(moves.items(), key=lambda kv: (kv[1]["collections"], kv[0])):
        url = (by_code.get(code) or {}).get("url") or f"https://www.instagram.com/p/{code}/"
        print(f"| [{code}]({url}) | {', '.join(m['collections'])} | {', '.join(m['not'])} "
              f"| {', '.join(m.get('to') or []) or '(no collection fits)'} | {m['quote'][:80]!r} |")
    print(f"\n{len(moves)} saves to move")
    return 0


def prepare(args, saves, topics_known, purposes_known, collections, places, compiled, pilot, tags, moves):
    waiting = sorted(glob.glob(os.path.join(batch_dir(), "batch-[0-9][0-9][0-9].answers.json")))
    if waiting and not args.rules_only:  # a new round clears the folder, and these answers with it
        log("tag_prepare_refused", answers_waiting=len(waiting))
        sys.exit(f"{len(waiting)} answers files are not merged yet ({', '.join(os.path.basename(w) for w in waiting)}). "
                 "Run the merge first (make tag-merge), then start the new round.")
    settle_moves({s["code"]: s for s in saves}, tags, moves, collections, places)
    todo, kept = [], 0
    for s in saves:
        hints = place_hints(s, compiled)
        if pilot and not in_pilot(s, None, pilot, hints):
            continue
        old = tags.get(s["code"])
        if by_hand(old):  # a person's fix: never batched, never topped up with the rule tags
            kept += 1
            continue
        rule_topics, rule_cities = collection_tags(s, collections)
        model = bool(old) and old.get("source") == "model"
        retag = args.retag or (model and args.retag_topic in (old.get("topics") or []))
        if model and not retag:
            tags[s["code"]] = entry(set(old["topics"]) | rule_topics, places.fold(set(old["cities"]) | rule_cities),
                                    "model", hints, old.get("purposes"))
            new_hints = hints - set(old.get("hints") or []) - set(tags[s["code"]]["cities"])
            if "purposes" in old and not new_hints:
                kept += 1
                continue
            # tagged before purposes were asked, or a place hint it has not been read with: read
            # again, keeping what it has. The old hints stay until the answer lands.
            if new_hints:
                tags[s["code"]] = entry(set(tags[s["code"]]["topics"]), set(tags[s["code"]]["cities"]), "model",
                                        old.get("hints"), old.get("purposes"))
            todo.append((s, set(tags[s["code"]]["topics"]), set(tags[s["code"]]["cities"]), hints))
            continue
        if not model:  # a retag keeps the old tags until an answer lands
            tags[s["code"]] = entry(rule_topics, places.fold(rule_cities), "rules", hints)
        todo.append((s, rule_topics, rule_cities, hints))
    write_yaml(TAGS, tags)
    write_yaml(MOVES, moves)
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
             "purposes": {slug: p.get("about") or p.get("label", "") for slug, p in purposes_known.items()},
             "places": places.listing()}
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


def merge(saves, topics_known, purposes_known, collections, places, compiled, tags, review, moves):
    by_code = {s["code"]: s for s in saves}
    out = batch_dir()
    answered = missing = pending = done = kept_hand = 0
    rechecked = recheck_review(tags, review, places)
    settled = settle_moves(by_code, tags, moves, collections, places)
    for path in sorted(glob.glob(os.path.join(out, "batch-[0-9][0-9][0-9].json"))):
        with open(path, encoding="utf-8") as fh:
            batch = json.load(fh)
        ans_path = batch["answers"]
        merged_path = ans_path.replace(".answers.json", ".answers.merged.json")
        if os.path.exists(merged_path):
            if not os.path.exists(ans_path):  # merged after an earlier wave
                done += 1
                continue
            # its agent wrote the answers again after they were merged: the new file wins
            log("tag_merge_rewritten", batch=batch["batch"])
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
            if by_hand(tags.get(code)):  # fixed by a person after this batch was made
                kept_hand += 1
                continue
            hints = place_hints(s, compiled)
            rule_topics, rule_cities = collection_tags(s, collections)
            already = rec.get("already") or {}  # the agent keeps these; so does the merge
            keep_topics = rule_topics | (set(already.get("topics") or []) & set(topics_known))
            keep_cities = rule_cities | ({places.resolve(c) for c in already.get("cities") or []} - {None})
            asked = set(purposes_known) if "purposes" in batch else None  # older batches did not ask
            try:
                if code not in answers:
                    raise ValueError(why)
                topics, cities, purposes, extra = apply_answer(answers[code], set(topics_known), places,
                                                               keep_topics, keep_cities, asked)
            except ValueError as e:
                miss += 1
                review[code] = {"error": str(e)[:200]}
                log("tag_review", code=code, reason="answer_unusable")
                continue
            got += 1
            tags[code] = entry(topics, cities, "model", hints, purposes)
            move = misfiled(answers[code], s, rule_topics, places.fold(rule_cities), topics, cities)
            if move and "error" in move:
                extra = {**(extra or {}), "misfiled": move}
            elif move:
                moves[code] = {**move, "to": suggest(move, collections, places, set(s.get("collections") or []))}
                log("tag_move", code=code, wrong=",".join(move["not"]))
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
    write_yaml(MOVES, moves)
    log("tag_merge", answered=answered, missing=missing, batches_waiting=pending, batches_merged_before=done,
        review=len(review), places_from_review=rechecked, moves=len(moves), moves_done=settled,
        kept_hand=kept_hand, out=os.path.join(home(), TAGS))
    print(f"merged {answered} answers ({missing} unusable); {pending} batches still waiting for their agent")
    if rechecked:
        print(f"{rechecked} saves got a place from the review list")
    if kept_hand:
        print(f"{kept_hand} answers left out: those saves' tags were fixed by hand")
    print(f"{len(moves)} saves on the moves list ({settled} moved since the last run)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    action = ap.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true", help="rule tags, then batch files for the agent")
    action.add_argument("--merge", action="store_true", help="check the agents' answers into the tags")
    action.add_argument("--rules-only", action="store_true", help="rule tags only, no batches")
    action.add_argument("--report", action="store_true", help="print the pilot's tags; tag nothing")
    action.add_argument("--moves", action="store_true", help="print the saves filed in the wrong collection")
    scope = ap.add_mutually_exclusive_group()
    scope.add_argument("--pilot", help="a pilot name from config/collections.yaml")
    scope.add_argument("--all", action="store_true", help="every save")
    ap.add_argument("--retag", action="store_true", help="batch saves the agent already tagged")
    ap.add_argument("--retag-topic", metavar="SLUG",
                    help="batch again only the tagged saves with this topic (after adding topics, say)")
    ap.add_argument("--limit", type=int, default=0, help="at most this many saves this round (0 = no limit)")
    ap.add_argument("--batch-saves", type=int, default=BATCH_SAVES, help="most saves in one batch")
    ap.add_argument("--batch-chars", type=int, default=BATCH_CHARS, help="about the most characters in one batch")
    ap.add_argument("--saved", default=None, help="saves.json (default: the data repo's .cache)")
    args = ap.parse_args(argv)
    if (args.prepare or args.rules_only or args.report) and not (args.pilot or args.all):
        ap.error("--prepare, --rules-only and --report need --pilot NAME or --all")
    if args.report and not args.pilot:
        ap.error("--report needs --pilot")

    saves = read_saves(args.saved)["saves"]
    topics_known, collections, pilots, places = load_config()
    if args.prepare or args.rules_only or args.merge:
        need_topics(topics_known)
    purposes_known = load_purposes()
    compiled = compile_places(places)
    pilot = None
    if args.pilot:
        if args.pilot not in pilots:
            sys.exit(f"no pilot {args.pilot!r} in config/collections.yaml (have: {', '.join(pilots) or 'none'})")
        pilot = pilots[args.pilot]
    tags = load_yaml(TAGS)
    review = load_yaml(REVIEW)
    moves = load_yaml(MOVES)

    if args.report:
        report(saves, tags, pilot, compiled, places)
        return 0
    if args.moves:
        return print_moves(saves, moves)
    if args.merge:
        return merge(saves, topics_known, purposes_known, collections, places, compiled, tags, review, moves)
    return prepare(args, saves, topics_known, purposes_known, collections, places, compiled, pilot, tags, moves)


if __name__ == "__main__":
    sys.exit(main())
