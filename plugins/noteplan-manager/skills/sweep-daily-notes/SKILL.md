---
name: sweep-daily-notes
description: Guided sweep of past daily notes — move sections forward to the next Friday (work) or next Sunday (personal), one section at a time, asking for intent when unclear
disable-model-invocation: true
---

# Sweep Daily Notes

You are a guided sweep assistant for NotePlan daily notes. Your job is to review past daily notes section by section and forward their content — unchanged — to the appropriate future daily note. You never modify content, only move sections. You ask before acting when intent is unclear.

## Environment Detection

**CRITICAL**: Do NOT use hardcoded paths. Detect the user's NotePlan directory dynamically:

```bash
NOTEPLAN_ROOT="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
```

**Directory Structure**:
- `$NOTEPLAN_ROOT/Calendar/` — Daily files (format: `YYYYMMDD.md`)
- `$NOTEPLAN_ROOT/Notes/` — Permanent notes

## Task Management

Use `TaskCreate` and `TaskUpdate` to track all phases with dependencies:

1. Ask mode (work or personal)
2. Pre-sweep git commit (blocked by 1) — **HARD MUST**
3. Discover daily notes in scope (blocked by 2)
4. Process each note — guided sweep (blocked by 3)
5. Validate via git diff (blocked by 4)
6. Final commit (blocked by 5)

Mark each task `in_progress` before starting, `completed` when done.

---

## Phase 1: Ask Mode

Use `AskUserQuestion` to determine sweep type:

```javascript
AskUserQuestion({
  questions: [{
    question: "Which notes do you want to sweep?",
    header: "Sweep mode",
    options: [
      {
        label: "Work notes",
        description: "Weekday daily notes from the past month — sections forwarded to next Friday"
      },
      {
        label: "Personal notes",
        description: "Weekend daily notes from the past 3 months — sections forwarded to next Sunday"
      }
    ],
    multiSelect: false
  }]
})
```

Based on the answer, set:

| Mode | Date range | Days of week | Target note |
|---|---|---|---|
| Work | Past 1 month from today | Mon–Fri only | Next Friday from today |
| Personal | Past 3 months from today | Sat–Sun only | Next Sunday from today |

### Calculating target date (bash):

```bash
# Today's date
TODAY=$(date +%Y-%m-%d)
DAY_OF_WEEK=$(date +%u)  # 1=Mon ... 7=Sun

# Next Friday (work mode)
DAYS_TO_FRI=$(( (5 - DAY_OF_WEEK + 7) % 7 ))
[ "$DAYS_TO_FRI" -eq 0 ] && DAYS_TO_FRI=7   # if today IS Friday, use NEXT Friday
NEXT_FRIDAY=$(date -v +${DAYS_TO_FRI}d +%Y%m%d)

# Next Sunday (personal mode)
DAYS_TO_SUN=$(( (7 - DAY_OF_WEEK + 7) % 7 ))
[ "$DAYS_TO_SUN" -eq 0 ] && DAYS_TO_SUN=7   # if today IS Sunday, use NEXT Sunday
NEXT_SUNDAY=$(date -v +${DAYS_TO_SUN}d +%Y%m%d)
```

The target note is `$NOTEPLAN_ROOT/Calendar/<TARGET_DATE>.md`. Create it if it doesn't exist (an empty file is fine — sections will be appended).

---

## Phase 2: Pre-Sweep Git Commit — HARD MUST

**This step is non-negotiable. Do not proceed to Phase 3 if it fails.**

```bash
cd "$NOTEPLAN_ROOT"
git status
```

If there are **any** uncommitted changes (staged or unstaged):

```bash
git add -A
git commit -m "Pre-sweep snapshot ($(date +%Y-%m-%d))"
```

If the git commit fails for any reason, **stop and report the error to the user**. Do not proceed.

After committing, confirm the working tree is clean:

```bash
git status  # must show "nothing to commit, working tree clean"
```

If not clean, stop and report.

---

## Phase 3: Discover Daily Notes in Scope

Find all daily note files matching the mode's date range and day-of-week filter:

```bash
# Build list of daily files in date range, filtered by day of week
NOTEPLAN_CALENDAR="$NOTEPLAN_ROOT/Calendar"

# List files, parse YYYYMMDD from filename, filter by day and date range
for f in "$NOTEPLAN_CALENDAR"/????????.md; do
  filename=$(basename "$f" .md)
  # Parse as date and check day of week + date range
  file_date=$(date -j -f "%Y%m%d" "$filename" +%Y-%m-%d 2>/dev/null) || continue
  day_of_week=$(date -j -f "%Y%m%d" "$filename" +%u)
  # Work mode: day 1-5; Personal mode: day 6-7
  # Date range check: within past 30 days (work) or 90 days (personal)
done
```

Sort files **oldest first** so we process the most backlogged notes first.

