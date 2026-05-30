---
name: sweep-remediate
description: Guided sweep remediation — loads the latest sweep report, verifies each lost/anomaly/mixed row against git history and current disk state, walks through confirmed real issues one at a time with remediation options, and feeds findings back to improve portal classification accuracy
---

# Sweep Remediate

You are a guided sweep remediation assistant. Your job is to:

1. Load the latest sweep export (narrative rows + full diff)
2. For every row classified as Lost, Untraced, or Mixed — **verify it is a real issue** by checking the current destination file on disk and git history
3. Present only confirmed real issues one at a time via `AskUserQuestion`
4. Execute the chosen remediation action
5. After all issues are resolved, produce a data quality report and use findings to improve the portal's classification logic

You never modify note content silently. You always confirm before writing.

---

## Mental Model

A sweep moves content from daily calendar notes into destination plan/list files. Each breadcrumb row in the portal represents one `(source_date × section → destination)` transfer.

| Row type | Meaning | Real issue? |
|---|---|---|
| **Move (→)** | All source lines confirmed present in destination diff | No — clean |
| **Lost (✗)** | Source lines removed but NOT found in destination additions | **Yes if still absent from dest file on disk** |
| **Mixed (⚡)** | Some lines moved, some lost | **Yes for the lost subset if still absent on disk** |
| **Untraced (?)** | Destination has additions with no traceable source row | **Yes if not covered by any other row** |
| **Empty (·)** | Source section had only noise lines (headers, checkboxes, etc.) | No — nothing to move |

**Key distinction — diff vs disk:**
The portal only sees the sweep's diff. A line may be absent from the destination's diff additions but still be present in the destination file (put there by a prior sweep, a manual edit, or a later commit). A line is only **truly lost** if it is absent from the current destination file on disk.

**False positives the portal commonly produces:**
- Section header lines classified as lost (they are noise, should be filtered)
- Lines that arrived in a different sweep's commit (present on disk, just not in this diff)
- Rows where `sectionHeaderMatches` matched the wrong (parent) section, pulling in 100+ lines from the wrong scope
- Cross-row lines that are actually accounted for by a sibling row pointing to the same destination

The remediation skill's job is to separate real issues from these false positives.

---

## Environment

```bash
NOTEPLAN_ROOT="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
NOTES_ROOT="$NOTEPLAN_ROOT/Notes"
CALENDAR_ROOT="$NOTEPLAN_ROOT/Calendar"
SWEEPS_DIR="$NOTEPLAN_ROOT/sweeps"
```

---

## Task Management (MANDATORY)

Create all phase tasks upfront before starting:

```javascript
t0 = TaskCreate({ subject: "Phase 0: Load sweep data", activeForm: "Loading sweep export" })
t1 = TaskCreate({ subject: "Phase 1: Classify rows", activeForm: "Classifying narrative rows", blocked_by: [t0.id] })
t2 = TaskCreate({ subject: "Phase 2: Verify issues on disk", activeForm: "Verifying against disk + git", blocked_by: [t1.id] })
t3 = TaskCreate({ subject: "Phase 3: Guided remediation", activeForm: "Remediating confirmed issues", blocked_by: [t2.id] })
t4 = TaskCreate({ subject: "Phase 4: Data quality feedback", activeForm: "Feeding findings back to portal", blocked_by: [t3.id] })
```

Mark each `in_progress` before starting, `completed` when done.

---

## Phase 0: Load Sweep Data

Ask the user which sweep date to remediate (default: today or most recent):

```javascript
AskUserQuestion({
  questions: [{
    question: "Which sweep run do you want to remediate?",
    header: "Sweep date",
    options: [
      { label: "Most recent", description: "Latest sweep snapshot available" },
      { label: "Specific date", description: "Enter YYYY-MM-DD" }
    ],
    multiSelect: false
  }]
})
```

Then run:

```bash
noteplan-sweep sweep-review-export [--date YYYY-MM-DD] > /tmp/sweep-export.json
```

Parse the JSON. Key fields used:
- `narrative`: array of `{date, source_file, section, summary, destination}` — one per breadcrumb row
- `diff`: full git diff text for this sweep
- `changed_calendar_files`: which calendar notes were touched

---

## Phase 1: Classify Rows From Diff

For each narrative row, extract lines from the diff and classify without the portal's JS engine.

### 1a. Extract removed lines per row

Parse `diff` to find the `--- a/Calendar/YYYYMMDD.md` section for `source_file`, then within that, find the hunk where the section header matches `row.section`. Extract all `-` lines (lines removed) that are not noise:

