.PHONY: help test-all test-discover test-config-manager test-templates test-organizer test-analyzer test-creator validate list-plugins tree install uninstall install-all install-symlinks install-cli update-all clean verify-installs doctor register

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
		install_path="$(HOME)/.claude/plugins/marketplaces/$(MARKETPLACE_NAME)/plugins/$$plugin_name"; \
		if [ -d "$$install_path" ]; then \
			status="$(GREEN)✓ installed$(NC)"; \
		else \
			status="$(YELLOW)✗ not installed$(NC)"; \
		fi; \
		description=$$(grep '"description"' "$$plugin/.claude-plugin/plugin.json" 2>/dev/null | head -1 | sed 's/.*: "\\(.*\\)".*/\\1/'); \
		echo "  $$status  $$plugin_name"; \
		[ -n "$$description" ] && echo "           $$description"; \
		if [ -d "$$install_path" ]; then \
			echo "           $(BLUE)Path:$(NC) $$install_path"; \
		fi; \
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

register: ## Manually register the marketplace in Claude
	@./scripts/register-marketplace.sh

install: ## Install all plugins using Claude CLI
	@if [ -n "$$CLAUDECODE" ]; then \
		echo "$(RED)⚠ Cannot run from within Claude Code session$(NC)"; \
		echo ""; \
		echo "$(YELLOW)Please run this command from a regular terminal:$(NC)"; \
		echo "   $(BLUE)cd $(MARKETPLACE_PATH) && make install$(NC)"; \
		echo ""; \
		echo "$(YELLOW)Or use the helper script:$(NC)"; \
		echo "   $(BLUE)./scripts/cli-install-all.sh$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Installing all plugins from $(MARKETPLACE_NAME) using Claude CLI...$(NC)"
	@echo ""
	@failed=0; \
	total=0; \
	plugins=$$(python3 -c "import json; data=json.load(open('.claude-plugin/marketplace.json')); print(' '.join([p['name'] for p in data['plugins']]))"); \
	for plugin in $$plugins; do \
		total=$$((total + 1)); \
		echo "$(YELLOW)Installing $$plugin@$(MARKETPLACE_NAME)...$(NC)"; \
		if claude plugin install "$$plugin@$(MARKETPLACE_NAME)" --scope user; then \
			echo "$(GREEN)✓$(NC) $$plugin installed successfully"; \
		else \
			echo "$(RED)✗$(NC) Failed to install $$plugin"; \
			failed=$$((failed + 1)); \
		fi; \
		echo ""; \
	done; \
	echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"; \
	if [ $$failed -eq 0 ]; then \
		echo "$(GREEN)✓ All $$total plugins installed successfully$(NC)"; \
	else \
		echo "$(RED)✗ $$failed of $$total plugin(s) failed to install$(NC)"; \
		exit 1; \
	fi

uninstall: ## Uninstall all plugins using Claude CLI
	@if [ -n "$$CLAUDECODE" ]; then \
		echo "$(RED)⚠ Cannot run from within Claude Code session$(NC)"; \
		echo ""; \
		echo "$(YELLOW)Please run this command from a regular terminal:$(NC)"; \
		echo "   $(BLUE)cd $(MARKETPLACE_PATH) && make uninstall$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Uninstalling all plugins from $(MARKETPLACE_NAME) using Claude CLI...$(NC)"
	@echo ""
	@failed=0; \
	total=0; \
	plugins=$$(python3 -c "import json; data=json.load(open('.claude-plugin/marketplace.json')); print(' '.join([p['name'] for p in data['plugins']]))"); \
	for plugin in $$plugins; do \
		total=$$((total + 1)); \
		echo "$(YELLOW)Uninstalling $$plugin@$(MARKETPLACE_NAME)...$(NC)"; \
		if claude plugin uninstall "$$plugin@$(MARKETPLACE_NAME)" --scope user; then \
			echo "$(GREEN)✓$(NC) $$plugin uninstalled successfully"; \
		else \
			echo "$(YELLOW)⚠$(NC)  $$plugin may not have been installed"; \
		fi; \
		echo ""; \
	done; \
	echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"; \
	echo "$(GREEN)✓ Uninstall process completed for $$total plugins$(NC)"

