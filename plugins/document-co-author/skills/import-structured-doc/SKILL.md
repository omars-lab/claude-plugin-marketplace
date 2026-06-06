---
name: import-structured-doc
description: Import a loose source document into a structured target template — convert source notes into a formatted doc with consistent sections, frontmatter, backlinks, and a hashtag/tag taxonomy
---

# Import Structured Doc

You are a document importer. You take a loose, unstructured source document (raw notes, a planning scratchpad, an exported page) and **restructure it into a target template** with consistent sections, frontmatter, backlinks, a hashtag/tag taxonomy, and a clear naming convention — without losing any of the original content.

This skill is template-driven. The **source directory**, the **target directory**, and the **section template** are all supplied or confirmed by the user at runtime. Nothing about the structure is hardcoded. A common example is converting loose "habit" planning notes into structured habit posts, but the same workflow applies to any source-doc → structured-doc conversion (meeting notes → decision records, research dumps → wiki pages, brainstorm files → spec docs, etc.).

The default 8-section template (Frontmatter, Diagram/Embed, Questions, Decision, Strategy, References, Kinds of Action Items, Specific Action Items) is an **example/default**, not law. Confirm or override it with the user before importing.

## Task Management (MANDATORY)

Create all 8 tasks with dependencies before doing any work. Run `TaskList()` afterward to show the workflow to the user.

```javascript
// Task #1: Gather configuration
TaskCreate({ subject: "Gather import configuration", activeForm: "Gathering configuration",
  description: "Use AskUserQuestion to confirm: source directory, target directory, section template (default or custom), tag/hashtag taxonomy root, file naming + extension, and whether processed source files should be tracked/moved. Store these for all later tasks." })

// Task #2: Git checkpoint (clean baseline)
TaskCreate({ subject: "Create git checkpoint", activeForm: "Creating git checkpoint",
  description: "In the repo that owns the target dir: run git status. If dirty, auto-commit pending changes to create a clean baseline. Record CHECKPOINT_COMMIT = git rev-parse HEAD. Do NOT prompt the user for this commit." })

// Task #3: Discover source + check for prior imports
TaskCreate({ subject: "Discover sources and check prior imports", activeForm: "Discovering sources",
  description: "List candidate files in source dir. For each, check for an import-tracking header and check the target dir / done dir for an existing equivalent. Skip already-imported docs and note them." })

// Task #4: Read and analyze each source
TaskCreate({ subject: "Read and analyze each source", activeForm: "Analyzing sources",
  description: "Read each pending source fully. Extract the core subject/title (strip filler words). Note any diagram/embed links, questions, rationale, strategy, references, and the abstract-vs-specific split of action items." })

// Task #5: Decide create-new vs merge (ask if unsure)
TaskCreate({ subject: "Decide create-new vs merge", activeForm: "Deciding create vs merge",
  description: "For each source, evaluate whether it should become a new doc or be merged into an existing one (similar objective, overlapping themes, complementary/minimal content). If uncertain, use AskUserQuestion to confirm before proceeding." })

// Task #6: Generate structured docs
TaskCreate({ subject: "Generate structured docs", activeForm: "Generating structured docs",
  description: "For each source: generate frontmatter, map content into the confirmed template sections, build the tag/hashtag taxonomy, apply naming conventions, and preserve ALL original content. See guides/section-template.md for the default template + extraction rules." })

// Task #7: Validate (quality checklist + git diff)
TaskCreate({ subject: "Validate against checklist and git diff", activeForm: "Validating",
  description: "Run the quality checklist (content preserved, sections present + ordered, frontmatter valid, taxonomy correct, naming correct). Run git diff and confirm only expected files changed. STOP and report if anything unexpected changed." })

// Task #8: Track sources + commit
TaskCreate({ subject: "Track sources and commit", activeForm: "Tracking and committing",
  description: "Only if Task #7 passes. Add import-tracking header to each source (the ONLY edit to a source), optionally move it to a done dir, then stage and commit with a descriptive message." })
```

After creating tasks, wire dependencies:

```javascript
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
TaskUpdate({ taskId: "5", addBlockedBy: ["4"] })
TaskUpdate({ taskId: "6", addBlockedBy: ["5"] })
TaskUpdate({ taskId: "7", addBlockedBy: ["6"] })
TaskUpdate({ taskId: "8", addBlockedBy: ["7"] })
```

Dependency flow:

```
#1 Gather config
 └─► #2 Git checkpoint
      └─► #3 Discover + check prior imports
           └─► #4 Read + analyze
                └─► #5 Create vs merge
                     └─► #6 Generate structured docs
                          └─► #7 Validate (checklist + git diff)
                               └─► #8 Track sources + commit
```

## Your Workflow

### Phase 0 — Create Tasks (MANDATORY FIRST STEP)

Create all 8 tasks, wire dependencies, and run `TaskList()`.

### Phase 1 (Task #1) — Gather Configuration

Nothing is assumed. Confirm the runtime configuration with the user:

```javascript
AskUserQuestion({
  questions: [
    {
      question: "Where are the loose source documents, and where should the structured docs be written?",
      header: "Directories",
      options: [
        { label: "I'll give paths", description: "Provide an absolute source dir and an absolute target dir" },
        { label: "Same dir, in place", description: "Restructure files in place within one directory" }
      ]
    },
    {
      question: "Which section template should the output follow?",
      header: "Template",
      options: [
        { label: "Default 8-section", description: "Frontmatter, Diagram/Embed, Questions, Decision, Strategy, References, Kinds of Action Items, Specific Action Items (see guides/section-template.md)" },
        { label: "Custom sections", description: "I'll provide the ordered list of sections and what goes in each" }
      ]
    },
    {
      question: "How should the tag/hashtag taxonomy and file naming work?",
      header: "Taxonomy & naming",
      options: [
        { label: "Default convention", description: "slug-derived filename matching frontmatter slug; nested tags as #<root>/<theme>" },
        { label: "Custom convention", description: "I'll specify the tag root, naming pattern, and file extension" }
      ]
    },
    {
      question: "After importing a source, how should it be tracked?",
      header: "Source tracking",
      options: [
        { label: "Header + move to done", description: "Add an import-tracking header, then move the source to a done/ dir" },
        { label: "Header only", description: "Add the tracking header but leave the source where it is" },
        { label: "Leave untouched", description: "Do not modify or move sources at all" }
      ]
    }
  ]
})
```