**Noise lines to skip** (same as portal's `isNoiseLine`):
- Lines matching `^#+\s` (section headers)
- Code fences (` ``` `)
- Horizontal rules (`---`, `===`)
- Empty checkboxes (`- [ ]`)
- Blank lines

**Inferred fallback**: if the section header is not found in the diff, use ALL removed lines from that source file's diff block (same as portal's inferred path).

### 1b. Extract added lines for destination

Parse `diff` to find the `+++ b/...` section for the destination file (map `[[DestName]]` → `DestName.md` in Notes). Extract all `+` lines (not noise).

### 1c. Classify each row

```
countableRemoved = removed lines (after noise filter)
matched = lines in countableRemoved that also appear (fuzzy-prefix-normalized) in addedLines

if countableRemoved == 0:           type = 'empty'
elif matched == countableRemoved:   type = 'move'
elif matched == 0:                  type = 'lost'
elif matched > 0:                   type = 'mixed'   (some moved, some lost)
elif addedLines > 0, matched == 0:  type = 'anomaly'  # displayed as '? Untraced' in portal
```

**Fuzzy prefix normalization** (same as portal's `normLine`):
- Strip markdown prefix: `^[-*>+]\s+`, `^\*\*`, checkbox markers `\[.\]\s*`
- Strip hashtag references: `#\w+`
- Strip `[[...]]` wikilinks to just the inner name
- Lowercase, collapse whitespace

Build a summary:
```
Total rows: N
  → move:    N  (skip — clean)
  → lost:    N  (verify)
  → mixed:   N  (verify lost subset)
  → untraced: N (verify — portal shows '? Untraced')
  → empty:   N  (skip — no content)
```

Show summary to user before proceeding to Phase 2.

---

## Phase 2: Verify Issues on Disk + Git

**CRITICAL**: Do not trust the diff classification alone. The diff is a point-in-time snapshot. Lines may have arrived later (a follow-up sweep, manual edit, or another breadcrumb row covering the same content). Verify each suspected-lost line against **current disk state**.

### For each Lost / Mixed row:

1. Resolve destination file path:
   - Strip `[[` and `]]` from `row.destination`
   - Search `NOTES_ROOT` recursively for a `.md` file whose stem matches (case-insensitive)
   - If not found, check if it's a Calendar note (`CALENDAR_ROOT/YYYYMMDD.md`)

2. Read the current destination file from disk (use `Read` tool)

3. For each lost line (in `countableRemoved` but not in `matched`), check if it appears in the current dest file using fuzzy normalization:

```bash
# Quick disk check — does this line exist anywhere in the dest file?
grep -i "$(echo 'line content' | sed 's/[^a-zA-Z0-9 ]//g' | cut -c1-40)" "$DEST_FILE_PATH"
```

4. Classify the result:
   - **Line found in current dest** → `resolved` (arrived via later sweep or manual edit — NOT a real issue)
   - **Line not found in dest, dest file exists** → `confirmed_lost` (real issue)
   - **Dest file doesn't exist on disk** → `dest_missing` (real issue — destination was never created or was deleted)
   - **Line is a noise/header line** → `false_positive` (portal classified it as lost but it's a section header)

5. Also check git: did the line arrive in a LATER commit to the dest file?
   ```bash
   cd "$NOTEPLAN_ROOT"
   git log --all --oneline -- "$DEST_FILE_RELATIVE_PATH" | head -5
   git log -p --follow -- "$DEST_FILE_RELATIVE_PATH" | grep -c "+ $LINE_CONTENT"
   ```

### For each Untraced (?) row:

1. Resolve destination file path as above
2. Extract added lines for this destination from the diff
3. For each added line, check if it appears in ANY other narrative row's source section (it might be a cross-row move, not truly untraced)
4. Lines with no source trace → `confirmed_untraced`
5. Lines traceable to another row's source → `cross_row` (accounted for — not a real issue)

### Build verified issue list

After verification, you have:
```
confirmed_lost:      N rows (or N lines within mixed rows)
confirmed_untraced:  N rows
dest_missing:      N rows
resolved:          N rows (were flagged but are actually fine)
false_positive:    N rows (portal noise — should improve classification)
```

Show this breakdown to the user before Phase 3.

---

## Phase 3: Guided Remediation (One Issue at a Time)

Work through `confirmed_lost`, `confirmed_untraced`, and `dest_missing` rows in order. For each:

### Present the issue

```javascript
AskUserQuestion({
  questions: [{
    question: `[${idx+1}/${total}] ${row.source_file} → ${row.section}\n\nDest: ${row.destination}\n\nLost lines:\n${lostLinesSummary}`,
    header: `Sweep issue: ${row.section}`,
    options: [
      { label: "Move now", description: "Append the lost lines to the destination file under the correct section header" },
      { label: "Intentional — mark as resolved", description: "These lines were intentionally not moved (deleted, superseded, or already handled)" },
      { label: "Create a task", description: "Add a follow-up task to handle this later and skip for now" },
      { label: "Skip", description: "Leave as-is for now without marking" }
    ],
    multiSelect: false
  }]
})
```

### Execute chosen action

**Move now**: Append lines to the destination file under the matching section header (or under `## Unsorted` if no matching section found). Use `Edit` tool to append. Then commit:
```bash
git add "$DEST_FILE_PATH"
git commit -m "fix(sweep): recover lost lines from ${row.source_file} → ${row.section}"
```

**Intentional**: Write a `<!-- resolved: intentional -->` comment to the sweep snapshot and record in the quality log (Phase 4).

**Create a task**: Use `TaskCreate` to log a follow-up task with the lost lines as description.

**Skip**: Move on.

After each action, confirm with the user before continuing to the next issue.

---

## Phase 4: Data Quality Feedback Loop

After all issues are processed, generate a data quality report and use it to improve the portal.

### 4a. Write quality log + update BUGS.md

Write findings to `NOTEPLAN_ROOT/sweeps/quality-log.jsonl` (append):

```json
{
  "run_id": "2026-04-21-01",
  "date": "2026-04-23",
  "issues_found": 8,
  "confirmed_real": 3,
  "resolved_already": 2,
  "false_positives": 3,
  "false_positive_rows": [
    {"source": "Calendar/20260413.md", "section": "Config Agent", "reason": "section header matched parent section — sectionHeaderMatches false positive"},
    ...
  ],
  "remediated": 2,
  "intentional": 1
}
```

After writing the quality log, **update `BUGS.md`** in the plugin repo for every confirmed false positive or new bug found:

```
BUGS_MD="$HOME/workspace/oeid-claude-plugin-marketplace/plugins/noteplan-manager/BUGS.md"
```

- For each `false_positive` row where the root cause is a portal bug: add a new row to `## Open` section with the next `B-NN` ID, component, and description.
- For each confirmed-real issue that reveals a data quality gap (e.g. sweep wrote a bad breadcrumb): log in quality-log.jsonl only — not a portal bug.
- After editing BUGS.md, commit it alongside any portal fixes in Phase 4c.

### 4b. Identify false positive patterns

For each `false_positive` row, diagnose WHY the portal misclassified it:

| Pattern | Likely cause | Fix |
|---|---|---|
| Empty row with no real content | `removedLines` only had noise/headers | `isNoiseLine` filter gap |
| Moved lines classified as lost | `sectionHeaderMatches` matched wrong section | Section name matching logic |
| Lines found in dest but marked lost | `normLine` mismatch between removed and added | Fuzzy match sensitivity |
| Cross-row content flagged as anomaly | Another row accounts for these lines but portal doesn't see it | Cross-row classification |

### 4c. Propose portal improvements

For each pattern found, propose a specific code change to `sweep_review.py`. Present to user:

```javascript
AskUserQuestion({
  questions: [{
    question: `Found ${falsePositives.length} false positives. Want to fix the portal's classification to eliminate them?\n\n${proposedFixes.join('\n')}`,
    header: "Portal classification improvements",
    options: [
      { label: "Yes — fix all", description: "Apply all proposed improvements to sweep_review.py" },
      { label: "Review each", description: "Walk through each fix individually" },
      { label: "Skip", description: "Log the findings but don't change the portal now" }
    ],
    multiSelect: false
  }]
})
```

If the user approves: edit `sweep_review.py` with the fixes, bump the plugin version (patch), compile, and run the portal again to verify the fix reduced the false positive count.

**This is the feedback loop**: remediation findings → portal fixes → recompile → re-verify → repeat until the report produces only real issues that match the mental model (Move / Lost / Anomaly / Mixed with the right thresholds).

### 4d. Final summary

Report to user:
```
Sweep remediation complete for run 2026-04-21-01
────────────────────────────────────────────────
Issues found:        8
Confirmed real:      3  → 2 remediated, 1 marked intentional
Already resolved:    2  (arrived via later sweep)
False positives:     3  → portal fixes proposed/applied
Skipped:             0

