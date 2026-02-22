---
name: suggest-groupings
description: Analyze screenshot content and dates to suggest which files to move between directories or from the Desktop into the Screenshots folder
---

# Suggest Screenshot Groupings

You are a screenshot organization analyst. When invoked, you scan the Screenshots root and the Desktop, run macOS Vision OCR on all images, then use content + date proximity to suggest moves — individual files to relocate, Desktop screenshots to import, or misplaced screenshots that clearly don't belong to their current directory's event context.

**Core philosophy: directories are event/project snapshots, not semantic categories.**

## Guiding Principles (Read First)

### 1. Event/Project Focus — Not Semantic Hierarchies

Directories represent a specific point in time and context: a workshop, a trip, a meeting, a working session. **Do not merge directories just because they share a topic.** A screenshot taken during the GSIP Workshop belongs in GSIP Workshop even if it shows the same tool as another dir.

```
✅ Keep separate:  "Agents in Azure" (Feb 5 session) ≠ "Agents in Servicenow" (Feb 9 session)
✅ Keep separate:  "SF Trip" (Feb 16) ≠ "Canceling NYC Trip" (Feb 20–22)
❌ Don't merge:    two dirs about "AI agents" that happened weeks apart
```

### 2. Date Locality as a Primary Signal

Screenshots taken close together in time are likely from the same working session, even if they don't obviously belong to the named directory. Use timestamps to:
- Identify files that were taken in a different time window than the rest of their directory (misplaced candidates)
- Identify clusters of Desktop screenshots that might form a new named directory
- Confirm or refute content-based grouping hypotheses

```
Example: A screenshot timestamped Feb 11 8:59 AM inside a "Feb 9" directory is
suspicious — it was likely captured during a different session and should be checked.
```

### 3. Only Suggest Moves for Clear Misfits

Don't move files just because the content is semantically richer elsewhere. Only flag a file if:
- Its timestamp is clearly outside the directory's event window, AND
- Its content shows a completely different context (different app, different workflow)

### 4. Preserve Tiny Directories

A directory with 2–3 files is fine — don't absorb it just because it's small. It likely represents a short but distinct event (a 1:1 meeting, a quick receipt capture).

---

## What This Skill Does

1. Confirm the Screenshots root + whether to scan Desktop too
2. Scan all screenshot directories and build a date-annotated inventory
3. Set up `screenshot-ocr` conda env (create if missing)
4. Run OCR on all screenshots; optionally summarize with non-interactive Claude Code
5. Analyze content + date proximity per directory to find misfits and Desktop candidates
6. Present move suggestions to user (no merges — individual files only)
7. Execute approved moves
8. Verify final state

---

## Task Management (MANDATORY)

**Before doing any work, create all 7 tasks:**

```javascript
TaskCreate({
  subject: "Scan — inventory directories, files, and timestamps",
  description: "List all subdirectories under Screenshots root. For each dir, list all files with modification timestamps. Also list screenshot/image files on the Desktop. Build inventory: {dir, files[], earliest_date, latest_date, date_range_days}.",
  activeForm: "Scanning directories and Desktop"
})

TaskCreate({
  subject: "OCR setup — ensure screenshot-ocr conda env is ready",
  description: "Check if 'screenshot-ocr' conda env exists (conda env list | grep -q screenshot-ocr). If missing, create it and install pyobjc-framework-Vision. Run smoke test regardless.",
  activeForm: "Setting up OCR environment"
})

TaskCreate({
  subject: "OCR — extract text from all screenshots",
  description: "Run ocr_screenshot.py via conda run -n screenshot-ocr on each image. Build content map. If any directory has dense/noisy OCR text, optionally run a non-interactive Claude Code summarization pass to produce cleaner per-file descriptions.",
  activeForm: "Running OCR"
})

TaskCreate({
  subject: "Analyze — find misfits and Desktop candidates",
  description: "Per directory: identify files whose timestamps fall clearly outside the dir's event window AND whose content shows a different context. For Desktop: identify image files and which Screenshots dir they likely belong to, or whether they need a new dir. Apply event/project focus principle — never suggest merging entire directories.",
  activeForm: "Analyzing content and dates"
})

TaskCreate({
  subject: "Present suggestions to user",
  description: "Show all proposed moves with rationale (timestamp + content evidence). Use AskUserQuestion for approval. No merge proposals — only individual file moves and Desktop imports.",
  activeForm: "Presenting suggestions"
})

TaskCreate({
  subject: "Execute approved moves",
  description: "Move approved files. For Desktop files going to Screenshots: mv to the target dir. For misplaced files: mv within Screenshots. For Desktop files needing a new dir: mkdir then mv.",
  activeForm: "Moving files"
})

TaskCreate({
  subject: "Verify final state",
  description: "List all directories after changes. Confirm file counts match expectations. Report any files that could not be moved.",
  activeForm: "Verifying"
})
```

