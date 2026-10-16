---
name: tag-saves
description: Tag each Instagram save with its topics (travel, design, recipes...) and places (a city, state or country) — collection rules first, then save-tagger agents reading batches of saves — into the data repo's data/tags.yaml. Use after import-saves, when someone wants their saves sorted by topic or city, or wants one pilot set of collections tagged before the rest.
---

# Tag Saves

Gives every save its **topics**, its **places** and its **purposes** (what the post is for: eat,
stay, get outdoors, see something), from fixed lists in the data repo. One save can have several
of each: a family road trip post can be travel *and* parenting-kids, and sit in
two places. The tags feed the split, media and hub steps.

## How a save gets its tags

1. **Collections.** `config/collections.yaml` maps a collection name to topics and places. A save
   in a mapped collection keeps those tags, unless the agent shows it was filed in the wrong one
   (see Moves).
2. **Place names.** `config/places.yaml` lists names to look for in a caption (whole words, any
   case) and hashtags. Every listed place, the looked-up ones in `data/places.yaml` too, also
   matches its name run together as a hashtag (`#examplefalls` → Example Falls), and a looked-up
   name of two words or more matches the caption (one-word names are too often plain words). A
   town named like an everyday word (Example Spring, or a town called Orchard) is listed in
   `places.yaml` with `common_word: true` and its own `hashtags` (`orchardes`); then `#orchard`
   is not a hint for it. Check the one-word towns each time `make places` adds some. A
   match is only a hint: it brings the save into a pilot, and the agent is told about it. A
   sourdough post tagged with a beach town's hashtag stays a recipe. A tagged save that gains a
   hint it was not read with (the place was added since) is read once more, keeping its tags.
   Two towns can share a name: a listed Example Town is only the one in the place it sits in.
   The agent names the other one `"Example Town, Other State"`, that name does not count as the
   listed town, and `make places` adds it under that name, in Other State.
3. **The `save-tagger` agent** (Haiku, `agents/save-tagger.md`) reads a batch of saves — caption,
   hashtags, creator, collections and the two above — and picks topics, places and purposes from
   the lists. The purposes come from `shared/scripts/purposes.py`, or `config/purposes.yaml` when
   the data repo has one; the hub's Purpose menu uses the same list. A recipe has none.
   Anything it names outside the lists goes to `data/tags-review.yaml` for a person to look at. It
   never goes into the tags.
4. **Places sit in places.** A tag on a city also tags the state it is in (a US city) or the
   country (anywhere else): `shared/scripts/places.py` folds the chain. The agent picks the most
   specific listed place and the merge adds the rest.

## Places: adding the missing ones

The agent names places that are not listed yet under `other_places` ("Example Falls, Example
State"). `scripts/add_places.py` looks each one up on OpenStreetMap (free, no key, one request a
second, every answer cached in `.cache/geocode.json`) and adds the cities, parks, regions, states
and countries to `data/places.yaml`. Each place gets its kind, latitude and longitude, a Google
Maps link (a plain search link, no key) and the place it sits in. A part of a city ("West
Example City") maps to the city. A road or a venue stays in review. Run `--merge` after it: the
saves whose suggestion is now listed get the place.

OpenStreetMap's first answer is often the wrong place of the same name, so the lookup asks for
five and ranks them (city, park, state, country first; then region; then a part of a city; then
by OpenStreetMap's importance score). Read the printed table every time. To fix a wrong match:
`lookup: "Name, State"` on a listed place in `config/places.yaml`, or a line in its `aliases:` map
for a name the agent uses.

## Moves: saves in the wrong collection

When a collection's tags are clearly wrong for a save (a park in another state saved to a city's
collection), the agent adds `misfiled: {not: [the wrong tags], quote: "words from the caption"}`.
The merge checks the quote is really in the caption, then puts the save on `data/moves.yaml` with
up to three collections that fit better. The tags are not changed yet: both stay until a new
export shows the save has left that collection, then the wrong tags are dropped and the move comes
off the list. `--moves` prints the list; the moves page shows it with links to open each post.

## Fixing by hand

To fix one save's tags yourself (drop a wrong place now rather than wait for the move, add a topic
the agent missed), edit its entry in `data/tags.yaml` and add `by: hand`. That entry is final:
no round reads the save again (`--retag` included), the merge ignores any answer for it, the
collection's tags are not added back, the review list adds no place to it, and a finished move
leaves it alone. Without the mark, the next round can undo the fix. A fix that holds for many
saves belongs in the lists instead (step 6).

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
   its collections, plus any save with a place match for its places. A pilot for a city lists
   its suburbs in `cities:` too (the listed towns within about 50 km): each suburb is a place of
   its own, and a city does not hold them the way a state holds its towns.
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
   come first: saves found outside the collections, and saves with 2 or more topics or places (a
   town and the state it sits in count as one place). Then
   it lists place matches the agent turned down. Read 20 rows against their captions, and show
   them to the user before going wider.