update: ## Update all installed plugins using Claude CLI
	@if [ -n "$$CLAUDECODE" ]; then \
		echo "$(RED)⚠ Cannot run from within Claude Code session$(NC)"; \
		echo ""; \
		echo "$(YELLOW)Please run this command from a regular terminal:$(NC)"; \
		echo "   $(BLUE)cd $(MARKETPLACE_PATH) && make update$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Updating all plugins from $(MARKETPLACE_NAME) using Claude CLI...$(NC)"
	@echo ""
	@failed=0; \
	total=0; \
	plugins=$$(python3 -c "import json; data=json.load(open('.claude-plugin/marketplace.json')); print(' '.join([p['name'] for p in data['plugins']]))"); \
	for plugin in $$plugins; do \
		total=$$((total + 1)); \
		echo "$(YELLOW)Updating $$plugin@$(MARKETPLACE_NAME)...$(NC)"; \
		if claude plugin update "$$plugin@$(MARKETPLACE_NAME)" --scope user; then \
			echo "$(GREEN)✓$(NC) $$plugin updated successfully"; \
		else \
			echo "$(YELLOW)⚠$(NC)  $$plugin may not have been installed or is already up-to-date"; \
		fi; \
		echo ""; \
	done; \
	echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"; \
	echo "$(GREEN)✓ Update process completed for $$total plugins$(NC)"

install-all: ## Auto-install all plugins to ~/.claude (recommended)
	@./scripts/auto-install-all.sh

install-cli: ## Instructions to install via Claude CLI
	@echo "$(BLUE)Install via Claude CLI (most reliable method)$(NC)"
	@echo ""
	@echo "$(YELLOW)1. Exit this Claude session completely$(NC)"
	@echo ""
	@echo "$(YELLOW)2. Run this command in your terminal:$(NC)"
	@echo "   $(GREEN)cd $(MARKETPLACE_PATH) && ./scripts/cli-install-all.sh$(NC)"
	@echo ""
	@echo "$(YELLOW)Or install plugins individually:$(NC)"
	@echo "   claude -p '/plugin install discover-oeid-plugins@$(MARKETPLACE_NAME)'"
	@echo "   claude -p '/plugin install noteplan-templates@$(MARKETPLACE_NAME)'"
	@echo "   claude -p '/plugin install noteplan-daily-organizer@$(MARKETPLACE_NAME)'"
	@echo "   claude -p '/plugin install noteplan-structure-analyzer@$(MARKETPLACE_NAME)'"
	@echo "   claude -p '/plugin install noteplan-note-creator@$(MARKETPLACE_NAME)'"
	@echo "   claude -p '/plugin install claude-permission-config-manager@$(MARKETPLACE_NAME)'"
	@echo ""
	@echo "$(YELLOW)3. Start a new Claude session and test!$(NC)"

install-symlinks: ## Create symlinks only (legacy method)
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

update-all: ## Update marketplace and all installed plugins (alias for 'update')
	@make --no-print-directory update

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
	@echo "$(YELLOW)0. Check installation health:$(NC)"
	@echo "   $(BLUE)make doctor$(NC)"
	@echo ""
	@echo "$(YELLOW)1. Add the marketplace:$(NC)"
	@echo "   $(BLUE)make register$(NC)"
	@echo "   Or manually: /plugin marketplace add $(MARKETPLACE_PATH)"
	@echo ""
	@echo "$(YELLOW)2. Install all plugins:$(NC)"
	@echo "   $(BLUE)make install$(NC)"
	@echo ""
	@echo "$(YELLOW)3. Explore plugins:$(NC)"
	@echo "   /discover-oeid-plugins:explore-plugins"
	@echo ""
	@echo "$(GREEN)Other useful commands:$(NC)"
	@echo "   $(BLUE)make update$(NC)     - Update all installed plugins"
	@echo "   $(BLUE)make uninstall$(NC)  - Uninstall all plugins"
	@echo "   $(BLUE)make list-plugins$(NC) - See what's installed"
	@echo ""
	@echo "$(BLUE)💡 Tip:$(NC) Run $(YELLOW)make doctor$(NC) anytime to diagnose issues"