**Set up dependencies (sequential):**

```javascript
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
TaskUpdate({ taskId: "5", addBlockedBy: ["4"] })
TaskUpdate({ taskId: "6", addBlockedBy: ["5"] })
TaskUpdate({ taskId: "7", addBlockedBy: ["6"] })
```

---

## Workflow

### Step 0: Task Setup

Create all 7 tasks with dependencies. Run `TaskList()` to show the plan.

### Step 1: Confirm Scope

Use `AskUserQuestion`:
- header: "Scan scope"
- question: "Where should I look for screenshots to analyze?"
- options:
  - "Screenshots folder only"
  - "Screenshots folder + Desktop (suggest imports)"

Also confirm the Screenshots root:
- header: "Screenshots folder"
- question: "Which folder is your Screenshots root?"
- options:
  - `~/Library/CloudStorage/OneDrive-ServiceNow/📸 Screenshots` (label: "Default OneDrive location")
  - `Other (enter path)`

### Step 2 (Task 1): Scan with Timestamps

Mark Task 1 as in_progress.

```bash
# Locate the installed scripts directory (version-agnostic)
SCRIPTS=$(find "$HOME/.claude/plugins/cache" -path "*/screenshot-manager/*/skills/suggest-groupings/scripts" -type d | head -1)
SCREENSHOTS_ROOT="$HOME/Library/CloudStorage/OneDrive-ServiceNow/📸 Screenshots"
```

**Screenshots + Desktop** (adjust flags to match scope confirmed in Step 1):
```bash
# Default — Screenshots + Desktop:
python3 "$SCRIPTS/scan_inventory.py"

# Screenshots only:
python3 "$SCRIPTS/scan_inventory.py" --screenshots-only

# Desktop only:
python3 "$SCRIPTS/scan_inventory.py" --desktop-only
```

Output is JSON: `{directories: {...}, desktop: [...], _summary: {...}}`.

Report: N directories, M total screenshots, K Desktop images found.

Mark Task 1 as completed.

### Step 3 (Task 2): OCR Environment

Mark Task 2 as in_progress.

```bash
# Check if env exists — skip creation if it does
conda env list | grep -q screenshot-ocr && echo "exists" || echo "missing"

# If missing:
conda create -n screenshot-ocr python=3.11 -y
conda run -n screenshot-ocr pip install pyobjc-framework-Vision

# Smoke test (always run)
conda run -n screenshot-ocr python3 -c "import Vision; print('Vision OK')"
```

Mark Task 2 as completed.

### Step 4 (Task 3): Run OCR

Mark Task 3 as in_progress.

Run batch OCR on the in-scope images. Adjust flags to match scope:

```bash
# Desktop only:
conda run -n screenshot-ocr python3 "$SCRIPTS/batch_ocr.py" --desktop

# Screenshots root only:
conda run -n screenshot-ocr python3 "$SCRIPTS/batch_ocr.py" --root "$SCREENSHOTS_ROOT"

# Both:
conda run -n screenshot-ocr python3 "$SCRIPTS/batch_ocr.py" --root "$SCREENSHOTS_ROOT" --desktop

# Single subdirectory:
conda run -n screenshot-ocr python3 "$SCRIPTS/batch_ocr.py" --dir "$SCREENSHOTS_ROOT/GSIP Workshop"
```

Output is a JSON map of `{ "<path>": {"text": "...", "error": null} }`.

**Optional OCR summarization via non-interactive Claude Code:**
If any directory has very dense OCR output (25+ screenshots), use a non-interactive Claude Code call to summarize per-directory OCR into clean 1–2 sentence descriptions:

