---
name: generate-makefile
description: Generate or enhance Makefiles following CEG standards for actionability, consistency, and simplicity. Creates test targets, validation, installation helpers, and actionable output with clear status indicators.
---

# Generate Makefile

You are a Makefile generator following CEG standards for actionability, consistency, and simplicity. When this skill is invoked, analyze the repository and generate or enhance a Makefile following established patterns.

## Core Principles

### 1. Actionability
- **Copy-paste ready commands** - Output should include exact commands users can copy
- **Status indicators** - Use ✓/✗/⚠️ to show state clearly
- **Progressive disclosure** - Show only what's needed at each step
- **Contextual help** - Provide next steps based on current state
- **Specific instructions** - "Run this exact command" not "configure appropriately"

### 2. Consistency
- **Naming conventions** - `test-<component>`, `install-<component>`, `setup-<component>`
- **Parameter patterns** - Use variables for paths, keep DRY
- **Output format** - Consistent headers, status messages, completion notices
- **Target structure** - Help first, then logical groupings

### 3. Simplicity
- **One target = one action** - Don't overload targets with multiple purposes
- **Clear descriptions** - Every target has `## Description` comment
- **Minimal dependencies** - Avoid complex dependency chains
- **Fail fast** - Check prerequisites early, give clear error messages
- **No hidden magic** - Be explicit about what's happening

## Standard Makefile Structure

```makefile
.PHONY: help <all-targets>

# Variables at top
PROJECT_DIR := $(shell pwd)
COMPONENT_DIR := $(PROJECT_DIR)/component

# Terminal title helper (only fires outside Claude Code sessions)
define set-title
	@if [ -z "$$CLAUDECODE" ]; then echo -ne "\033]0;$(1)\007"; fi
endef

help: ## Show this help message
	@echo "Project Name - Make Targets"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make validate            # Validate configuration"
	@echo "  make test-all            # Run all tests"

# Testing targets
test-component: ## Test component with description
	$(call set-title,Testing component)
	@echo "==> Testing component..."
	@echo ""
	[test commands]
	@echo ""
	@echo "✓ Test complete!"

# Installation targets
install-component: ## Install component (show what to run)
	$(call set-title,Installing component)
	@echo "==> Installing component..."
	@echo ""
	@echo "Prerequisites:"
	@echo "  ✓ Check 1"
	@echo "  ✗ Check 2 - run this to fix"
	@echo ""
	@echo "Run this command:"
	@echo "  /command install component"

# Validation targets
validate: ## Validate project configuration
	$(call set-title,Validating project)
	@echo "==> Validating project..."
	@echo ""
	[validation checks]
	@echo ""
	@echo "==> Validation complete!"

# Utility targets
list-components: ## List components with status (✓/✗/⚠️)
	$(call set-title,Listing components)
	@echo "==> Components:"
	@echo ""
	@echo "✓ component-1 - installed"
	@echo "✗ component-2 - not installed"
	@echo "  → To install: make install-component-2"

clean: ## Remove temporary files
	$(call set-title,Cleaning project)
	@echo "==> Cleaning up..."
	@find . -name ".DS_Store" -delete
	@echo "==> Clean complete!"
```

## Target Patterns

### Help Target (Always First)

```makefile
help: ## Show this help message
	@echo "Project Name - Make Targets"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make example-1           # Description"
	@echo "  make example-2           # Description"
	@echo ""
	@echo "Notes:"
	@echo "  - Important note 1"
	@echo "  - Important note 2"
```

**Standard:** Help is default target, shows sorted list with examples

### Test Targets

```makefile
test-component: ## Test the component (non-interactive)
	$(call set-title,Testing component)
	@echo "==> Testing component..."
	@echo "==> Running: command --flag value"
	@echo ""
	@command --flag value
	@echo ""
	@echo "✓ Test complete!"

test-all: ## Test all components sequentially
	$(call set-title,Testing all components)
	@echo "==> Testing all components..."
	@echo ""
	@$(MAKE) test-component-1
	@echo ""
	@echo "---"
	@echo ""
	@$(MAKE) test-component-2
	@echo ""
	@echo "==> All tests complete!"
```