doctor: ## Diagnose marketplace and plugin installation issues
	@echo "$(BLUE)🩺 Claude Plugin Marketplace Doctor$(NC)"
	@echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo ""
	@echo "$(YELLOW)📍 Current Marketplace Path:$(NC)"
	@echo "   $(MARKETPLACE_PATH)"
	@echo ""
	@errors=0; \
	warnings=0; \
	\
	echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"; \
	echo "$(YELLOW)1. Checking Marketplace Registration...$(NC)"; \
	echo ""; \
	if [ -f "$(HOME)/.claude/plugins/known_marketplaces.json" ]; then \
		if grep -q '"$(MARKETPLACE_NAME)"' "$(HOME)/.claude/plugins/known_marketplaces.json"; then \
			echo "   $(GREEN)✓$(NC) Marketplace '$(MARKETPLACE_NAME)' is registered"; \
			registered_path=$$(python3 -c "import json; data=json.load(open('$(HOME)/.claude/plugins/known_marketplaces.json')); print(data.get('$(MARKETPLACE_NAME)', {}).get('installLocation', ''))" 2>/dev/null); \
			if [ -n "$$registered_path" ]; then \
				echo "   $(BLUE)Path:$(NC) $$registered_path"; \
				if [ "$$registered_path" != "$(MARKETPLACE_PATH)" ]; then \
					echo "   $(YELLOW)⚠$(NC)  Registered path differs from current path"; \
					warnings=$$((warnings + 1)); \
				fi; \
			fi; \
		else \
			echo "   $(RED)✗$(NC) Marketplace '$(MARKETPLACE_NAME)' is NOT registered"; \
			echo "   $(BLUE)Fix:$(NC) Run the following command in Claude:"; \
			echo "        $(YELLOW)/plugin marketplace add $(MARKETPLACE_PATH)$(NC)"; \
			errors=$$((errors + 1)); \
		fi; \
	else \
		echo "   $(RED)✗$(NC) known_marketplaces.json not found"; \
		errors=$$((errors + 1)); \
	fi; \
	echo ""; \
	\
	echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"; \
	echo "$(YELLOW)2. Checking Marketplace Directory...$(NC)"; \
	echo ""; \
	marketplace_dir="$(HOME)/.claude/plugins/marketplaces/$(MARKETPLACE_NAME)"; \
	if [ -d "$$marketplace_dir" ]; then \
		echo "   $(GREEN)✓$(NC) Marketplace directory exists"; \
		echo "   $(BLUE)Path:$(NC) $$marketplace_dir"; \
		if [ -f "$$marketplace_dir/marketplace.json" ]; then \
			echo "   $(GREEN)✓$(NC) marketplace.json exists"; \
		else \
			echo "   $(RED)✗$(NC) marketplace.json missing"; \
			errors=$$((errors + 1)); \
		fi; \
	else \
		echo "   $(YELLOW)⚠$(NC)  Marketplace directory not found"; \
		echo "   $(BLUE)Expected:$(NC) $$marketplace_dir"; \
		warnings=$$((warnings + 1)); \
	fi; \
	echo ""; \
	\
	echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"; \
	echo "$(YELLOW)3. Checking Plugin Installations...$(NC)"; \
	echo ""; \
	for plugin in plugins/*/; do \
		plugin_name=$$(basename $$plugin); \
		echo "   $(BLUE)Plugin:$(NC) $$plugin_name"; \
		\
		source_path="$(MARKETPLACE_PATH)/$$plugin"; \
		install_path="$$marketplace_dir/plugins/$$plugin_name"; \
		\
		if [ -L "$$install_path" ]; then \
			target=$$(readlink "$$install_path"); \
			if [ -d "$$target" ]; then \
				echo "      $(GREEN)✓$(NC) Symlink exists and valid"; \
				echo "        $(BLUE)→$(NC) $$target"; \
			else \
				echo "      $(RED)✗$(NC) Symlink broken (target missing)"; \
				echo "        $(BLUE)Points to:$(NC) $$target"; \
				echo "        $(BLUE)Should be:$(NC) $$source_path"; \
				echo "        $(BLUE)Fix:$(NC) Run: ln -sf \"$$source_path\" \"$$install_path\""; \
				errors=$$((errors + 1)); \
			fi; \
		elif [ -d "$$install_path" ]; then \
			echo "      $(YELLOW)⚠$(NC)  Directory exists (not a symlink)"; \
			warnings=$$((warnings + 1)); \
		else \
			echo "      $(RED)✗$(NC) Not installed"; \
			echo "        $(BLUE)Fix:$(NC) Run: /plugin install $$plugin_name@$(MARKETPLACE_NAME)"; \
			errors=$$((errors + 1)); \
		fi; \
		\
		if grep -q "\"$$plugin_name@$(MARKETPLACE_NAME)\"" "$(HOME)/.claude/plugins/installed_plugins.json" 2>/dev/null; then \
			echo "      $(GREEN)✓$(NC) Registered in installed_plugins.json"; \
		else \
			echo "      $(YELLOW)⚠$(NC)  Not registered in installed_plugins.json"; \
			warnings=$$((warnings + 1)); \
		fi; \
		echo ""; \
	done; \
	\
	echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"; \
	echo "$(YELLOW)4. Checking Plugin Skills...$(NC)"; \
	echo ""; \
	for plugin in plugins/*/; do \
		plugin_name=$$(basename $$plugin); \
		if [ -d "$$plugin/skills" ]; then \
			skill_count=$$(find "$$plugin/skills" -name "SKILL.md" | wc -l | tr -d ' '); \
			if [ $$skill_count -gt 0 ]; then \
				echo "   $(BLUE)$$plugin_name:$(NC) $$skill_count skill(s)"; \
				for skill_file in $$plugin/skills/*/SKILL.md; do \
					skill_name=$$(basename $$(dirname $$skill_file)); \
					echo "      - /$$plugin_name:$$skill_name"; \
				done; \
			fi; \
		fi; \
	done; \
	echo ""; \
	\
	echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"; \
	echo "$(YELLOW)5. Quick Fix Commands...$(NC)"; \
	echo ""; \
	if [ $$errors -gt 0 ] || [ $$warnings -gt 0 ]; then \
		if ! grep -q '"$(MARKETPLACE_NAME)"' "$(HOME)/.claude/plugins/known_marketplaces.json" 2>/dev/null; then \
			echo "   $(YELLOW)Register marketplace:$(NC)"; \
			echo "      $(BLUE)make register$(NC)"; \
			echo ""; \
		fi; \
		echo "   $(YELLOW)Install/reinstall all plugins:$(NC)"; \
		echo "      $(BLUE)make install$(NC)"; \
		echo ""; \
		echo "   $(YELLOW)Update all plugins:$(NC)"; \
		echo "      $(BLUE)make update$(NC)"; \
		echo ""; \
		echo "   $(YELLOW)Uninstall all plugins:$(NC)"; \
		echo "      $(BLUE)make uninstall$(NC)"; \
		echo ""; \
	fi; \
	\
	echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"; \
	echo "$(YELLOW)📊 Summary:$(NC)"; \
	echo ""; \
	if [ $$errors -eq 0 ] && [ $$warnings -eq 0 ]; then \
		echo "   $(GREEN)✓ All checks passed! Your marketplace is healthy.$(NC)"; \
	else \
		if [ $$errors -gt 0 ]; then \
			echo "   $(RED)✗ Found $$errors error(s)$(NC)"; \
		fi; \
		if [ $$warnings -gt 0 ]; then \
			echo "   $(YELLOW)⚠ Found $$warnings warning(s)$(NC)"; \
		fi; \
		echo ""; \
		echo "   $(BLUE)Run the fix commands above to resolve issues.$(NC)"; \
	fi; \
	echo ""; \
	echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"

.DEFAULT_GOAL := help
