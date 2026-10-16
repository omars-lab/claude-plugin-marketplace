#!/usr/bin/env python3
"""split_saves.py — split each saved post that is not travel (a recipe, a design idea, a business
tip) into the things its caption names, each with the caption's own words for it. The reading is
done by the save-splitter agent in batches; this script never calls a model.

    split_saves.py --prepare --pilot NAME   batch files for the pilot's non-travel saves
    split_saves.py --prepare --all          the same for every tagged save
    split_saves.py --merge                  check the agents' answers and write the items
    options: --limit N (saves in this round), --redo (read saves already split again),
             --batch-saves N, --batch-chars N

Reads   $INSTAGRAM_HOME/.cache/saves.json          captions and creators (from import-saves)
        $INSTAGRAM_HOME/config/topics.yaml         the topics; `travel` is left to the spot steps
        $INSTAGRAM_HOME/config/collections.yaml    the pilots
        $INSTAGRAM_HOME/data/tags.yaml             each save's topics (from tag-saves)
Writes  $INSTAGRAM_HOME/data/items.yaml            code → {topics: [split for], items: [{topic, kind,
                                                   name, quote}]}; `items: []` when the caption names
                                                   nothing specific
        $INSTAGRAM_HOME/data/items-review.yaml     code → [{why, ...}]: items that failed a check, or
                                                   why a save's answer could not be used
        $INSTAGRAM_HOME/.cache/batches/split/      batch-NNN.json (in), batch-NNN.answers.json (out),
                                                   renamed .answers.merged.json once merged, and
                                                   merged.jsonl (one line per merged batch)
--prepare writes only the batch files; nothing in data/ changes until --merge.

Which saves go in
  A save goes in when its tags hold a topic other than travel (travel's items are its spots, from
  resolve-post-location). It is skipped once data/items.yaml has an entry for it that was split for
  the same topics, `items: []` included, so a rerun only reads new saves. A save whose topics
  changed since (the tagger added one) is read again, whole. --redo reads every save again.

What an item is, by topic (the kind the agent picks; KINDS below, or `item_kinds:` on a topic in
config/topics.yaml)
  recipes: a dish or drink;  design: a subject or a technique;  business and 3D prints: an idea or
  a product;  parenting, other and any topic not known here: a one-line note.

What the merge checks, per item
  1. `quote` is in the caption word for word (shared/scripts/quote.py). If not: review, never data.
     No made-up items.
  2. `topic` is one of the save's own non-travel topics. If not: review.
  3. `name` is there. `kind` must be one of the topic's kinds; any other word becomes the topic's
     first kind (a label is not worth losing a checked item over).
  The same name twice under one topic is kept once. A save with no usable answer (none, not JSON,
  the wrong shape) gets no entry, its reason goes in the review file, and the next --prepare
  batches it again. An item that failed a check is not read again: a person looks at the review.

Fixing by hand
  Edit a save's entry in data/items.yaml and add `by: hand`. That entry is final: no round batches
  the save again (--redo included) and the merge ignores any answer for it. Deleting an entry sends
  the save back to the agent on the next round.

A new --prepare removes the last round's batch files, so it stops while any answers are not merged
yet. Rerunning --merge is safe: a merged batch is never merged twice, and the files are written
sorted by code, so a merge with nothing new changes nothing.
"""

import argparse
import glob
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.join(HERE, os.pardir, os.pardir)
sys.path.insert(0, os.path.join(SKILLS, os.pardir, "shared", "scripts"))
sys.path.insert(0, os.path.join(SKILLS, "tag-saves", "scripts"))
sys.path.insert(0, os.path.join(SKILLS, "resolve-post-location", "scripts"))

from home import cache, home  # noqa: E402
from log import log  # noqa: E402
from pilot import in_pilot  # noqa: E402
from places import load_yaml  # noqa: E402
from quote import norm, quote_ok  # noqa: E402
from resolve_post_location import write_yaml  # noqa: E402
from tag_saves import BATCH_CHARS, BATCH_SAVES, CAPTION_CHARS, by_hand, chunk, size, write_json  # noqa: E402

