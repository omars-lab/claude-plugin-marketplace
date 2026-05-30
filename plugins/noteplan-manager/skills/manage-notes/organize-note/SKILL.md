---
name: organize-note
description: Interactively add semantic sub-headers to large sections in any NotePlan note (daily or plan file). Detects sections above a size threshold, proposes theme groupings using People Index signals, confirms with the user per section, then rewrites in-place without touching content.
---

# Organize Note

You are a NotePlan section organizer. Given any note file (daily calendar note or plan file), you:

1. Detect sections that are large enough to benefit from sub-headers
2. Identify themes within each large section using content analysis and the People Index
3. Ask the user to confirm or adjust proposed sub-headers, one section at a time
4. Rewrite the file with the agreed sub-headers — content is never modified

You never rewrite, paraphrase, delete, or add content. The only new text you introduce is `##` (or `###`) sub-header lines and the minimal blank lines around them.

---

## Invocation

```
/noteplan-manager:organize-note [file-path]
```

If no file path is provided, ask:

```javascript
AskUserQuestion({
  questions: [{
    question: "Which file do you want to organize?",
    header: "File to organize",
    freeText: true
  }]
})
```

Accept both absolute paths and NotePlan wikilink-style names (e.g. `[[20260413]]` → resolve to `$CALENDAR_ROOT/20260413.md`).

---

## Environment Detection

```bash
NOTEPLAN_ROOT="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
NOTES_ROOT="$NOTEPLAN_ROOT/Notes"
CALENDAR_ROOT="$NOTEPLAN_ROOT/Calendar"

PEOPLE_INDEX_WORK="$NOTES_ROOT/🏢 ServiceNow/📋 Lists/🏢📋 References[People].md"
PEOPLE_INDEX_EARLBEAR="$NOTES_ROOT/👥 EarlBear/📋 Lists/👥📋 References[People].md"
```

---

## Phase 1: Load Context

**Task**: `TaskCreate({ subject: "Load People Index + read file" })`

1. Read `$PEOPLE_INDEX_WORK` and `$PEOPLE_INDEX_EARLBEAR` to build a People Map:
   ```
   {
     "arish":   { plans: ["POC Establishing A2A Poc", "Assisting esgenius"], domain: "🏢" },
     "dennis":  { plans: ["Building an ATF Creation POC"], domain: "🏢" },
     "saad":    { plans: ["EarlBear Infrastructure", "Auto Deck Generation"], domain: "👥" },
     ...
   }
   ```

2. Read the target file completely.

3. Detect file type:
   - **Daily note**: path is in `$CALENDAR_ROOT/` or filename is `YYYYMMDD.md`
   - **Plan file**: has frontmatter with `doctype: 📆`
   - **List file**: has frontmatter with `doctype: 📋`
   - **Other**: treat as general note

4. Report: `"Loaded: {filename} ({N} lines, type: {type}). People index: {P} people."`

**Mark task completed.**

---

## Phase 2: Parse Sections

**Task**: `TaskCreate({ subject: "Parse sections and identify large ones" })`

Parse the file into top-level sections separated by `#` headings. For each section, record:

```json
{
  "header": "# Config Agent",
  "level": 1,
  "start_line": 10,
  "end_line": 89,
  "line_count": 79,
  "task_count": 31,
  "existing_subsections": ["## ARB & Governance"],
  "people_signals": ["arish", "sa'd", "anna"],
  "has_prose": true,
  "has_code_blocks": true,
  "theme_clusters": []   // filled in Phase 3
}
```

**Large section threshold**: A section qualifies for sub-header analysis when it has:
- **≥ 15 lines** OR **≥ 8 tasks** AND
- **< 70% already covered by existing `##` sub-headers** (sections that are already subdivided are skipped unless partially uncovered)

After parsing, report a summary:

```
📄 {filename} — {N} top-level sections

  ✅ # I Owe         (7 lines, 7 tasks) — small, skip
  🔍 # Config Agent  (79 lines, 31 tasks, 1 existing sub-header) — LARGE, will analyze
  ✅ # Training      (11 lines, 7 tasks) — small, skip
  ✅ # EarlBear      (4 lines, 1 task) — small, skip
  ✅ # Home          (4 lines, 2 tasks) — small, skip
  ✅ # References    (8 lines, 0 tasks) — small, skip

1 section needs sub-header refinement.
```

**Mark task completed.**

---

## Phase 3: Theme Clustering (per large section)

For each large section, analyze its content to identify natural theme clusters. Do this without reading any other files — use only what's in the section.

**Clustering signals** (apply in order, score each cluster):

| Signal | Score | Example |
|---|---|---|
| Person name from People Index appears in a task | +3 per person | "Arish" → A2A POC cluster |
| Sub-header already exists | +5 for content under it | `## ARB & Governance` already present |
| Keyword cluster (3+ tasks share a root word) | +2 | "eval", "evaluate", "harness" → Eval cluster |
| URL domain cluster (3+ URLs share a domain) | +2 | 3 `servicenow.com` links → Platform cluster |
| Code block | +1 for a "Code / Snippets" cluster | ``` block present |
| Prose paragraph (non-task, non-URL text) | +1 per paragraph | Contributes to nearest keyword cluster or "Notes" |
| Task mentions a named document (`PRD`, `ARB`, `diagram`) | +2 for Governance cluster | |
| Task mentions `eval`, `test`, `harness`, `stress` | +2 for Testing cluster | |
| Task mentions `CLI`, `script`, `install`, `deploy`, `agent` | +2 for Development cluster | |
| Task mentions `sandbox`, `instance`, `project collection`, `platform` | +2 for Platform cluster | |

**Minimum cluster size**: A cluster needs ≥ 2 content items to become a sub-header. Singletons fall into the nearest related cluster or "Unsorted" within the section.

**Proposed clusters** → proposed `##` sub-header names. Use the user's existing section names as inspiration (e.g. if they already have `## ARB & Governance`, don't call it `## Governance`). Match their naming style: concrete, semantic, not generic (avoid `## Misc`, `## Other`).

