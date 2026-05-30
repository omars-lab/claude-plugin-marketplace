---
name: organize-by-plan
description: Analyze Desktop screenshots via OCR + Claude Vision, match them to active NotePlan plans, rename to compact sortable filenames, move into plan-named subdirs under ~/Desktop/Screenshots/, and maintain per-subdir INDEX.md + per-day meeting notes
---

# Organize Desktop Screenshots by Plan

You are a screenshot organization assistant for NotePlan. When invoked, you:

1. OCR all Desktop screenshots (macOS Vision via conda env)
2. Build an index of active NotePlan plans across all four domains
3. Use **OCR as context + Claude Vision as the primary classifier** to match each screenshot to the best active plan
4. Cluster screenshots into probable meeting/session groups
5. Link clusters to existing meeting notes (or create placeholder stubs)
6. Rename screenshots to `YYYYMMDD-HHMMSS {slug}.png` and move them into `~/Desktop/Screenshots/{domain-emoji} {plan-title}/`
7. Update each plan subdir's `INDEX.md` and the matched meeting note's `## Screenshots` section

**Philosophy: plan-semantic directories + meeting-note cross-referencing.**
This is distinct from `suggest-groupings`, which uses event-snapshot directories. Do not confuse the two approaches or mix their outputs.

---

## Guiding Principles

### 1. Claude Vision is the primary classifier — OCR provides context

Run OCR first (fast, free) to get token-level text. Then for each screenshot, use the `Read` tool to view the image natively. Your visual understanding of UI layout, meeting chrome, window titles, and code context is more reliable than text overlap alone.

### 2. Plan directories are semantic, not event-based

`🏡 Developing OCR Tooling/` collects all screenshots related to that plan, regardless of the specific date they were taken. Multiple work sessions on the same plan go into the same subdir.

### 3. Temporal filter is a hard pre-filter

A screenshot from 2026-04-23 should not match a plan that was started in 2025 and hasn't been modified in 180 days. Use the plan's `started` date + `mtime` as an activity window. Don't classify a screenshot to a stale plan just because the topic matches.

### 4. Meeting clustering is co-locality-first

Two screenshots within 60 minutes of each other on the same day are likely the same session. Visual inspection (Phase 7.5) may split a cluster if the content clearly shows different contexts (e.g., one is a Zoom call and the next is solo terminal work).

### 5. Confirm before mutating

Every filesystem write — moves, renames, INDEX.md updates, meeting note creations — requires user approval via `AskUserQuestion`. The approval flows are batched (per plan-bucket, per meeting cluster) so the user approves a logical group at a time, not 399 individual files.

### 6. Idempotent writes everywhere

`update_index.py` and `update_meeting.py` are no-ops if the entry is already present. Re-running the skill after a partial failure is safe.

---

## What This Skill Does

1. Confirm source (Desktop) and target (`~/Desktop/Screenshots/`)
2. Set up `screenshot-ocr` conda env and run macOS Vision OCR on all Desktop screenshots
3. Build active-plan index + existing-meeting index from NotePlan
4. Match screenshots to plans (OCR pre-pass → Claude Vision classification → final assignment)
5. Cluster screenshots into meeting sessions; visually extract title + attendees
6. Present plan-bucket approval to user
7. For each cluster: match to existing meeting note or create placeholder (AskUserQuestion)
8. Execute all approved moves: rename, move, update INDEX.md + meeting note
9. Verify final state

---

## Task Management (MANDATORY)

**Before doing any work, create all phase tasks with dependencies:**

