---
name: split-saves
description: Split each saved Instagram post that is not travel (recipes, design, business, 3D prints, parenting, other) into the things its caption names, a dish, a technique, a product idea or a tip, each with the caption's exact words, into the data repo's data/items/ folder (one file per topic). Save-splitter agents read batches of saves; the script checks every quote. Use after tag-saves, when someone wants their recipe, design or business saves broken into items, or when the topic files other repos read have empty item lists. Not for travel saves; their items are spots (resolve-post-location).
---

# Split Saves

A saved recipe post can hold three recipes; a design post can show a pattern and the way to draw
it; a business post can give five tips. This step lists those things per save, so the topic files
other repos read (`out/<topic>.yaml`, from **send-topics**) carry items instead of an empty list.
Travel is left out: a travel save's items are its spots, from **resolve-post-location**.

## What an item is

Each item has a `topic` (one of the save's own topics, never travel), a `kind`, a short `name` and
a `quote`: the caption's own words for it, checked word for word. The kind depends on the topic:

| Topic | Kinds |
|---|---|
| recipes | `dish`: a dish or drink to make |
| design | `subject`: a thing shown or made; `technique`: a way of making or drawing it |
| business, 3D prints | `idea`: a tip, plan or thing to make; `product`: a product, tool or material named |
| parenting, other, any other topic | `note`: one line saying what the post tells you |

The list is `KINDS` in `scripts/split_saves.py`. A topic the script does not know is matched by a
word in its slug (recipe, design, print, business) and otherwise gets `note`. To set a topic's
kinds yourself, add `item_kinds: {kind: what counts}` to it in the data repo's
`config/topics.yaml`.

**Give every topic a kind for the things people name, not only for advice.** The agent leaves out
anything that fits none of a topic's kinds, so a topic with only `tip` and `quote` loses every
book, course, product or piece of gear its posts name, and the save comes out `items: []`. When you
add a topic, give it a `resource` or `product` kind as well (a book, talk, course, app, tool or
product named). If you add a kind after a round, delete the entries of that topic's empty saves
(see "Fixing by hand") and run the round again, so they are read with the new kind; batches made
before the change carry the old kinds, so make them again with `--prepare` once their wave is in.

## How a save gets its items

1. **Which saves.** Every tagged save (`data/tags.yaml`) with a topic other than travel, tagged by
   the agent or only by its collection. A save is skipped once `data/items/` has an entry for
   it split for the same topics, `items: []` included, so a rerun only reads new saves. A save
   whose topics changed since (a later tagging round added one) is read again. `--redo` reads
   every save again.
2. **The `save-splitter` agent** (Haiku, `agents/save-splitter.md`) reads a batch: per save the
   code, creator, its topics, hashtags and caption, and per topic its kinds. It answers with a list
   of items per save, or `[]` when the caption names nothing specific. It never invents one.
3. **The merge checks every item.** The quote must be in the caption word for word (case, curly
   quotes and spacing aside; `shared/scripts/quote.py`) and the topic must be one of the save's
   own. An item that fails goes to `data/items-review.yaml` with the reason, never into the data.
   A kind not on the topic's list becomes the topic's first kind. The same name twice under one
   topic is kept once. Names are cut at 120 characters and quotes at 300.
4. **A save with no usable answer** (the agent skipped it, or the answers file is not JSON) gets
   no entry; its reason goes in the review file and the next round batches it again.

**No script calls a model.** The script writes batch files and checks the answers; this session
starts the agents. They run on the plan Claude Code is logged in with, so there is no API key.

## Fixing by hand

Edit a save's entry in its file under `data/items/` and add `by: hand`. That entry is final: no round batches
the save again (`--redo` included) and the merge ignores any answer for it. To have the agent read
a save again, delete its entry. An item in the review file whose quote was nearly right can be
copied into the save's entry by hand with the caption's exact words.

## Batches and pacing

The same as **tag-saves**: batches of at most 40 saves or about 60,000 characters, whichever comes
first, sorted by first topic then code so similar posts sit together; captions cut at 2,500
characters; a save is never split across batches. Change it with `--batch-saves` and
`--batch-chars`.

- **Waves of at most 4 agents.** Start them in one message, wait for all 4, then merge.
- **Merge after every wave.** A batch whose agent has not run yet is reported as waiting and left
  alone; a merged batch is never merged twice.
- **Stop on a limit.** If an agent comes back with a usage limit, rate limit or overloaded error,
  start no more agents. Merge what finished and say what is left.
- A new `--prepare` removes the last round's batch files, so it stops while any answers are not
  merged yet and says to run the merge first.
- **Check the batch size after a round** with tag-saves' `batch_review.py --kind split`. On the
  first full run (6,000 saves, haiku) an agent's context grew by about 0.83 tokens per caption
  character over a 57,000-token start, so batches of about 75,000 characters stay under 120,000
  tokens. 80,000-character batches went just over and still missed nothing.
- **How much work the whole library is.** Only saves that are not travel are split, and the last
  line of `--prepare` says how many wait in all. At 40 a batch, 1,000 of them is about 25 batches,
  so 7 waves of 4 agents. Cap a round with `SPLIT_LIMIT=400` (about 10 batches, 3 waves), merge,
  check, then the next round. The pilot needs no cap.

## Steps

1. **Check the inputs.** `.cache/saves.json` exists (else **import-saves**) and `data/tags.yaml`
   has the saves tagged (else **tag-saves**). Track the run with `TaskCreate`.
2. **Prepare.** The pilot first (`pilots:` in `config/collections.yaml`), then everything:
   ```bash
   make split-prepare                          # the pilot (PILOT=california by default)
   make split-prepare PILOT= SPLIT_LIMIT=400   # every save, 400 per round
   ```
   It prints one batch path per line, then how many saves wait in all.
3. **Run the agents, a wave at a time.** One Agent call per batch path, at most 4 per message:
   - `subagent_type: instagram-manager:save-splitter`, prompt: the batch path.
   - If that agent type isn't listed (the plugin was changed but not reloaded), use
     `subagent_type: general-purpose`, `model: haiku`, prompt:
     `Follow <plugin>/agents/save-splitter.md exactly. Batch: <path>`.

   Each replies `wrote <N> answers to <path>`.
4. **Merge after each wave.**
   ```bash
   make split-merge
   ```
   It prints `merged <N> answers (<M> unusable), <I> items kept and <R> sent to review; <K>
   batches still waiting for their agent`. When K is 0 the round is done.
5. **Spot-check.** Open a file in `data/items/` and read 20 saves against their captions (the post link
   is `https://www.instagram.com/p/<code>/`): are the names right, is anything missed, are the
   `[]` saves really empty? Then read `data/items-review.yaml`: a lot of "quote is not in the
   caption" means the agent is rewording, so tighten `agents/save-splitter.md`. Show the user
   before the next round.
6. **Send.** `make send-topics` puts the items into `out/<topic>.yaml`; `make check` checks the
   file's shape and every quote against its caption.

## What the files hold

```
.cache/batches/split/batch-001.json             {batch, answers: <path>, topics: {slug: {about, kinds: {kind: what}}}, saves: [{code, creator, topics, hashtags, caption}]}
.cache/batches/split/batch-001.answers.json     written by the agent: {"answers": {<code>: [{topic, kind, name, quote}]}}
.cache/batches/split/batch-001.answers.merged.json   the same, renamed once merged
.cache/batches/split/merged.jsonl               one line per merged batch: saves, answered, missing, chars
data/items/<topic>.yaml                         <code>: {topics: [recipes-coffee], items: [{topic, kind, name, quote}]}; by: hand on a fixed one
data/items-review.yaml                          <code>: [{why, topic, kind, name, quote}] or [{why}] when the answer was unusable
```

`topics` in an entry are the topics the save was split for, so a change shows. Every file is
sorted by code, so a rerun with nothing new leaves git clean.

**One file per topic.** A save's whole entry sits in the file of the first of its own topics,
sorted (a save tagged business and recipes-coffee goes in `business.yaml`, both topics' items
together); a save with no topics goes in `other.yaml`. One file grew past the data repo's 1 MB
limit, so the items are split this way (`shared/scripts/items_store.py` reads and writes them).
A repo that still has the old single `data/items.yaml` keeps working: it is read, and the next
merge moves its entries into the folder and removes it. `make check` flags a save that sits in
two files or in the wrong one.

## Example

An invented save from `@example_baker`, tagged recipes-coffee, says "Two bakes this week: my
lemon drizzle loaf and a brown butter blondie. #baking". The agent answers two `dish` items, quoting
"my lemon drizzle loaf" and "a brown butter blondie". If it had quoted "lemon drizzle cake", that
item would go to review with "quote is not in the caption", and the blondie would still be kept.

## Known gaps

- The same dish named in several posts is not yet merged into one item listing all their codes.
- A save whose caption names nothing (`items: []`) is not yet listed for a look at its video.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/split_saves.py --prepare` | Batch files for the agents, of non-travel saves not split yet; prints their paths and how many wait | The start of every round | `make split-prepare` or `python3 scripts/split_saves.py --prepare --pilot <name>` (`--all --limit 400`, `--redo`) |
| `scripts/split_saves.py --merge` | Checks every item's quote and topic, writes `data/items/<topic>.yaml` and `items-review.yaml`; says how many batches still wait | After every wave of agents | `make split-merge` or `python3 scripts/split_saves.py --merge` |
| `scripts/test_split_saves.py` | Offline tests on invented saves, with a fake agent writing canned answers | After any change to this step | `python3 scripts/test_split_saves.py` |

Other options: `--limit N` (saves per round), `--batch-saves N` (default 40), `--batch-chars N`
(default 60000), `--saved PATH` (another saves.json).