**Standards:**
- Non-interactive by default (use `<<<` for input if needed)
- Show what command is being run
- Clear start/end markers
- Use `@$(MAKE)` for chaining targets

### Installation Targets

```makefile
install-component: ## Install component to system
	$(call set-title,Installing component)
	@echo "==> Installing component..."
	@echo ""
	@echo "Checking prerequisites..."
	@if ! command -v dependency >/dev/null 2>&1; then \
		echo "❌ dependency not found in PATH"; \
		echo ""; \
		echo "Please install dependency first."; \
		exit 1; \
	fi
	@echo "✓ dependency found"
	@echo ""
	@echo "==> Installation Instructions:"
	@echo ""
	@echo "Run this command in the target system:"
	@echo "  /command install component-name"
	@echo ""
	@echo "Or follow these steps:"
	@echo "  1. Step one"
	@echo "  2. Step two"
```

**Standards:**
- Check prerequisites first
- Use ✓/✗/❌/⚠️ for status
- Provide exact commands to run
- Exit early with clear error messages

### List/Status Targets

```makefile
list-components: ## List components (shows ✓/✗/⚠️ status)
	$(call set-title,Listing components)
	@echo "==> Project Components"
	@echo ""
	@if [ -f "$$HOME/.config/state.json" ]; then \
		STATE_INSTALLED="true"; \
		echo "Project Status: ✓ Configured"; \
	else \
		STATE_INSTALLED="false"; \
		echo "Project Status: ✗ Not Configured"; \
	fi
	@echo ""
	@echo "==> Components:"
	@echo ""
	@for component in components/*/; do \
		component_name=$$(basename $$component); \
		if [ -d "$$HOME/.installed/$$component_name" ]; then \
			echo "✓ 📦 $$component_name"; \
			echo "   Description of component"; \
		else \
			echo "✗ 📦 $$component_name"; \
			echo "   Description of component"; \
			echo "   → To install: make install-$$component_name"; \
		fi; \
		echo ""; \
	done; \
	echo "Legend:"; \
	echo "  ✓  - Installed"; \
	echo "  ✗  - Not installed"; \
	echo "  ⚠️  - Configuration issue"
```

**Standards:**
- Show overall project status first
- Per-component status with indicators
- Actionable commands for each not-installed item
- Clear legend explaining indicators
- Empty line between items for readability

### Validation Targets

```makefile
validate: ## Validate project configuration
	$(call set-title,Validating project)
	@echo "==> Validating project configuration..."
	@echo ""
	@if command -v jq >/dev/null 2>&1; then \
		echo "==> Checking JSON files..."; \
		for file in $$(find . -name "*.json"); do \
			echo "  Checking $$file..."; \
			jq empty "$$file" && echo "  ✓ $$file is valid"; \
		done; \
	else \
		echo "⚠ jq not installed, skipping JSON validation"; \
		echo "  Install with: brew install jq"; \
	fi
	@echo ""
	@echo "==> Checking directory structure..."
	@for dir in required_dir_1 required_dir_2; do \
		if [ -d "$$dir" ]; then \
			echo "  ✓ $$dir exists"; \
		else \
			echo "  ✗ Missing $$dir"; \
		fi; \
	done
	@echo ""
	@echo "==> Validation complete!"
```

**Standards:**
- Group related checks together
- Show what's being validated
- Use ✓/✗/⚠️ for status
- Provide installation commands for missing tools
- Continue validation even if non-critical checks fail

## Output Format Standards

### Headers

```makefile
@echo "==> Action Description"
@echo ""
```

### Progress Indicators

```makefile
@echo "==> Step 1: Doing thing..."
@echo "✓ Thing completed"
@echo ""
@echo "==> Step 2: Doing other thing..."
```

### Status Messages

```makefile
✓  - Success, completed, installed, valid
✗  - Not done, not installed, missing
❌  - Error, failed, invalid
⚠️  - Warning, skipped, optional issue
📦  - Package, component, plugin
🔧  - Configuration, setup
📝  - Documentation, notes
→  - Action to take, command to run
```

### Completion Messages

```makefile
@echo ""
@echo "✓ Test complete!"
@echo "==> Validation complete!"
@echo "==> All tests complete!"
```