Skip files that:
- Are the target note itself
- Are today's note
- Are completely empty

Report how many files are in scope before starting the guided sweep.

---

## Phase 4: Guided Sweep — One Note at a Time

Process each daily note in scope sequentially, oldest first.

### For each daily note:

**Step 4a — Read and parse sections**

Read the file and identify all markdown headers and their content blocks:
- Top-level (`# Header`)
- Sub-headers (`## Header`, `### Header`)
- Content between headers (paragraphs, task lists, bullets)

Also treat leading content before any header as an implicit "untitled" section.

**Step 4b — Skip if nothing to sweep**

Skip sections that consist entirely of completed tasks (`* [x]` / `- [x]`). Completed tasks are historical record and must never be moved.

If **all** sections are complete-only, mark the note as "nothing to sweep" and move on.

**Step 4c — Present sections to user**

For each note that has sweepable content, show the user a summary and ask what to do:

```javascript
AskUserQuestion({
  questions: [{
    question: `Daily note ${fileDate} has ${n} section(s) with content. What would you like to do?`,
    header: `Sweep: ${fileDate}`,
    options: [
      { label: "Sweep all sections to target note", description: "Move every section with incomplete content to the target date" },
      { label: "Review each section individually", description: "I'll ask you about each section one at a time" },
      { label: "Skip this note", description: "Leave this daily note as-is" }
    ],
    multiSelect: false
  }]
})
```

**Step 4d — Per-section questions (when reviewing individually or when intent is unclear)**

For each section, ask:

```javascript
AskUserQuestion({
  questions: [{
    question: `Section "${sectionHeader}" from ${fileDate}:\n\n${sectionPreview}\n\nWhat should happen to this section?`,
    header: `Section: "${sectionHeader}"`,
    options: [
      { label: "Move to target note as-is", description: `Append this section under the same header in ${targetDate}.md` },
      { label: "Move under a different header", description: "Place this section under a different heading in the target note" },
      { label: "Skip — leave it here", description: "Don't move this section" }
    ],
    multiSelect: false
  }]
})
```

If the user chooses "Move under a different header", follow up:

```javascript
AskUserQuestion({
  questions: [{
    question: "What heading should this content go under in the target note?",
    header: "Target heading",
    freeText: true
  }]
})
```

**Step 4e — Move the section**

When a section is confirmed for moving:
- Append the section (header + content block, **verbatim — zero content changes**) to the target note
- If the target heading already exists in the target note, append the content block under the existing header (don't duplicate the header)
- Remove the section from the source daily note
- Do NOT remove completed-task-only blocks; those stay

**No content modification rule:** The text of notes, tasks, bullets, and paragraphs must be copied exactly as-is. The only structural change allowed is the addition/removal of the markdown header in the source/target.

---

## Phase 5: Validate via Git Diff

After all notes are processed:

```bash
cd "$NOTEPLAN_ROOT"
git diff
```

Verify:
- [ ] **No content was modified** — only moves (deletions in source = additions in target)
- [ ] **Completed tasks were not moved** — `[x]` tasks remain in source files
- [ ] **Target note received all swept sections** — check target file additions
- [ ] **No files were accidentally deleted**
- [ ] **Line counts are consistent** — removed lines ≈ added lines (minus any merged headers)

If any check fails, **do not commit**. Report the discrepancy to the user and offer to rollback:

```bash
git checkout -- .   # rollback all changes (only if user confirms)
```

---

## Phase 6: Final Commit

```bash
cd "$NOTEPLAN_ROOT"
git add -A
git commit -m "sweep(daily): forward sections to ${TARGET_DATE} (${MODE} mode)

- Processed ${N_NOTES} daily note(s) in scope
- Swept ${N_SECTIONS} section(s) to ${TARGET_DATE}.md
- Skipped ${N_SKIPPED} section(s) (user choice or completed-only)
- Source notes cleaned: ${N_CLEANED} files modified"
```

Report a final summary to the user:
- How many notes were processed
- How many sections were swept to the target
- How many were skipped
- Target note path

---

## Rules

| Rule | Detail |
|---|---|
| Pre-commit is mandatory | Never skip Phase 2. Fail loudly if git is not clean after commit attempt. |
| No content changes | Copy section content verbatim. Zero edits to wording, tasks, or formatting. |
| Completed tasks never move | `[x]` tasks are historical record. Skip them unconditionally. |
| Ask when intent is unclear | Never guess silently. Use `AskUserQuestion` for ambiguous sections. |
| Today's note is off-limits | Never sweep today's daily note — it is active. |
| Target note is off-limits as source | Never sweep the target note into itself. |
| One sweep at a time | This skill processes work OR personal in a single run. Run again for the other mode. |

---

## Safety

- Always operate inside the git repository
- Pre-commit snapshot before any file changes
- Validate via git diff before committing
- Offer git rollback if validation fails
- Use task tracking for auditability
