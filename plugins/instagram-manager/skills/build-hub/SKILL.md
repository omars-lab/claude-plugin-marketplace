---
name: build-hub
description: Build the saves hub, a local website made from the data repo. It has a map with a pin for every tagged save, a page per place listing every saved post that names it, and a page per post with its caption, topics and place links. Use when someone wants to see their Instagram saves on a map, browse them by place, or check what a pilot looks like after tagging, spot-finding or a thumbnail run.
---

# Build Hub

Turns the data repo's files into a small website in `.cache/hub/`. The site has three kinds of page:

- **`index.html`: the map.** Saves near each other are grouped into numbered bubbles, which split
  into pins as you zoom in. Each pin opens a popup with:
  - the thumbnail;
  - @creator;
  - the caption's first 140 characters or so;
  - links to the post's page, to Instagram, and to the pin's place in Google Maps (a Google search
    for its name and area, not an exact Google place yet).

  Above the map is a row of menus: **State**, **National attraction**, **Purpose** and **Topic**.
  Each option shows how many posts it holds once the other menus and the search are applied, most
  posts first.
  - A national attraction is a park or spot whose name, or the name OpenStreetMap found for it, says
    National Park, Seashore, Monument and so on. Picking one (or a state) keeps only the pins and
    places inside it, so a road-trip post that names a park shows just its park pins.
  - A post's purpose (Eat & drink, Stay, Adventure & outdoors, See & do) comes from the kinds of
    place it names: a café, a hotel, a waterfall, a museum. A post that names only towns shows as
    "Not worked out yet" until the tagger gives it `purposes`. `config/purposes.yaml` in the data
    repo, when there, replaces the built-in list in `shared/scripts/purposes.py` (same shape).
  - The picks go into the page's link (`index.html#np=...&pu=...`), so a view can be bookmarked.

  Beside the map is the list of places with how many posts name each, and a search box. The search
  looks through captions, creators and place names. On a phone, the map sits above the list.
- **`places/<name>.html`: one page per place.** Each page has:
  - a small map and a Google Maps link;
  - the place it sits in, and the places inside it, each with its count;
  - a card for every saved post that names it.

  A card shows the thumbnail (or a grey box), @creator, the caption's own words for the place
  (highlighted), the post's topics, and links to the post's page and to Instagram.
- **`posts/<code>.html`: one page per post.** The thumbnail, the full caption, the creator, the
  date it was saved, its topics and collections, a link to every place it names (each with a
  Google Maps link), and the Instagram link; a post that names one place also gets an "Open in
  Google Maps" button.

Nothing on these pages is typed by hand: every build writes them fresh from the data. The pages
hold captions, so they stay in `.cache/` and never go into git. The script makes no Instagram
requests and calls no model. The map tiles come from OpenStreetMap when you open a page, with its
credit showing.

## Where a post's pin goes

A post gets one pin for each of its **most exact places**: the places it is tagged with that no
other place it is tagged with sits inside. A post tagged with a town and its state gets a pin at
the town, not the state.

- **Spots win.** A spot is a beach, a trail or a café the post names, kept in `data/pins.yaml` by
  **resolve-post-location**. When a post has spots, they replace the pin of the area they sit in.
  A spot is a place of its own with its own page, linked up to its area. Posts that name the same
  OpenStreetMap thing share one spot page.
- **Spots OpenStreetMap doesn't list.** OpenStreetMap is thin on small restaurants and cafés, so
  many land in `data/pins-review.yaml` as "not found near Example Town" (or a doubtful match).
  Each still becomes a spot, with a dashed pin at its town and a Google Maps link that searches its
  name in that town (`Example Cafe, Example Town`). The post then opens the café, not the town.
  The doubtful match's own name and lat/lon are never used. Entries marked `drop: true`, or that
  failed the quote or area check, are left out. The review file stays the list for a person to fix.
- **Wide pins.** A post tagged only with a state or a country gets a grey pin at that state's or
  country's middle, so it still shows up on the map.
