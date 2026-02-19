.PHONY: help test-all test-discover test-config-manager test-templates test-organizer test-analyzer test-creator test-workflow validate validate-plugins list-plugins tree install uninstall install-symlinks update update-all update-force version-check version-bump version-init clean verify-installs doctor register

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

validate: ## Validate marketplace.json structure (via ceg)
	@ceg marketplace validate $(MARKETPLACE_NAME)

validate-plugins: ## Validate all plugins against framework standards (local checks)
	@./scripts/validate-plugins.sh

validate-plugin: ## Validate a single plugin (PLUGIN=name)
	@if [ -z "$(PLUGIN)" ]; then \
		echo "$(RED)Usage: make validate-plugin PLUGIN=<name>$(NC)"; \
		exit 1; \
	fi
	@./scripts/validate-plugins.sh $(PLUGIN)

list-plugins: ## List all plugins with status
	@ceg marketplace plugins $(MARKETPLACE_NAME)

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
	@ceg marketplace test-workflow $(MARKETPLACE_NAME)

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
	@ceg marketplace register $(MARKETPLACE_NAME)

install: ## Install all plugins using Claude CLI (non-interactive)
	@ceg marketplace install $(MARKETPLACE_NAME)

uninstall: ## Uninstall all plugins using Claude CLI (non-interactive)
	@ceg marketplace uninstall $(MARKETPLACE_NAME)

update: ## Check for changes, bump versions, then update plugins
	@ceg marketplace version-check $(MARKETPLACE_NAME)
	@ceg marketplace update $(MARKETPLACE_NAME)

install-symlinks: ## Create symlinks for all plugins (legacy method)
	@echo "$(BLUE)Installing all plugins from $(MARKETPLACE_NAME)...$(NC)"
	@failed=0; \
	for plugin in plugins/*/; do \
		plugin_name=$$(basename $$plugin); \
		echo "$(YELLOW)Installing $$plugin_name...$(NC)"; \
		if ceg marketplace install-single $(MARKETPLACE_NAME) $$plugin_name; then \
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
	@ceg marketplace update $(MARKETPLACE_NAME)

update-all: ## Update marketplace and all installed plugins (alias for 'update')
	@make --no-print-directory update

version-check: ## Check which plugins need version bumps (dry run)
	@ceg marketplace version-check $(MARKETPLACE_NAME) --dry-run

version-bump: ## Manually bump a plugin version (PLUGIN=name TYPE=major|minor|patch)
	@if [ -z "$(PLUGIN)" ] || [ -z "$(TYPE)" ]; then \
		echo "$(RED)Usage: make version-bump PLUGIN=<name> TYPE=<major|minor|patch>$(NC)"; \
		echo "$(YELLOW)Example: make version-bump PLUGIN=claude-manager TYPE=minor$(NC)"; \
		exit 1; \
	fi
	@ceg marketplace version-bump $(MARKETPLACE_NAME) $(PLUGIN) $(TYPE) --commit

version-init: ## Initialize version tracking for all plugins (one-time setup)
	@ceg marketplace version-init $(MARKETPLACE_NAME)

verify-installs: ## Verify all plugins are correctly installed
	@ceg marketplace verify $(MARKETPLACE_NAME)

clean: ## Clean build artifacts and caches
	@ceg marketplace clean $(MARKETPLACE_NAME)

noteplan-info: ## Show NotePlan directory information
	@echo "$(BLUE)NotePlan Directories:$(NC)"
	@echo ""
	@echo "$(YELLOW)Notes:$(NC)"
	@echo "  /Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/"
	@echo ""
	@echo "$(YELLOW)Calendar (Daily Files):$(NC)"
	@echo "  /Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Calendar/"
	@echo ""
	@echo "$(YELLOW)Templates:$(NC)"
	@echo "  /Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/@Templates/"

quick-start: ## Quick start guide
	@ceg marketplace quick-start $(MARKETPLACE_NAME)

doctor: ## Diagnose marketplace and plugin installation issues
	@ceg marketplace doctor $(MARKETPLACE_NAME)

.DEFAULT_GOAL := help
