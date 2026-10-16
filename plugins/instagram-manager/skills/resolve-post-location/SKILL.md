---
name: resolve-post-location
description: Turn each saved Instagram post into map pins for the specific spots its caption names (a beach, a café, a trailhead), found on OpenStreetMap near the town or park the save is tagged with, into the data repo's data/pins.yaml. Use after tag-saves and add_places.py, when someone wants spot-level pins for the hub's map or place pages, wants to know which spots a list post ("13 places in Example Town") names, or wants to look over or fix the pins in data/pins-review.yaml.
---

# Resolve Post Location

Tagging puts a save in an area: a town, a park, a region. This skill goes one level down, to the
**spots** the post is about: the beach, the café, the trailhead. Each spot gets a pin with
OpenStreetMap's name, kind, lat/lon and ids, and the caption's own words for it. The hub's place
pages and map read the pins.

It works like tag-saves: a script prepares batches, an agent reads them, and a script checks the
answers. **No script calls a model**, and there is no API key: this session starts the agents.

## How a spot becomes a pin

1. **Prepare.** `resolve_post_location.py --prepare` takes the saves tagged with at least one
   area more exact than a state or country (a town, a park, a region with a pin in
   `data/places.yaml`). Each save in a batch carries its code, creator, caption, and those areas
   with their kind and lat/lon.
2. **Read.** A `post-locator` agent (Haiku, `agents/post-locator.md`) reads one batch. For each
   save it lists the spots the caption names. Each one has `said`, the caption's words copied
   exactly, and `near`, the area it sits in (or the closest one, for a spot just outside it). It
   copies the caption's `address` or `lat`/`lon` for the spot when there are any. It does not
   guess: a spot the caption does not name is not a spot. A post that names 13 places lists all
   13. A post that names none gets `[]`. A venue's own post can name the creator as the spot.
3. **Merge.** `--merge` checks each spot:
   - `said` is in the caption word for word, or is the creator's own handle. If not, the spot
     goes to review. An `address` the caption does not give is dropped.
   - `near` is one of the save's areas. If not, the spot goes to review.
   - The spot is looked up on OpenStreetMap inside a box around its area (a "bounded" search:
     Nominatim's `viewbox` with `bounded=1`, through `shared/scripts/geocode.py`, cached, one
     request a second). The box is the area's reach plus 25 km. A same-name place far away never
     comes back, and a near miss comes back with its distance.
   - The first answer within the area's **reach** is kept. The reach is 25 km of the area's pin.
     A park or region also counts its own OpenStreetMap box grown by 10 km.
   - **Coordinates in the caption** are the pin, with no lookup, if they fall within reach.
   - **An address, when the name isn't found.** OpenStreetMap is thin on small restaurants and
     cafés. When the name is not found and the caption gives the spot's address, the address is
     looked up in the same box; the pin goes there, named for the venue (`kind: address`), and its
     Google Maps link searches the name at that address.
   - Kept spots go to `data/pins.yaml`. The rest go to `data/pins-review.yaml` with `why`:
     "not found near Example Town", "38 km from Example Town", "quote not in caption". The hub
     still shows the lookup misses, as dashed pins at their town that search the venue by name.
   - Saves that name no spot go to `data/no-spot.yaml`, the "look at the video" list for when
     frames are read.
4. **Look.** `pins_page.py` puts every pin on a map beside its quote. Every pin is a guess until a
   person has looked: a lookup can land on the town centre, or on the sandwich shop next to the
   café the post meant.

## Fixing the review list

Each entry in `data/pins-review.yaml` says why it is there. Edit it by hand:

- **`lookup: "Other Name"`**: the next `--merge` searches that text instead of the caption's
  words. A person wrote it, so there is no quote check. If it is found within reach, it moves to
  `pins.yaml`, with `asked:` showing what was searched.
- **`near:`** can be changed to another area in `data/places.yaml`.
- **`drop: true`** leaves the entry alone for good.
- Deleting all of a save's entries sends the save back to the agent on the next round.

A spot with the wrong area (a café in the next town over) is fixed with `near:`. A spot in an area
that is not listed yet needs that area added with `add_places.py` first.

## Pacing: waves, and stopping on a limit

The same as tag-saves:

- **Waves of at most 4 agents.** Start them in one message, wait for all 4, then merge.
- **Merge after every wave.** A merged batch is never merged twice. A batch whose agent hasn't run
  yet is reported as waiting and left alone.
- **Stop on a limit.** If an agent comes back with a usage limit, rate limit or overloaded error,
  start no more agents. Merge what finished, tell the user what is left, and pick up later.
- The merge's OpenStreetMap lookups run at one a second. A batch of 40 saves with 3 spots each
  takes about two minutes the first time; after that the answers come from the cache.

## Steps