```javascript
// Phase tasks (create all first)
const t1 = await TaskCreate({ subject: "Scope confirm", description: "Confirm Desktop source, Screenshots target, show counts.", activeForm: "Confirming scope" })
const t2 = await TaskCreate({ subject: "OCR env setup", description: "Check/create screenshot-ocr conda env.", activeForm: "Setting up OCR environment" })
const t3 = await TaskCreate({ subject: "OCR — extract text from Desktop screenshots", description: "Run batch_ocr.py --desktop. Save JSON to /tmp/organize-by-plan/ocr.json.", activeForm: "Running OCR on Desktop screenshots" })
const t4 = await TaskCreate({ subject: "Build plan index", description: "Run scan_plans.py. Save JSON to /tmp/organize-by-plan/plans.json.", activeForm: "Building active plan index" })
const t5 = await TaskCreate({ subject: "Build meeting index", description: "Run scan_meetings.py. Save JSON to /tmp/organize-by-plan/meetings.json.", activeForm: "Building meeting index" })
const t6 = await TaskCreate({ subject: "Match screenshots to plans (OCR pre-pass)", description: "Run match_screenshots.py. Save manifest to /tmp/organize-by-plan/manifest.json.", activeForm: "Matching screenshots to plans" })
const t7 = await TaskCreate({ subject: "Claude Vision classification", description: "Read each screenshot image; classify against candidate plans; update manifest.", activeForm: "Classifying screenshots with Vision" })
const t8 = await TaskCreate({ subject: "Cluster into meeting sessions", description: "Run cluster_meetings.py. Save to /tmp/organize-by-plan/clusters.json.", activeForm: "Clustering meeting sessions" })
const t9 = await TaskCreate({ subject: "Visual meeting extraction", description: "Read representative screenshots per cluster; extract title + attendees.", activeForm: "Extracting meeting details" })
const t10 = await TaskCreate({ subject: "Present plan-bucket suggestions", description: "AskUserQuestion per plan bucket for approval.", activeForm: "Presenting plan buckets" })
const t11 = await TaskCreate({ subject: "Resolve meeting linkage", description: "AskUserQuestion per cluster; link to existing meeting or create placeholder.", activeForm: "Resolving meeting linkage" })
const t12 = await TaskCreate({ subject: "Execute moves", description: "Fan out per-screenshot tasks: rename, move, update INDEX.md + meeting note.", activeForm: "Executing moves" })
const t13 = await TaskCreate({ subject: "Verify final state", description: "Run verify.py --pretty. Check INDEX.md and meeting note entry counts.", activeForm: "Verifying" })
const t14 = await TaskCreate({ subject: "Summary report", description: "Report moved counts, plan distribution, meeting notes updated.", activeForm: "Summarising" })

// Sequential dependencies
await TaskUpdate({ taskId: t2.id, addBlockedBy: [t1.id] })
await TaskUpdate({ taskId: t3.id, addBlockedBy: [t2.id] })
await TaskUpdate({ taskId: t4.id, addBlockedBy: [t3.id] })
await TaskUpdate({ taskId: t5.id, addBlockedBy: [t3.id] })
await TaskUpdate({ taskId: t6.id, addBlockedBy: [t4.id, t5.id] })
await TaskUpdate({ taskId: t7.id, addBlockedBy: [t6.id] })
await TaskUpdate({ taskId: t8.id, addBlockedBy: [t3.id] })
await TaskUpdate({ taskId: t9.id, addBlockedBy: [t8.id] })
await TaskUpdate({ taskId: t10.id, addBlockedBy: [t7.id] })
await TaskUpdate({ taskId: t11.id, addBlockedBy: [t9.id, t10.id] })
await TaskUpdate({ taskId: t12.id, addBlockedBy: [t11.id] })
await TaskUpdate({ taskId: t13.id, addBlockedBy: [t12.id] })
await TaskUpdate({ taskId: t14.id, addBlockedBy: [t13.id] })
```

Run `TaskList()` to show the plan before proceeding.

---

## Workflow

### Step 0: Locate scripts

```bash
SCRIPTS=$(find "$HOME/.claude/plugins/cache" \
  -path "*/screenshot-manager/*/skills/suggest-groupings/scripts" \
  -type d | head -1)
MY_SCRIPTS=$(find "$HOME/.claude/plugins/cache" \
  -path "*/screenshot-manager/*/skills/organize-by-plan/scripts" \
  -type d | head -1)
DESKTOP="$HOME/Desktop"
SCREENSHOTS_ROOT="$HOME/Desktop/Screenshots"
NOTEPLAN_ROOT="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
mkdir -p /tmp/organize-by-plan
```

