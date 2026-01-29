.PHONY: help test-all test-discover test-config-manager test-templates test-organizer test-analyzer test-creator validate list-plugins tree install-all update-all clean verify-installs

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
	@echo "$(BLUE)Validating marketplace configuration...$(NC)"
	@if [ -f .claude-plugin/marketplace.json ]; then \
		python3 -m json.tool .claude-plugin/marketplace.json > /dev/null 2>&1 && \
		echo "$(GREEN)✓$(NC) marketplace.json is valid JSON" || \
		echo "$(RED)✗$(NC) marketplace.json has syntax errors"; \
	else \
		echo "$(RED)✗$(NC) marketplace.json not found"; \
	fi
	@echo "$(BLUE)Checking plugin structure...$(NC)"
	@for plugin in plugins/*/; do \
		plugin_name=$$(basename $$plugin); \
		if [ -f "$$plugin/.claude-plugin/plugin.json" ]; then \
			python3 -m json.tool "$$plugin/.claude-plugin/plugin.json" > /dev/null 2>&1 && \
			echo "$(GREEN)✓$(NC) $$plugin_name: plugin.json valid" || \
			echo "$(RED)✗$(NC) $$plugin_name: plugin.json invalid"; \
		else \
			echo "$(RED)✗$(NC) $$plugin_name: plugin.json missing"; \
		fi; \
	done

list-plugins: ## List all plugins with status
	@echo "$(BLUE)📦 Plugins in $(MARKETPLACE_NAME)$(NC)"
	@echo ""
	@for plugin in plugins/*/; do \
		plugin_name=$$(basename $$plugin); \
		if [ -d "$(HOME)/.claude/plugins/marketplaces/$(MARKETPLACE_NAME)/plugins/$$plugin_name" ]; then \
			status="$(GREEN)✓ installed$(NC)"; \
		else \
			status="$(YELLOW)✗ not installed$(NC)"; \
		fi; \
		description=$$(grep '"description"' "$$plugin/.claude-plugin/plugin.json" 2>/dev/null | head -1 | sed 's/.*: "\\(.*\\)".*/\\1/'); \
		echo "  $$status  $$plugin_name"; \
		[ -n "$$description" ] && echo "           $$description"; \
		echo ""; \
	done

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

install-all: ## Install all plugins
	@echo "$(BLUE)Installing all plugins from $(MARKETPLACE_NAME)...$(NC)"
	@failed=0; \
	for plugin in plugins/*/; do \
		plugin_name=$$(basename $$plugin); \
		echo "$(YELLOW)Installing $$plugin_name...$(NC)"; \
		if ./scripts/install-plugin.sh $$plugin_name; then \
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

update-all: ## Update all installed plugins
	@echo "$(BLUE)Updating marketplace...$(NC)"
	@claude -p "/plugin marketplace update"
	@echo "$(BLUE)Updating all plugins...$(NC)"
	@for plugin in plugins/*/; do \
		plugin_name=$$(basename $$plugin); \
		if [ -d "$(HOME)/.claude/plugins/marketplaces/$(MARKETPLACE_NAME)/plugins/$$plugin_name" ]; then \
			echo "$(YELLOW)Updating $$plugin_name...$(NC)"; \
			claude -p "/plugin update $$plugin_name"; \
		fi; \
	done
	@echo "$(GREEN)✓ All plugins updated$(NC)"

verify-installs: ## Verify all plugins are correctly installed
	@./scripts/verify-installs.sh

clean: ## Clean build artifacts and caches
	@echo "$(BLUE)Cleaning build artifacts...$(NC)"
	@find . -type f -name '*.pyc' -delete
	@find . -type d -name '__pycache__' -delete
	@find . -type d -name '.pytest_cache' -delete
	@find . -type f -name '.DS_Store' -delete
	@echo "$(GREEN)✓ Cleaned$(NC)"

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
	@echo "$(BLUE)🚀 Quick Start Guide$(NC)"
	@echo ""
	@echo "$(YELLOW)1. Add the marketplace:$(NC)"
	@echo "   /plugin marketplace add $(MARKETPLACE_PATH)"
	@echo ""
	@echo "$(YELLOW)2. Install discovery plugin:$(NC)"
	@echo "   /plugin install discover-oeid-plugins@$(MARKETPLACE_NAME)"
	@echo ""
	@echo "$(YELLOW)3. Explore plugins:$(NC)"
	@echo "   /discover-oeid-plugins:explore-plugins"
	@echo ""
	@echo "$(YELLOW)4. Install plugins you need:$(NC)"
	@echo "   /plugin install noteplan-templates@$(MARKETPLACE_NAME)"
	@echo "   /plugin install noteplan-daily-organizer@$(MARKETPLACE_NAME)"
	@echo "   /plugin install noteplan-structure-analyzer@$(MARKETPLACE_NAME)"
	@echo "   /plugin install noteplan-note-creator@$(MARKETPLACE_NAME)"
	@echo ""
	@echo "$(GREEN)Or install all at once:$(NC)"
	@echo "   make install-all"

.DEFAULT_GOAL := help
