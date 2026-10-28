# Your saves folder. No code lives here: every target calls a script in the instagram-manager
# plugin, which reads and writes this folder through INSTAGRAM_HOME. setup_home.py copied this
# file here and filled in PLUGIN; `make help` lists the targets. Each skill's make lines run here.

PLUGIN      ?= @PLUGIN@
# The newest Instagram export in ~/Downloads; EXPORT=path/to/instagram-....zip for another one.
EXPORT      ?= $(lastword $(sort $(wildcard $(HOME)/Downloads/instagram-*.zip)))

export INSTAGRAM_HOME := $(CURDIR)
# Thumbnails, videos and stills go here, never into git; data/media.yaml points at them.
export INSTAGRAM_MEDIA_DIR ?= $(CURDIR)/media
# PILOT=<name> runs a step on one pilot set from config/collections.yaml first; empty means all saves.
PILOT ?=
SCOPE = $(if $(PILOT),--pilot $(PILOT),--all)
HUB_PILOT ?=
HUB_SCOPE = $(if $(HUB_PILOT),--pilot $(HUB_PILOT),--all)
TAG   = python3 $(PLUGIN)/skills/tag-saves/scripts/tag_saves.py
SPLIT = python3 $(PLUGIN)/skills/split-saves/scripts/split_saves.py
# Batch sizes for the agents, and the most saves one round takes (empty = no cap).
TAG_BATCH_SAVES   ?= 40
TAG_BATCH_CHARS   ?= 60000
TAG_LIMIT         ?=
TAG_RETAG         ?=
TAG_RETAG_TOPIC   ?=
SPLIT_BATCH_SAVES ?= 40
SPLIT_BATCH_CHARS ?= 60000
SPLIT_LIMIT       ?=
SPLIT_REDO        ?=
LOCATE_REDO       ?=
PLACES_DRY        ?=
OVERTURE_DRY      ?=
OVERTURE_RELEASE  ?=
FRAMES_REDO       ?=
STILLS_REDO       ?=
VIDEO_LIST        ?= .cache/frames/stuck.txt
MEDIA_LIMIT       ?= 5
# MEDIA_ONE=1: 1 instagram.com request a post (fetch-media's --one-request; try 20 posts first).
# MEDIA_RECHECK=file: posts to ask for again without writing anything for them (--recheck).
MEDIA_ONE         ?=
MEDIA_RECHECK     ?=
MEDIA_FLAGS = $(strip $(if $(MEDIA_ONE),--one-request) $(if $(MEDIA_RECHECK),--recheck $(MEDIA_RECHECK)))
# The python that has yt-dlp (pip install yt-dlp), for the fetch steps.
MEDIA_PYTHON      ?= python3
# Google place ids need GOOGLE_MAPS_API_KEY in the environment (find-google-ids says how);
# GOOGLE_DRY=1 lists the searches with no key and no calls. Picks (PICK, NONE, CHAIN) need no key.
GOOGLE_DRY        ?=
GOOGLE_LIMIT      ?=
GOOGLE_ONLY       ?=
GOOGLE_REFRESH    ?=
GOOGLE_BOX        ?=
GOOGLE_PRUNE      ?=
PICK              ?=
NONE              ?=
CHAIN             ?=
PICK_BY           ?= hand
GOOGLE_FLAGS = $(strip $(if $(GOOGLE_DRY),--dry-run) $(if $(GOOGLE_LIMIT),--limit $(GOOGLE_LIMIT)) \
  $(if $(GOOGLE_ONLY),--only '$(GOOGLE_ONLY)') $(if $(GOOGLE_REFRESH),--refresh) \
  $(if $(GOOGLE_BOX),--box-km $(GOOGLE_BOX)) $(if $(GOOGLE_PRUNE),--prune) \
  $(foreach p,$(PICK),--pick '$(p)') $(foreach n,$(NONE),--none '$(n)') \
  $(foreach c,$(CHAIN),--chain '$(c)') $(if $(PICK)$(NONE)$(CHAIN),--by $(PICK_BY)))
# The hub on http://127.0.0.1:$(PORT)/, and the data API (Docker) on $(API_PORT).
PORT              ?= 8765
API_PORT          ?= 8780
API_COMPOSE        = docker compose -f $(PLUGIN)/skills/serve-api/docker/compose.yaml
export API_PORT

.PHONY: help import unsaved-page forget-unsaved collections tag-prepare tag-merge tag-rules tag-report places overture overture-check-prepare overture-check tag-moves moves-page split-prepare split-merge locate-prepare locate-merge locate-check-prepare locate-check pins-page decisions-page media-trial media-day media-impersonate-env frames-stuck media-video frames frames-text frames-merge stills stills-need-video google-ids send-topics hub serve check test api api-stop api-logs api-test api-schema

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-20s %s\n", $$1, $$2}'