---

### Phase 1 (Task 1): Scope Confirm

Mark Task 1 `in_progress`.

Count Desktop screenshots and show date range:
```bash
ls -1 "$DESKTOP"/Screenshot\ *.png 2>/dev/null | wc -l
ls -1 "$DESKTOP"/Screenshot\ *.png 2>/dev/null | sort | head -1
ls -1 "$DESKTOP"/Screenshot\ *.png 2>/dev/null | sort | tail -1
```

Use `AskUserQuestion`:
- header: "Confirm scope"
- question: "Found N screenshots on ~/Desktop (DATE_RANGE). Confirm: organize these into ~/Desktop/Screenshots/ with plan-named subdirs?"
- options: ["Yes — proceed", "Change target directory", "Cancel"]

Mark Task 1 `completed`.

---

### Phase 2 (Task 2): OCR Environment

Mark Task 2 `in_progress`.

```bash
conda env list | grep -q screenshot-ocr && echo "exists" || echo "missing"
```

If missing:
```bash
conda create -n screenshot-ocr python=3.11 -y
conda run -n screenshot-ocr pip install pyobjc-framework-Vision
```

Smoke test (always):
```bash
conda run -n screenshot-ocr python3 -c "import Vision; print('Vision OK')"
```

Mark Task 2 `completed`.

---

### Phase 3 (Task 3): OCR Desktop Screenshots

Mark Task 3 `in_progress`.

```bash
conda run -n screenshot-ocr python3 "$SCRIPTS/batch_ocr.py" --desktop \
  > /tmp/organize-by-plan/ocr.json
```

Report: N files OCR'd, N errors, sample of 3 shortest OCR results (likely blank screenshots).

Mark Task 3 `completed`.

---

### Phase 4 (Task 4): Build Plan Index

Mark Task 4 `in_progress`.

Determine the screenshot date range from the OCR filenames (e.g. 260223:260424) and use it for the date-range filter:
```bash
python3 "$MY_SCRIPTS/scan_plans.py" \
  --since-days 90 \
  --date-range 260223:260424 \
  > /tmp/organize-by-plan/plans.json
```

Report: N active plans by domain (🏢 X, 🏡 Y, ☕️ Z, 👥 W). List the first 5 plan titles so user can sanity-check.

Mark Task 4 `completed`.

---

### Phase 5 (Task 5): Build Meeting Index

Mark Task 5 `in_progress`.

```bash
python3 "$MY_SCRIPTS/scan_meetings.py" \
  --date-range 260223:260424 \
  > /tmp/organize-by-plan/meetings.json
```

Report: N existing meeting notes found in the screenshot window (by domain).

Mark Task 5 `completed`.

---

### Phase 6 (Task 6): OCR Pre-pass Match

Mark Task 6 `in_progress`.

```bash
python3 "$MY_SCRIPTS/match_screenshots.py" \
  --ocr /tmp/organize-by-plan/ocr.json \
  --plans /tmp/organize-by-plan/plans.json \
  --threshold 3 \
  --out /tmp/organize-by-plan/manifest.json
```

Report:
- Total screenshots processed
- Screenshots with temporal match (at least one candidate plan)
- Screenshots with `confidence: high` / `medium` / `low` / `unmatched`
- Top 5 plans by candidate count

Mark Task 6 `completed`.

---

### Phase 6.5 (Task 7): Claude Vision Classification

Mark Task 7 `in_progress`.

This is the primary classification pass. Load `manifest.json` into memory. For each screenshot entry (process in batches of ~10 to stay within context):

1. Use the **`Read` tool** to view the screenshot image at `entry.src`.
2. Read `entry.ocr_excerpt` and `entry.candidates` (top-3 plan shortlist from OCR pre-pass).
3. Decide: which candidate plan best matches what you see, OR is it `Unsorted`?