```bash
claude --print "Summarize what these screenshots are about in 1-2 sentences. Focus on: what tool/context is shown, what task was being done. Text:\n\n$ocr_text_for_dir" 2>/dev/null
```

Use summaries to enrich analysis; per-file text is still needed for misfit detection.

Mark Task 3 as completed.

### Step 5 (Task 4): Analyze for Misfits and Desktop Candidates

Mark Task 4 as in_progress.

#### Misfit Detection (files in Screenshots dirs)

For each directory, compute its **event window**: the date range covering 90% of its files (drop outliers).

A file is a **misfit candidate** if ALL of the following are true:
1. Its timestamp is >3 days outside the directory's event window
2. Its OCR content shows a clearly different tool/context than the other files in that directory
3. There is a more appropriate directory for it (by date proximity AND content match)

**Do not flag** a file as a misfit just because:
- It's semantically similar to another directory — event context takes precedence
- It's one of a few outlier dates but the content matches the directory topic

#### Desktop Candidates

For each Desktop image:
1. Find the closest Screenshots directory by date (file mtime vs directory event window)
2. Check content match via OCR
3. Determine: assign to existing dir, create new dir, or skip

A Desktop image belongs to an **existing Screenshots dir** if:
- Its date falls within or ≤3 days of that dir's event window
- Its content matches the dir's topic

A Desktop image needs a **new Screenshots dir** if:
- No existing dir is a good match
- Multiple Desktop images share the same date/context (name the new dir descriptively)

#### Output Format

Build a structured proposal:
```json
{
  "misfit_moves": [
    {
      "file": "Screenshot 2026-02-11 at 8.59.44 AM.png",
      "from": "GSIP Workshop",
      "to": "Agents in Azure",
      "timestamp": "2026-02-11",
      "dir_event_window": "2026-02-10 to 2026-02-11",
      "rationale": "Content shows ai.azure.com agent list. Same tool/session as Agents in Azure (Feb 5), not workshop content. Timestamp is within workshop window but content is a clear misfit."
    }
  ],
  "desktop_imports": [
    {
      "file": "Screenshot 2026-02-20.png",
      "destination": "Canceling NYC Trip",
      "is_new_dir": false,
      "rationale": "Date Feb 20 matches trip cancellation window. OCR shows CWT booking interface."
    }
  ],
  "no_action": [
    {
      "dir": "Requesting Feedback",
      "reason": "2 files, single event (1:1 meeting Feb 13), content is coherent. Keep as-is."
    }
  ]
}
```

Mark Task 4 as completed.

### Step 6 (Task 5): Present to User

Mark Task 5 as in_progress.

Present misfit moves:
```
Move: "GSIP Workshop/Screenshot 2026-02-11 at 8:59 AM.png" → "Agents in Azure"
Why: Shows ai.azure.com agents list — same tool as Agents in Azure, not workshop content.
Timestamp: Feb 11 (within workshop window but content mismatch)
```

Present Desktop imports:
```
Import: Desktop/Screenshot 2026-02-20.png → "Canceling NYC Trip"
Why: Date Feb 20 + OCR shows CWT booking, matches trip cancellation context.

Import: Desktop/Screenshot 2026-02-22.png + Screenshot 2026-02-22 (2).png → NEW DIR "Spotnana Research"
Why: 2 images, same date, show Spotnana hotel/flight UI — no existing dir matches.
```

Use `AskUserQuestion`:
- header: "Approve moves"
- question: "Which of these moves do you want to apply?"
- multiSelect: true
- options: one per suggested move/import (max 4 at a time; paginate if more)

For new directory suggestions, confirm the name:
- header: "New dir name"
- question: "What should the new directory be called for these N Desktop screenshots?"
- options: [proposed name, "Enter different name"]

Mark Task 5 as completed.

### Step 7 (Task 6): Execute

Mark Task 6 as in_progress.

Build a JSON manifest of approved moves and pass it to `move_files.py`. The script handles U+202F (narrow no-break space) in macOS screenshot filenames automatically.

```bash
# Write the manifest based on approved moves, then execute:
python3 "$SCRIPTS/move_files.py" --manifest /tmp/moves.json
```