1. **Check the inputs.** `.cache/saves.json` exists (else run **import-saves**). `data/tags.yaml`
   has the saves' places (else run **tag-saves**). `data/places.yaml` has their pins (else run
   `add_places.py`). Track the run with `TaskCreate`.
2. **Prepare the pilot.**
   ```bash
   python3 <plugin>/skills/resolve-post-location/scripts/resolve_post_location.py --prepare --pilot <name>
   ```
   It prints one batch path per line. It refuses to start while a batch has answers that are not
   merged yet: run `--merge` first.
3. **Run the agents, a wave at a time.** One Agent call per batch path, at most 4 per message:
   - `subagent_type: instagram-manager:post-locator`, prompt: the batch path.
   - If that agent type isn't listed (the plugin was changed but not reloaded), use
     `subagent_type: general-purpose`, `model: haiku`, prompt:
     `Follow <plugin>/agents/post-locator.md exactly. Batch: <path>`.

   Each replies `wrote <N> answers to <path>`. A missing answer is fine: the save is batched again
   next round.
4. **Merge after each wave.**
   ```bash
   python3 <plugin>/skills/resolve-post-location/scripts/resolve_post_location.py --merge
   ```
   It prints `<N> spots pinned, <M> for review, <K> saves name no spot, <U> saves with no usable
   answer; <W> batches still waiting for their agent`.
5. **Look over the pins.** Run `pins_page.py` and open `.cache/hub/pins.html`. Check 20 pins
   against their quotes: is the green pin on the beach the caption names? Show the user before
   going wider.
6. **Fix the review list** (above), then `--merge` again.
7. **Go wider** once the user has seen the pilot: `--prepare --all`. That is a change of scope,
   so ask with `AskUserQuestion`.

## What the files hold

```
.cache/batches/locate/batch-001.json            {batch, answers: <path>, saves: [{code, creator, areas: [{name, kind, lat, lon}], caption}]}
.cache/batches/locate/batch-001.answers.json    written by the agent: {"answers": {<code>: [{said, near, name?}], <code>: []}}
.cache/batches/locate/batch-001.answers.merged.json   the same, renamed once merged
.cache/batches/locate/merged.jsonl              one line per merged batch: saves, pins, review, no_spot, unanswered
data/pins.yaml                                  <code>: [{name, said, near, kind, lat, lon, km, osm?, wikidata?, found, map, asked?, address?}]
data/pins-review.yaml                           <code>: [{said, near, why, asked?, address?, and what was found if anything; lookup?, drop?}]
data/no-spot.yaml                               <code>: {areas: [Example Town]}
.cache/geocode.json                             every OpenStreetMap answer, misses too (bounded searches keyed by their box)
```

An example pin, all invented:

```yaml
EXAMPLECODE1:
- name: Example Cove Beach      # as OpenStreetMap names it
  said: example cove beach      # the caption's words, exactly as written
  near: Example Town            # the area from data/places.yaml
  kind: beach                   # OpenStreetMap's type
  lat: 40.045
  lon: -120.0
  km: 5.0                       # from the area's pin
  osm: node/123456
  wikidata: Q100001             # when OpenStreetMap has one
  found: Example Cove Beach, Example County, Example State
  map: https://www.google.com/maps/search/?api=1&query=Example+Cove+Beach%2C+Example+Town
```

`osm` and `wikidata` are the ids other place wikis carry, so a place page elsewhere can list the
saves that name it. The files are sorted by code, so a merge with nothing new leaves git clean.
A save's new answer (`--redo`) replaces its old pins; a `lookup:` or `drop:` a person added to a
review entry carries over when the agent names the same spot again.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/resolve_post_location.py --prepare` | Batch files for the post-locator agents: the saves with an area more exact than a state, not answered yet; prints their paths | The start of every round | `python3 scripts/resolve_post_location.py --prepare --pilot <name>` (or `--all`); data repo: `make locate-prepare` |
| `scripts/resolve_post_location.py --merge` | Checks the answers, looks each spot up near its area, writes pins, review and no-spot; searches review entries that have a `lookup:` | After every wave of agents, and after editing the review list | `python3 scripts/resolve_post_location.py --merge`; data repo: `make locate-merge` |
| `scripts/pins_page.py` | The pins on a Leaflet map beside a list: creator, quote, what OpenStreetMap found, distance from the area, post link; review entries after with their reason | After a merge, before trusting the pins | `python3 scripts/pins_page.py` (writes `.cache/hub/pins.html`; `--out PATH` for elsewhere); data repo: `make pins-page` |
| `scripts/test_resolve_post_location.py` | Offline tests with a fake agent and a fake OpenStreetMap | After any change to these scripts or to `geocode.py` | `python3 scripts/test_resolve_post_location.py` |

Other options: `--redo` (read saves that already have an answer), `--limit N` (saves per round),
`--batch-saves N` (default 40), `--batch-chars N` (default 60000), the same limits as tag-saves.