### Error Messages

```makefile
echo "❌ Prerequisite not found"
echo ""
echo "Please install it first:"
echo "  brew install package"
echo ""
exit 1
```

## Terminal Title Pattern

When targets run in a standalone terminal (not inside a Claude Code session), set the terminal tab/window title to reflect the target being run. This gives users immediate visual context about what's executing, especially when multiple terminal tabs are open.

### Detection

Claude Code sets the `CLAUDECODE` environment variable. Guard the title escape so it only fires in standalone terminals:

```makefile
# Define a reusable macro at the top of the Makefile (after variables)
define set-title
	@if [ -z "$$CLAUDECODE" ]; then echo -ne "\033]0;$(1)\007"; fi
endef
```

### Usage in Targets

Call `$(call set-title,...)` as the **first line** of every target:

```makefile
test-component: ## Test the component
	$(call set-title,Testing component)
	@echo "==> Testing component..."
	@command --flag value
	@echo "✓ Test complete!"

install-component: ## Install component
	$(call set-title,Installing component)
	@echo "==> Installing component..."
	...

validate: ## Validate project configuration
	$(call set-title,Validating project)
	@echo "==> Validating project configuration..."
	...
```

### Title Naming Convention

Use present participle form matching the target action:

| Target | Title |
|--------|-------|
| `test-component` | `Testing component` |
| `test-all` | `Testing all components` |
| `install-plugin` | `Installing plugin` |
| `validate` | `Validating project` |
| `clean` | `Cleaning project` |
| `list-components` | `Listing components` |

**Standards:**
- Title should be short and descriptive (what the user sees in their tab bar)
- Use present participle ("Testing...", "Installing...", not "Test" or "Install")
- Include the project or component name when it adds clarity
- `help` target does NOT need a title (it runs instantly)

## Non-Interactive Testing Pattern

For CLI tools that expect interactive input:

```makefile
test-component: ## Test component with input (non-interactive)
	@echo "==> Testing component..."
	@echo "==> Running: command with-input"
	@echo ""
	@command <<< "input-value"
	@echo ""
	@echo "✓ Test complete!"
```

**Standard:** Use here-strings `<<<` to provide input non-interactively

## Variable Patterns

```makefile
# Paths
PROJECT_DIR := $(shell pwd)
COMPONENT_DIR := $(PROJECT_DIR)/components
BUILD_DIR := $(PROJECT_DIR)/build

# External paths (user-specific)
EXTERNAL_DIR := /Users/username/path/to/external

# Computed values
COMPONENT_NAME := $(shell basename $(PROJECT_DIR))
VERSION := $(shell cat VERSION 2>/dev/null || echo "unknown")

# Configuration
TIMEOUT := 120000
PYTHON_ENV := myenv
```

**Standards:**
- Define at top of Makefile
- Use `:=` for immediate evaluation
- Group by category (paths, config, computed)
- Comment external/user-specific paths

## Conditional Logic Pattern

```makefile
target: ## Description
	@if [ condition ]; then \
		echo "Condition met"; \
		command; \
	else \
		echo "Condition not met"; \
		echo "Do this instead"; \
		exit 1; \
	fi
```