Store all answers. These drive every later phase.

### Phase 2 (Task #2) — Git Checkpoint

Because this skill **creates and modifies files**, establish a clean baseline first so any unintended change is visible in a later diff.

```bash
cd "<repo-owning-the-target-dir>"
git status --short
# If there are pending changes, auto-commit them to create a clean baseline:
git add -A
git commit -m "chore: checkpoint before import-structured-doc run

Auto-committed by import-structured-doc to create a clean baseline.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
CHECKPOINT_COMMIT=$(git rev-parse HEAD)
```

This is an auto-commit — **do not prompt the user** for it. If the repo is already clean, just record `CHECKPOINT_COMMIT`.

### Phase 3 (Task #3) — Discover Sources & Check Prior Imports

- List candidate files in the source directory.
- For each, check whether it already carries an import-tracking header.
- Check the target directory (and any `done/` directory) for an equivalent doc by name/slug/subject.
- Skip anything already imported and note it. Only process pending sources.

### Phase 4 (Task #4) — Read & Analyze

Read each pending source **fully**. Identify:
- The core subject/title — strip filler/planning words; use specific, non-generic terms.
- Any diagram/embed links, standalone references, questions, rationale, and strategy.
- The split between **abstract/repeatable** activities and **specific/one-off** action items.

Do not lose content — you are reorganizing, not rewriting.

### Phase 5 (Task #5) — Decide Create-New vs Merge

For each source, decide whether to create a new doc or merge into an existing one. Merge when objectives overlap heavily, themes/categories coincide, content is complementary, or one side is minimal. Keep them separate when objectives, activity types, or purposes are distinct. **If uncertain, ask:**

```javascript
AskUserQuestion({
  questions: [
    {
      question: "This source overlaps with an existing doc. Create a new doc or merge into the existing one?",
      header: "Create or merge",
      options: [
        { label: "Create new", description: "The objective is distinct enough to stand alone" },
        { label: "Merge into existing", description: "Combine sections, themes, and tasks; preserve all content from both" }
      ]
    }
  ]
})
```

### Phase 6 (Task #6) — Generate Structured Docs

For each source, produce the structured output per the confirmed template: generate frontmatter, map content into the ordered sections, build the tag/hashtag taxonomy, and apply the naming convention. Preserve all original content.

The default template, per-section extraction rules, the abstract/specific split, the hashtag rules, frontmatter shape, and naming conventions are detailed in **`guides/section-template.md`**. Read it before generating, and adapt it if the user supplied a custom template.

### Phase 7 (Task #7) — Validate

Run the quality checklist (below) and validate the change set with git:

```bash
cd "<repo-owning-the-target-dir>"
git status --short
git diff --stat
```

Confirm **only the expected files** were created/modified. If anything unexpected changed, **STOP**, report it, and do not commit.

### Phase 8 (Task #8) — Track Sources & Commit

Only after Task #7 passes:
- Per the Phase 1 choice, add an import-tracking header to each processed source. This is the **only** edit ever made to a source file:

  ```
  ---
  **IMPORTED FROM**: `<source-path>`
  **IMPORTED INTO**: `<target-path>`
  **IMPORT DATE**: <today's date>
  ---
  ```

- Optionally move the source to the configured `done/` directory.
- Stage and commit:

  ```bash
  git add -A
  git commit -m "feat: import N source docs into structured template

  - Created/merged: <list>
  - Tracked sources with import headers
  Skill: import-structured-doc

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
  ```

## Success Criteria

- All original content is preserved — nothing dropped, original phrasing kept where possible.
- Every confirmed template section is present and in the correct order.
- Frontmatter is valid and complete (slug/title/description/tags/date as configured).
- Tag/hashtag taxonomy is consistent: only root-level items carry tags; sub-items inherit from their parent; all tags follow the configured `<root>/<theme>` shape.
- Specific action items are grouped by theme and sorted by importance; every specific item maps to an abstract category.
- File naming matches the configured convention (slug-aligned filename + correct extension).
- Already-imported sources were detected and skipped.
- Merge-vs-create decisions were made deliberately (and confirmed with the user when uncertain).
- `git diff` shows only the expected files changed; the run was committed cleanly.

## Common Mistakes to Avoid

- **Hardcoding paths or template specifics.** Source dir, target dir, sections, taxonomy, and naming all come from Phase 1 — never assume them.
- **Editing source files beyond the tracking header.** The tracking header is the only permitted change to a source.
- **Losing or rewriting content.** Reorganize; don't paraphrase away detail. Even minimal-content sources keep the full section skeleton.
- **Tagging sub-items.** Only un-indented/root items get hashtags; indented sub-items inherit from their parent.
- **Converting strategic questions into statements.** Keep questions in question form, grouped under their relevant abstract category.
- **Skipping the git checkpoint.** Without a clean baseline you cannot prove the diff is clean.
- **Committing despite an unexpected diff.** If validation surfaces changes you did not intend, stop and report — do not commit.
- **Creating a new doc when a merge was correct (or vice versa).** When unsure, ask before writing.
- **Generic, ambiguous titles.** Use specific terms that clearly name the actual subject.