import: ## Read the saved posts from the export zip into .cache/saves.json (EXPORT=path)
	@test -n "$(EXPORT)" || { echo "import: no instagram-*.zip in ~/Downloads; run make import EXPORT=path/to/the.zip (import-saves says how to get it)" >&2; exit 2; }
	python3 $(PLUGIN)/skills/import-saves/scripts/import_saved.py --from-zip "$(EXPORT)"
	python3 $(PLUGIN)/skills/import-saves/scripts/unsaved.py --flag

unsaved-page: ## The saves you unsaved (flagged, nothing removed) as a page: .cache/hub/unsaved.html
	python3 $(PLUGIN)/skills/import-saves/scripts/unsaved.py --page --make

forget-unsaved: ## Take only the saves you name out of data/ (CODES="a b", FORGET_DRY=1 first)
	python3 $(PLUGIN)/skills/import-saves/scripts/unsaved.py --forget $(CODES) $(if $(FORGET_DRY),--dry-run)

collections: ## Your collections and their sizes
	python3 $(PLUGIN)/skills/import-saves/scripts/import_saved.py --list

tag-prepare: ## Rule tags, then batch files for the save-tagger agents
	$(TAG) --prepare $(SCOPE) --batch-saves $(TAG_BATCH_SAVES) --batch-chars $(TAG_BATCH_CHARS) $(strip $(if $(TAG_LIMIT), --limit $(TAG_LIMIT))$(if $(TAG_RETAG), --retag)$(if $(TAG_RETAG_TOPIC), --retag-topic $(TAG_RETAG_TOPIC)))

tag-merge: ## Fold the agents' answers into data/tags.yaml; run after each wave
	$(TAG) --merge

tag-rules: ## The free rules only, no agents
	$(TAG) $(SCOPE) --rules-only

tag-report: ## The tags as a table, with what to spot-check
	$(TAG) --report $(SCOPE)

places: ## Look up the places left in review on OpenStreetMap, then merge (PLACES_DRY=1 to only print the table)
	python3 $(PLUGIN)/skills/tag-saves/scripts/add_places.py $(if $(PLACES_DRY),--dry-run)
	$(if $(PLACES_DRY),,$(TAG) --merge)

overture: ## Pin venues OpenStreetMap lacks from Overture Maps' open places data (OVERTURE_DRY=1 to only print the table)
	python3 $(PLUGIN)/skills/resolve-post-location/scripts/overture_positions.py $(SCOPE) $(if $(OVERTURE_DRY),--dry-run) $(if $(OVERTURE_RELEASE),--release $(OVERTURE_RELEASE))

overture-check-prepare: ## The held venues a reader could clear → batch files; then one overture-checker agent per batch, at most 4 at a time
	python3 $(PLUGIN)/skills/resolve-post-location/scripts/overture_positions.py $(SCOPE) --check-prepare $(if $(OVERTURE_RELEASE),--release $(OVERTURE_RELEASE))

overture-check: ## After each wave of agents: pin the Overture rows they picked
	python3 $(PLUGIN)/skills/resolve-post-location/scripts/overture_positions.py --check-merge

tag-moves: ## Saves filed in the wrong collection, as a table
	$(TAG) --moves

moves-page: ## The moves list as a page: .cache/hub/moves.html
	python3 $(PLUGIN)/skills/tag-saves/scripts/moves_page.py

split-prepare: ## Batch files for the save-splitter agents: saves that are not travel, not split yet
	$(SPLIT) --prepare $(SCOPE) --batch-saves $(SPLIT_BATCH_SAVES) --batch-chars $(SPLIT_BATCH_CHARS) $(if $(SPLIT_LIMIT),--limit $(SPLIT_LIMIT)) $(if $(SPLIT_REDO),--redo)

split-merge: ## Check the agents' items into data/items/<topic>.yaml; run after each wave
	$(SPLIT) --merge

locate-prepare: ## Batch files for the post-locator agents: the spots each save names
	python3 $(PLUGIN)/skills/resolve-post-location/scripts/resolve_post_location.py --prepare $(SCOPE) $(if $(LOCATE_REDO),--redo)

locate-merge: ## Check the agents' spots, look them up near their area, write data/pins.yaml
	python3 $(PLUGIN)/skills/resolve-post-location/scripts/resolve_post_location.py --merge

locate-check-prepare: ## Your check posts (data/locate-checks.yaml) as one batch for one post-locator agent
	python3 $(PLUGIN)/skills/resolve-post-location/scripts/check_locator.py --prepare

locate-check: ## Score the post-locator on data/locate-checks.yaml
	python3 $(PLUGIN)/skills/resolve-post-location/scripts/check_locator.py

pins-page: ## New pins on a map with their quotes, to look over: .cache/hub/pins.html
	python3 $(PLUGIN)/skills/resolve-post-location/scripts/pins_page.py

decisions-page: ## Everything waiting on you, on one page: .cache/hub/decisions.html
	python3 $(PLUGIN)/skills/build-hub/scripts/decisions_page.py $(HUB_SCOPE) --make

