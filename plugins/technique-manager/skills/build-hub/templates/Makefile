# Technique hub: specs, context, notes and page-comment threads for Claude techniques.
# Built by technique-manager's build-hub skill. The site goes to .cache/hub/ (not tracked).
TM   := {{TM}}
PORT ?= 8790
PY   ?= python3

.PHONY: help hub serve archive backup context sync status

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

sync: hub ## Send the post-safe content to the studio
	$(PY) $(TM)/sync-studio/scripts/sync_studio.py --root .

status: ## Each technique's status and focus
	@$(PY) -c 'import json,glob;[print(f"{(s:=json.load(open(p))).get(\"status\",\"idea\"):9} {s[\"slug\"]}") for p in sorted(glob.glob("specs/[!_]*.json"))]'
