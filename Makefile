.PHONY: help test-all test-discover test-config-manager test-templates test-organizer test-analyzer test-creator test-workflow validate validate-plugins list-plugins tree install install-lite uninstall install-symlinks update update-all update-force version-check version-bump version-bump-all version-init clean verify-installs doctor register sync-remote

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
RED := \033[0;31m
NC := \033[0m # No Color

# Marketplace info
MARKETPLACE_NAME := oeid-claude-plugins
MARKETPLACE_PATH := $(shell pwd)

help: ## Show this help message
	@echo "$(BLUE)OEID Claude Plugin Marketplace$(NC)"
	@echo "$(YELLOW)Available targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

validate: ## Validate marketplace.json structure
	@./scripts/cli validate $(MARKETPLACE_NAME)

validate-plugins: ## Validate all plugins against framework standards (local checks)
	@./scripts/validate-plugins.sh

validate-plugin: ## Validate a single plugin (PLUGIN=name)
	@if [ -z "$(PLUGIN)" ]; then \
		echo "$(RED)Usage: make validate-plugin PLUGIN=<name>$(NC)"; \
		exit 1; \
	fi
	@./scripts/validate-plugins.sh $(PLUGIN)

list-plugins: ## List all plugins with status
	@./scripts/cli plugins $(MARKETPLACE_NAME)

tree: ## Display marketplace directory structure
	@echo "$(BLUE)Directory Structure:$(NC)"
	@if command -v tree > /dev/null 2>&1; then \
		tree -L 3 -I '__pycache__|*.pyc|.git' .; \
	else \
		find . -maxdepth 3 -not -path '*/\.*' -not -path '*/__pycache__*' | sort | sed 's|[^/]*/| |g'; \
	fi

test-discover: ## Test discover-oeid-plugins skill
	@echo "$(BLUE)Testing discover-oeid-plugins...$(NC)"
	@echo "To test manually, run:"
	@echo "  $(YELLOW)/discover-oeid-plugins:explore-plugins$(NC)"

test-config-manager: ## Test claude-permission-config-manager skills
	@echo "$(BLUE)Testing claude-permission-config-manager...$(NC)"
	@echo "Available skills:"
	@echo "  $(YELLOW)/claude-permission-config-manager:manage-permissions$(NC)"
	@echo "  $(YELLOW)/claude-permission-config-manager:setup-working-dirs$(NC)"
	@echo "  $(YELLOW)/claude-permission-config-manager:setup-dev-env$(NC)"

test-templates: ## Test noteplan-templates skills
	@echo "$(BLUE)Testing noteplan-templates...$(NC)"
	@echo "Available skills:"
	@echo "  $(YELLOW)/noteplan-templates:list-templates$(NC)"
	@echo "  $(YELLOW)/noteplan-templates:manage-templates$(NC)"
	@echo "  $(YELLOW)/noteplan-templates:create-template$(NC)"

test-organizer: ## Test noteplan-daily-organizer skills
	@echo "$(BLUE)Testing noteplan-daily-organizer...$(NC)"
	@echo "Available skills:"
	@echo "  $(YELLOW)/noteplan-daily-organizer:organize-daily$(NC)"
	@echo "  $(YELLOW)/noteplan-daily-organizer:move-content$(NC)"

test-analyzer: ## Test noteplan-structure-analyzer skills
	@echo "$(BLUE)Testing noteplan-structure-analyzer...$(NC)"
	@echo "Available skills:"
	@echo "  $(YELLOW)/noteplan-structure-analyzer:analyze-structure$(NC)"
	@echo "  $(YELLOW)/noteplan-structure-analyzer:suggest-improvements$(NC)"

test-creator: ## Test noteplan-note-creator skills
	@echo "$(BLUE)Testing noteplan-note-creator...$(NC)"
	@echo "Available skills:"
	@echo "  $(YELLOW)/noteplan-note-creator:create-note$(NC)"
	@echo "  $(YELLOW)/noteplan-note-creator:quick-note$(NC)"

test-workflow: ## Test complete plugin lifecycle (uninstall -> install -> update)
	@./scripts/cli test-workflow $(MARKETPLACE_NAME)

test-all: ## Run all plugin tests
	@make --no-print-directory test-discover
	@echo ""
	@make --no-print-directory test-config-manager
	@echo ""
	@make --no-print-directory test-templates
	@echo ""
	@make --no-print-directory test-organizer
	@echo ""
	@make --no-print-directory test-analyzer
	@echo ""
	@make --no-print-directory test-creator

register: ## Register the marketplace in Claude
	@./scripts/cli register $(MARKETPLACE_NAME)

install: ## Install all plugins using Claude CLI (non-interactive)
	@./scripts/cli install $(MARKETPLACE_NAME)

install-lite: ## Install only claude-manager plugin
	@./scripts/cli install-single $(MARKETPLACE_NAME) claude-manager

uninstall: ## Uninstall all plugins using Claude CLI (non-interactive)
	@./scripts/cli uninstall $(MARKETPLACE_NAME)

update: ## Check for changes, bump versions, then update plugins
	@./scripts/cli version-check $(MARKETPLACE_NAME)
	@./scripts/cli update $(MARKETPLACE_NAME)

install-symlinks: ## Create symlinks for all plugins (legacy method)
	@echo "$(BLUE)Installing all plugins from $(MARKETPLACE_NAME)...$(NC)"
	@failed=0; \
	for plugin in plugins/*/; do \
		plugin_name=$$(basename $$plugin); \
		echo "$(YELLOW)Installing $$plugin_name...$(NC)"; \
		if ./scripts/cli install-single $(MARKETPLACE_NAME) $$plugin_name; then \
			echo ""; \
		else \
			failed=$$((failed + 1)); \
			echo ""; \
		fi; \
	done; \
	if [ $$failed -eq 0 ]; then \
		echo "$(GREEN)✓ All plugins installed successfully$(NC)"; \
	else \
		echo "$(RED)✗ $$failed plugin(s) failed to install$(NC)"; \
		exit 1; \
	fi

update-force: ## Force update all plugins without version check
	@./scripts/cli update $(MARKETPLACE_NAME)

update-all: ## Update marketplace and all installed plugins (alias for 'update')
	@make --no-print-directory update

version-check: ## Check which plugins need version bumps (dry run)
	@./scripts/cli version-check $(MARKETPLACE_NAME) --dry-run

version-bump: ## Manually bump a plugin version (PLUGIN=name TYPE=major|minor|patch)
	@if [ -z "$(PLUGIN)" ] || [ -z "$(TYPE)" ]; then \
		echo "$(RED)Usage: make version-bump PLUGIN=<name> TYPE=<major|minor|patch>$(NC)"; \
		echo "$(YELLOW)Example: make version-bump PLUGIN=claude-manager TYPE=minor$(NC)"; \
		exit 1; \
	fi
	@./scripts/cli version-bump $(MARKETPLACE_NAME) $(PLUGIN) $(TYPE) --commit

version-bump-all: ## Auto-bump all plugins that have changes since last version commit
	@./scripts/cli version-bump-all $(MARKETPLACE_NAME)

version-init: ## Initialize version tracking for all plugins (one-time setup)
	@./scripts/cli version-init $(MARKETPLACE_NAME)

verify-installs: ## Verify all plugins are correctly installed
	@./scripts/cli verify $(MARKETPLACE_NAME)

clean: ## Clean build artifacts and caches
	@./scripts/cli clean $(MARKETPLACE_NAME)

NOTEPLAN_PLUGINS_DIR = $(HOME)/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Plugins

install-noteplan-quicknote: ## Install oeid-noteplan-quicknote into NotePlan Plugins dir and reload
	@mkdir -p "$(NOTEPLAN_PLUGINS_DIR)/oeid.noteplan-quicknote"
	@cp plugins/oeid-noteplan-quicknote/plugin.json "$(NOTEPLAN_PLUGINS_DIR)/oeid.noteplan-quicknote/"
	@cp plugins/oeid-noteplan-quicknote/script.js "$(NOTEPLAN_PLUGINS_DIR)/oeid.noteplan-quicknote/"
	@echo "$(GREEN)✓ Installed to $(NOTEPLAN_PLUGINS_DIR)/oeid.noteplan-quicknote$(NC)"
	@osascript -e 'tell application "NotePlan 3" to reloadPlugins' 2>/dev/null \
		&& echo "$(GREEN)✓ NotePlan plugins reloaded$(NC)" \
		|| echo "$(YELLOW)⚠ NotePlan not running — reload plugins manually$(NC)"

reload-noteplan: ## Reload NotePlan plugins via AppleScript (no file copy)
	@osascript -e 'tell application "NotePlan 3" to reloadPlugins' 2>/dev/null \
		&& echo "$(GREEN)✓ Plugins reloaded$(NC)" \
		|| echo "$(YELLOW)⚠ NotePlan not running$(NC)"

uninstall-noteplan-quicknote: ## Remove oeid-noteplan-quicknote from NotePlan Plugins dir
	@rm -rf "$(NOTEPLAN_PLUGINS_DIR)/oeid.noteplan-quicknote"
	@echo "$(GREEN)✓ Removed oeid.noteplan-quicknote$(NC)"
	@osascript -e 'tell application "NotePlan 3" to reloadPlugins' 2>/dev/null || true

noteplan-info: ## Show NotePlan directory information
	@echo "$(BLUE)NotePlan Directories:$(NC)"
	@echo ""
	@echo "$(YELLOW)Notes:$(NC)"
	@echo "  $(HOME)/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/"
	@echo ""
	@echo "$(YELLOW)Calendar (Daily Files):$(NC)"
	@echo "  $(HOME)/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Calendar/"
	@echo ""
	@echo "$(YELLOW)Templates:$(NC)"
	@echo "  $(HOME)/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/@Templates/"

quick-start: ## Quick start guide
	@./scripts/cli quick-start $(MARKETPLACE_NAME)

doctor: ## Diagnose marketplace and plugin installation issues
	@./scripts/cli doctor $(MARKETPLACE_NAME)

# GitHub sync configuration
# -------------------------
# This marketplace has two remotes:
#   - origin (mac-studio): Internal remote, keeps original commit authors
#   - github: Public GitHub remote, rewrites commits to use GITHUB_AUTHOR_EMAIL
#
# Two-step workflow:
#   1. sync-remote-init (one-time): Rewrites ALL history and force pushes to GitHub
#   2. sync-remote (incremental): Only rewrites NEW commits since last sync
#
# This ensures:
#   - GitHub shows omar_eid21@yahoo.com as author
#   - Origin (mac-studio) preserves original commit metadata
#   - GitHub commit IDs remain stable after initial setup
GITHUB_REMOTE := git@github.com:omars-lab/claude-plugin-marketplace.git
GITHUB_REMOTE_NAME := github
GITHUB_AUTHOR_NAME := Omar Eid
GITHUB_AUTHOR_EMAIL := omar_eid21@yahoo.com

sync-remote-init: ## DESTRUCTIVE: Rewrite ALL history and force push (requires typing RESET)
	@./scripts/sync-to-github-init.sh "$(GITHUB_REMOTE)" "$(GITHUB_REMOTE_NAME)" "$(GITHUB_AUTHOR_NAME)" "$(GITHUB_AUTHOR_EMAIL)"

sync-remote: ## Incremental sync: rewrite only NEW commits since last sync
	@./scripts/sync-to-github.sh "$(GITHUB_REMOTE)" "$(GITHUB_REMOTE_NAME)" "$(GITHUB_AUTHOR_NAME)" "$(GITHUB_AUTHOR_EMAIL)"

sync-remote-status: ## Show GitHub sync state
	@if [ -f .git/github-sync-state ]; then \
		echo "$(BLUE)GitHub Sync State:$(NC)"; \
		grep -v "^#" .git/github-sync-state | grep -v "^$$" | while read line; do \
			key=$$(echo "$$line" | cut -d: -f1); \
			val=$$(echo "$$line" | cut -d: -f2-); \
			printf "  $(GREEN)%-10s$(NC) %s\n" "$$key:" "$$val"; \
		done; \
		echo ""; \
		local_head=$$(git rev-parse HEAD); \
		last_synced=$$(grep "^local:" .git/github-sync-state | cut -d: -f2); \
		if [ "$$local_head" = "$$last_synced" ]; then \
			echo "  $(GREEN)✓ Up to date$(NC)"; \
		else \
			new_count=$$(git rev-list --count "$$last_synced..$$local_head"); \
			echo "  $(YELLOW)$$new_count new commit(s) to sync$(NC)"; \
		fi; \
		if [ -f .git/github-sync-mapping ]; then \
			mapping_count=$$(grep -v "^#" .git/github-sync-mapping | grep -v "^$$" | wc -l | tr -d ' '); \
			echo "  $(BLUE)$$mapping_count commits mapped$(NC)"; \
		fi; \
	else \
		echo "$(YELLOW)No sync state. Run 'make sync-remote-init' first.$(NC)"; \
	fi

push-all: ## Push to both origin (studio) and GitHub (with author rewrite)
	@echo "$(BLUE)Pushing to all remotes...$(NC)"
	@echo ""
	@echo "$(BLUE)[1/2] Pushing to origin (studio)...$(NC)"
	@branch=$$(git rev-parse --abbrev-ref HEAD); \
	git push origin $$branch && echo "  $(GREEN)✓$(NC) Pushed to origin" || echo "  $(RED)✗$(NC) Failed to push to origin"
	@echo ""
	@echo "$(BLUE)[2/2] Syncing to GitHub (with author rewrite)...$(NC)"
	@./scripts/sync-to-github.sh "$(GITHUB_REMOTE)" "$(GITHUB_REMOTE_NAME)" "$(GITHUB_AUTHOR_NAME)" "$(GITHUB_AUTHOR_EMAIL)"

sync-remote-lookup: ## Look up GitHub SHA for a local commit (SHA=<commit>)
	@if [ -z "$(SHA)" ]; then \
		echo "$(RED)Usage: make sync-remote-lookup SHA=<commit>$(NC)"; \
		exit 1; \
	fi
	@if [ ! -f .git/github-sync-mapping ]; then \
		echo "$(RED)No mapping file. Run 'make sync-remote-init' first.$(NC)"; \
		exit 1; \
	fi
	@full_sha=$$(git rev-parse "$(SHA)" 2>/dev/null); \
	if [ -z "$$full_sha" ]; then \
		echo "$(RED)Invalid commit: $(SHA)$(NC)"; \
		exit 1; \
	fi; \
	github_sha=$$(grep "^$$full_sha " .git/github-sync-mapping | cut -d' ' -f2); \
	if [ -z "$$github_sha" ]; then \
		echo "$(YELLOW)No GitHub mapping for $$full_sha$(NC)"; \
		echo "$(YELLOW)Commit may not have been synced yet.$(NC)"; \
	else \
		echo "$(GREEN)Local:$(NC)  $$full_sha"; \
		echo "$(GREEN)GitHub:$(NC) $$github_sha"; \
	fi

.DEFAULT_GOAL := help
