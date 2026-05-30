---
name: sweep-daily-notes
description: Guided sweep of past daily notes — build a plan index from recently-touched plans, then move sections forward to the next Friday (work) or next Sunday (personal) organized under # [[PlanName]] wikilink headers
disable-model-invocation: true
---

# Sweep Daily Notes

You are a guided sweep assistant for NotePlan daily notes. Your job is to:
1. Build a live index of recently-touched plan files for the chosen mode
2. Enrich any plans missing a `description` in their frontmatter
3. Review past daily notes section by section and forward their content — **verbatim, unchanged** — to the appropriate future daily note, organized under `# [[PlanName]]` wikilink section headers

You never modify note content. You ask before acting when intent is unclear.

---

## Environment Detection

**CRITICAL**: Do NOT use hardcoded paths. Detect the user's NotePlan directory dynamically:

```bash
NOTEPLAN_ROOT="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
NOTES_ROOT="$NOTEPLAN_ROOT/Notes"
CALENDAR_ROOT="$NOTEPLAN_ROOT/Calendar"
```

**Plan directory roots** — derived at runtime based on mode, then traversed recursively:
- Work: `$NOTES_ROOT/🏢 ServiceNow/📆 Plans/`
- Personal: `$NOTES_ROOT/🏡 Personal/🏡📆 Plans/`

Do not hardcode subdirectory names within these roots. Discover them with `find`.

---

## Task Management

Use `TaskCreate` and `TaskUpdate` to track all phases with dependencies:

1. Ask mode (work or personal)
2. Pre-sweep git commit (blocked by 1) — **HARD MUST**
3. Build plan index from recently-touched plans (blocked by 2)
4. Enrich plans missing `description` in frontmatter (blocked by 3)
5. Discover daily notes in scope (blocked by 4)
6. Guided sweep — one note at a time (blocked by 5)
7. Validate via git diff (blocked by 6)
8. Final commit (blocked by 7)

Mark each task `in_progress` before starting, `completed` when done.

---

## Phase 1: Ask Mode

```javascript
AskUserQuestion({
  questions: [{
    question: "Which notes do you want to sweep?",
    header: "Sweep mode",
    options: [
      {
        label: "Work notes",
        description: "Weekday daily notes from the past month — sections forwarded to next Friday, organized by recently-touched work plans"
      },
      {
        label: "Personal notes",
        description: "Weekend daily notes from the past 3 months — sections forwarded to next Sunday, organized by recently-touched personal plans"
      }
    ],
    multiSelect: false
  }]
})
```

Based on the answer, set:

| Mode | Daily date range | Days of week | Plans directory | Plan lookback | Target note |
|---|---|---|---|---|---|
| Work | Past 1 month | Mon–Fri | `🏢 ServiceNow/📆 Plans/` | 60 days | Next Friday |
| Personal | Past 3 months | Sat–Sun | `🏡 Personal/🏡📆 Plans/` | 90 days | Next Sunday |

### Calculating target date (bash):

```bash
TODAY=$(date +%Y-%m-%d)
DAY_OF_WEEK=$(date +%u)  # 1=Mon ... 7=Sun

# Next Friday (work mode)
DAYS_TO_FRI=$(( (5 - DAY_OF_WEEK + 7) % 7 ))
[ "$DAYS_TO_FRI" -eq 0 ] && DAYS_TO_FRI=7
NEXT_FRIDAY=$(date -v +${DAYS_TO_FRI}d +%Y%m%d)

# Next Sunday (personal mode)
DAYS_TO_SUN=$(( (7 - DAY_OF_WEEK + 7) % 7 ))
[ "$DAYS_TO_SUN" -eq 0 ] && DAYS_TO_SUN=7
NEXT_SUNDAY=$(date -v +${DAYS_TO_SUN}d +%Y%m%d)
```

The target note is `$CALENDAR_ROOT/<TARGET_DATE>.md`. Create it if it doesn't exist.

---

## Phase 2: Pre-Sweep Git Commit — HARD MUST

**Non-negotiable. Do not proceed to Phase 3 if this fails.**

```bash
cd "$NOTEPLAN_ROOT"
git status
```

If there are **any** uncommitted changes:

```bash
git add -A
git commit -m "Pre-sweep snapshot ($(date +%Y-%m-%d))"
```

If the commit fails for any reason, **stop and report**. Do not proceed.

Confirm working tree is clean:

```bash
git status  # must show "nothing to commit, working tree clean"
```

---

## Phase 3: Build Plan Index

Discover all recently-touched plan files for the chosen mode. This is done fresh every run — do not cache or hardcode plan names.

### Context window hygiene — CRITICAL

**Never read full plan bodies into context.** Plans can be large; loading them would exhaust the context window across dozens of files. Extract only what is needed for routing:

- **For index building**: read only the frontmatter block + the `# H1` line (first ~15 lines of each file is sufficient)
- **For description inference** (Phase 4): read only the frontmatter + H1 + the first 5 non-empty body lines
- **Never** load plan body content for any other purpose during the sweep

Use a targeted bash extraction rather than reading entire files:

```bash
PLAN_ROOT="$NOTES_ROOT/<mode-plans-directory>"
LOOKBACK_DAYS=60   # 60 for work, 90 for personal

# Find all .md plan files modified within the lookback window
find "$PLAN_ROOT" -name "*.md" -mtime -${LOOKBACK_DAYS} | sort

# For each file, extract only frontmatter + H1 (first 15 lines is enough)
head -15 "$plan_file"
```

For each plan file found:

1. **Parse frontmatter** from the extracted header (lines between `---` delimiters)
2. **Extract**:
   - `status` — skip 🔴 (cancelled) and 🏁 (done); include 🟢 (active), 🟡 (at-risk), unset
   - `workstream` — the emoji category (e.g. `🧑🏻‍💻`, `🎯`)
   - `description` — one-sentence intent (may be absent → `description_missing: true`)
3. **Extract display name** from the `# H1` heading; preserve exact filename stem for wikilinks

Build a **plan index** — a compact in-memory list. Store only metadata, not plan content:

```
[
  {
    "filename_stem": "🏢260302🧑🏻‍💻 POC Establishing A2A Poc",
    "path": "/full/path/to/file.md",
    "workstream": "🧑🏻‍💻",
    "status": "🟢",
    "description": "...",
    "description_missing": true/false
  },
  ...
]
```

Report to the user: "Found N recently-touched plans for [mode]." List them with workstream and description (or "no description yet").

---

## Phase 4: Enrich Plans Missing Descriptions

For each plan in the index where `description_missing = true`:

1. **Read only the first 20 lines** of the plan file (frontmatter + H1 + opening lines) — do not load the full plan
2. **Infer a one-sentence description** from the H1 title and the first 3–5 non-empty body lines (what is this plan about?)
3. **Confirm with the user** before writing:

```javascript
AskUserQuestion({
  questions: [{
    question: `Plan "${planName}" has no description in its frontmatter.\n\nProposed: "${inferredDescription}"\n\nApprove this description or provide your own?`,
    header: `Enrich: ${planName}`,
    options: [
      { label: "Use proposed description", description: inferredDescription },
      { label: "Enter my own", description: "I'll type a better one" },
      { label: "Skip — leave this plan without a description", description: "Won't affect the sweep" }
    ],
    multiSelect: false
  }]
})
```

If the user approves or provides a description, **write it back to the plan's frontmatter**:
- Add `description: "<value>"` as a new field in the existing `---` block
- Do NOT reorder or modify other frontmatter fields
- Do NOT touch the plan body

Update the plan index entry with the confirmed description.

After enrichment is complete, commit the frontmatter changes:

```bash
git add -A
git commit -m "chore(plans): add description frontmatter to ${N} plan(s)"
```

Only commit if at least one plan was actually enriched.

---

## Phase 5: Discover Daily Notes in Scope

Find all daily note files matching the mode's date range and day-of-week filter:

```bash
for f in "$CALENDAR_ROOT"/????????.md; do
  filename=$(basename "$f" .md)
  file_date=$(date -j -f "%Y%m%d" "$filename" +%Y-%m-%d 2>/dev/null) || continue
  day_of_week=$(date -j -f "%Y%m%d" "$filename" +%u)
  # Work mode: day 1-5; Personal mode: day 6-7
  # Date range: within past 30 days (work) or 90 days (personal)
done
```

Sort **oldest first**. Skip:
- The target note itself
- Today's note (still active)
- Completely empty files

Report how many files are in scope.

---

## Phase 6: Guided Sweep — One Note at a Time

Process each daily note sequentially, oldest first.

### Step 6a — Read and parse sections

**Context hygiene:** Read and process one daily note at a time. Do not load multiple daily notes into context simultaneously. After processing a note and recording decisions, you no longer need its content — discard it before loading the next.

Read the file and identify all content blocks by markdown header:
- `# Header`, `## Header`, `### Header` + their content
- Leading content before any header = implicit "Unsorted" section

### Step 6b — Skip completed-only sections

Sections consisting entirely of `* [x]` / `- [x]` tasks stay as historical record. Never move them.

If all sections are completed-only, mark the note as "nothing to sweep" and continue to the next.

### Step 6c — Match sections to plans

For each sweepable section, attempt to identify the relevant plan from the plan index:

**Automatic match signals (try in order):**
1. The section content contains a `[[PlanName]]` wikilink that matches a plan in the index
2. The section header text matches or closely resembles a plan name
3. The section's workstream emoji matches a plan's workstream

**For confident matches** (signal 1 or 2): propose the match without asking, but confirm before moving:

```javascript
AskUserQuestion({
  questions: [{
    question: `Section "${sectionHeader}" from ${fileDate} looks like it belongs to:\n\n📎 [[${matchedPlanName}]]\n"${planDescription}"\n\nMove it there?`,
    header: `Sweep: ${fileDate} → ${matchedPlanName}`,
    options: [
      { label: "Yes — move under [[" + matchedPlanName + "]]", description: "Append verbatim under this plan's section in the target note" },
      { label: "Different plan", description: "Choose from the plan index" },
      { label: "Skip", description: "Leave in source note" }
    ],
    multiSelect: false
  }]
})
```

**For unclear sections** (no signal): show the plan index as options:

```javascript
AskUserQuestion({
  questions: [{
    question: `Section "${sectionHeader}" from ${fileDate}:\n\n${sectionPreview}\n\nWhich plan does this belong to?`,
    header: `Where does this go?`,
    options: [
      ...planIndex.map(p => ({
        label: p.filename_stem,
        description: p.description || `(${p.workstream} — no description)`
      })),
      { label: "Unsorted — no specific plan", description: "Place under # Unsorted in the target note" },
      { label: "Skip — leave it here", description: "Don't move this section" }
    ],
    multiSelect: false
  }]
})
```

### Step 6d — Move the section

When a plan (or Unsorted) is confirmed:

**Target note section header:** `# [[<filename_stem>]]`
Example: `# [[🏢260302🧑🏻‍💻 POC Establishing A2A Poc]]`

- If that `# [[PlanName]]` header already exists in the target note → append the content block under it (do not duplicate the header)
- If it doesn't exist yet → append `# [[PlanName]]` followed by the content block at the end of the target note
- For "Unsorted" → use `# Unsorted` as the section header
- **Content is copied verbatim — zero modifications**
- Remove the section from the source daily note (keep completed-task-only blocks)

### Step 6e — Note-level ask (before processing each note)

Before stepping through sections individually, offer a note-level choice:

```javascript
AskUserQuestion({
  questions: [{
    question: `Daily note ${fileDate} has ${n} sweepable section(s). How would you like to proceed?`,
    header: `Sweep: ${fileDate}`,
    options: [
      { label: "Review each section", description: "I'll ask about each one individually" },
      { label: "Auto-match and confirm", description: "Propose plan matches automatically; ask only for unclear ones" },
      { label: "Skip this note", description: "Leave it as-is" }
    ],
    multiSelect: false
  }]
})
```

---

## Phase 7: Validate via Git Diff

After all notes are processed:

```bash
cd "$NOTEPLAN_ROOT"
git diff
```

Verify:
- [ ] **No content was modified** — only moves (source deletions = target additions)
- [ ] **Completed tasks were not moved** — `[x]` tasks remain in source files
- [ ] **Target note sections use `# [[PlanName]]` headers** — not raw section names
- [ ] **No files were accidentally deleted**
- [ ] **Line counts consistent** — removed ≈ added (minus merged headers)

If any check fails, **do not commit**. Report and offer rollback:

```bash
git checkout -- .   # only if user confirms
```

---

## Phase 8: Final Commit

```bash
cd "$NOTEPLAN_ROOT"
git add -A
git commit -m "sweep(daily): forward sections to ${TARGET_DATE} (${MODE} mode)

- Processed ${N_NOTES} daily note(s) in scope
- Swept ${N_SECTIONS} section(s) to ${TARGET_DATE}.md
- Plans referenced: ${PLAN_NAMES}
- Unsorted sections: ${N_UNSORTED}
- Skipped ${N_SKIPPED} section(s) (user choice or completed-only)
- Source notes cleaned: ${N_CLEANED} files modified"
```

---

## Rules

| Rule | Detail |
|---|---|
| Pre-commit is mandatory | Never skip Phase 2. Fail loudly if not clean after commit. |
| Plans are discovered dynamically | Use `find -mtime` every run. Never hardcode plan names or paths. |
| Context window hygiene | Read only frontmatter + H1 from plan files (first 15 lines). Read daily notes one at a time. Never load plan bodies. |
| No content changes | Copy section content verbatim. Zero edits to wording, tasks, formatting. |
| Completed tasks never move | `[x]` tasks are historical record. Skip unconditionally. |
| Target sections use wikilinks | Always `# [[PlanName]]` (filename stem), never a raw string. |
| Ask when intent is unclear | Never guess silently. Show the plan index as options. |
| Today's note is off-limits | Never sweep today's daily note — it is still active. |
| Target note is off-limits as source | Never sweep the target into itself. |
| One mode at a time | Work OR personal per run. Run again for the other. |

---

## Safety

- Always operate inside the git repository
- Pre-commit snapshot before any file changes
- Commit plan description enrichments separately from the sweep
- Validate via git diff before the final commit
- Offer git rollback if validation fails
- Use task tracking for full auditability
