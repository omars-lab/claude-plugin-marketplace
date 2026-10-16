---
name: build-hub
description: Build the saves hub, a local website made from the data repo. It has a map with a pin for every tagged save, a page per place listing every saved post that names it, a page per post with its caption, topics and place links, a page per topic listing the recipes, ideas and tips its saves name, and a decisions page listing everything waiting on the user (Google places to pick, spots to check, saves to move, steps to run). Use when someone wants to see their Instagram saves on a map, browse them by place or by topic, or check what a pilot looks like after tagging, spot-finding or a thumbnail run, or when they ask what is waiting on them.
---

# Build Hub

Turns the data repo's files into a small website in `.cache/hub/`. The site has four kinds of page:

- **`index.html`: the map.** Saves near each other are grouped into numbered bubbles, which split
  into pins as you zoom in. Each pin opens a popup with:
  - the thumbnail;
  - @creator;
  - the caption's first 140 characters or so;
  - links to the post's page, to Instagram, and to the pin's place in Google Maps: Google's own
    page for that place when **find-google-ids** kept its id (`data/google.yaml`), otherwise a
    Google search for its name and area. A place page says who chose the id when it was not a
    person: "matched by its name: check it" (`by: auto`) or "picked by Claude from Google's list:
    check it" (`by: claude`). A spot marked a chain (`verdict: chain`) keeps the search, which shows
    every branch, and its page says "a chain: every branch near <area>, any will do".

  Above the map is a row of menus: **State or country**, **National attraction**, **Purpose** and
  **Topic**. Each option shows how many posts it holds once the other menus and the search are
  applied, most posts first.
  - A post sits under the widest place above each of its places: the state for a US town, the
    country for a town abroad (Example Port → Example Land). A place with no state or country above it is left
    out of this menu, so give a new town abroad its country in `data/places.yaml`.
  - A national attraction is a park or spot whose name, or the name OpenStreetMap found for it, says
    National Park, Seashore, Monument and so on. Picking one (or a state) keeps only the pins and
    places inside it, so a road-trip post that names a park shows just its park pins.
  - A post's purpose (Eat & drink, Stay, Adventure & outdoors, See & do) comes from the kinds of
    place it names: a café, a hotel, a waterfall, a museum. A post that names only towns shows as
    "Not worked out yet" until the tagger gives it `purposes`. `config/purposes.yaml` in the data
    repo, when there, replaces the built-in list in `shared/scripts/purposes.py` (same shape).
  - The picks go into the page's link (`index.html#np=...&pu=...`), so a view can be bookmarked.

  A single row right above the map says what each kind of pin means. Beside the map is the list of
  places with how many posts name each, and a search box. The search
  looks through captions, creators and place names. On a phone, the map sits above the list.
  Every page with a map keeps it on the right (the main map, place pages, the pins page) and on top
  on a phone, so the pages read the same way.
- **`<state or country>/index.html`: one map per state or country** (`california/`, `example-land/`)
  that has a pin. It is the same page, cut down to the posts with a pin there, and to the places and
  pins inside it, so a road trip that also pins somewhere far away shows only its pins in this
  state. Its counts are worked out over that cut. The first menu, **Map**, switches between
  every map: "Every state and country" (the page at `index.html`), then each state or country with
  its post count, most posts first. Place and post pages link back to their state's map ("← The map
  of Example State"). Each build removes the folders it wrote last time (they carry a marker
  comment) before writing them again, so a state with no pins left loses its map; a folder without
  the marker is never touched.