Manifest format:
```json
[
  {"src": "/Users/you/Desktop/Screenshot 2026-02-20.png",
   "dest_dir": "/path/to/📸 Screenshots/Canceling NYC Trip"},
  {"src": "/path/to/📸 Screenshots/GSIP Workshop/Screenshot 2026-02-11 at 8.59.44 AM.png",
   "dest_dir": "/path/to/📸 Screenshots/Agents in Azure"}
]
```

`dest_dir` is created automatically if it does not exist. Output is JSON `{"moved": [...], "failed": [...]}`.

Report each move from the output.

Mark Task 6 as completed.

### Step 8 (Task 7): Verify

Mark Task 7 as in_progress.

```bash
python3 "$SCRIPTS/verify.py" --pretty
```

Confirm file counts match expectations.

Mark Task 7 as completed.

---

## Scripts

All scripts live in `skills/suggest-groupings/scripts/`. Locate them at runtime:
```bash
SCRIPTS=$(find "$HOME/.claude/plugins/cache" -path "*/screenshot-manager/*/skills/suggest-groupings/scripts" -type d | head -1)
```

### `scan_inventory.py`

Inventory Screenshots directories and/or Desktop images. Default (no flags) scans both.

```bash
python3 "$SCRIPTS/scan_inventory.py"                     # Screenshots + Desktop (default)
python3 "$SCRIPTS/scan_inventory.py" --screenshots-only  # Screenshots root only
python3 "$SCRIPTS/scan_inventory.py" --desktop-only      # Desktop only
python3 "$SCRIPTS/scan_inventory.py" --root /custom/path
```

Output JSON: `{directories: {name: {files, earliest, latest, range_days}}, desktop: [{name, mtime}], _summary}`.

### `move_files.py`

Move files according to a JSON manifest. Handles U+202F in macOS screenshot filenames. Creates destination directories automatically.

```bash
python3 "$SCRIPTS/move_files.py" --manifest /tmp/moves.json

# Or pipe JSON:
echo '[{"src": "/Desktop/Screenshot.png", "dest_dir": "/Screenshots/MyDir"}]' \
    | python3 "$SCRIPTS/move_files.py"
```

Output JSON: `{"moved": [...], "failed": [...]}`. Exits non-zero if any moves failed.

### `batch_ocr.py`

Run OCR on all images in a directory or on the Desktop in a single call. Requires `screenshot-ocr` conda env.

```bash
conda run -n screenshot-ocr python3 "$SCRIPTS/batch_ocr.py" --desktop
conda run -n screenshot-ocr python3 "$SCRIPTS/batch_ocr.py" --root /path/to/Screenshots
conda run -n screenshot-ocr python3 "$SCRIPTS/batch_ocr.py" --dir "/path/to/GSIP Workshop"
```

Output JSON: `{"<path>": {"text": "...", "error": null}, ...}`. Supports `--desktop`, `--root`, `--dir`, `--files`.

### `ocr_screenshot.py`

Extract text from a single screenshot using macOS Vision OCR. Requires `screenshot-ocr` conda env.

```bash
conda run -n screenshot-ocr python3 "$SCRIPTS/ocr_screenshot.py" "/path/to/screenshot.png"
```

Output JSON: `{"path": "...", "text": "..."}`. Handles U+202F (narrow no-break space) in macOS screenshot filenames automatically.

### `verify.py`

Print a file-count summary of each Screenshots subdirectory after moves.

```bash
python3 "$SCRIPTS/verify.py" --pretty           # human-readable table
python3 "$SCRIPTS/verify.py"                    # JSON output
python3 "$SCRIPTS/verify.py" --root /custom/path [--pretty]
```

`--pretty` prints `N files across M dirs` + a count-per-dir table. Default is JSON: `{root, total_files, dirs: [{dir, file_count, files[]}]}`.

---

## Safety Rules

- **Never merge entire directories.** Only move individual files.
- **Event context wins over semantics.** Two directories about the same tool are still separate events.
- **Always confirm before moving.** All moves require user approval via AskUserQuestion.
- **Preserve tiny directories.** 2–3 file dirs represent real distinct events.
- **Desktop imports are additive only.** Never delete Desktop originals — just copy... actually `mv` is fine for imports; user is explicitly requesting these moves.

---

## Related Skills

- **sort-dirs** — Prefix directory names with dates after organizing files
- **introduce** — Overview of all skills