**What to look for:**
- Code editor, terminal, or browser showing URLs / project names → match against development plans
- Zoom/Meet UI with a title or participants → note it for clustering; match to the plan that session was likely about
- ServiceNow UI (portal, incident table, catalog) → match to a 🏢 work plan
- NaqshCoffee design tools, Figma, Canva → ☕️ domain plans
- EarlBear deck, Shopify, auto-deck tools → 👥 domain plans
- Generic unrecognized content → `Unsorted`

**Output format per screenshot** (update manifest.json in memory):
```json
{
  "src": "...",
  "vision_plan_file": "/path/to/matched/plan.md or null",
  "vision_subdir_name": "🏡 Developing OCR Tooling or Unsorted",
  "vision_confidence": "high | medium | low",
  "vision_note": "one-line reason"
}
```

After processing all screenshots, merge vision results into manifest: for each entry, if `vision_plan_file` is set, it overrides the OCR `top_candidate`. Write the updated manifest back to `/tmp/organize-by-plan/manifest.json`.

Report: N reclassified (OCR top-candidate overridden), N moved to Unsorted, N unchanged.

Mark Task 7 `completed`.

---

### Phase 7 (Task 8): Cluster into Meeting Sessions

Mark Task 8 `in_progress`.

```bash
python3 "$MY_SCRIPTS/cluster_meetings.py" \
  --ocr /tmp/organize-by-plan/ocr.json \
  --gap-minutes 60 \
  --out /tmp/organize-by-plan/clusters.json
```

Report: N clusters across M days. List all clusters with: date, time window, file count, tool_guess, title_guess.

Mark Task 8 `completed`.

---

### Phase 7.5 (Task 9): Visual Meeting Extraction

Mark Task 9 `in_progress`.

For each cluster, `Read` the first 1–2 representative screenshot files to visually verify and enrich:

- **Confirm or split the cluster**: if the first and last file look like clearly different meetings/contexts, flag the cluster for manual review (it may need the gap-minutes threshold lowered).
- **Extract meeting title**: look for Zoom/Meet window title, calendar invite text, document title, whiteboard header. Override `title_guess` if you find something better.
- **Extract attendees**: look for participant panels, name badges, Google Meet people strip, Zoom sidebar. Override `attendees_guess`.
- **Identify tool**: Zoom, Google Meet, Teams, Slack, in-person whiteboard, solo terminal session.

Update `clusters.json` in memory with the enriched `title_guess`, `attendees_guess`, `tool_guess` per cluster.

Mark Task 9 `completed`.

---

### Phase 8 (Task 10): Present Plan-Bucket Suggestions

Mark Task 10 `in_progress`.

From `manifest.json`, group screenshots by `vision_subdir_name`. For each group (paginate 4 at a time with `AskUserQuestion`):

```
Move 14 files into "🏡 Developing OCR Tooling/"?

Sample:
  • 20260424-092158 batch-ocr-output.png — "batch_ocr.py processed 399 files..."
  • 20260424-101402 vision-api-error.png — "Vision framework not loaded..."
  • 20260423-160233 scan-inventory-schema.png — "scan_inventory emits per-dir date windows..."
```

Use `AskUserQuestion`:
- header: "Plan bucket"
- question: (as above)
- multiSelect: false
- options: ["Approve all N files", "Skip this bucket (leave on Desktop)", "Enter different plan"]

For the `Unsorted/` bucket, offer the same approval flow.

Record approved buckets in memory. Mark Task 10 `completed`.

---

### Phase 9 (Task 11): Resolve Meeting Linkage

Mark Task 11 `in_progress`.

For each cluster from `clusters.json` (that has at least one screenshot in an approved bucket):

1. Cross-reference `meetings.json` for notes on the same date.
2. Score existing meetings by overlap with `title_guess` and `attendees_guess` (keyword overlap on both fields).
3. Sort by score descending and present top matches.

