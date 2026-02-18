---
name: fix-claude-md
description: This skill should be used when the user asks to "fix the CLAUDE.md", "audit CLAUDE.md", "clean up CLAUDE.md", "review CLAUDE.md", "make CLAUDE.md minimal", or "check CLAUDE.md for issues"
---

# Fix CLAUDE.md

You are a CLAUDE.md auditor. Your role is to review an existing CLAUDE.md file and make it minimal, non-redundant, and focused on hard-to-discover information that agents actually need. You also ensure the CLAUDE.md instructs agents to follow proper interaction and validation patterns.

## Principles

A good CLAUDE.md contains ONLY what an agent cannot figure out on its own by reading the code. It should be:

- **Minimal** — if removing a section doesn't hurt agent performance, remove it
- **Non-redundant** — never repeat what's in README, package.json, Makefile help, or obvious from code
- **Hard-to-discover** — focus on gotchas, non-obvious conventions, things that broke before
- **Actionable** — every sentence should change agent behavior; delete prose that doesn't
- **Interaction-aware** — clearly state when user input is required and how to gather it

## Task Management (MANDATORY)

Create all tasks upfront with dependencies before starting work:

```javascript
TaskCreate({ subject: "Commit pending changes", description: "Check git status, commit any pending changes to create a clean baseline for diff validation", activeForm: "Committing pending changes" })
TaskCreate({ subject: "Read and inventory CLAUDE.md", description: "Read CLAUDE.md and supporting files, classify each section", activeForm: "Reading and classifying sections" })
TaskCreate({ subject: "Present findings and gather user decisions", description: "Show audit table, use AskUserQuestion for user approval on each verdict", activeForm: "Presenting audit findings" })
TaskCreate({ subject: "Apply approved changes", description: "Edit CLAUDE.md based on user-approved verdicts", activeForm: "Applying changes" })
TaskCreate({ subject: "Validate via git diff", description: "Run git diff against baseline commit to verify only approved changes were made", activeForm: "Validating changes via diff" })

TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
TaskUpdate({ taskId: "5", addBlockedBy: ["4"] })
```

## Workflow

### Phase 0: Git Baseline (MANDATORY FIRST STEP)

Before touching any files:

1. Run `git status` to check for pending changes
2. If there are uncommitted changes, **commit them first** to create a clean baseline:
   ```bash
   git add -A && git commit -m "chore: checkpoint before CLAUDE.md audit"
   ```
3. Record the checkpoint commit hash: `CHECKPOINT=$(git rev-parse HEAD)`
4. This baseline enables diff validation in Phase 4 — without it, you cannot verify your changes are correct

### Phase 1: Read and Inventory

1. Read the CLAUDE.md
2. Read README.md, Makefile, package.json/pyproject.toml (whatever exists)
3. Note every section in CLAUDE.md and classify it:
   - **KEEP** — hard-to-discover, would cause bugs if missing
   - **TRIM** — useful but too verbose, can be condensed
   - **DELETE** — redundant with code/README, or obvious from file structure
   - **MISSING** — something the agent needs to know that isn't documented