ITEMS = os.path.join("data", "items.yaml")
REVIEW = os.path.join("data", "items-review.yaml")
TAGS = os.path.join("data", "tags.yaml")
TRAVEL = "travel"
NAME_CHARS = 120
QUOTE_CHARS = 300

NOTE = {"note": "one line saying what the post tells you, in your own short words"}
# The kinds of item each topic gives, slug → {kind: what counts}. A topic not listed here is matched
# by a word in its slug (GUESS), then falls back to a one-line note. `item_kinds:` on a topic in
# config/topics.yaml replaces both.
KINDS = {
    "recipes-coffee": {"dish": "a dish or drink to make (a recipe, a bake, a coffee drink)"},
    "islamic-design": {"subject": "a thing shown or made (a pattern, a building, a tile, a piece of "
                                  "calligraphy)",
                       "technique": "a way of making or drawing it (a construction, a method, a tool)"},
    "3d-printing": {"idea": "a thing to make or a way to make it", "product": "a printer, a material, a "
                                                                              "tool or a model to get"},
    "business": {"idea": "a tip or plan for starting or running a business",
                 "product": "a product, tool or service named"},
    "parenting-kids": NOTE,
    "other": NOTE,
}
GUESS = (("recipe", "recipes-coffee"), ("cook", "recipes-coffee"), ("design", "islamic-design"),
         ("print", "3d-printing"), ("business", "business"))


def batch_dir():
    return cache("batches", "split")


def kinds_for(slug, conf=None):
    """{kind: what counts} for one topic."""
    own = (conf or {}).get("item_kinds") if isinstance(conf, dict) else None
    if isinstance(own, dict) and own:
        return {str(k): str(v) for k, v in own.items()}
    if slug in KINDS:
        return KINDS[slug]
    for word, like in GUESS:
        if word in slug:
            return KINDS[like]
    return NOTE


def own_topics(tag, topics_known):
    """The save's topics this step splits for: every known topic but travel."""
    if not isinstance(tag, dict):
        return []
    return sorted({t for t in tag.get("topics") or [] if isinstance(t, str) and t != TRAVEL
                   and (not topics_known or t in topics_known)})


def record(save, topics):
    """One save as the agent sees it."""
    owner = save.get("owner") or {}
    return {"code": save["code"], "creator": f"@{owner.get('username', '')} ({owner.get('name', '')})",
            "topics": topics, "hashtags": save.get("hashtags") or [],
            "caption": (save.get("caption") or "")[:CAPTION_CHARS]}


def one_line(v, cap):
    return re.sub(r"\s+", " ", v).strip()[:cap] if isinstance(v, str) else ""


def check_items(answer, caption, own, topics_conf):
    """(items, review) from one save's answer. Raises ValueError when the answer is not a list of
    items (the save then has no usable answer)."""
    raw = answer.get("items") if isinstance(answer, dict) else answer
    if not isinstance(raw, list):
        raise ValueError("answer is not a list of items")
    items, review, seen = [], [], set()
    for it in raw:
        if not isinstance(it, dict):
            review.append({"why": "an item is not {topic, kind, name, quote}", "said": str(it)[:200]})
            continue
        topic, kind = it.get("topic"), it.get("kind")
        name, quote = one_line(it.get("name"), NAME_CHARS), one_line(it.get("quote"), QUOTE_CHARS)
        out = {"topic": topic if isinstance(topic, str) else str(topic), "kind": kind, "name": name, "quote": quote}
        if topic not in own:
            review.append({"why": f"topic {topic} is not one of this save's topics ({', '.join(own)})", **out})
            continue
        if not quote_ok(quote, caption):
            review.append({"why": "quote is not in the caption", **out})
            continue
        if not name:
            review.append({"why": "no name", **out})
            continue
        kinds = kinds_for(topic, topics_conf.get(topic))
        out["kind"] = kind if kind in kinds else next(iter(kinds))
        key = (topic, norm(name))
        if key in seen:
            continue
        seen.add(key)
        items.append(out)
    return items, review


