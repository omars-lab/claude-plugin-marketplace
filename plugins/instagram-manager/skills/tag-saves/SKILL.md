---
name: tag-saves
description: Tag each Instagram save with its topics (travel, design, recipes...) and places (a city, state or country) — collection rules first, then save-tagger agents reading batches of saves — into the data repo's data/tags.yaml. Use after import-saves, when someone wants their saves sorted by topic or city, or wants one pilot set of collections tagged before the rest.
---

# Tag Saves

Gives every save its **topics** and its **places**, from fixed lists in the data repo. One save
can have several of each: a family road trip post can be travel *and* parenting-kids, and sit in
two places. The tags feed the split, media and hub steps.

## How a save gets its tags

1. **Collections.** `config/collections.yaml` maps a collection name to topics and places. A save
   in a mapped collection always keeps those tags.
2. **Place names.** `config/places.yaml` lists names to look for in a caption (whole words, any
   case) and hashtags. A match is only a hint: it brings the save into a pilot, and the agent is
   told about it. A sourdough post tagged with a beach town's hashtag stays a recipe.
3. **The `save-tagger` agent** (Haiku, `agents/save-tagger.md`) reads a batch of saves — caption,
   hashtags, creator, collections and the two above — and picks topics and places from the lists.
   Anything it names outside the lists goes to `data/tags-review.yaml` for a person to look at. It
   never goes into the tags.

**No script calls a model.** The script writes batch files and checks the answers; this session
starts the agents. They run on the plan Claude Code is logged in with, so there is no API key.

A save an agent has tagged is skipped next time, so a rerun only reads new saves. If an answer
is missing or unusable, the save keeps its collection tags, the reason goes in the review file,
and the next round batches it again.

## Batches: how big, and why

`--prepare` sorts the saves (by first collection, then code, so similar posts sit together) and
cuts them into batches of **at most 40 saves or about 60,000 characters** (about 15,000 tokens),
whichever comes first. A save is never split. Captions are cut at 2,500 characters.

That keeps one agent's reading well inside its context, with room to think and write the
answers, while 40 saves is few enough that a missed save is easy to see. Change it with
`--batch-saves` and `--batch-chars`; the batch review (below) says when to.

## Pacing: waves, and stopping on a limit

Each agent reads a whole batch, so many at once can hit the plan's usage limits.

- **Waves of at most 4 agents.** Start them in one message, wait for all 4, then merge.
- **Merge after every wave** (`--merge`). Answers are saved as they come, so stopping between
  waves loses nothing. A batch whose agent hasn't run yet is reported as waiting and left alone.
- **Stop on a limit.** If an agent comes back with a usage limit, rate limit or overloaded error,
  start no more agents. Merge what finished, tell the user what is left and when the limit
  resets, and pick up later with another `--merge` after the remaining agents run.
- **Cap a round** for the full library: `--limit 1000` (about 25 batches) per round, merge,
  check, then the next round. The pilot needs no cap.

## Steps

1. **Check the inputs.** `.cache/saves.json` exists (else run **import-saves**). `config/topics.yaml`,
   `config/collections.yaml` and `config/places.yaml` exist. Track the run with `TaskCreate`.
2. **Prepare the pilot.** Each new step runs on a pilot first (`pilots:` in `collections.yaml`):
   its collections, plus any save with a place match for its places.
   ```bash
   python3 <plugin>/skills/tag-saves/scripts/tag_saves.py --rules-only --pilot <name>   # how big is it?
   python3 <plugin>/skills/tag-saves/scripts/tag_saves.py --prepare --pilot <name>      # rule tags + batch files
   ```
   `--prepare` prints one batch path per line.
3. **Run the agents, a wave at a time.** One Agent call per batch path, at most 4 per message:
   - `subagent_type: instagram-manager:save-tagger`, prompt: the batch path.
   - If that agent type isn't listed (the plugin was changed but not reloaded), use
     `subagent_type: general-purpose`, `model: haiku`, prompt:
     `Follow <plugin>/agents/save-tagger.md exactly. Batch: <path>`.

   Each replies `wrote <N> answers to <path>`. A reply with fewer answers than the batch has saves
   is fine; merge sends the missing ones to the next round.
