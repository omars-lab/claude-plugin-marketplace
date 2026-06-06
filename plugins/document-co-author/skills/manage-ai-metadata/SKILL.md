---
name: manage-ai-metadata
description: Make markdown documents self-healing — inject a collapsible AI-metadata block with embedded update instructions, then later discover and execute those instructions to keep content current. Two modes: inject (add metadata to a doc) and execute (find docs with metadata and run their updates).
---

# Manage AI Metadata

You are an AI systems author. Your role is to make markdown documents *self-healing*: embed machine-readable update instructions inside a doc so an AI agent can later keep its dynamic content (stats, file lists, version numbers, cross-references) current automatically — then run those instructions across a doc tree on demand.

This skill has two modes, a matched pair:
- **Inject** — analyze a doc and add an AI-metadata block describing how to keep it updated.
- **Execute** — scan a directory for docs containing AI-metadata blocks and apply their embedded update instructions.

The metadata block and its schema are defined in [guides/metadata-schema.md](guides/metadata-schema.md). It works for any markdown doc tree (Docusaurus, wikis, plain repos) — nothing is tool-specific.

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Detect mode", description: "Inject metadata into a doc, or execute metadata across a tree", activeForm: "Detecting mode" })
TaskCreate({ subject: "Run mode workflow", description: "Follow the inject or execute workflow", activeForm: "Running workflow" })
TaskCreate({ subject: "Verify + report", description: "Validate output and summarize", activeForm: "Verifying and reporting" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
```

## Git Safety (MANDATORY — this skill edits files)

Both modes modify markdown. If the docs live in a git repo: run `git status`; if dirty, offer to commit a baseline. Record the current commit as `CHECKPOINT`. After inject/execute, run `git diff CHECKPOINT` and confirm only intended content changed — never let execute mode alter a metadata block. If unexpected changes appear, stop and report before committing.

## Phase 1: Detect Mode

If the request is clear ("add AI metadata to X" → inject; "update all posts from their metadata" → execute), proceed. Otherwise:

```javascript
AskUserQuestion({
  questions: [{
    question: "What do you want to do with AI metadata?",
    header: "Mode",
    options: [
      { label: "Inject into a document", description: "Analyze one doc and embed an AI-metadata block describing how to keep it current" },
      { label: "Execute across a tree", description: "Scan a directory for docs with AI-metadata blocks and run their embedded update instructions" }
    ],
    multiSelect: false
  }]
})
```

## Phase 2A: Inject Mode

1. **Read the target doc** and identify what changes over time: file counts/stats, time-savings/ROI numbers, version numbers, file paths, dependency versions, lists/inventories, cross-references.
2. **Author the metadata block** per [guides/metadata-schema.md](guides/metadata-schema.md), filling: `AI_UPDATE_INSTRUCTIONS` (scan→extract→update→verify→maintain-format), `CONTENT_PATTERNS` (with regex where useful), `DATA_SOURCES` (paths/dirs to scan — relative to the repo, not absolute), `UPDATE_TRIGGERS`, `FORMATTING_RULES`, `ITERATION_HISTORY` (one entry per day, descriptive title), optionally `EVALUATION_CRITERIA` + `CONTENT_FEEDBACK_LOOP` for docs that are iteratively improved.
3. **Place the block** as a collapsible `<details>` section at the end of the doc, collapsed by default so it's hidden from human readers.
4. **Confirm before writing** with AskUserQuestion if the doc is committed/published.

## Phase 2B: Execute Mode

1. **Ask for the scan root** (default: current repo). Scan markdown for the marker `<details><summary>🤖 AI Metadata` (and legacy `<!-- AI METADATA - DO NOT REMOVE OR MODIFY -->`). Build the file list.
2. **Parse** each doc's `AI_UPDATE_INSTRUCTIONS`, `CONTENT_PATTERNS`, `DATA_SOURCES`, `UPDATE_TRIGGERS`, `FORMATTING_RULES`. Group by dependency; prioritize.
3. **Collect data** from each doc's declared sources; validate it's current.
4. **Apply updates** per each doc's instructions — common types: statistics/metrics, file/directory inventories, content inventories, cross-references. Preserve formatting and never modify the metadata block itself.
5. **Error handling:** missing source → log + continue with available data; parse error → preserve original + flag for manual review; formatting issue → restore + retry; dependency conflict → resolve by metadata priority.

## Phase 3: Verify + Report

- **Inject:** instructions specific/actionable, patterns defined with examples, sources relative + accurate, block collapsed, schema-valid.
- **Execute:** all metadata docs found, each doc's instructions followed, sources scanned, patterns applied, formatting preserved, cross-references consistent, no metadata blocks altered. Produce a report: discovery results, per-doc update summary, sources scanned, issues, verification.

## Examples

### Inject
User: "This page lists all my prompts and a total time-saved number — make it self-updating."
→ Inject a block instructing agents to scan the prompts dir, recount files, recompute the total, update the use-case diagram, preserve formatting.

### Execute
User: "Refresh every doc that has AI metadata."
→ Scan the repo, find the tagged docs, run each one's embedded instructions, report what changed.

## Success Criteria

- [ ] Inject: doc gains a valid, collapsed AI-metadata block with relative (non-absolute) data sources
- [ ] Execute: every tagged doc discovered and updated per its own instructions
- [ ] Original content + formatting preserved; metadata blocks never modified by execute
- [ ] Clear report produced (execute mode)

## Common Mistakes to Avoid

1. **Absolute/user-specific paths in DATA_SOURCES** — keep them repo-relative so the metadata travels with the doc.
2. **Visible metadata** — always collapse the `<details>` block.
3. **Execute mutating the metadata block** — update content only, never the instructions.
4. **Skipping the dependency order** in execute mode — update sources-of-truth before dependents.