def load_saves(path):
    with open(path or cache("saves.json"), encoding="utf-8") as fh:
        return json.load(fh)["saves"]


def prepare(args, saves, topics_conf, pilot, tags, items):
    waiting_answers = sorted(glob.glob(os.path.join(batch_dir(), "batch-[0-9][0-9][0-9].answers.json")))
    if waiting_answers:  # a new round clears the folder, and these answers with it
        log("split_prepare_refused", answers_waiting=len(waiting_answers))
        sys.exit(f"{len(waiting_answers)} answers files are not merged yet "
                 f"({', '.join(os.path.basename(w) for w in waiting_answers)}). "
                 "Run the merge first (make split-merge), then start the new round.")
    todo, done, hand, from_rules, changed = [], 0, 0, 0, 0
    for s in saves:
        tag = tags.get(s["code"])
        if pilot and not in_pilot(s, tag, pilot):
            continue
        own = own_topics(tag, topics_conf)
        if not own:
            continue
        old = items.get(s["code"])
        if by_hand(old):  # a person's fix: never batched again
            hand += 1
            continue
        if isinstance(old, dict) and not args.redo:
            if sorted(old.get("topics") or []) == own:
                done += 1
                continue
            changed += 1  # its topics changed since it was split: read again, whole
        if tag.get("source") == "rules" and not by_hand(tag):
            from_rules += 1
        todo.append((s, own))
    waiting = len(todo)
    if args.limit:
        todo = todo[:args.limit]
    todo.sort(key=lambda t: (t[1][0], t[0]["code"]))  # similar posts sit together
    batches = chunk([record(s, own) for s, own in todo], args.batch_saves, args.batch_chars)

    out = batch_dir()
    os.makedirs(out, exist_ok=True)
    for old in glob.glob(os.path.join(out, "batch-*.json")):  # a new round replaces the last one
        os.remove(old)
    asked = sorted({t for _, own in todo for t in own})
    lists = {t: {"about": (topics_conf.get(t) or {}).get("about") or (topics_conf.get(t) or {}).get("label", ""),
                 "kinds": kinds_for(t, topics_conf.get(t))} for t in asked}
    for i, recs in enumerate(batches, 1):
        name = f"batch-{i:03d}"
        path = os.path.join(out, name + ".json")
        write_json(path, {"batch": name, "answers": os.path.join(out, name + ".answers.json"), "topics": lists,
                          "saves": recs})
        log("split_batch", batch=name, saves=len(recs), chars=sum(size(r) for r in recs))
        print(path)
    log("split_prepare", scope=args.pilot or "all", waiting=waiting, saves=len(todo), batches=len(batches),
        already_split=done, topics_changed=changed, by_hand=hand, rule_tagged_only=from_rules,
        batch_saves=args.batch_saves, batch_chars=args.batch_chars, dir=out)
    print(f"{waiting} non-travel saves waiting to be split; {len(todo)} in this round, in {len(batches)} "
          f"batches ({done} split before, {hand} fixed by hand)", file=sys.stderr)
    return 0


