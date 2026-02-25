---
name: review-noteplan
description: Systematic review of your NotePlan vault — task scan, link audit, or structure analysis. Generates a dated report and consultation file in @Archive/🧮 Reviews/Manual Reviews/.
---

# Review NotePlan

You are a NotePlan vault reviewer. When this skill is invoked, run a systematic review and save the results to the review archive.

## What This Skill Does

Guides a structured review of your NotePlan vault across three modes:

| Mode | What It Analyzes |
|---|---|
| **Task Scan** | Completed and scheduled tasks by year, categorized by workstream |
| **Link Audit** | Wiki links and markdown links — finds broken references and headers with trailing whitespace |
| **Structure Analysis** | File naming compliance, emoji conventions, orphaned or misplaced files |

Artifacts are saved to:
```
$NOTES_ROOT/@Archive/🧮 Reviews/Manual Reviews/<YYMMDD>-<type>/
  report.md         ← findings and summary
  consultation.md   ← items needing your decision
```

## Scripts

```bash
SCRIPTS_DIR="$HOME/.claude/plugins/noteplan-manager/skills/review-noteplan/scripts"
```

| Script | Purpose |
|---|---|
| `scan_tasks.py` | Scan for completed/scheduled tasks by year and domain |
| `check_links.py` | Discover and validate all links; detect headers with trailing space |

## Workflow

### Step 0: Task Setup (MANDATORY FIRST STEP)

Create tasks before doing any work:

```javascript
TaskCreate({ subject: "Select review type and collect inputs", activeForm: "Selecting review type" })
TaskCreate({ subject: "Run analysis", activeForm: "Running analysis" })
TaskCreate({ subject: "Generate report and consultation file", activeForm: "Generating report" })
TaskCreate({ subject: "Present findings and next steps", activeForm: "Presenting findings" })

// Dependencies
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

### Step 1: Select Review Type and Collect Inputs

Mark Task #1 `in_progress`.

Use `AskUserQuestion` to ask what kind of review to run:

```
What kind of review?

Options:
- Task Scan — completed/scheduled tasks by year and workstream
- Link Audit — broken links, header trailing-space issues
- Structure Analysis — naming conventions, emoji compliance, file placement
```

**For Task Scan:** also ask for year (default: current year) and domain (work/personal/all).

**Paths:**
```bash
NOTES_ROOT="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes"
CALENDAR_ROOT="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Calendar"
REVIEW_DIR="$NOTES_ROOT/@Archive/🧮 Reviews/Manual Reviews"
```

Set output directory from today's date:
```bash
TODAY=$(date +%y%m%d)
REVIEW_TYPE="<task-scan|link-audit|structure>"
OUTPUT_DIR="$REVIEW_DIR/${TODAY}-${REVIEW_TYPE}"
mkdir -p "$OUTPUT_DIR"
```

Mark Task #1 `completed`, Task #2 `in_progress`.

### Step 2: Run Analysis

#### Task Scan

```bash
SCRIPTS_DIR="$HOME/.claude/plugins/noteplan-manager/skills/review-noteplan/scripts"

python3 "$SCRIPTS_DIR/scan_tasks.py" \
  --notes-dir "$NOTES_ROOT" \
  --calendar-dir "$CALENDAR_ROOT" \
  --year <YEAR> \
  --domain <work|personal|all> \
  --output "$OUTPUT_DIR/scan-results.json"
```

The script outputs a JSON file with:
```json
{
  "year": 2026,
  "domain": "work",
  "summary": {"total_files": N, "total_tasks": N, "by_workstream": {...}},
  "tasks": [{"file": "...", "line": N, "task": "...", "workstream": "...", "date": "..."}]
}
```

#### Link Audit

```bash
python3 "$SCRIPTS_DIR/check_links.py" \
  --notes-dir "$NOTES_ROOT" \
  --output "$OUTPUT_DIR/link-results.json"
```

The script outputs:
```json
{
  "summary": {"total_links": N, "unique_links": N, "broken": N, "headers_with_trailing_space": N},
  "broken_links": [{"file": "...", "line": N, "link": "...", "reason": "..."}],
  "headers_with_trailing_space": [{"file": "...", "line": N, "header": "..."}]
}
```

#### Structure Analysis

Claude performs this directly without a script:
- Walk `$NOTES_ROOT` and check each `.md` file against naming conventions (CLAUDE.md rules)
- Flag files not matching their domain's naming pattern
- Flag files in wrong directories (e.g., a personal plan in a work folder)
- Flag duplicate artifacts (NotePlan sync conflicts like `Name 2.md`, `Name 2 8.md`)
- Output a structured list of violations

Mark Task #2 `completed`, Task #3 `in_progress`.

### Step 3: Generate Report and Consultation File

Write two files to `$OUTPUT_DIR`:

#### report.md

```markdown
# NotePlan Review — <Type> — <YYMMDD>

Generated: <date>
Scope: <year/domain/path>

## Summary

<summary stats>

## Findings

<organized findings>

## Recommended Actions

<prioritized list of actions Claude can take automatically>
```

#### consultation.md

Items that require your decision before action:

```markdown
# Review Consultation — <Type> — <YYMMDD>

Items below need your input before proceeding.

## [Item Title]

**Finding:** <what was found>
**Options:**
- A: <option A>
- B: <option B>
**Recommendation:** <Claude's recommendation>
**Status:** ⏳ Pending

---
```

Mark Task #3 `completed`, Task #4 `in_progress`.

### Step 4: Present Findings and Next Steps

Show a summary:

```
✅ Review complete — <YYMMDD>-<type>

Report:       $OUTPUT_DIR/report.md
Consultation: $OUTPUT_DIR/consultation.md

Summary:
  <key stats from analysis>

Top findings:
  <3–5 bullet highlights>

Recommended next steps:
  1. Read report.md for full findings
  2. Review consultation.md for items needing your decision
  3. <any automatic fixes available via other skills>
```

If there are automatically fixable issues, offer to run the relevant skill:
- Broken emoji encoding → `/noteplan-manager:fix-work-emojis` or `/noteplan-manager:fix-personal-emojis`
- Frontmatter issues → `/noteplan-manager:fix-frontmatter`
- Broken links → identify and fix manually or flag for `/noteplan-manager:fix-reference`

Mark Task #4 `completed`. Show `TaskList()` to confirm all tasks done.

## Review Archive Structure

The archive lives **outside the plugin** — it is your NotePlan vault:
```
$NOTES_ROOT/@Archive/🧮 Reviews/
  Manual Reviews/
    <YYMMDD>-task-scan/
      report.md
      consultation.md
      scan-results.json
    <YYMMDD>-link-audit/
      report.md
      consultation.md
      link-results.json
    <YYMMDD>-structure/
      report.md
      consultation.md
```

This keeps all review history in one queryable location. Claude never cleans up old reviews — that is your decision.

## Git Safety

If the NotePlan notes directory is a git repo, check for pending changes before writing:

```bash
cd "$NOTES_ROOT"
git status --short
```

New review files go in `@Archive/` and are net-new — no risk of overwriting existing content. No pre-commit needed, but mention it if there are pending changes on files being analyzed.
