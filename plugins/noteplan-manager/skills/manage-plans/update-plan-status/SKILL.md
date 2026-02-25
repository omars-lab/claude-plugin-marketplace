---
name: update-plan-status
description: Change the status of one or more personal plan files — updates frontmatter status field, H1 title emoji, filename, self-referencing todo, and adds completed date when marking Done (✅)
---

# Update Plan Status

You are a plan status manager. When invoked, you change the status of one or more personal plan files. Status lives in two places: the `status:` frontmatter field and the status emoji embedded in the H1 title and filename. This skill keeps all three in sync.

## Status Emojis

| Emoji | Status | Notes |
|---|---|---|
| `🔮` | Future | Not yet started |
| `🚦` | Ready | Ready to start (no folder equivalent) |
| `🟢` | Started | Active / in progress |
| `🟡` | Paused | On hold |
| `🔴` | Blocked | Blocked by dependency |
| `❎` | Canceled | Won't do |
| `✅` | Done | Completed — also sets `completed` date |

## What Changes Per File

For each plan file being updated:

1. **Frontmatter `status:` field** — replace old status emoji with new one
2. **`completed:` field** — add `completed: YYMMDD` (today) when new status is `✅`; remove if changing away from `✅`
3. **H1 title status emoji** — replace 2nd emoji in H1 if it's a status emoji, or insert one if missing
4. **Filename** — rename via `git mv` to match new H1 title (Golden Rule)
5. **Self-referencing todo** — update wiki-link to match new filename

## Title Pattern

```
# 🏡<status><YYMMDD><plantype> Title
Example: # 🏡🟢260117👨🏻‍💻 Developing Claude Cron for Note Organization
```

Status emoji is always the **2nd emoji** in the title, immediately after the namespace emoji (`🏡`).

**Status emoji detection:** Check if the 2nd emoji in the title is one of: `🔮🚦🟢🟡🔴❎✅`
- If yes: replace it with the new status emoji
- If no: insert the new status emoji after the first emoji

## Frontmatter Format

Regular plan notes use `---` (triple dash) delimiters — standard YAML:

```yaml
---
doctype: 📆
status: 🟢        ← update this
started: 260117
namespace: 🏡
plantype: 👨🏻‍💻
---
```

When marking ✅ Done, also add/update `completed`:

```yaml
---
doctype: 📆
status: ✅
started: 260117
completed: 260221    ← add this (today's date in YYMMDD format)
namespace: 🏡
plantype: 👨🏻‍💻
---
```

When changing away from ✅, remove `completed` if present.

## Self-Referencing Todo

```
Before: * [ ] Is [[🏡🟢260117👨🏻‍💻 Developing Claude Cron]] done? >2026-W3
After:  * [ ] Is [[🏡✅260117👨🏻‍💻 Developing Claude Cron]] done? >2026-W3
```

## Plans Directory

```
$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏡 Personal/🏡📆 Plans/
```

After the `flatten-plans` migration, plan files live in workstream subfolders directly under this path (no status-bucket folders).

## Task Management (MANDATORY)

**Before doing ANY work, create all 6 tasks:**

```javascript
// Task #1: Select scope
TaskCreate({
  subject: "Select scope — which plans to update",
  description: "Ask user which plans to update via AskUserQuestion. Options:\n- Single file (path or title search)\n- By current status (e.g. all 🔮 Future → 🟢 Started)\n- By workstream (e.g. all in 👨🏻‍💻 Development)\n- All plans matching a title pattern\nStore scope selection.",
  activeForm: "Selecting scope"
})

// Task #2: Scan and show matching files
TaskCreate({
  subject: "Scan — find matching plan files",
  description: "Based on scope selection, find all matching .md files in 🏡📆 Plans/. For each file, read frontmatter to get current status and H1 title. Show the list to user for confirmation before proceeding.",
  activeForm: "Scanning plan files"
})

// Task #3: Ask new status
TaskCreate({
  subject: "Ask new status",
  description: "Show AskUserQuestion with all 7 status options (🔮 Future, 🚦 Ready, 🟢 Started, 🟡 Paused, 🔴 Blocked, ❎ Canceled, ✅ Done). If marking ✅, note that today's date will be added as completed date.",
  activeForm: "Selecting new status"
})

// Task #4: Preview changes
TaskCreate({
  subject: "Preview — show all changes before applying",
  description: "For each file, show exactly what will change:\n- Frontmatter: old status → new status\n- H1 title: old title → new title (with status emoji change)\n- Filename: old filename → new filename\n- Self-ref todo: old wiki-link → new wiki-link\n- completed field: added/removed/unchanged\nAsk user to confirm before applying.",
  activeForm: "Previewing changes"
})

// Task #5: Apply changes
TaskCreate({
  subject: "Apply — update frontmatter, title, rename files",
  description: "For each file:\n1. Edit frontmatter: update status field, add/remove completed field\n2. Edit H1: replace/insert status emoji\n3. Edit self-ref todo: update wiki-link\n4. git mv: rename file to match new H1 title\nProcess all files.",
  activeForm: "Applying status changes"
})

// Task #6: Validate and commit
TaskCreate({
  subject: "Validate and commit",
  description: "Run git diff to verify changes:\n- Only status emoji fields changed in frontmatter\n- Only status emoji changed in H1 titles\n- Files renamed (not deleted + new)\n- completed field added/removed correctly\nIf validation passes: commit with descriptive message.",
  activeForm: "Validating and committing"
})
```

**Set up dependencies (sequential):**

```javascript
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
TaskUpdate({ taskId: "5", addBlockedBy: ["4"] })
TaskUpdate({ taskId: "6", addBlockedBy: ["5"] })
```

