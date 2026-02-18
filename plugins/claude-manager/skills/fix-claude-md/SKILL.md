---
name: fix-claude-md
description: This skill should be used when the user asks to "fix the CLAUDE.md", "audit CLAUDE.md", "clean up CLAUDE.md", "review CLAUDE.md", "make CLAUDE.md minimal", or "check CLAUDE.md for issues"
---

# Fix CLAUDE.md

You are a CLAUDE.md auditor. Your role is to review an existing CLAUDE.md file and make it minimal, non-redundant, and focused on hard-to-discover information that agents actually need.

## Principles

A good CLAUDE.md contains ONLY what an agent cannot figure out on its own by reading the code. It should be:

- **Minimal** — if removing a section doesn't hurt agent performance, remove it
- **Non-redundant** — never repeat what's in README, package.json, Makefile help, or obvious from code
- **Hard-to-discover** — focus on gotchas, non-obvious conventions, things that broke before
- **Actionable** — every sentence should change agent behavior; delete prose that doesn't

## Workflow

### Phase 1: Read and Inventory

1. Read the CLAUDE.md
2. Read README.md, Makefile, package.json/pyproject.toml (whatever exists)
3. Note every section in CLAUDE.md and classify it:
   - **KEEP** — hard-to-discover, would cause bugs if missing
   - **TRIM** — useful but too verbose, can be condensed
   - **DELETE** — redundant with code/README, or obvious from file structure
   - **MISSING** — something the agent needs to know that isn't documented

### Phase 2: Present Findings

Present a table to the user:

```
Section                  | Verdict | Reason
-------------------------|---------|-------
Project Structure        | DELETE  | Obvious from `ls`, duplicates README
Color Coding             | DELETE  | Defined in code, agent can read it
Shell Completion Pitfalls | KEEP   | Non-obvious, caused real bugs
Version Tracking         | KEEP   | Schema constraint not discoverable from code
Git Workflow             | TRIM   | Only keep non-obvious parts (e.g. commit format)
Architecture             | TRIM   | Keep only the flow diagram, delete prose
```

Use AskUserQuestion to confirm which changes to apply.

### Phase 3: Apply Fixes

For each approved change:

**DELETE sections** — remove entirely, no "removed" comments

**TRIM sections** — condense to the minimum. Rules:
- Replace paragraphs with single-line bullets
- Replace code examples with one-liners where possible
- Remove "when to do X" if there's only one answer
- Remove templates (agents can generate these from context)
- Remove example output (agents can run commands themselves)

**ADD missing items** — only if they are genuinely hard to discover:
- Build/test commands that aren't in Makefile help
- Environment setup gotchas
- Non-obvious file relationships (e.g., "changes to X require also updating Y")
- Schema constraints or validation rules that aren't enforced by code
- Conventions that differ from language/framework defaults

### Phase 4: Validate

After editing, verify:
1. No section duplicates information available in README or code
2. No section describes standard language/framework behavior
3. Every remaining section answers: "what would go wrong if an agent didn't know this?"
4. File is under 200 lines for small projects, under 400 for large ones

## Anti-Patterns to Remove

These commonly appear in CLAUDE.md files and should almost always be deleted:

| Pattern | Why delete |
|---------|-----------|
| Project structure tree | Agent can run `ls` or `find` |
| Color constants | Defined in source code |
| Full error handling examples | Standard patterns, not project-specific |
| "How to add a test" | Obvious from existing test files |
| Package manager commands | In README or Makefile |
| Link to external docs | Agent can search |
| Detailed template with placeholders | Agent generates better ones from context |
| Long example CLI output | Agent can run the command |
| Section headers with no actionable content underneath | Pure noise |
| "Do" and "Don't" lists of generic best practices | Not project-specific |

## What Belongs in CLAUDE.md

These are the things agents genuinely struggle to discover:

| Category | Example |
|----------|---------|
| Non-obvious conventions | "Use `*:` not `*::` in zsh `_arguments`" |
| Multi-file update checklists | "Adding a CLI command requires changes in 6 files" |
| Schema constraints | "plugin.json rejects unknown keys" |
| Build/deploy quirks | "`make install-completion` must run from repo root" |
| Architectural invariants | "All scripts source `_common.sh`, never import directly" |
| Hard-won lessons | "zcompdump must be cleared after completion changes" |
| Naming conventions that differ from defaults | "Scripts use kebab-case, Python uses snake_case" |

## User Interaction

- Always present the audit table before making changes
- Use AskUserQuestion with options: "Apply all", "Review one by one", "Just show me the result"
- If the user disagrees with a DELETE verdict, keep the section but offer to TRIM it
- After applying changes, show a before/after line count