4. **Merge after each wave.**
   ```bash
   python3 <plugin>/skills/tag-saves/scripts/tag_saves.py --merge
   ```
   It prints `merged <N> answers (<M> unusable); <K> batches still waiting for their agent`.
   When K is 0 the round is done.
5. **Spot-check.** `--report --pilot <name>` prints the pilot as a table. Rows that need a look
   come first: saves found outside the collections, and saves with 2 or more topics or places. Then
   it lists place matches the agent turned down. Read 20 rows against their captions, and show
   them to the user before going wider.
6. **Fix the lists, not the tags.** A missed place goes in `places.yaml`. A topic or place
   suggested in `tags-review.yaml` is added to the config by a person. Then prepare again;
   `--retag` sends saves already tagged by an agent back through.
7. **Go wider** once the user has seen the pilot: `--all`, in rounds of `--limit 1000`. That is a
   change of scope, so ask with `AskUserQuestion`. The options: tag every save now (about 210
   batches over several rounds on the plan, and the later steps can use every topic), or fix the
   lists and rerun the pilot first (a few batches, but the other topics wait).
8. **Check.** The data repo's `make check` confirms every tag uses a known topic and place, and
   every code is a save in the export.

## What the files hold

```
.cache/batches/tag/batch-001.json            {batch, answers: <path>, topics: {slug: about}, places: [...], saves: [...]}
.cache/batches/tag/batch-001.answers.json    written by the agent: {"answers": {<code>: {topics, cities, other_topics?, other_places?}}}
.cache/batches/tag/batch-001.answers.merged.json   the same, renamed once merged (so it is never merged twice)
.cache/batches/tag/merged.jsonl              one line per merged batch: saves, answered, missing, chars (for the batch review)
data/tags.yaml                               <code>: {topics: [travel, parenting-kids], cities: [Example State], source: model, hints: [Example State]}
data/tags-review.yaml                        <code>: {other_topics: [...], other_places: [...]} or {error: "..."}
```

`source` is `model` (an agent tagged it) or `rules` (collection tags only: `--rules-only`, or no
usable answer yet). `hints` are the place matches. `tags.yaml` is sorted by code, so a rerun with
no changes leaves git clean. A new `--prepare` removes the last round's batch files.

## Batch review

After a few rounds, look at whether the batch size is right: per batch, how many tokens the
agent used, how long it took and how many saves it missed, from `merged.jsonl` and the agents'
session transcripts. Many missed saves in big batches means smaller batches; quick, complete
batches well under the limit mean bigger ones.

## Example

An invented pilot, "coast": collections "Weekend Trips" → travel and "Example State". A save from
`@example_creator` outside that collection says "sunset at Example Bay" with `#examplebay`. Both
are listed for Example State in `places.yaml`, so the save comes into the pilot and the agent
tags it travel / Example State. The report flags it as "found outside the collections".

## Known gap

A pilot only looks at its collections and at saves with a place match. A save about the place
whose caption names nothing on the list is missed until `--all` runs.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/tag_saves.py --rules-only` | Collection tags and place matches only, no batches | Sizing a pilot, or checking a config change | `python3 scripts/tag_saves.py --rules-only --pilot <name>` |
| `scripts/tag_saves.py --prepare` | Rule tags, then batch files for the agents; prints their paths | The start of every round | `python3 scripts/tag_saves.py --prepare --pilot <name>` (or `--all --limit 1000`) |
| `scripts/tag_saves.py --merge` | Checks the agents' answers and folds them into `tags.yaml`; says how many batches still wait | After every wave of agents | `python3 scripts/tag_saves.py --merge` |
| `scripts/tag_saves.py --report` | The pilot as a table, what to check first | Spot-checking a round | `python3 scripts/tag_saves.py --report --pilot <name>` |
| `scripts/test_tag_saves.py` | Offline tests, with a fake agent writing canned answers | After any change to the tagger | `python3 scripts/test_tag_saves.py` |

Other options: `--retag`, `--limit N` (saves per round), `--batch-saves N` (default 40),
`--batch-chars N` (default 60000).