- **No pin yet.** A place that has never been looked up (no latitude and longitude in
  `data/places.yaml`) still gets a page. Its posts are pinned at the next place up that has a pin.
  The build log names such places (`ev=hub_no_pin`).

The map opens on the pilot's own places (for example, a state). Pins for posts that also name
somewhere far away are still there when you zoom out.

## Which saves go in

- `--pilot <name>`: the saves in the pilot's collections, plus any save tagged with one of the
  pilot's places. This is the same rule the tag report uses.
- `--all`: every save.

## What it reads

| File | What for | If it's missing |
|---|---|---|
| `.cache/saves.json` | caption, creator, link, date saved, collections | stop: run **import-saves** |
| `data/tags.yaml` | each save's topics and places | builds, with a note: post pages only, no pins (run **tag-saves**) |
| `data/places.yaml` | each place's kind, pin, map link and the place it sits in | builds, with no pins (run **tag-saves**) |
| `config/collections.yaml` | the pilots | `--pilot` stops; `--all` still works |
| `config/topics.yaml` | the topics' display names | the topic's short name shows instead |
| `data/pins.yaml` | spots, with the caption's words for them | fine: area pins only |
| `data/pins-review.yaml` | spots OpenStreetMap did not place: dashed pins at their town | fine: no dashed pins |
| `data/media.yaml` + `$INSTAGRAM_MEDIA_DIR` | thumbnails; copied into `.cache/hub/thumbs/` | fine: grey boxes |

Each build clears and rewrites `places/` and `posts/`. Other pages in the folder, like the moves
page or the spot review page, are kept, and the map page links to them.

## Steps

1. **Build** from the data repo. Track the build, the look and any fixes with `TaskCreate`.
   ```bash
   make hub                    # the pilot; PILOT= for every save
   ```
   It prints one line of counts: saves, how many have a pin, how many sit at a town, park or spot
   rather than a whole state, place pages, spots and thumbnails. A second line is the **venue
   check**: of the posts tagged `eat` or `stay`, how many open a spot OpenStreetMap placed, a spot
   pinned at its town, or only a town. The codes of the town-only ones are in the log
   (`ev=hub_venues town_only_codes=...`). Read their captions: either the caption names no venue
   (fine, the video may), or the locator missed one (fix **resolve-post-location**'s agent).
2. **Look at it.** `make serve`, then open `http://localhost:8765/`. Check the map, one place
   page and one post page, on a wide window and a narrow one.
3. **Fix the data, not the pages.** A pin in the wrong spot means its place in
   `data/places.yaml` is wrong (fix it there, or with the `lookup:` field and **tag-saves**'
   `add_places.py`). A missing spot comes from **resolve-post-location**. A missing thumbnail comes
   from **fetch-media**. Then build again.
4. **Going past the pilot** (`--all`) is a change of scope, so ask with `AskUserQuestion` first.
   The options: build every save now (every tagged save gets a pin, but saves tagged only by
   collection rules may sit in the wrong place), or keep the pilot until its places, spots and
   thumbnails look right (a smaller site to check, but the rest of the saves wait).

## Example

An invented pilot, "coast", has a save from `@example_creator` tagged with Example Bay and Example
State, and a spot from `data/pins.yaml`, Example Falls, near Example Bay. The build makes:

- a pin at Example Falls;
- `places/example-falls.html`, whose card highlights "Example Falls trail", the caption's own
  words;
- `places/example-bay.html`, which lists Example Falls among the places inside it;
- `places/example-state.html`, which lists Example Bay;
- `posts/<code>.html`, with links to all three places.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/build_hub.py` | Writes the site to `.cache/hub/`: the map, one page per place, one page per post, and the thumbnails | After tagging, finding spots or fetching thumbnails, to see the result | `python3 scripts/build_hub.py --pilot <name>` (or `--all`; `--out DIR` for another folder) |
| `scripts/test_build_hub.py` | Offline tests on an invented data repo: which saves go in, where the pins go, spot pages, links up and down, thumbnails, and captions that try to break the page | After any change to the build script | `python3 scripts/test_build_hub.py` |