**Standards:**
- Use `\` for line continuation in shell blocks
- Always provide else branch or exit code
- Echo what's happening at each branch

## Common Targets to Include

### Essential Targets

```makefile
help       - Show available commands (default target)
validate   - Validate project configuration
clean      - Remove temporary files
```

### Testing Targets

```makefile
test-<component>  - Test specific component
test-all          - Test all components
test-integration  - Run integration tests
```

### Installation Targets

```makefile
install-<component>  - Show how to install component
setup-<component>    - One-time setup for component
```

### Utility Targets

```makefile
list-<things>   - List things with status indicators
status          - Show overall project status
tree            - Show directory structure
```

## When to Create This Makefile

Generate a Makefile when:

1. **Project has multiple components** - Testing, building, installing multiple parts
2. **Complex setup steps** - Installation requires multiple tools or steps
3. **Repeated commands** - Users run same commands frequently
4. **Status checking needed** - Want to show what's installed/configured
5. **Onboarding** - New contributors need clear entry points

## What to Include

Analyze the project for:

- **Testing needs** - How do you test components?
- **Installation steps** - What needs to be installed/configured?
- **Validation requirements** - What should be validated?
- **Common operations** - What do users do frequently?
- **Prerequisites** - What tools/dependencies are required?

## Instructions

When invoked:

1. **Analyze the repository:**
   - Look for components, plugins, services
   - Identify test scripts or test instructions
   - Find configuration files
   - Check for installation documentation
   - Note prerequisites and dependencies

2. **Generate Makefile with:**
   - Help target (first, default)
   - Test targets for each component
   - Installation/setup targets
   - Validation target
   - List/status targets with indicators
   - Clean target
   - Utility targets as needed

3. **Follow standards:**
   - ✓ All targets have `## Description` comments
   - ✓ Help target shows examples
   - ✓ Tests are non-interactive by default
   - ✓ Status indicators used consistently (✓/✗/⚠️)
   - ✓ Actionable output with exact commands
   - ✓ Clear error messages with remediation steps
   - ✓ Variables defined at top
   - ✓ `set-title` macro defined and used on all targets (except `help`)
   - ✓ `.PHONY` declarations included

4. **Document patterns used:**
   - Explain variable definitions
   - Note any user-specific paths to update
   - Describe testing approach
   - Highlight key targets for common workflows

5. **Provide usage guidance:**
   - How to run the Makefile
   - Which targets to use for common tasks
   - How to extend with new targets
   - Maintenance notes

## Example Usage

```bash
# Generate Makefile for current project
/code-quality-manager:generate-makefile

# Generate with specific focus
/code-quality-manager:generate-makefile --focus=testing

# Enhance existing Makefile
/code-quality-manager:generate-makefile --enhance
```

## Output

Generate a complete Makefile with:

1. **Header comment** - Project name, description, usage
2. **Variables section** - All configurable paths and values
3. **Help target** - Default, shows all targets with examples
4. **Testing targets** - For each component, plus test-all
5. **Installation targets** - With prerequisite checks
6. **Validation target** - Check configuration and structure
7. **List/status targets** - Show component status with indicators
8. **Utility targets** - Clean, tree, etc.
9. **Footer comment** - Maintenance notes, extension guidance

## Quality Checklist

Before finalizing, verify:

✅ Help is the default target (first in file)
✅ All targets have `.PHONY` declarations
✅ All targets have `## Description` comments
✅ Status indicators (✓/✗/⚠️) used consistently
✅ Non-installed items show install commands
✅ Error messages include remediation steps
✅ Variables defined and documented at top
✅ Test targets are non-interactive
✅ Terminal title set via `set-title` macro on all targets (except `help`)
✅ No user-specific hardcoded paths (or clearly marked)
✅ Output is clean and readable
✅ Examples provided in help text
✅ Targets are sorted logically (help, test, install, validate, util)

## Anti-Patterns to Avoid

❌ **Complex target dependencies** - Keep targets independent where possible
❌ **Hidden behavior** - Echo what's happening at each step
❌ **Interactive prompts in tests** - Use here-strings or flags for non-interactive
❌ **Generic error messages** - "Error" → "❌ Dependency X not found. Install with: command"
❌ **Unclear status** - "Done" → "✓ Test complete!"
❌ **Missing help text** - Every target needs `## Description`
❌ **Inconsistent naming** - Pick pattern and stick to it (test-X, install-X)
❌ **Hardcoded paths** - Use variables for paths that might change

## Success Criteria

A well-generated Makefile should:

✅ User can understand all available commands with `make help`
✅ User can test any component with `make test-<component>`
✅ User knows exactly what to run to install/setup (copy-paste ready)
✅ User can see status at a glance with indicators
✅ User gets clear error messages with remediation steps
✅ New contributors can onboard by reading the Makefile
✅ Maintainers can easily add new targets following patterns

Remember: **The Makefile is executable documentation**. It should be as clear and helpful as written docs, but with the power to actually perform actions.

## Task Management

Use `TaskCreate` and `TaskUpdate` to track progress across the generation workflow.

## User Interaction

Use `AskUserQuestion` when the intent is ambiguous — generate from scratch, enhance an existing Makefile, or focus on specific target types.
