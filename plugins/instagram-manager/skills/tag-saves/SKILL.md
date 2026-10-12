---
name: tag-saves
description: Tag each Instagram save with its topics (travel, design, recipes...) and places (a city, state or country) — collection rules first, then Claude Haiku for the rest — into the data repo's data/tags.yaml. Use after import-saves, when someone wants their saves sorted by topic or city, or wants one pilot set of collections tagged before the rest.
---

# Tag Saves

Gives every save its **topics** and its **places**, from fixed lists in the data repo. One save
can have several of each: a family road trip post can be travel *and* parenting-kids, and sit in
two places. The tags feed the split, media and hub steps.

## How a save gets its tags

1. **Collections.** `config/collections.yaml` maps a collection name to topics and places. A save
   in a mapped collection always keeps those tags.
2. **Place names.** `config/places.yaml` lists names to look for in a caption (whole words, any
   case) and hashtags. A match is only a hint: it brings the save into a pilot, and the model is
   told about it. A sourdough post tagged with a beach town's hashtag stays a recipe.
3. **The model** (Claude Haiku) reads the caption, hashtags, creator, collections and the two
   above, and picks topics and places from the lists. Anything it names outside the lists goes to
   `data/tags-review.yaml` for a person to look at. It never goes into the tags.

The model answers through a forced tool call (`tag`), so its reply comes back as the four lists,
never as text to parse.

A save the model has tagged is skipped next time, so a rerun only pays for new saves. If a reply
can't be used, the save keeps its collection tags, the reason goes in the review file, and the
next run tries again. If the API turns the account down (out of credit, a bad key), the run stops
at once, keeps what it tagged, and prints the API's message; rerun once that is fixed.

## Steps

1. **Check the inputs.** `.cache/saves.json` exists (else run **import-saves**). `config/topics.yaml`,
   `config/collections.yaml` and `config/places.yaml` exist. Track the run with `TaskCreate`.
2. **Start with the pilot.** Each new step runs on a pilot first (`pilots:` in
   `collections.yaml`): its collections, plus any save with a place match for its places.
   ```bash
   python3 <plugin>/skills/tag-saves/scripts/tag_saves.py --pilot <name> --rules-only   # free: how big is it?
   python3 <plugin>/skills/tag-saves/scripts/tag_saves.py --pilot <name>                # the model
   ```
   Model calls are a fraction of a cent each, so a run just goes. The last line logs the total:
   `ev=tag_done tagged=160 failed=0 calls=160 tokens_in=... tokens_out=... review=12`.
3. **Spot-check.** `--report --pilot <name>` prints the pilot as a table. Rows that need a look
   come first: saves found outside the collections, and saves with 2 or more topics or places. Then
   it lists place matches the model turned down. Read 20 rows against their captions, and show
   them to the user before going wider.
4. **Fix the lists, not the tags.** A missed place goes in `places.yaml`. A topic or place
   suggested in `tags-review.yaml` is added to the config by a person. Then rerun; `--retag` asks
   the model again for saves it already tagged.
5. **Go wider** once the user has seen the pilot: `--all`. That is a change of scope, so ask with
   `AskUserQuestion`. The options: tag every save now (about one call per save, a few dollars,
   and the later steps can use every topic), or fix the lists and rerun the pilot first (cheap,
   but the other topics wait).
6. **Check.** The data repo's `make check` confirms every tag uses a known topic and place, and
   every code is a save in the export.

## What `tags.yaml` holds

```
<code>: {topics: [travel, parenting-kids], cities: [Example State], source: model, hints: [Example State]}
```

`source` is `model` or `rules` (collection tags only: `--rules-only`, or a reply that failed).
`hints` are the place matches. The file is sorted by code, so a rerun with no changes leaves git
clean.

## Example

An invented pilot, "coast": collections "Weekend Trips" → travel and "Example State". A save from
`@example_creator` outside that collection says "sunset at Example Bay" with `#examplebay`. Both
are listed for Example State in `places.yaml`, so the save comes into the pilot and the model
tags it travel / Example State. The report flags it as "found outside the collections".

## Known gap

A pilot only looks at its collections and at saves with a place match. A save about the place
whose caption names nothing on the list is missed until `--all` runs.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/tag_saves.py --pilot NAME --rules-only` | Collection tags and place matches only, no model | Sizing a pilot, or checking a config change, for free | `python3 scripts/tag_saves.py --pilot <name> --rules-only` |
| `scripts/tag_saves.py --pilot NAME` | Tags the pilot's saves with the model | The pilot run | `python3 scripts/tag_saves.py --pilot <name>` |
| `scripts/tag_saves.py --all` | Tags every save | After the pilot has been checked | `python3 scripts/tag_saves.py --all` |
| `scripts/tag_saves.py --report --pilot NAME` | The pilot as a table, what to check first | Spot-checking a run | `python3 scripts/tag_saves.py --report --pilot <name>` |
| `scripts/test_tag_saves.py` | Offline tests, canned model replies | After any change to the tagger | `python3 scripts/test_tag_saves.py` |

Other options: `--limit N` caps the model calls (a trial), `--workers N` (default 6), `--retag`.