---

## Phase 4: Confirm Per Section (interactive)

**Task**: `TaskCreate({ subject: "Confirm sub-headers with user" })`

For each large section, present ONE `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: `# ${sectionHeader} has ${lineCount} lines and ${taskCount} tasks.

Proposed sub-headers:
  ## ARB & Governance  (${n1} items) — ARB review, diagram, security model, data governance
  ## Eval & Testing    (${n2} items) — eval harness, option C, stress test, tc checklists
  ## Agent Development (${n3} items) — TableBuilder bug, install script, CLI, back out
  ## Platform / NowEngage (${n4} items) — custom tables, sandbox, project collections
  ## Collaboration     (${n5} items) — Sa'd sheet, Arish docs, Anthropic session

People signals used: Arish (→ Eval + Collaboration), Sa'd (→ Collaboration), Anna (→ Governance)

Do you want to use these sub-headers?`,
    header: `Organize: ${sectionHeader}`,
    options: [
      { label: "Use proposed sub-headers", description: "Write as shown above" },
      { label: "Adjust — I'll type changes", description: "Tell me what to rename, merge, or split" },
      { label: "Skip this section", description: "Leave this section as-is" }
    ],
    multiSelect: false
  }]
})
```

**If "Adjust"**: ask a follow-up freeText question — "What changes? (e.g. 'merge Eval + Agent Development into one', 'rename Platform to ServiceNow Platform', 'add a ## References sub-header for the URLs')" — then apply the adjustments and re-present once for confirmation.

**If "Skip"**: move on to the next large section.

**Mark task completed.**

---

## Phase 5: Write Reorganized File

**Task**: `TaskCreate({ subject: "Write reorganized file" })`

For each confirmed section reorganization:

1. Within the section's line range, assign each content block (root bullet + all its descendants, prose paragraph, code block, URL line) to its confirmed sub-header.
2. Keep blocks in their **original relative order within each sub-header**. Do not sort or reorder.
3. Write the full file back:
   - Everything outside large sections: unchanged, character-for-character
   - Large sections: header preserved, content regrouped under `##` sub-headers, each sub-header followed by one blank line, content blocks separated by one blank line between groups
4. Do NOT:
   - Change any text
   - Fix typos
   - Remove duplicate-looking lines (unless they are exact character-for-character duplicates on consecutive lines within the same block)
   - Add summary lines, tables, or metadata
   - Move content outside the section it was in

**Inflation check**: New lines introduced = number of new `##` headers + their surrounding blank lines. Should be ≤ 5 lines per sub-header added. Flag to user if output is more than 10% longer than input.

**Mark task completed.**

---

## Phase 6: Validate + Commit

**Task**: `TaskCreate({ subject: "Validate and commit" })`

Run a content preservation check:

```python
import re

with open(original_path) as f:
    original_lines = [l.rstrip() for l in f if l.strip() and not l.startswith('##')]

with open(new_path) as f:
    new_lines = [l.rstrip() for l in f if l.strip() and not l.startswith('##')]

# Every non-header, non-blank line from original must appear in new
missing = [l for l in original_lines if l not in new_lines]
if missing:
    print(f"FAIL: {len(missing)} lines missing from output")
    for l in missing[:10]:
        print(f"  - {l!r}")
else:
    print("PASS: all content lines preserved")
```

If validation fails: **do not commit**. Report the missing lines to the user and offer to retry or revert to the original.

If validation passes: commit:

```bash
cd "$NOTEPLAN_ROOT"
git add "{file_path}"
git commit -m "refactor({filename}): add semantic sub-headers to {N} large section(s)

$(for each_section in reorganized_sections:
  echo "  - ${section_header}: added ${n} sub-headers (${sub_header_names})")

No content modified — structure only.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

**Mark task completed.**

---

## Rules

| Rule | Detail |
|---|---|
| Content is sacred | Every content line must appear in output exactly as written. |
| Bullet hierarchies are atomic | A root-level bullet and all its descendants move together. Never split a tree. |
| Existing sub-headers are respected | If a `##` already exists in the section, preserve it and only add sub-headers for uncovered content. |
| People Index is a hint | Person names inform cluster proposals — never force content under a person's name as a sub-header. Use their associated initiative (e.g. "Arish" → "A2A POC" cluster, not "## Arish"). |
| Minimum cluster size | A proposed sub-header needs ≥ 2 content items. Singletons join the nearest cluster. |
| One question per section | Present all proposed sub-headers for a section in a single AskUserQuestion — never ask one per sub-header. |
| Skip already-organized sections | If a section is fully covered by existing `##` sub-headers, skip it silently. |
| No generic headers | Do not use `## Misc`, `## Other`, `## General` as sub-header names unless the user explicitly requests it. |
| Validate before commit | Content preservation check must pass before any commit. |

---

## Related Skills

- **organize-plans** — Organize a plan file's top-level content into `##` sections (no sub-header refinement)
- **sweep-daily-notes** — Move content from daily notes to plan files
- **manage-filenames** — Fix filename/heading mismatches
