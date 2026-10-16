---
name: find-google-ids
description: Find Google's own place for each spot a saved Instagram post names (a restaurant, a beach, a trailhead) and keep only its Google place id, so every Google Maps link in the hub and in the files other repos read opens that exact place instead of a search. Use when a spot's Google Maps link opens a city or a list instead of the place, after new spots land (resolve-post-location, read-frames), when someone asks which saved places have shut for good, or before another repo's intake reads out/ and wants place ids.
---

# Find Google Ids

A spot's Google Maps link is a search for its name and town, so it can open a list, the wrong
branch, or the whole city. Google's place id fixes that: a link carrying `query_place_id` opens
Google's own page for that one place, with its hours, photos and reviews. This skill finds the id
for each spot with one Google search and keeps only the id.

Track the run with `TaskCreate`: one task per step below, each marked done as it finishes.

## What may be kept, and what may not

Google's terms let us keep a place id for good and nothing else of theirs. The reading this follows
was agreed for a sister project (its `docs/research/google-terms/options.md`); this skill keeps to it:

- **Kept**, in `data/google.yaml`: the place id, our own search text, `match` or `none`, who chose
  (`auto`, `claude` or `hand`) and the date. Nothing more.
- **Shown on screen only, never written** (not in a log, not in `.cache`, not in a batch file): the
  candidates' names, addresses, kinds and "CLOSED FOR GOOD".
- **Never asked for**: Google's coordinates. Every pin on the map stays OpenStreetMap's or a
  person's, so a spot with no pin of its own still has no pin after this skill. The search is
  limited to a box round our own pin, or round the spot's town when it has none.
- **No sweep.** It searches only the spots the saves already name, never for new places.

## Before you start

- **Spots.** `data/pins.yaml` and the venues OpenStreetMap lacks in `data/pins-review.yaml`
  (**resolve-post-location**, **read-frames**).
- **The key.** `GOOGLE_MAPS_API_KEY` (Places API (New)). The data repo's `make google-ids` runs the
  script through `dotenvx run`, which decrypts the key into that one process from an encrypted
  `.env`; the key is never printed and goes to Google only in a request header.
- **The price.** Each search is "Text Search Pro" (because it asks for names and addresses to show):
  5,000 free a month, then $32 per 1,000. A pick's id check is free. Google stops the key for the
  day at its daily cap (an HTTP 429 that says "per day"); the run stops cleanly, keeps what it found,
  and the same command the next day carries on. Shared with any other project on the same key.

## Steps

1. **Dry run.** `google_ids.py --pilot <name> --dry-run` (`make google-ids GOOGLE_DRY=1`) lists each spot,
   its search text and its box, with no key and no calls. Spots with no pin whose area is a state or
   a country have no box narrow enough and are left out (`ev=google_no_box`). Two more lists can
   follow:
   - **"not searched: filed under the wrong area"**: spots with no pin that the locator says are
     really in another town (`really_in`). A box round the wrong town would waste the search. Fix
     their area first (**resolve-post-location**, "A spot in the wrong area"), then run this again.
   - **"kept ids no spot uses any more"**: the spot moved to a new pin or town, which gives it a
     new key, or it was dropped. `--prune` (`GOOGLE_PRUNE=1`) drops them. It first prints any that
     a person or Claude picked, so a moved spot's pick can be made again. Stale ids are worked
     out over every save, not only the pilot, so another area's ids are never dropped.
2. **Search.** `make google-ids` (`GOOGLE_LIMIT=` for a trial). One search per spot, even when several
   posts name it. Google's top 3 come back, and:
   - **kept by name** (`by: auto`): exactly one of the 3 carries every word of our name, and our
     name says enough to tell places apart (two words, or one of five letters or more). This goes a
     step past a person choosing every id: the names are compared in memory and only the id is
     kept, so it is the "on screen, nothing saved" case. The hub marks these links "matched by its
     name: check it";
   - **nothing in the box** (`verdict: none`): not searched again;
   - **everything else** is printed with a link and a `PICK='KEY=PLACE_ID'` line per candidate.
3. **Look with your own eyes.** Open five or so kept-by-name links and check each opens the place
   the post means, not a namesake. Read the "CLOSED FOR GOOD" lines: a closed spot stays (the post
   still names it) but is worth telling the user about.
