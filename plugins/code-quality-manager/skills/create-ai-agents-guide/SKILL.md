---
name: create-ai-agents-guide
description: Generate an AI-AGENTS.md governance guide for the current repo — a 13-section playbook telling AI agents how to safely modify the codebase. Use when asked to "create AI-AGENTS.md", "add an AI agents guide", "write a governance guide for AI modifications", or to document architecture, critical rules, and constraints for agent edits.
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, TaskCreate, TaskUpdate, AskUserQuestion
---

# Create AI-AGENTS Guide

You generate a comprehensive `AI-AGENTS.md` at the root of **the repository you are invoked in**. The file is a governance guide: it tells future AI agents the architecture, conventions, critical rules, and constraints they must respect when editing this codebase. You must **analyze the actual repo first**, then populate the 13-section template with real, repo-specific facts — never ship empty `[placeholders]`.

The template lives in [guides/ai-agents-template.md](guides/ai-agents-template.md). Read it before drafting.

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Analyze repository", description: "Detect stack, structure, entry points, conventions, test/build commands", activeForm: "Analyzing repository" })
TaskCreate({ subject: "Scope sections", description: "Confirm repo type and which of the 13 sections apply", activeForm: "Scoping sections" })
TaskCreate({ subject: "Draft AI-AGENTS.md", description: "Populate template sections with real, repo-specific content", activeForm: "Drafting AI-AGENTS.md" })
TaskCreate({ subject: "Write and verify", description: "Write file to repo root, confirm no leftover placeholders", activeForm: "Writing and verifying" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

## Git Safety (MANDATORY — this skill writes files)

This skill writes an `AI-AGENTS.md` to the repo. Run `git status` first; if dirty, offer to commit a baseline. Record the current commit as `CHECKPOINT`. After writing, run `git diff CHECKPOINT` and confirm only `AI-AGENTS.md` was created/changed. If unexpected changes appear, stop and report before committing.

## Your Workflow

### Phase 1 — Analyze the Repository

Discover the facts that will fill the template. Do not guess; read the repo.

1. Identify the stack from manifests:
   ```bash
   ls package.json pyproject.toml Cargo.toml go.mod pom.xml build.gradle Gemfile composer.json 2>/dev/null
   ```
2. Map top-level structure and entry points:
   ```bash
   ls -la
   git ls-files | head -200
   ```
3. Find test/build/run commands (Makefile, scripts, CI):
   ```bash
   grep -E '^[a-zA-Z0-9_-]+:' Makefile 2>/dev/null
   ls .github/workflows 2>/dev/null
   ```
4. Read the README and any existing docs to capture purpose and conventions.
5. Skim core source files to learn real patterns: state management, data flow, naming, recurring component/module shapes. Note 1-2 real code snippets to cite in Section 6.
6. For UI repos, locate the theme/design tokens (colors, spacing, breakpoints).

### Phase 2 — Scope the Sections

Confirm the repo type so you keep relevant sections and drop ones that don't apply (e.g. omit "Design System" for a backend library).

```javascript
AskUserQuestion({
  questions: [{
    question: "What kind of repository is this? (Pick the closest — it determines which sections apply.)",
    header: "Repo Type",
    options: [
      { label: "Frontend / UI app", description: "Include all 13 sections, including Design System & Styling and responsive/accessibility rules" },
      { label: "Backend service / API", description: "Drop Design System; emphasize data flow, API contracts, state/persistence, and critical rules" },
      { label: "Library / SDK / CLI", description: "Drop Design System; emphasize public API stability, usage patterns, and versioning constraints" },
      { label: "Monorepo / mixed", description: "Keep all sections; scope per package and note cross-package boundaries" }
    ],
    multiSelect: false
  }]
})
```

If anything critical is ambiguous after analysis (e.g. no detectable test command, unclear primary purpose), ask a focused follow-up rather than inventing details.

### Phase 3 — Draft AI-AGENTS.md

Working from [guides/ai-agents-template.md](guides/ai-agents-template.md), fill each in-scope section with concrete findings from Phase 1:

- Replace every `[bracketed placeholder]` with real values — repo name, technologies, actual file paths, real commands.
- Cite real code snippets from the codebase in Common Patterns, not invented examples.
- Make Critical Rules specific: name the functionality, files, and contracts that must not break.
- Make the Testing Checklist actionable with this repo's actual test/build commands.
- Drop sections that genuinely don't apply rather than leaving them empty.

### Phase 4 — Write and Verify

1. Write the populated guide to `AI-AGENTS.md` at the repo root. If one already exists, read it first and merge/update rather than blindly overwriting.
2. Verify no placeholders or fabricated paths remain:
   ```bash
   grep -nE '\[[a-z][^]]*\]' AI-AGENTS.md   # should find no leftover [placeholders]
   ```
3. Spot-check that referenced files and commands actually exist in the repo.
4. Report the path written and a short summary of which sections were included/omitted.

## Success Criteria

- [ ] `AI-AGENTS.md` exists at the repo root
- [ ] Every section reflects real, analyzed repo facts — no leftover `[placeholders]`
- [ ] Stack, file paths, and commands match what's actually in the repo
- [ ] Critical Rules name concrete functionality/files/contracts to protect
- [ ] Common Patterns cite real code from the codebase
- [ ] Testing Checklist uses the repo's actual test/build commands
- [ ] Sections that don't apply to this repo type are omitted, not left empty

## Common Mistakes to Avoid

- Shipping the template verbatim with `[brackets]` still in it
- Inventing file paths, commands, or code examples instead of reading the repo
- Including Design System sections for a backend/library repo
- Overwriting an existing AI-AGENTS.md without merging prior content
- Vague rules ("don't break things") instead of naming what must be preserved
- Hardcoding another project's paths/names — always generate for the current repo