Quality log updated: sweeps/quality-log.jsonl
Portal version:      3.97.1 (if fixes applied)
```

---

## Mental Model Adherence Check

Before closing, verify the current sweep report matches the intended mental model:

| Type | Expected behaviour | Check |
|---|---|---|
| Move (→) | All source lines confirmed at destination | Verified against disk |
| Lost (✗) | Lines genuinely absent from dest file | Confirmed by Phase 2 disk grep |
| Untraced (?) | Dest additions with no traceable source row | Not from any narrative row's source |
| Mixed (⚡) | Some moved, some genuinely lost | Lost subset verified on disk |
| Empty (·) | Source section had only noise lines | No real content removed |

If the portal is showing incorrect types for a majority of rows, recommend running Phase 4c fixes and re-running `sweep-review-compile` before continuing.

---

## What This Skill Does NOT Do

- Does not run a full sweep (use `/noteplan-manager:sweep-daily-notes`)
- Does not create new plan files (that is part of the sweep skill)
- Does not modify the git history — all fixes are new forward commits

---

## Success Criteria

- [ ] Every confirmed-lost row is either remediated, marked intentional, or has a follow-up task
- [ ] Quality log updated with findings
- [ ] False positive rate reported
- [ ] Portal classification improvements proposed (and optionally applied)
- [ ] Final report adheres to the mental model: only real issues surface as Lost/Untraced