Use `AskUserQuestion`:
- header: "Meeting link"
- question: "Cluster {date} {time_window} · {file_count} files · OCR title guess: '{title_guess}' · attendees: {attendees_guess_list}. Link to an existing meeting, create a placeholder, or skip the meeting layer?"
- options (dynamic):
  - (if scored matches exist) "Link to: 🏢 260423 1-1 Ritesh.md"
  - (if second match exists) "Link to: 🏢 260423 Planning.md"
  - "Create placeholder meeting note" → follow-up questions:
    - Domain (🏢 / 🏡 / ☕️ / 👥) — default: domain of the most-matched plan for this cluster
    - Title (pre-filled with `title_guess`, editable via "Other")
  - "Skip meeting layer for this cluster"

Record the resolved `meeting_file` (or `null`) per cluster → save to `/tmp/organize-by-plan/meeting-resolution.json`.

Mark Task 11 `completed`.

---

### Phase 10 (Task 12): Execute Moves

Mark Task 12 `in_progress`.

**Create one `TaskCreate` per approved screenshot** (from the approved manifest entries). Set `subject` to the new filename, `activeForm` to "Moving {new_filename}".

Process screenshots one at a time. For each:

1. Mark its task `in_progress`.

2. **Compute new_filename** using `slugify_ocr.py`:
   ```bash
   OCR_TEXT=$(python3 -c "import json,sys; d=json.load(open('/tmp/organize-by-plan/ocr.json')); print(d.get('$SRC_PATH',{}).get('text','')[:300])")
   SLUG=$(python3 "$MY_SCRIPTS/slugify_ocr.py" --text "$OCR_TEXT")
   # Extract timestamp from original filename: "Screenshot YYYY-MM-DD at H.MM.SS AM.png"
   # → YYYYMMDD-HHMMSS
   NEW_FILENAME="$TIMESTAMP-$SLUG.png"
   ```

3. **Ensure dest subdir exists**:
   ```bash
   DEST_DIR="$SCREENSHOTS_ROOT/$SUBDIR_NAME"
   mkdir -p "$DEST_DIR"
   ```

4. **Move + rename** via `move_files.py` (handles NNBSP in source paths):
   ```bash
   echo "[{\"src\": \"$SRC\", \"dest_dir\": \"$DEST_DIR\", \"new_name\": \"$NEW_FILENAME\"}]" \
     | python3 "$SCRIPTS/move_files.py"
   ```
   Note: `move_files.py` writes to `dest_dir / src.name`. After the move, rename within dest dir if needed:
   ```bash
   mv "$DEST_DIR/$(basename $SRC)" "$DEST_DIR/$NEW_FILENAME" 2>/dev/null || true
   ```

5. **Update INDEX.md**:
   ```bash
   python3 "$MY_SCRIPTS/update_index.py" \
     --subdir "$DEST_DIR" \
     --entry "{\"new_filename\": \"$NEW_FILENAME\", \"mtime\": \"$SS_DATE\", \"ocr_excerpt\": \"$EXCERPT\", \"plan_file\": \"$PLAN_FILE\"}"
   ```

6. **Update meeting note** (if cluster has a resolved meeting file):
   ```bash
   MEETING_FILE=$(python3 -c "...lookup cluster for this screenshot from meeting-resolution.json...")
   if [ -n "$MEETING_FILE" ]; then
     python3 "$MY_SCRIPTS/update_meeting.py" \
       --meeting-file "$MEETING_FILE" \
       --entries "[{\"new_filename\": \"$NEW_FILENAME\", \"abs_path\": \"$DEST_DIR/$NEW_FILENAME\", \"ocr_excerpt\": \"$EXCERPT\"}]"
   fi
   ```
   For placeholder meetings that haven't been created yet (first screenshot in cluster):
   ```bash
   python3 "$MY_SCRIPTS/update_meeting.py" \
     --create \
     --meeting-file "$MEETING_FILE" \
     --title "$MEETING_TITLE" \
     --date "$YYMMDD" \
     --domain-emoji "$DOMAIN_EMOJI" \
     --entries "[...]"
   ```

7. Mark its task `completed`.

On any sub-step failure: mark the screenshot's task failed with reason; log the error; continue with next file. Do not abort the run.

Mark Task 12 `completed`.

---

### Phase 11 (Task 13): Verify

Mark Task 13 `in_progress`.

