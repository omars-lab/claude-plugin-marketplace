---
name: send-topics
description: Write the files other repos read from the Instagram data repo — out/travel/<state or country>.yaml with every travel save naming a place there and each spot it names (quote, OpenStreetMap id, lat/lon, Google Maps link, still and clip), and out/<topic>.yaml for every other topic. Use when another project (a trip planner, a recipe site, a design repo) should pick up saved posts, after tagging, spot-finding or stills change, or when someone asks what a topic sends and to which repo.
---

# Send Topics

Each topic in `config/topics.yaml` names the repos it feeds (`feeds:`). This skill writes what those
repos read, into the data repo's `out/` folder, in git. Each repo's own intake decides what to take
from it; this skill never writes into another repo. No model is called and nothing is fetched.

**Skip this step if no other project reads your saves.** The map and the hub pages do not need
it. `feeds:` is only a note of who reads each file, for example `feeds: [trip-planner]` on travel
when a trip-planning repo picks up `out/travel/`; a topic nobody reads has `feeds: []`, and
nothing breaks either way.

Track the run with `TaskCreate`: one task per step below, each marked done as it finishes.

## What it writes

- **`out/travel/<area>.yaml`**, one per state or country, the top of the place's chain in
  `data/places.yaml` (Example Town → Example State). A trip planner reads only the area it plans.
  A road trip across two states is in both files, each with only its spots there.
- **`out/<topic>.yaml`** for every other topic, even one with no saves yet, so a reading repo can
  count on the file being there. Each save's `items` are the things **split-saves** found in its
  caption under that topic (`data/items/<topic>.yaml`); `[]` until it has read the save.

Every file starts with `topic`, `area` (travel only), `feeds`, `scope` (which saves are in it:
the pilot only, or every tagged save) and `count`, then `saves`, sorted by code.

A save carries `code`, `url`, `creator`, `saved_at`, `kind`, `topics`, `purposes`, `places` (its
most exact tagged places in that area: the town, not the state), `thumb`, `also_in` (its other
topics, and its other travel areas such as `travel/example-state`) and `items`.

A travel item is a spot:

```yaml
- name: Example Falls            # as OpenStreetMap names it
  said: Example Falls trail      # the caption's words, or the words on screen
  near: Example Park             # the area it sits in
  kind: waterfall                # OpenStreetMap's type
  lat: 11.1
  lon: 21.1
  osm: node/101
  wikidata: Q101                 # when OpenStreetMap has one
  map: https://www.google.com/maps/search/?api=1&query=Example+Falls%2C+Example+Park&query_place_id=ChIJexample
  google_id: ChIJexample         # when find-google-ids kept one: the map link opens that exact place
  overture: 00000000-0000-4000-8000-000000000101   # only when lat/lon are from Overture Maps
  overture_release: 2026-01-01.0 #   the Overture release they were read from
  licence: CDLA-Permissive-2.0   #   or Apache-2.0 (rows from Foursquare)
  from: caption                  # or video, when read-frames found it
  exact: true                    # false: no open map lists it; no lat/lon
  listed: true                   # only when exact is false and no google_id is kept: list it, don't pin it
  still: EXAMPLE1/spots/still-example-falls.jpg
  clip: EXAMPLE1/spots/clip-example-falls.webp
  t: 4.9                         # seconds into the reel
  still_from: name               # or area: the moment its area was on screen
  area: Example Park             # only with still_from: area; spots of one area share the files
```

Any other topic's item is what the caption names, from split-saves:

```yaml
- topic: recipes-coffee          # the file's topic
  kind: dish                     # dish; subject or technique; idea or product; note
  name: Example lemon loaf       # a short name
  quote: my easy lemon loaf      # the caption's own words, checked word for word
```

`exact: false` spots are the venues OpenStreetMap is thin on (small restaurants, cafés), from
`data/pins-review.yaml`. Their map link searches the name in its town. One with a kept `google_id`
is a spot the hub shows with a dashed pin at its town, which Google's map moves to the venue. One
with neither is `listed: true`: no source has its position, so the hub lists it under its town and
an intake should too, never stacking it on the town's middle (decision 13 in the data repo's
DESIGN.md).

A spot with `overture` has its position from Overture Maps' places data, which other repos may
keep. A repo that shows it credits Overture, and Foursquare for `licence: Apache-2.0` rows; the data
repo's `docs/licences/README.md` has the line to show. `thumb`, `still` and `clip` are paths inside `$INSTAGRAM_MEDIA_DIR`,
outside git; an intake copies the files it uses. `google_id` is Google's place id and nothing else
of Google's (**find-google-ids**); an intake can keep it and never search for the place again.

No caption and no collection names go in, only the short quotes the data repo already keeps.

## Steps

1. **Write.** `make send-topics` in your saves folder (`--pilot <name>` by default; `PILOT=` for
   every save). A pilot run writes the travel file for the pilot's own areas and the topic files
   with the pilot's saves, so an `also_in` such as `travel/other-state` can name a file that is
   not written until `--all` (the `scope` line says so). `--all` writes every file and removes
   the ones no longer written.
   - **Pilots add up.** The topic files (`out/<topic>.yaml`) are shared by every pilot. A pilot
     run keeps the entries other pilots wrote, replaces its own, and drops its own saves that
     left the topic; the `scope` line then names every pilot in the file. A file written by
     `--all` is left alone by a pilot run (`ev=send_kept_full_file`): run `--all` again instead.
2. **Read the log.**
   - `ev=send_place_not_travel`: a save names a place but is not tagged `travel` (a recipe post
     naming four cafés). If it is a place worth going to, add `travel` to its topics in
     `data/tags.yaml` with `by: hand` (**tag-saves**, "Fixing by hand") and write again. A news
     clip or a fact post stays out.
   - `ev=send_travel_no_place`: a travel save with no place yet (**tag-saves**).
   - `ev=send_spot_no_area`: a spot whose area is not on the place list, in a post spanning
     areas, so it fits no one file (**resolve-post-location**).
3. **Look at the travel file.** Open it and check a road-trip save (its spots split by state),
   one `exact: false` spot and one spot with `still_from: area`.
4. **Going past the pilot** (`--all`) sends saves no person has checked yet, so ask with
   `AskUserQuestion` first. The options: send every tagged save now (other repos see every state
   at once, but places and spots outside the pilot may be rough until they are tagged and found),
   or keep the pilot only (what goes out is checked, but other states wait).
5. **Commit `out/`** in the data repo, by name. A rerun on the same data writes the same bytes, so
   the diff shows only what changed.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/send_topics.py` | Writes `out/travel/<area>.yaml` and `out/<topic>.yaml` from the data files | After tagging, spots or stills change, before another repo's intake runs | `python3 scripts/send_topics.py --pilot <name>` (or `--all`; `--out DIR` for another folder) |
| `scripts/test_send_topics.py` | Offline tests on an invented data repo: a file per state, a road trip split across two, a spot OpenStreetMap lacks, a kept Google id (and one whose search text changed), an area still, `also_in`, a non-travel save left out and logged, non-travel items from split-saves, empty topic files, the pilot's scope, two pilots adding up in one topic file (and a save leaving it), a pilot leaving an `--all` file alone, the same bytes on a rerun, stale files removed | After any change to the script | `python3 scripts/test_send_topics.py` |

## What it can't do yet

- **One item across several saves.** The same dish named in three posts is three items, one per
  save; nothing merges them yet.
- **Writing into the other repos.** Each repo's intake reads `out/` and records what it took.
