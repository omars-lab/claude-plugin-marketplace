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
   - **A road is not a venue.** A road for cars is never the answer unless the name asked says it
     is one ("Example Street", "Example Blvd", "Example Bridge": OpenStreetMap stores a bridge as
     the road over it) or a person wrote the `lookup`. A taco stand's name often matches a street
     nearby. Trails and walkways stay. With only a road found: "not found near Example Town (only a
     street of that name)".
   - The first answer within the area's **reach** is kept. The reach is 25 km of the area's pin.
     A park or region also counts its own OpenStreetMap outline box, grown by 10 km. A place
     OpenStreetMap stores as a single point comes back with a made-up box (a whole degree either
     way for a region), so that box is ignored; a park or region with no outline reaches 50 km
     from its pin instead.
     A city that sprawls past 25 km (its suburbs, an airport, a space centre) gets a `box_km:` in
     `config/places.yaml`; that width is then its reach here too, and Google's search box in
     find-google-ids. A spot held back as "38 km from Example Town" is searched again at the next
     merge once its town's reach covers that distance; one still out of reach is left alone.
   - **Another of the save's areas.** When the spot is found but out of reach, or found under a
     different name, it is tried again near each other area of the save within 60 km of what was
     found, and pinned for the first area where it passes every check. The agent may pick the
     wrong one of two nearby towns; the post is still right about the spot.
   - **Coordinates in the caption** are the pin, with no lookup, if they fall within reach.
   - **An address, when the name isn't found.** OpenStreetMap is thin on small restaurants and
     cafés. When the name is not found and the caption gives the spot's address, the address is
     looked up in the same box; the pin goes there, named for the venue (`kind: address`), and its
     Google Maps link searches the name at that address.
     OpenStreetMap does not know suites and units ("Suite 107", "Ste B", "#12", "Unit 4", a
     letter after the street type), so the lookup drops them; the pin keeps the full address.
     A review entry from before this rule is retried once without its unit at the next merge,
     and marked `street_tried: true` if it is still not found.
     A hit must carry the address's house number: OpenStreetMap sometimes knows only the road,
     and a long road's point can be kilometres from the venue. An address pin made before this
     check whose find has no house number moves to review at the next merge ("only the street
     was found"); a person's pin stays.
   - **An address, when the name is found somewhere else.** A name like a chain's can find
     another branch across town. When the caption gives an address with a house number and the
     name's find does not carry that number, the address is looked up too, and wins if found. If
     it is not found, the spot goes to review ("found Example Grill by name, but not at the
     caption's address", with `address_tried: true`), not onto the other branch. A name pin from
     before this check moves to review at the next merge and has its address looked up once; a
     person's pin stays.
   - Kept spots go to `data/pins.yaml`. The rest go to `data/pins-review.yaml` with `why`:
     "not found near Example Town", "38 km from Example Town", "quote not in caption". The hub
     still shows the lookup misses, as dashed pins at their town that search the venue by name.
   - Saves that name no spot go to `data/no-spot.yaml`, the "look at the video" list for when
     frames are read.
4. **Look.** `pins_page.py` puts every pin on a map beside its quote. Every pin is a guess until a
   person has looked: a lookup can land on the town centre, or on the sandwich shop next to the
   café the post meant.

## Fixing by hand

Each entry in `data/pins-review.yaml` says why it is there. Edit it by hand:

- **`lookup: "Other Name"`**: the next `--merge` searches that text instead of the caption's
  words. A person wrote it, so there is no quote check, and no name check either: whatever is
  found within reach moves to `pins.yaml`, named for the find, with `asked:` showing what was
  searched, and keeps its `lookup:`. So read the merged pin's `found:` line before trusting it,
  and never give a lookup the same words that already found the wrong place ("Example HTX" that
  found a bar of another name). Give the place's own full name ("Example Market Hall") instead.
  The `said:` must still be the caption's words: an agent that wrote "Example Hall" for the
  caption's `@examplehall` gets `said: '@examplehall'`.
- **A venue inside a bigger place OpenStreetMap lists** (a shop in a mall, a stall in a food
  hall), when OpenStreetMap lacks the venue or has only another branch: a `lookup:` would rename
  the pin after the mall, and the Google search would then find the mall. Write the pin in
  `pins.yaml` by hand at the mall's position instead, with the venue's own `name:` and `by: hand`.
- **`ok: true`**: the find is right after all (a different name for the same place, or a spot
  really that far out). The next `--merge` moves it to `pins.yaml` as found, marked `by: hand`.
- **`near:`** can be changed to another area in `data/places.yaml`, always together with a
  `lookup:`. A changed `near:` alone is not searched again, and a re-read puts the agent's area
  back (see the next section).
- **`drop: true`** leaves the entry out for good. On a pin in `pins.yaml` it does the same: the
  next `--merge` moves the pin to review, and the hub leaves it out.
- **`by: hand`** on a pin a person wrote or okayed in `pins.yaml` (a branch the search missed, a
  pin placed from the map).
- Deleting all of a save's entries sends the save back to the agent on the next round.

**These fixes survive a re-read.** A `--redo` round or the video's spots merged again never
replaces an entry with `lookup:`, `ok: true`, `drop: true` or `by: hand`, and the agent's spots with the same
`said` are left out for that save, whatever area it files them under this time. Deleting a wrong
pin is not a fix, because the next re-read finds it again; mark it `drop: true` instead.

## Venues abroad

Outside the US, OpenStreetMap has the sights (a citadel, a national park) but few of the cafés,
sweets shops and huts a post names, above all those known only by an Instagram handle. In the
first trial abroad, most such venues stayed in review as "not found". Don't chase them
with `lookup:` one by one:

- **Leave them in review.** The hub shows them as dashed pins at their town, and **find-google-ids**
  searches them by name in a box round that town. Its pick gives the exact Google Maps link even
  though the venue has no pin of its own. That covers most of the gap.
- **Check the handle the agent wrote.** Agents misspell handles ("Example Tidei" for a handle
  that reads Example Tide), and the lookup then finds nothing. Fix it with a `lookup:` of the right name.
- **A namesake in a neighbouring country.** A lake or sea shared by two countries can be found on
  the wrong shore, tens of kilometres off. Leave it in review rather than `ok: true` unless the
  caption says that side.

## A spot in the wrong area

The agent must file each spot under one of the save's own areas. A road-trip reel saved under one
park often names stops in another town, state or country, and each of those lands under whichever
area is closest. That can be a park hundreds of kilometres away. The search then looks round the
wrong town, finds nothing, and the spot sits in review. Its map link searches the wrong town too.

**How the merge points them out.** After each `--merge` it lists, under "spots in review look
filed under the wrong area", every review spot that either:

- has `really_in`, where the agent quoted the caption's own place for it ("Day 3: Other Town"), or
- was found more than 60 km from its area.

The log line is `ev=locate_wrong_area spots=N`. A find far off can also be a namesake: a café of
the same name in another town while the spot's area is right. Read the caption. If the area is
right, a `lookup:` with a better name is the whole fix.

**The fix, for each listed spot:**

1. **Add its real area** to `config/places.yaml`. Give it a `lookup:` such as "Other Town, Other
   State" when the bare name finds the wrong place, and an `in:` for its state or country.
2. **Look it up.** Run `add_places.py --dry-run` and check that each match is the right place,
   then run `add_places.py` for real. In the data repo: `make places PLACES_DRY=1`, then
   `make places`.
3. **Point the spot at it.** In `data/pins-review.yaml`, set `near:` to the new area and `lookup:`
   to the name to search. Use the caption's name, or the map's own name for it when that differs
   ("God's Thumb" for a caption's "The Thumb"). Both are needed. `lookup:` is what makes the next
   merge search again and what keeps the fix through a re-read.
4. **Merge** (`make locate-merge`). Check each newly pinned spot against its quote. A spot that is
   still not found stays in review under the right area, ready for a person.
5. **Refresh the Google ids.** Run `make google-ids GOOGLE_DRY=1`, then
   `make google-ids GOOGLE_PRUNE=1`. The moved spots have new pins, so they are searched
   afresh, and their old ids, searched round the wrong town, are dropped (**find-google-ids**).

A café in the next town over, both of them already listed areas, needs only step 3.

## Pacing: waves, and stopping on a limit

The same as tag-saves:

- **Waves of at most 4 agents.** Start them in one message, wait for all 4, then merge.
- **Merge after every wave.** A merged batch is never merged twice. A batch whose agent hasn't run
  yet is reported as waiting and left alone.
- **Stop on a limit.** If an agent comes back with a usage limit, rate limit or overloaded error,
  start no more agents. Merge what finished, tell the user what is left, and pick up later.
- The merge's OpenStreetMap lookups run at one a second. A batch of 40 saves with 3 spots each
  takes about two minutes the first time; after that the answers come from the cache.
- **Check the batch size after a round** with tag-saves' `batch_review.py --kind locate`. A
  locate agent uses more context per character than a tagger (it writes more), and its biggest
  batches have come close to a 120,000-token budget; keep `--batch-chars` where the review says.

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
   - **After any change to the agent or the merge, run the check set first.** The data repo's
     `data/locate-checks.yaml` lists real posts and the spots each one should give, restaurants
     first, since OpenStreetMap misses them most. `check_locator.py --prepare` writes one batch
     of those posts; run one post-locator agent on it; then `check_locator.py` scores every listed
     spot before (the pins now) and after (the agent's answers): **pinned**, **at its town** (a
     dashed pin that Google Maps searches by name) or **lost**. It also names any spot the list
     says must not be pinned, and spots the agent named that the list lacks. A change that loses
     a spot the pins had is a step back. Only after the score improves, re-run the pilot with
     `--redo`.
7. **Go wider** once the user has seen the pilot: `--prepare --all`. That is a change of scope,
   so ask with `AskUserQuestion`.

## What the files hold

```
.cache/batches/locate/batch-001.json            {batch, answers: <path>, saves: [{code, creator, areas: [{name, kind, lat, lon}], caption}]}
.cache/batches/locate/batch-001.answers.json    written by the agent: {"answers": {<code>: [{said, near, name?, address?, lat?, lon?, really_in?}], <code>: []}}
.cache/batches/locate/batch-001.answers.merged.json   the same, renamed once merged
.cache/batches/locate/merged.jsonl              one line per merged batch: saves, chars, pins, review, no_spot, unanswered (for the batch review)
data/pins.yaml                                  <code>: [{name, said, near, kind, lat, lon, km, osm?, wikidata?, found, map, asked?, address?, from?, lookup?, by?}]
data/pins-review.yaml                           <code>: [{said, near, why, asked?, address?, really_in?, and what was found if anything; lookup?, drop?}]
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
A save's new answer (`--redo`) replaces its old pins, except the video's and a person's fixes
(see "Fixing by hand").

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/resolve_post_location.py --prepare` | Batch files for the post-locator agents: the saves with an area more exact than a state, not answered yet; prints their paths | The start of every round | `python3 scripts/resolve_post_location.py --prepare --pilot <name>` (or `--all`); data repo: `make locate-prepare` |
| `scripts/resolve_post_location.py --merge` | Checks the answers, looks each spot up near its area, writes pins, review and no-spot; searches review entries that have a `lookup:` | After every wave of agents, and after editing the review list | `python3 scripts/resolve_post_location.py --merge`; data repo: `make locate-merge` |
| `scripts/pins_page.py` | The pins on a Leaflet map beside a list: creator, quote, what OpenStreetMap found, distance from the area, post link; review entries after with their reason; each post with a small picture that turns into a flipbook of its reel while on screen (at most 8 moving at once; made by extract-stills' `previews.py` when missing) | After a merge, before trusting the pins | `python3 scripts/pins_page.py` (writes `.cache/hub/pins.html`; `--out PATH` for elsewhere; `--no-previews` to leave the pictures out); data repo: `make pins-page` |
| `scripts/check_locator.py` | Scores the agent on the hand-made check set: each listed spot pinned, at its town or lost, before and after; wrong and extra spots | Before trusting a change to `post-locator.md` or the merge | `python3 scripts/check_locator.py --prepare`, one agent, then `python3 scripts/check_locator.py`; data repo: `make locate-check-prepare`, `make locate-check` |
| `scripts/test_check_locator.py` | Offline tests of the scoring, on invented spots | After any change to `check_locator.py` | `python3 scripts/test_check_locator.py` |
| `scripts/test_resolve_post_location.py` | Offline tests with a fake agent and a fake OpenStreetMap | After any change to these scripts or to `geocode.py` | `python3 scripts/test_resolve_post_location.py` |

Other options: `--redo` (read saves that already have an answer), `--limit N` (saves per round),
`--batch-saves N` (default 40), `--batch-chars N` (default 60000), the same limits as tag-saves.