- **`places/<name>.html`: one page per place.** Each page has:
  - a small map and a Google Maps link;
  - the place it sits in, and the places inside it, each with its count;
  - a card for every saved post that names it.

  A card shows the spot's still, else the post's small picture (else a grey box), @creator, the
  caption's own words for the place (highlighted), the post's topics, and links to the post's page
  and to Instagram. A reel's small picture turns into a short flipbook while it is on screen (see
  "Lists of many posts" below).

  One place that posts call by several names still gets one page, under the shortest name:
  - spots pinned at one position whose names start with the name OpenStreetMap found there
    ("Example Roastery USA" and "Example Roastery Uptown" at Example Roastery's address);
  - spots shown at their town whose names are the same once the town words at the end are taken
    off and the words joined up ("Example Cafe TX" and "Examplecafe Fixture Town").

  Two shops at one mall's position stay two pages: neither name starts with the mall's.
- **`posts/<code>.html`: one page per post.** The thumbnail, the full caption, the creator, the
  date it was saved, its topics and collections, a link to every place it names (each with a
  Google Maps link), the things it names (**split-saves**: a dish, an idea, a tip, each linking to
  its topic's page), and the Instagram link; a post that names one place also gets an "Open in
  Google Maps" button.
  A reel with spot stills (**extract-stills**) also gets "The places in the video": one picture per
  spot, in the order they show in the video, each linking to the spot's page with its time in the
  reel and a "Play 3 s" button that plays the clip. Spots the video shows only by their area
  ("Stop 2. Big Sur") share their area's picture: it shows once, titled with the area, with
  "Spots here:" linking each of them.

- **`topics/<topic>.html`: one page per topic but travel**, listed on `topics/index.html` and
  linked first in the map's bar as "Topics". It lists the things the topic's saves name, a section
  per kind (Dishes, Ideas, Tips, in the order `item_kinds` gives in `config/topics.yaml`), each
  with the save's small picture, the caption's words, @creator, the date saved and the Instagram
  link. A filter box narrows every section at once ("Notes 36 of 280") and says how many match.
  Saves of the topic with nothing named yet are listed last, so none is hidden. Travel has no page:
  its chips link to the map with that topic picked. A topic named only in items (not in
  `config/topics.yaml`) still gets a page, under its short name.

**Spot stills.** Where a spot has a still in `data/stills.yaml`, its place page card and its map
popup show that still instead of the reel's cover. The clip plays while the pointer is on a
picture, unless the viewer asks for reduced motion; then only the button plays it. Stills and clips
are copied into `.cache/hub/stills/<code>/`. A spot whose files are missing falls back to the
cover.

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

## What a pin looks like

A pin's **colour** says how exact it is: a spot the post names, a spot at its town, a town, park
or region, or only a state or country. The **icon** inside says what kind of place it is: food,
coffee, a beach, a waterfall, a trail, a place to stay and so on (`ICONS` in `build_hub.py`, 20
kinds). The icon comes from the OpenStreetMap kind. If the kind says nothing, a spot's name words
decide it ("Example Cafe" gets coffee; a tea, juice or dessert bar is not a bar). If that fails
too, the post's purpose decides when every post naming it is tagged eat or stay. Anything left
gets "other spot". The legend above the map has one row for colour and one for icon, and lists
only the icons on the map, bars and wineries last. Each icon's number counts the pins in the
map's view, recounted after every pan, zoom, menu change or search; an icon with none in view
dims.
On a phone, each legend row is one line that scrolls sideways. The small maps on place and post
pages use the same icons.

A state's map opens on that state. With `--pilot`, the page at `index.html` opens on the pilot's
own places; pins for posts that also name somewhere far away are still there when you zoom out.

## Which saves go in

- `--all`: every save. This is what `make hub` builds.
- `--pilot <name>`: the saves in the pilot's collections, plus any save tagged with one of the
  pilot's places. This is the same rule the tag report uses. Use it to check one pilot on its own
  (`make hub HUB_PILOT=<name>`).

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
| `data/items/<topic>.yaml` | the things each save names, for the topic pages and post pages | fine: topic pages list the saves only (run **split-saves**) |
| `data/stills.yaml` + `$INSTAGRAM_MEDIA_DIR` | a still and clip per spot; copied into `.cache/hub/stills/` | fine: the reel's cover |
| `ffmpeg`, `img2webp` | the small pictures and flipbooks in `.cache/hub/previews/` (**extract-stills**' `previews.py`, made only when missing or older than their source) | fine: the full thumbnail; `--no-previews` skips them |

**Lists of many posts.** A place page can list a hundred posts, and the map's post list after a
search up to a hundred. Each shows the post's small picture (144 × 192, about 5 KB, loaded only
when near the screen). A reel's flipbook (12 frames from the whole video, about 50 KB) loads and
plays only while at least 60% of its picture is on screen, at most 8 at once, and turns back into
the picture when it scrolls away. With reduced motion asked for, it plays only under the pointer.
The post page and the map popup keep the full thumbnail.

Each build clears and rewrites `places/` and `posts/`. Other pages in the folder, like the moves
page or the spot review page, are kept, and the map page links to them.

## Steps

1. **Build** from your saves folder. Track the build, the look and any fixes with `TaskCreate`.
   ```bash
   make hub                    # every save; HUB_PILOT=<name> for one pilot
   ```
   It prints one line of counts: saves, how many have a pin, how many sit at a town, park or spot
   rather than a whole state, place pages, spots, thumbnails and spot stills. A second line is the **venue
   check**: of the posts tagged `eat` or `stay`, how many open a spot OpenStreetMap placed, a spot
   pinned at its town, or only a town. The codes of the town-only ones are in the log
   (`ev=hub_venues town_only_codes=...`). Read their captions: either the caption names no venue
   (fine, the video may), or the locator missed one (fix **resolve-post-location**'s agent).
2. **Look at it.** `make serve` (by hand: `python3 -m http.server 8765 --bind 127.0.0.1
   --directory .cache/hub`), then open `http://localhost:8765/`; Ctrl-C stops it. Check
   the map, one place page and one post page, on a wide window and a narrow one. If the folder has page comments
   on (development-manager's enable-page-comments, serving `.cache/hub` itself), the pages carry a
   Comment button, so the person can point at a wrong pin or a bad still and Claude hears about it.
   The author's own data repo has `make serve` run the comment server itself (`.page-comments/run serve --root
   .cache/hub --port $(PORT)`), so there is one address. With a separate `make comments` on another
   port, note that answers picked on the decisions page are kept per address.
3. **Fix the data, not the pages.** A pin in the wrong spot means its place in
   `data/places.yaml` is wrong (fix it there, or with the `lookup:` field and **tag-saves**'
   `add_places.py`). A missing spot comes from **resolve-post-location**. A missing thumbnail comes
   from **fetch-media**. Then build again.
4. **Check a new state on its own map.** After a new place runs through tagging, spots and
   thumbnails, open its map (`/<state>/`) and look for pins outside it. Saves tagged only by
   collection rules can sit in the wrong place; those show up there, and on the moves page.

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
| `scripts/build_hub.py` | Writes the site to `.cache/hub/`: the map, one map per state or country, one page per place, one page per post, one page per topic, the thumbnails, and each post's small picture and flipbook | After tagging, finding spots or fetching thumbnails, to see the result. It writes the decisions page too | `python3 scripts/build_hub.py --all` (or `--pilot <name>`; `--out DIR` for another folder; `--no-previews` to skip the small pictures; `--links FILE` and `--make` go to the decisions page) |
| `scripts/test_build_hub.py` | Offline tests on an invented data repo: which saves go in, where the pins go, a map per state with only its pins (and old map folders cleared), the "State or country" menu (a town abroad under its country), spot pages, links up and down, thumbnails, small pictures and flipbooks on the lists (and `--no-previews`), a kept Google id opening its exact place, a chain keeping its search for every branch, and captions that try to break the page | After any change to the build script | `python3 scripts/test_build_hub.py` |
| `scripts/decisions_page.py` | Writes `.cache/hub/decisions.html`, everything waiting on a person: Google's place to pick per spot (numbered options that open the exact place, "A chain: any branch near here" and "None of these", building one `google_ids.py --pick … --none … --chain …` line), spots to check, tags to check (saves the tagger could not tag, places not in `config/places.yaml`, topics two or more saves suggested), items whose words were not in the caption, saves to move, answers not merged, reels waiting on a fetch go-ahead, and a hand-kept list of decisions made elsewhere. Spots shown at their town only are not counted, since they work, but the opening line says how many. Each step it names is the plugin's own command; `--make` prints the data repo's make lines | `build_hub.py` runs it itself with the same scope, so the map always links a fresh one; run it alone after a step that leaves something for a person. Give it the hub's own scope: it works out each post's hub page name the way the build does | `python3 scripts/decisions_page.py --pilot <name>` (or `--all`; `--links FILE`, `--make`, `--out PATH`) |
| `scripts/test_decisions_page.py` | Offline tests on invented data: which Google picks still show (not picked or marked a chain since, same search, still a spot), the chain option, spots to check versus shown at their town, answers waiting, reels waiting, the hand-kept list (done ones left out, only http links), escaping, the page holding only ids of Google's, and post links using the build's page names (codes that differ only by case, a post outside the pilot) | After any change to the decisions script | `python3 scripts/test_decisions_page.py` |