6. **Fix the lists, not the tags.** A missed place goes in `places.yaml`. A topic or place
   suggested in `tags-review.yaml` is added to the config by a person. Then prepare again;
   `--retag` sends saves already tagged by an agent back through.
   A save an agent tagged before purposes were asked (no `purposes` in its tags) goes back once by
   itself, with its topics and places under `already`, so the round adds purposes without dropping
   a place. A `--retag` sends only the collection's tags under `already`, so it can drop one.
   After adding topics, `--retag-topic other` sends back only the saves filed under `other`, the
   same way, so each can move to a new topic; the rest keep their tags.
7. **Go wider** once the user has seen the pilot: `--all`, in rounds of `--limit 1000`. That is a
   change of scope, so ask with `AskUserQuestion`. The options: tag every save now (about 210
   batches over several rounds on the plan, and the later steps can use every topic), or fix the
   lists and rerun the pilot first (a few batches, but the other topics wait).
8. **Check.** The data repo's `make check` confirms every tag uses a known topic and place, and
   every code is a save in the export.

## What the files hold

```
.cache/batches/tag/batch-001.json            {batch, answers: <path>, topics: {slug: about}, purposes: {slug: about}, places: {name: sits in}, saves: [...]}
.cache/batches/tag/batch-001.answers.json    written by the agent: {"answers": {<code>: {topics, cities, purposes, other_topics?, other_places?, misfiled?}}}
.cache/batches/tag/batch-001.answers.merged.json   the same, renamed once merged (so it is never merged twice)
.cache/batches/tag/merged.jsonl              one line per merged batch: saves, answered, missing, chars (for the batch review)
data/tags.yaml                               <code>: {topics: [travel, parenting-kids], cities: [Example State], purposes: [adventure], source: model, hints: [Example State]}
data/tags-review.yaml                        <code>: {other_topics: [...], other_places: [...]} or {error: "..."}
data/places.yaml                             places: {<name>: {kind, in, lat, lon, found, map}}, aliases: {<said>: <name>}
data/moves.yaml                              <code>: {collections, not: [...], quote, fits: {topics, cities}, to: [...]}
.cache/geocode.json                          every OpenStreetMap answer, misses too, so a name is asked once
```

`source` is `model` (an agent tagged it) or `rules` (collection tags only: `--rules-only`, or no
usable answer yet). `by: hand` marks an entry a person fixed (see "Fixing by hand"). `hints` are the place matches. `tags.yaml` is sorted by code, so a rerun with
no changes leaves git clean. A new `--prepare` removes the last round's batch files, so it stops while any answers are not merged yet and says to run `--merge` first (`--rules-only` still runs).

## Batch review

After each round (and before the first round of `--all`), check the batch size:

```bash
python3 <plugin>/skills/tag-saves/scripts/batch_review.py          # --kind tag|split|locate|frames, --budget N
```

It finds every batch agent in the data repo's Claude Code transcripts and prints one row per run:
saves, characters, the most context it reached, output tokens, minutes, saves it missed (from
`merged.jsonl`) and any error (a rate limit, say). It reads numbers only; no caption or answer is
printed. A `~` before the characters means the size of what the agent read, a little over the
batch's own count (older locate and frames merges did not log it).