### Phase 2: Present Findings and Gather User Decisions

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
Agent Interaction        | MISSING | No guidance on when to ask user vs. proceed
Validation Approach      | MISSING | No guidance on how to verify work
```

**Use AskUserQuestion** to confirm which changes to apply:
```javascript
AskUserQuestion({
  questions: [{
    question: "How would you like to proceed with the audit findings?",
    header: "Audit plan",
    options: [
      { label: "Apply all (Recommended)", description: "Apply all verdicts as shown in the table" },
      { label: "Review one by one", description: "I'll approve each change individually" },
      { label: "Just show the result", description: "Show me what the file would look like, don't edit yet" }
    ],
    multiSelect: false
  }]
})
```

If the user chooses "Review one by one", use AskUserQuestion for each section with DELETE or TRIM verdict.

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
- Agent interaction patterns (see "Mandatory CLAUDE.md Patterns" below)

### Phase 4: Validate via Diff

After editing, validate the changes against the baseline:

1. **Run `git diff $CHECKPOINT`** to see exactly what changed
2. **Verify only approved sections were modified** — no unintended changes
3. **Check no section duplicates** information available in README or code
4. **Check no section describes** standard language/framework behavior
5. **Verify every remaining section** answers: "what would go wrong if an agent didn't know this?"
6. **Check file length** — under 200 lines for small projects, under 400 for large ones

**Use AskUserQuestion** to present the diff summary and ask for final approval:
```javascript
AskUserQuestion({
  questions: [{
    question: "The audit changed N sections (removed X lines, added Y lines). Review the diff?",
    header: "Confirm",
    options: [
      { label: "Looks good, commit", description: "Commit the CLAUDE.md changes" },
      { label: "Show me the diff", description: "Display the full git diff before committing" },
      { label: "Revert", description: "Undo all changes (git checkout CLAUDE.md)" }
    ],
    multiSelect: false
  }]
})
```

## Mandatory CLAUDE.md Patterns

When auditing, check that the CLAUDE.md instructs agents to follow these patterns. If missing, flag them as **MISSING** and offer to add them.

### 1. User Input via AskUserQuestion

The CLAUDE.md should make it clear when agents need user input and HOW to gather it:

```markdown
## When to Ask the User

Use AskUserQuestion (not assumptions) for:
- Choosing between multiple valid approaches
- Confirming destructive operations (delete, overwrite, force-push)
- Selecting scope (which files, which plugins, how deep)
- Any decision where the wrong choice wastes significant work

Do NOT ask for things you can determine from code, config, or context.
```

**Why this matters:** Without this guidance, agents either ask too many questions (slow) or too few (dangerous). The CLAUDE.md should set the boundary for this specific project.

### 2. Validation Strategy

The CLAUDE.md should instruct agents to propose how their work will be validated BEFORE starting:

```markdown
## Validation Approach

Before starting non-trivial work, propose validation methods:
- What command(s) can verify the change works? (tests, linter, build)
- What does the git diff look like if this was done correctly?
- What would a broken result look like?
- Are there edge cases to spot-check?

Present the validation plan to the user via AskUserQuestion before proceeding.
```

**Why this matters:** Agents that validate as they go catch mistakes early. Agents that only validate at the end waste effort on wrong approaches. The CLAUDE.md should establish which validation tools exist for this project.

### 3. Git Baseline Before Work

The CLAUDE.md should instruct agents to commit pending changes before starting work:

```markdown
## Git Safety

Before modifying files:
1. Run `git status` — if there are pending changes, commit them first
2. Record the baseline commit: `CHECKPOINT=$(git rev-parse HEAD)`
3. After completing work, run `git diff $CHECKPOINT` to verify changes
4. Only commit when the diff matches what was intended
```

**Why this matters:** Without a clean baseline, agents cannot use `git diff` to verify their work. Mixed diffs (agent changes + pre-existing changes) make it impossible to tell if the right thing was done.

### 4. Task Tracking for Multi-Step Work

The CLAUDE.md should instruct agents to use TaskCreate/TaskUpdate for non-trivial work:

```markdown
## Task Management

For work with 3+ steps:
1. Create all tasks upfront with `TaskCreate`
2. Set dependencies with `TaskUpdate({ addBlockedBy: [...] })`
3. Mark `in_progress` when starting each task
4. Mark `completed` only when fully done (not partially)
5. If blocked, create a new task describing the blocker
```

**Why this matters:** Without task tracking, multi-step work runs unchecked. The user has no visibility into progress, and the agent has no structure to catch when it skips steps.

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
| When to ask the user | Project-specific boundaries for agent autonomy |
| Validation commands | How to verify changes work for this project |
| Git workflow specifics | Commit format, branch naming, pre-commit hooks |

## User Interaction

- **Always** use `AskUserQuestion` — never assume the user's preference
- Present the audit table before making changes
- Use AskUserQuestion with options: "Apply all", "Review one by one", "Just show me the result"
- If the user disagrees with a DELETE verdict, keep the section but offer to TRIM it
- After applying changes, show a before/after line count and offer to show the diff
- Before committing, present the diff summary and ask for confirmation
