# Technique hub: specs, context, notes and page-comment threads for Claude techniques.
# Built by technique-manager's build-hub skill. The site goes to .cache/hub/ (not tracked).
# The plugin's skills: the marketplace checkout when this Mac has one, else the newest
# installed copy of the plugin. TM=… on the command line overrides both.
TM   ?= $(firstword $(wildcard {{TM}}) $(shell ls -d $(HOME)/.claude/plugins/cache/*/technique-manager/*/skills 2>/dev/null | sort -V | tail -1))
PORT ?= 8790
PY   ?= python3

.PHONY: help hub serve archive backup context sync status transcripts responder-on responder-off responder-status

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/' | expand -t 12

archive: ## Copy linked sessions into archive/ before Claude Code deletes them
	@$(PY) $(TM)/build-hub/scripts/archive_sessions.py --root . | $(PY) -c 'import json,sys;d=json.load(sys.stdin);print("archived",len(d["archived"]),"new,",d["already"],"kept,",len(d["missing"]),"missing")'

hub: archive ## Render every technique and build the hub site (SLUG=… for one)
	@mkdir -p .cache
	@$(PY) $(TM)/recreate-technique/scripts/render_page.py --root . $(if $(SLUG),--spec specs/$(SLUG).json,--all) > .cache/render.json || (cat .cache/render.json; exit 1)
	@$(PY) $(TM)/build-hub/scripts/build_hub.py --root .

serve: hub ## The hub with page comments, at http://localhost:$(PORT)/
	.page-comments/run serve --root .cache/hub --port $(PORT)

backup: ## Copy archive/ and comment screenshots to the upstream machine (adds only, never deletes)
	@$(PY) $(TM)/build-hub/scripts/backup_hub.py --root . --text

context: ## Fetch pre-context for one technique: make context SLUG=…
	@test -n "$(SLUG)" || (echo "usage: make context SLUG=<slug>"; exit 1)
	$(PY) $(TM)/research-backstory/scripts/fetch_context.py --root . --spec $(SLUG)

transcripts: ## Find sessions on the studio by their words, copy them to a temp folder, show snippets: make transcripts GREP="…" [SINCE=YYYY-MM-DD]
	@test -n "$(GREP)" || (echo 'usage: make transcripts GREP="<words>" [SINCE=YYYY-MM-DD]'; exit 1)
	@mkdir -p .cache
	@$(PY) $(TM)/search-transcripts/scripts/remote_sessions.py fetch --root . --grep "$(GREP)" $(if $(SINCE),--since $(SINCE)) > .cache/transcripts.json
	@$(PY) -c 'import json;d=json.load(open(".cache/transcripts.json"));print("%s: copied %d matching sessions into %s, skipped %d over the size limit" % (d["host"], len(d["files"]), d["out"], len(d["skipped"])))'
	@$(PY) $(TM)/search-transcripts/scripts/remote_sessions.py snippets --grep "$(GREP)" "$$($(PY) -c 'import json;print(json.load(open(".cache/transcripts.json"))["out"])')"

sync: hub ## Send the post-safe content to the studio
	$(PY) $(TM)/sync-studio/scripts/sync_studio.py --root .

status: ## Each technique's status and focus
	@$(PY) -c 'import json,glob;[print(f"{(s:=json.load(open(p))).get(\"status\",\"idea\"):9} {s[\"slug\"]}") for p in sorted(glob.glob("specs/[!_]*.json"))]'

responder-on: ## Answer comments in the background while no session is open (macOS)
	@$(PY) $(TM)/build-hub/scripts/responder.py on --root .

responder-off: ## Stop the background responder
	@$(PY) $(TM)/build-hub/scripts/responder.py off --root .

responder-status: ## Is it on, what's waiting on Claude, its last log lines
	@$(PY) $(TM)/build-hub/scripts/responder.py status --root .