Then one line per kind. It fits the most context an agent reached against its batch's size and
says how big a batch can be and stay under the budget (default 120,000 tokens), in `--batch-chars`
and in saves. Every agent starts at about 40,000–50,000 tokens before it reads its batch, so fewer,
bigger batches use less of the plan, as long as no saves go missing.

- **Saves missed, or a run over the budget:** make batches smaller.
- **No saves missed and the runs well under the budget:** try the suggested size on the next round
  (both `--batch-saves` and `--batch-chars`), then run the review again.
- **Runs hit a rate or usage limit:** that is pacing, not size: smaller waves, or wait.

A batch is cut at whichever comes first, 40 saves or 60,000 characters; most tagging batches stop at
40 saves, so raising `--batch-chars` alone changes little.

## Example

An invented pilot, "coast": collections "Weekend Trips" → travel and "Example State". A save from
`@example_creator` outside that collection says "sunset at Example Bay" with `#examplebay`. Both
are listed for Example State in `places.yaml`, so the save comes into the pilot and the agent
tags it travel / Example State. The report flags it as "found outside the collections".

## Known gaps

A pilot only looks at its collections and at saves with a place match. A save about the place
whose caption names nothing on the list is missed until `--all` runs.

A venue saved in a collection for another topic (a sweets shop in a business collection) can come
back with that topic and its town, but no `travel`. send-topics logs it as
`ev=send_place_not_travel`; read those and add `travel` by hand when it is a place to go. A place
named only as an event's venue (a giveaway at a café abroad) is not a trip: clear its `cities` by
hand instead.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/tag_saves.py --rules-only` | Collection tags and place matches only, no batches | Sizing a pilot, or checking a config change | `python3 scripts/tag_saves.py --rules-only --pilot <name>` |
| `scripts/tag_saves.py --prepare` | Rule tags, then batch files for the agents; prints their paths | The start of every round | `python3 scripts/tag_saves.py --prepare --pilot <name>` (or `--all --limit 1000`) |
| `scripts/tag_saves.py --prepare --retag-topic <slug>` | Batches again only the agent-tagged saves with that topic, with only their collection's tags under `already` | After adding topics to `topics.yaml`: re-read the `other` saves against the longer list | `python3 scripts/tag_saves.py --prepare --all --retag-topic other --limit 1000` |
| `scripts/tag_saves.py --merge` | Checks the agents' answers and folds them into `tags.yaml`; says how many batches still wait | After every wave of agents | `python3 scripts/tag_saves.py --merge` |
| `scripts/tag_saves.py --report` | The pilot as a table, what to check first | Spot-checking a round | `python3 scripts/tag_saves.py --report --pilot <name>` |
| `scripts/tag_saves.py --moves` | The saves filed in the wrong collection, with where to move them | After a merge that found moves | `python3 scripts/tag_saves.py --moves` |
| `scripts/moves_page.py` | The moves list as a page: per save the collection it is in, where to move it, the caption with the quote marked, a link to the post and a "Moved" tick kept in the browser | When there are saves to move and you want to work through them in the app | `python3 scripts/moves_page.py` (writes `.cache/hub/moves.html`; `--out PATH` for elsewhere) |
| `scripts/add_places.py` | Looks up unlisted places on OpenStreetMap and adds them, with map links and the place each sits in | After a round leaves places in review, then `--merge` | `python3 scripts/add_places.py --dry-run` first, then without |
| `scripts/batch_review.py` | One row per batch agent run (tag, split, locate, frames) from the transcripts and merge logs, then the batch size that fits under a context budget | After a round, and before the first `--all` round | `python3 scripts/batch_review.py` (`--kind tag`, `--budget 100000`, `--transcripts DIR`) |
| `scripts/test_tag_saves.py` | Offline tests, with a fake agent writing canned answers | After any change to the tagger | `python3 scripts/test_tag_saves.py` |
| `scripts/test_batch_review.py` | Offline tests on invented transcripts and merge logs | After any change to the batch review | `python3 scripts/test_batch_review.py` |

Other options: `--retag`, `--retag-topic SLUG`, `--limit N` (saves per round), `--batch-saves N` (default 40),
`--batch-chars N` (default 60000).