## Workflow

### Step 0: Task Setup (Do First)

Create all 6 tasks with dependencies, run `TaskList()` to show plan.

### Step 1 (Task #1): Select Scope

Use `AskUserQuestion`:

```
Which plans do you want to update?

- Single file (search by title or provide path)
- By current status (e.g. all 🔮 Future plans → 🟢 Started)
- By workstream (e.g. all in 👨🏻‍💻 Development)
- All plans matching a title pattern
```

Store the scope selection.

### Step 2 (Task #2): Scan

Based on scope, find matching files:

```bash
PLANS_DIR="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏡 Personal/🏡📆 Plans"

# All plans
find "$PLANS_DIR" -name "*.md" -type f | sort

# By workstream
find "$PLANS_DIR/👨🏻‍💻 Development" -name "*.md" -type f | sort

# By status (filter by frontmatter or filename emoji)
grep -rl "status: 🔮" "$PLANS_DIR" --include="*.md"
```

For single-file: search by title substring across all plan files.

For each match, read and show:
- Current path
- Current status (from frontmatter)
- Current H1 title

Show list via `AskUserQuestion` (confirm this is the right set).

### Step 3 (Task #3): Ask New Status

Use `AskUserQuestion`:

```
What status should these N files be changed to?

- 🔮 Future — not yet started
- 🚦 Ready — ready to start
- 🟢 Started — active / in progress
- 🟡 Paused — on hold
- 🔴 Blocked — blocked by dependency
- ❎ Canceled — won't do
- ✅ Done — completed (today's date will be recorded as completed date)
```

### Step 4 (Task #4): Preview Changes

For each file, compute and show:

```
File: 🏡🟢260117👨🏻‍💻 Developing Claude Cron.md
  Status:    🟢 → ✅
  H1 title:  # 🏡🟢260117👨🏻‍💻 Developing Claude Cron
           → # 🏡✅260117👨🏻‍💻 Developing Claude Cron
  Filename:  🏡🟢260117👨🏻‍💻 Developing Claude Cron.md
           → 🏡✅260117👨🏻‍💻 Developing Claude Cron.md
  Self-ref:  [[🏡🟢260117👨🏻‍💻 Developing Claude Cron]]
           → [[🏡✅260117👨🏻‍💻 Developing Claude Cron]]
  Completed: (none) → completed: 260221
```

Show all files. Use `AskUserQuestion`: **Apply these changes? Yes / No / Edit list**

### Step 5 (Task #5): Apply Changes

For each file:

#### 5a: Update Frontmatter

```
Before:
---
status: 🟢
started: 260117
---

After (→ ✅):
---
status: ✅
started: 260117
completed: 260221
---
```

Use the Edit tool to update frontmatter. Place `completed` immediately after `status`. When changing *away* from ✅, remove the `completed` line.

#### 5b: Update H1 Title

Find the H1 line. Replace the status emoji (2nd emoji position):

```
# 🏡🟢260117👨🏻‍💻 Developing Claude Cron
→
# 🏡✅260117👨🏻‍💻 Developing Claude Cron
```

Use the Edit tool.

#### 5c: Update Self-Referencing Todo

Find `* [ ] Is [[old-title]] done?` and update the wiki-link:

```
* [ ] Is [[🏡🟢260117👨🏻‍💻 Developing Claude Cron]] done? >2026-W3
→
* [ ] Is [[🏡✅260117👨🏻‍💻 Developing Claude Cron]] done? >2026-W3
```

Use the Edit tool.

#### 5d: Rename File (git mv)

```bash
cd "$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"

git mv "Notes/🏡 Personal/🏡📆 Plans/👨🏻‍💻 Development/🏡🟢260117👨🏻‍💻 Developing Claude Cron.md" \
       "Notes/🏡 Personal/🏡📆 Plans/👨🏻‍💻 Development/🏡✅260117👨🏻‍💻 Developing Claude Cron.md"
```

**Edit file content (steps 5a–5c) before `git mv`.**

### Step 6 (Task #6): Validate and Commit

```bash
cd "$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"

git diff --stat HEAD
git status --short
```

Verify:
- All changed files show the expected status emoji change in frontmatter and H1
- Files renamed correctly (show as renames, not delete + new)
- `completed` field added/removed as expected
- No other content modified

If validation passes, commit:

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(personal-plans): Update plan status to <emoji> <StatusName>

Files updated: N
New status: <emoji> <StatusName>
<If ✅>: Completed date recorded: YYMMDD
Skill: update-plan-status

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

Show final summary with all files changed.

## Safety Checks

- **Git mv only**: Always use `git mv` for renames to preserve history
- **Edit before move**: Update file content before `git mv`
- **Preview first**: Always show full preview and get user confirmation before applying
- **Frontmatter delimiters**: Regular notes use `---` (triple dash), not `--` (double dash)
- **Status emoji position**: Must be 2nd emoji in H1 title (after namespace `🏡`)
- **Completed field**: Only add when status is `✅`; remove when changing away from `✅`
- **Golden Rule**: filename (minus `.md`) must always match H1 title (minus `# `)

## Example Usage

```bash
/noteplan-manager:update-plan-status

# User selects: By current status → 🔮 Future
# Skill finds 12 Future plans, shows list
# User selects new status: 🟢 Started
# Skill shows preview of 12 file changes
# User confirms
# Skill updates all 12 files, renames them, commits
```

## Related Skills

- **flatten-plans** — one-time migration to create the flat structure this skill works on
- **fix-plans** — fix structural issues (frontmatter, headers) without changing status
- **fix-filenames** — enforce Golden Rule across all plan files
- **discover-structure** — regenerate `🗺️ Note Map.md` after structural changes