```bash
python3 "$SCRIPTS/verify.py" --pretty --root "$SCREENSHOTS_ROOT"
```

Also spot-check:
- 3 random moved files: confirm they exist in `SCREENSHOTS_ROOT`, no longer on `DESKTOP`.
- 2 random INDEX.md files: confirm entries are present and formatted correctly.
- 2 random meeting notes that were updated: confirm `## Screenshots` section exists with at least one entry.

Report: total files in `Screenshots/`, per-subdir counts, Unsorted count, any mismatches.

Mark Task 13 `completed`.

---

### Phase 12 (Task 14): Summary

Mark Task 14 `in_progress`.

Report:
- **X screenshots** moved across **N plan subdirs**
- **Y** sent to `Unsorted/`
- **Z meeting notes** touched (**A** existing updated, **B** placeholder stubs created)
- Top 5 plans by screenshot count
- Plans in the index that received zero screenshots (the temporal/semantic filter may be worth tuning for them)
- Any screenshots that failed to move (with reasons)

Mark Task 14 `completed`.

---

## Scripts

### New scripts (in this skill)

All at `skills/organize-by-plan/scripts/`. Locate at runtime:
```bash
MY_SCRIPTS=$(find "$HOME/.claude/plugins/cache" \
  -path "*/screenshot-manager/*/skills/organize-by-plan/scripts" \
  -type d | head -1)
```

| Script | Purpose | CLI |
|---|---|---|
| `scan_plans.py` | Active-plan index | `--root PATH --since-days N --date-range A:B` |
| `scan_meetings.py` | Existing meeting index | `--root PATH --date YYMMDD --date-range A:B` |
| `match_screenshots.py` | OCR pre-pass match | `--ocr JSON --plans JSON --threshold N --out JSON` |
| `cluster_meetings.py` | Session clustering | `--ocr JSON --gap-minutes N --out JSON` |
| `slugify_ocr.py` | Rename slug derivation | `--text "..." --max-words N --max-chars N` |
| `update_index.py` | Idempotent INDEX.md update | `--subdir PATH --entry JSON` |
| `update_meeting.py` | Idempotent meeting-note update | `--meeting-file PATH --entries JSON [--create ...]` |

### Reused scripts (from suggest-groupings)

Locate via:
```bash
SCRIPTS=$(find "$HOME/.claude/plugins/cache" \
  -path "*/screenshot-manager/*/skills/suggest-groupings/scripts" \
  -type d | head -1)
```

| Script | Purpose |
|---|---|
| `batch_ocr.py --desktop` | Batch Vision OCR for Desktop |
| `move_files.py --manifest` | NNBSP-safe file moves |
| `verify.py --pretty --root PATH` | Post-move file count verification |

---

## Safety Rules

- **Never delete screenshots** — only move + rename. `move_files.py` uses `shutil.move`.
- **Always confirm before mutating** — all moves and note writes require `AskUserQuestion` approval.
- **NNBSP-safe paths** — always resolve screenshot paths through `move_files.py` or via its `resolve_src` logic (handles U+202F narrow no-break space in macOS screenshot filenames).
- **Preserve mtime** — `shutil.move` and macOS `mv` preserve mtime by default.
- **Idempotent note writes** — `update_index.py` and `update_meeting.py` skip entries already present; re-running the skill after partial failure is safe.
- **Per-file task on failure** — mark the screenshot's task as failed with reason; do not abort the rest of the batch.
- **Never modify content above `## Screenshots`** in meeting notes — strictly append-only below that anchor.

---

## Related Skills

- **suggest-groupings** — Event-snapshot organization (chronological event dirs). Use instead of this skill when you want to organize by when something happened, not what plan it belonged to.
- **sort-dirs** — Prefix plan subdirs with `YYYY-MM-DD` date after organizing. Run after this skill to add chronological prefix to plan-named dirs.
- **extract-urls** — Extract URLs from browser screenshots. Complementary: run after this skill to harvest links from screenshots in a specific subdir.
- **introduce** — Overview of all screenshot-manager skills.