def merge(saves, topics_conf, tags, items, review):
    by_code = {s["code"]: s for s in saves}
    out = batch_dir()
    answered = missing = pending = merged_before = kept_hand = n_items = n_review = 0
    for path in sorted(glob.glob(os.path.join(out, "batch-[0-9][0-9][0-9].json"))):
        with open(path, encoding="utf-8") as fh:
            batch = json.load(fh)
        ans_path = batch["answers"]
        merged_path = ans_path.replace(".answers.json", ".answers.merged.json")
        if os.path.exists(merged_path):
            if not os.path.exists(ans_path):  # merged after an earlier wave
                merged_before += 1
                continue
            # its agent wrote the answers again after they were merged: the new file wins
            log("split_merge_rewritten", batch=batch["batch"])
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
            if by_hand(items.get(code)):  # fixed by a person after this batch was made
                kept_hand += 1
                continue
            own = own_topics(tags.get(code), topics_conf) or sorted(rec.get("topics") or [])
            try:
                if code not in answers:
                    raise ValueError(why)
                kept, bad = check_items(answers[code], s.get("caption") or "", own, topics_conf)
            except ValueError as e:
                miss += 1
                review[code] = [{"why": str(e)[:200]}]
                log("split_review", code=code, reason="answer_unusable")
                continue
            got += 1
            items[code] = {"topics": own, "items": kept}
            n_items += len(kept)
            for b in bad:
                log("split_review", code=code, reason=re.sub(r"\W+", "_", b["why"].split(" (")[0])[:40])
            if bad:
                review[code] = bad
                n_review += len(bad)
            else:
                review.pop(code, None)
        answered += got
        missing += miss
        log("split_merge_batch", batch=batch["batch"], saves=len(batch["saves"]), answered=got, missing=miss,
            chars=sum(size(r) for r in batch["saves"]))
        with open(os.path.join(out, "merged.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "batch": batch["batch"],
                                 "batch_file": path, "saves": len(batch["saves"]), "answered": got,
                                 "missing": miss, "chars": sum(size(r) for r in batch["saves"])}) + "\n")
        os.replace(ans_path, merged_path)
    write_yaml(ITEMS, items)
    write_yaml(REVIEW, review)
    log("split_merge", answered=answered, missing=missing, items=n_items, items_to_review=n_review,
        batches_waiting=pending, batches_merged_before=merged_before, kept_hand=kept_hand,
        out=os.path.join(home(), ITEMS))
    print(f"merged {answered} answers ({missing} unusable), {n_items} items kept and {n_review} sent to "
          f"review; {pending} batches still waiting for their agent")
    if kept_hand:
        print(f"{kept_hand} answers left out: those saves' items were fixed by hand")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    action = ap.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true", help="batch files for the save-splitter agents")
    action.add_argument("--merge", action="store_true", help="check the agents' answers into data/items.yaml")
    scope = ap.add_mutually_exclusive_group()
    scope.add_argument("--pilot", help="a pilot name from config/collections.yaml")
    scope.add_argument("--all", action="store_true", help="every tagged save")
    ap.add_argument("--redo", action="store_true", help="batch saves that are already split")
    ap.add_argument("--limit", type=int, default=0, help="at most this many saves this round (0 = no limit)")
    ap.add_argument("--batch-saves", type=int, default=BATCH_SAVES, help="most saves in one batch")
    ap.add_argument("--batch-chars", type=int, default=BATCH_CHARS, help="about the most characters in one batch")
    ap.add_argument("--saved", default=None, help="saves.json (default: the data repo's .cache)")
    args = ap.parse_args(argv)
    if args.prepare and not (args.pilot or args.all):
        ap.error("--prepare needs --pilot NAME or --all")

    saves = load_saves(args.saved)
    topics_conf = load_yaml(os.path.join("config", "topics.yaml")).get("topics") or {}
    tags = load_yaml(TAGS)
    items = load_yaml(ITEMS)
    if args.merge:
        return merge(saves, topics_conf, tags, items, load_yaml(REVIEW))
    pilot = None
    if args.pilot:
        pilots = load_yaml(os.path.join("config", "collections.yaml")).get("pilots") or {}
        if args.pilot not in pilots:
            sys.exit(f"no pilot {args.pilot!r} in config/collections.yaml (have: {', '.join(pilots) or 'none'})")
        pilot = pilots[args.pilot]
    return prepare(args, saves, topics_conf, pilot, tags, items)


if __name__ == "__main__":
    sys.exit(main())