4. **Pick the rest.** For each printed spot, keep the right candidate:
   `make google-ids PICK='KEY=PLACE_ID'` (several `--pick` on the script). The id is checked with
   Google's free id-only call and Google's current id is kept. None right: `NONE=KEY`. A spot to
   search again: `GOOGLE_ONLY=KEY GOOGLE_REFRESH=1`, or `GOOGLE_BOX=5` for a wider box.
   - **Claude picks first**, reading the printed list on screen (never a copy in a file), and
     records them with `PICK_BY=claude` (`--by claude`). Pick only where one candidate is plainly the
     place: the same name with a word added or dropped, the park for a park. For a chain, read
     the post's caption first: when it names a street or a branch, that branch wins over the one
     nearest our pin (search again with `GOOGLE_BOX=5` if it is not in the list). Mark `NONE` where Google gave a different place, a neighbourhood, or only a namesake far
     off. The hub marks these links "picked by Claude from Google's list: check it".
   - **Leave real toss-ups for the user** (two branches equally near, a name that could be either
     of two places) and list them in the report; their picks go in with the default `PICK_BY=hand`.
     Every spot left for a person is kept in `.cache/google-to-pick.json`: our search text and
     Google's candidate ids in Google's order, nothing else of Google's. A spot leaves it once it is
     picked, marked none, kept by name or searched with nothing found. The hub's decisions page
     (**build-hub**, `decisions.html`) lists them as "Option 1, 2, 3", each opening that exact place
     on Google Maps, and builds the `make google-ids PICK=… NONE=…` line to copy.
   - A spot marked `none` because its town or area in our data is wrong (a beach filed under a
     park in another state) is fixed in resolve-post-location ("A spot in the wrong area"). The
     fix gives it a new pin, so it is searched again on the next run, and `GOOGLE_PRUNE=1` drops
     the old `none`.
5. **Build** (**build-hub**, **send-topics**). Every spot with a kept id gets a link that opens that
   exact place, on its place page, its map popup and its post page, and `google_id` in
   `out/travel/<area>.yaml`. A spot whose name or address changes later has a new search text, so
   its old id is not used until it is searched again.
6. **Commit `data/google.yaml`** in the data repo.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/google_ids.py` | One Google search per spot, keeps an id by name or prints candidates (and keeps their ids in `.cache/google-to-pick.json` for the decisions page); `--pick`/`--none` record a person's choice | After new spots land, or to pick the leftovers | `python3 scripts/google_ids.py --pilot <name>` (`--all`, `--only`, `--limit`, `--refresh`, `--box-km`, `--dry-run`, `--prune`, `--pick KEY=ID`, `--none KEY`, `--by hand\|claude`) |
| `../../shared/scripts/google_places.py` | The search, the box, the name rule, the waits after a refusal, and the link; build-hub and send-topics use it to put kept ids into links | Imported, not run | — |
| `scripts/test_google_ids.py` | Offline tests with Google stubbed: the box, the name rule (one match, two, a short name), each spot searched once, the town box, a rerun skipping kept spots, `--pick` keeping Google's current id, `--none`, the daily cap, the waits, a spot in the wrong area left unsearched, stale ids listed and pruned (never another area's), and that the file and the spots left for a person hold nothing of Google's but ids | After any change to either script | `python3 scripts/test_google_ids.py` |

In the data repo: `make google-ids` with `GOOGLE_DRY=1`, `GOOGLE_LIMIT=`, `GOOGLE_ONLY=`,
`GOOGLE_REFRESH=1`, `GOOGLE_BOX=`, `GOOGLE_PRUNE=1`, `PICK=` and `NONE=` (several, space-separated), `PICK_BY=`
(`hand`, the default, or `claude`), and `PILOT=`
(empty for every save). Before a run past the pilot, take the spot count from the dry run and ask
with `AskUserQuestion`: all at once (one search per spot, against the month's 5,000 free and the
daily cap shared with other projects) or one area at a time (slower, easier to check by eye).

## What it can't do

- **Put spots on the map.** Google's coordinates are never kept, so spots with no pin stay off the
  map; placing them is OpenStreetMap's job or a person's.
- **Find new places**, or keep hours, ratings or photos. Google's own place card can show those live
  on a hub page once the hub is online, with a key locked to its address; nothing would be saved.