media-trial: ## Thumbnails, logged out and slow (MEDIA_LIMIT=5 per run; fetch-media says the limits)
	$(MEDIA_PYTHON) $(PLUGIN)/skills/fetch-media/scripts/fetch_media.py $(SCOPE) --limit $(MEDIA_LIMIT) $(MEDIA_FLAGS)

media-day: ## Thumbnail runs all day at the set pace: 1 h on, 1 h off, 9am-9pm, until nothing is left or a stop
	$(MEDIA_PYTHON) $(PLUGIN)/skills/fetch-media/scripts/media_day.py $(SCOPE) --limit 150 $(MEDIA_FLAGS)

media-impersonate-env: ## A Python for browser-like fetching (MEDIA_PYTHON=.cache/venv-impersonate/bin/python3): yt-dlp plus curl_cffi
	python3 -m venv --system-site-packages .cache/venv-impersonate
	.cache/venv-impersonate/bin/python3 -m pip install -q "yt-dlp[curl-cffi]==$$(python3 -c 'import yt_dlp; print(yt_dlp.version.__version__)')"

frames-stuck: ## The reels whose place is not in the caption: .cache/frames/stuck.txt
	python3 $(PLUGIN)/skills/read-frames/scripts/read_frames.py --stuck $(SCOPE)

media-video: ## Video and full cover for the reels in VIDEO_LIST, logged out and slow (MEDIA_LIMIT)
	$(MEDIA_PYTHON) $(PLUGIN)/skills/fetch-media/scripts/fetch_media.py --video $(VIDEO_LIST) --limit $(MEDIA_LIMIT)

frames: ## Frames, their text and contact sheets, then batches for the frame-reader agents
	python3 $(PLUGIN)/skills/read-frames/scripts/read_frames.py --prepare $(if $(FRAMES_REDO),--redo)

frames-text: ## Read the words again on frames already made
	python3 $(PLUGIN)/skills/read-frames/scripts/read_frames.py --text

frames-merge: ## Check the frame-reader agents' spots and write the pins
	python3 $(PLUGIN)/skills/resolve-post-location/scripts/resolve_post_location.py --merge --frames

stills: ## A still and a 3 s clip for each spot a reel names → data/stills.yaml (STILLS_REDO=1)
	python3 $(PLUGIN)/skills/extract-stills/scripts/extract_stills.py $(SCOPE) $(if $(STILLS_REDO),--redo)

stills-need-video: ## The reels naming 2 or more spots with no video yet → .cache/stills/need-video.txt
	python3 $(PLUGIN)/skills/extract-stills/scripts/extract_stills.py --need-video $(SCOPE)

google-ids: ## Google's place id for each spot → data/google.yaml (GOOGLE_DRY GOOGLE_LIMIT GOOGLE_ONLY GOOGLE_REFRESH GOOGLE_BOX GOOGLE_PRUNE PICK NONE CHAIN)
	python3 $(PLUGIN)/skills/find-google-ids/scripts/google_ids.py $(SCOPE) $(GOOGLE_FLAGS)

send-topics: ## The files other projects read: out/travel/<area>.yaml and out/<topic>.yaml
	python3 $(PLUGIN)/skills/send-topics/scripts/send_topics.py $(SCOPE)

hub: ## The hub as a local site in .cache/hub/, with its decisions page
	python3 $(PLUGIN)/skills/build-hub/scripts/build_hub.py $(HUB_SCOPE) --make

serve: ## Show the hub on http://127.0.0.1:$(PORT)/ (Ctrl-C stops it)
	python3 -m http.server $(PORT) --bind 127.0.0.1 --directory .cache/hub

check: ## Config and data files load and fit together
	python3 $(PLUGIN)/shared/scripts/check_data.py

test: ## The plugin's offline tests
	@for t in $(PLUGIN)/shared/scripts/test_*.py $(PLUGIN)/skills/*/scripts/test_*.py; do \
	  case $$t in */serve-api/*) continue;; esac; python3 $$t || exit 1; done

api: ## The data API in Docker on http://127.0.0.1:$(API_PORT)/docs
	$(API_COMPOSE) up -d --build
	@echo "api: http://127.0.0.1:$(API_PORT)/docs  (writes need the token in .cache/api-token)"

api-stop: ## Stop the data API
	$(API_COMPOSE) down

api-logs: ## The data API's last log lines
	$(API_COMPOSE) logs --tail 50 api

api-test: ## The data API's offline tests, inside its image
	$(API_COMPOSE) run --rm --no-deps api python3 /plugin/skills/serve-api/scripts/test_api.py

api-schema: ## Write the API's JSON Schema files into the plugin (after a contract change)
	docker run --rm -v $(PLUGIN):/plugin instagram-api:local python3 /plugin/skills/serve-api/scripts/api.py --schema /plugin/skills/serve-api/schema
