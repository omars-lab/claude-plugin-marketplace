---
name: sweep-daily-notes
description: Guided day-by-day sweep of past daily notes — builds a plan index from recently-touched plans, proposes a full mapping plan per day, optionally creates new plan files, and moves sections verbatim under # [[PlanName]] wikilink headers in the target note
---

# Sweep Daily Notes

You are a guided sweep assistant for NotePlan daily notes. Your job is to:

1. Build a live index of recently-touched plan files for the chosen mode
2. Enrich any plans missing a `description` in their frontmatter
3. Work **one day at a time** — announce the earliest date with sweepable content, propose a complete section mapping for that day, confirm with the user, then execute before moving to the next day
4. Optionally create new plan files (from template) when a section deserves its own plan
5. Move content **verbatim** under `# [[PlanName]]` wikilink headers in the target note

You never modify note content. You ask before acting when intent is unclear.

---

## Environment Detection

**CRITICAL**: Do NOT use hardcoded paths. Detect the user's NotePlan directory dynamically:

```bash
NOTEPLAN_ROOT="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
NOTES_ROOT="$NOTEPLAN_ROOT/Notes"
CALENDAR_ROOT="$NOTEPLAN_ROOT/Calendar"
```

**Plan directory roots** — derived from mode, traversed recursively:
- Work: `$NOTES_ROOT/🏢 ServiceNow/📆 Plans/`
- Personal: `$NOTES_ROOT/🏡 Personal/🏡📆 Plans/`

Discover subdirectories with `find` — never hardcode subdir names.

---

## Task Management

Use `TaskCreate` and `TaskUpdate` to track all phases with dependencies:

1. Ask mode
2. Pre-sweep git commit (blocked by 1) — **HARD MUST**
3. Build plan index (blocked by 2)
4. Enrich missing descriptions (blocked by 3)
5. Discover daily notes in scope (blocked by 4)
6. Day-by-day guided sweep (blocked by 5) — one task per day
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
      },
      {
        label: "Both",
        description: "All daily notes from the past 3 months — weekday notes to next Friday (work plans), weekend notes to next Sunday (personal plans), sorted by date oldest-first"
      }
    ],
    multiSelect: false
  }]
})
```

Set based on answer:

| Mode | Daily date range | Days of week | Plans dir | Plan lookback | New plan subdir | Target note |
|---|---|---|---|---|---|---|
| Work | Past 1 month | Mon–Fri | `🏢 ServiceNow/📆 Plans/` | 60 days | `{workstream}/` | Next Friday |
| Personal | Past 3 months | Sat–Sun | `🏡 Personal/🏡📆 Plans/` | 90 days | `Present/{plantype}/` | Next Sunday |
| Both | Past 3 months | Mon–Sun | Both of the above | 90 days | Per day-of-week | Fri for weekdays, Sun for weekends |

**Both mode**: build both work and personal plan indexes in Phase 3. For each daily note in Phase 6, apply the correct index and target based on the note's day-of-week (Mon–Fri → work rules; Sat–Sun → personal rules).

### Calculating target date:

```bash
TODAY=$(date +%Y-%m-%d)
DAY_OF_WEEK=$(date +%u)

DAYS_TO_FRI=$(( (5 - DAY_OF_WEEK + 7) % 7 ))
[ "$DAYS_TO_FRI" -eq 0 ] && DAYS_TO_FRI=7
NEXT_FRIDAY=$(date -v +${DAYS_TO_FRI}d +%Y%m%d)

DAYS_TO_SUN=$(( (7 - DAY_OF_WEEK + 7) % 7 ))
[ "$DAYS_TO_SUN" -eq 0 ] && DAYS_TO_SUN=7
NEXT_SUNDAY=$(date -v +${DAYS_TO_SUN}d +%Y%m%d)
```

The target note is `$CALENDAR_ROOT/<TARGET_DATE>.md`. Create it if it doesn't exist.

---

## Phase 2: Pre-Sweep Git Commit — HARD MUST

**Non-negotiable. Do not proceed if this fails.**

```bash
cd "$NOTEPLAN_ROOT"
git status
```

If there are any uncommitted changes:

```bash
git add -A
git commit -m "Pre-sweep snapshot ($(date +%Y-%m-%d))"
```

If the commit fails, **stop and report**. Confirm the tree is clean before continuing.

---

## Phase 3: Build Plan Index

### Context window hygiene — CRITICAL

**Never read full plan bodies into context.** Extract only:
- For index building: first 15 lines of each file (frontmatter + H1)
- For description inference: first 20 lines (frontmatter + H1 + opening body lines)
- Process one daily note at a time during the sweep — discard after processing

```bash
PLAN_ROOT="$NOTES_ROOT/<mode-plans-directory>"
LOOKBACK_DAYS=60   # 60 for work, 90 for personal

find "$PLAN_ROOT" -name "*.md" -mtime -${LOOKBACK_DAYS} | sort

# Extract only frontmatter + H1 per plan
head -15 "$plan_file"
```

For each plan file:
1. Parse frontmatter between `---` delimiters
2. Extract `status` — skip 🔴 and 🏁; include 🟢, 🟡, unset
3. Extract `workstream` (work) or `plantype` (personal) — the emoji category
4. Extract `description` if present (may be absent → `description_missing: true`)
5. Extract display name from `# H1`; preserve exact filename stem for wikilinks

Build a compact plan index (metadata only, no content):

```
[
  {
    "filename_stem": "🏢260302🧑🏻‍💻 POC Establishing A2A Poc",
    "path": "/full/path/to/file.md",
    "workstream_or_plantype": "🧑🏻‍💻",
    "status": "🟢",
    "description": "...",
    "description_missing": true/false
  }
]
```

Report: "Found N recently-touched plans." List with workstream and description.

---

## Phase 4: Enrich Plans Missing Descriptions + Filename/Title Consistency Check

### Filename/Title Consistency Check (run alongside description enrichment)

While processing plans for missing descriptions, also check for H1/filename mismatches and fix them:

1. **For each plan**, compare `filename_stem` against the H1 heading
2. **Rename file → match H1** when the filename is a plain/untitled string (no `🏢YYMMDD` or `🏡YYMMDD` prefix) but the H1 has a proper convention
3. **Fix H1 → match filename** when the filename has proper convention but H1 differs (e.g. different emoji, extra " 2" suffix, or alternate wording) — this is safer because filenames are the canonical wikilink reference
4. **Flag as ambiguous** (don't auto-fix) when: neither has proper convention, the mismatch is a trailing `?`, it's a date-format filename (`YYYY-MM-DD ...`), or the name difference is significant enough to need human judgment
5. **Commit all fixes** together with the description enrichment in a single `chore(plans): add description frontmatter …; fix N H1 titles and M filenames` commit

**Never silently drop `?` from a filename H1 without noting it.** Report ambiguous cases to the user after the commit so they can run `/noteplan-manager:manage-filenames` for a deeper pass.

---

### Bulk path (preferred when N > 5 plans missing descriptions)

When many plans are missing descriptions, the one-by-one approach is impractical. Use the bulk path instead:

1. **Read first 20 lines of ALL missing-description plans** in a single Python pass — extract H1 + first 3–5 non-empty body lines for each
2. **Infer descriptions** from H1 + body preview for all plans at once
3. **Present ALL inferred descriptions** grouped by workstream in a single conversation message for review
4. **Ask for bulk approval** with a single `AskUserQuestion`:
   ```javascript
   AskUserQuestion({ questions: [{ question: "The N proposed descriptions are listed above. Approve all and commit, or skip?", header: "Bulk approve", options: [{ label: "Approve all — write + commit" }, { label: "Skip description enrichment" }] }] })
   ```
5. **Write all approved descriptions** to frontmatter in one Python pass (no other changes)
6. **Commit** with: `git commit -m "chore(plans): add description frontmatter to ${N} plan(s)"`

### One-by-one path (only when N ≤ 5)

For each plan where `description_missing = true`:

1. Read only the first 20 lines of the plan
2. Infer a one-sentence description from H1 + first 3–5 non-empty body lines
3. Confirm before writing:

```javascript
AskUserQuestion({
  questions: [{
    question: `Plan "${planName}" has no description.\n\nProposed: "${inferredDescription}"\n\nApprove or provide your own?`,
    header: `Enrich: ${planName}`,
    options: [
      { label: "Use proposed", description: inferredDescription },
      { label: "Enter my own", description: "I'll type a better one" },
      { label: "Skip", description: "Leave without description" }
    ],
    multiSelect: false
  }]
})
```

Write confirmed descriptions back to frontmatter (`description:` field, no other changes). Commit separately if any plans were enriched:

```bash
git add -A
git commit -m "chore(plans): add description frontmatter to ${N} plan(s)"
```

---

## Phase 5: Discover Daily Notes in Scope

Find all daily note files in the date range and day-of-week filter:

```bash
for f in "$CALENDAR_ROOT"/????????.md; do
  filename=$(basename "$f" .md)
  file_date=$(date -j -f "%Y%m%d" "$filename" +%Y-%m-%d 2>/dev/null) || continue
  day_of_week=$(date -j -f "%Y%m%d" "$filename" +%u)
  # Work: day 1–5, past 30 days; Personal: day 6–7, past 90 days
done
```

Sort **oldest first**. Skip: target note itself, today's note, empty files.

Report: "Found N daily notes in scope. Earliest: {date}, Latest: {date}."

---

## Phase 6: Day-by-Day Guided Sweep

Process one daily note at a time, oldest first. **Complete each day fully before moving to the next.**

### Step 6a — Announce the day

Open each daily note and scan for sweepable content (any section with at least one non-completed line):

```
📅 Earliest date with sweepable content: {fileDate}

Found {n} section(s) with incomplete content:
  • "{sectionHeader1}" — {lineCount} lines
  • "{sectionHeader2}" — {lineCount} lines
  • ...
```

### Step 6b — Classify sections for the day

For each sweepable section, determine the best destination using the plan index and classify it:

**Match signals (try in order):**
1. Section content contains `[[PlanName]]` wikilink matching a plan in the index → `✅ Confident`
2. Section header text closely matches a plan name → `✅ Confident`
3. Section's workstream emoji matches a single plan's workstream → `✅ Confident`
4. Clearly personal content (shopping, errands, `[[🏡...]]` wikilinks in work mode) → `⏭️ Skip`
5. Completed-task-only block → `⏭️ Skip`
6. Anything else → `❓ Uncertain`

**For sections that seem substantial** (more than 3 lines, contain tasks, describe a distinct topic), also flag as "could be new plan."

**Sections may be split by line** when individual items within a section reference different plans (e.g. a `# POCs` block with two different `[[PlanName]]` wikilinks). Split these and classify each line individually.

**Same-plan entries are merged in the target** — multiple sections routing to the same plan get merged under one `# [[PlanName]]` header.

Announce the classification before routing:

```
📅 {fileDate} — {n} sweepable section(s):
  ✅ {k} confident match(es) — will auto-route
  ❓ {m} uncertain section(s) — will ask individually
  ⏭️  {j} skip(s) — personal/completed
```

### Step 6c — Route uncertain sections one at a time

**For every `❓ Uncertain` section, ask individually with AskUserQuestion — one question per section, no bulk prompts.**

#### Scoring: top-5 plan suggestions

Before presenting the routing question, score every plan in the index against the section's content and header. Use the following signals (additive):

| Signal | Score |
|---|---|
| Section content contains `[[filename_stem]]` exact wikilink match | +10 |
| Section header text contains a word from the plan's filename stem (case-insensitive) | +5 |
| Section content contains a word from the plan's filename stem (case-insensitive, ≥ 4 chars) | +3 |
| Plan's workstream/plantype emoji appears in section header or content | +2 |
| Plan has `status: 🟢` (active) | +1 |

Select the **top 5 plans** by score (break ties by recency — most-recently-modified first). These are the only plan options shown. Always append the fixed options below.

For each uncertain section (in source order):

```javascript
// Compute top5 before calling AskUserQuestion
const top5 = scoredPlanIndex
  .sort((a, b) => b.score - a.score || b.mtime - a.mtime)
  .slice(0, 5);

AskUserQuestion({
  questions: [{
    question: `Section "${sectionHeader}" from ${fileDate}:\n\n${sectionPreview}\n\nTop suggested destinations (scored by content match):`,
    header: `Route: "${sectionHeader}" (${currentIndex}/${totalUncertain})`,
    options: [
      ...top5.map((p, i) => ({
        label: `[[${p.filename_stem}]]`,
        description: `#${i+1} match · ${p.description || `(${p.workstream_or_plantype} — no description)`}`
      })),
      { label: "🆕 Create a new plan/file for this", description: "This section deserves its own plan file" },
      { label: "📥 Unsorted", description: "Place under # Unsorted in the target note" },
      { label: "⏭️ Skip — leave it here", description: "Don't move this section" }
    ],
    multiSelect: false
  }]
})
```

> **Note:** If none of the top-5 match the user's intent, the user can choose "🆕 Create a new plan/file" or "📥 Unsorted". The full plan index is available in the description enrichment step if needed, but is never dumped into the routing UI.

Show a **progress counter** in the header (`1/3`, `2/3`, etc.) so the user knows how many uncertain sections remain.

If **"🆕 Create a new plan"** is selected → go to **Step 6d: Create New Plan**, then return to routing.

After all uncertain sections are routed, **present the complete day plan** (confident + newly routed):

```
📋 Final sweep plan for {fileDate}:

  ✅ "# Servicenow"  →  [[🏢260302🧑🏻‍💻 Understanding Servicenow Agentic AI Landscape]]
     Reason: content about AI features matches plan scope
     Destination: 20XXXXXX.md (target note)
     ```
     - [ ] I Need to make a AI Feature Catalog ...
     	- [ ] Map out all servicenow agentic features
     ```

  ✅ "# POCs" line 1  →  [[🏢260302🧑🏻‍💻 POC Experimenting with Servicenow MCP]]
     Reason: exact wikilink match
     Destination: 20XXXXXX.md (target note)
     ```
     - [ ] [[🏢260302🧑🏻‍💻 POC: Experimenting with Servicenow MCP]]
     ```

  📥 "# Research"  →  Unsorted (user routed)

  ⏭️  "# Completed Items"  →  (skip — completed-only)
  ⏭️  "# Shopping"  →  (skip — personal content)
```

Then ask to execute:

```javascript
AskUserQuestion({
  questions: [{
    question: `Ready to execute the sweep for ${fileDate}?`,
    header: `Execute: ${fileDate}`,
    options: [
      { label: "Execute", description: "Move all confirmed sections as shown" },
      { label: "Skip this day entirely", description: "Leave all sections in this note as-is" }
    ],
    multiSelect: false
  }]
})
```

### Step 6d — Create New Plan (optional sub-flow)

When a section should become its own plan, gather the needed inputs:

```javascript
AskUserQuestion({
  questions: [
    {
      question: "What should this plan be called?",
      header: "New plan: title",
      freeText: true
    },
    {
      // Work mode:
      question: "Which workstream does this belong to?",
      header: "New plan: workstream",
      options: [
        // Discover by listing subdirs of the plans root:
        // ls "$PLAN_ROOT" → each subdir is a workstream
        // Present as options dynamically
      ]
    },
    // OR for personal mode:
    {
      question: "What kind of plan is this?",
      header: "New plan: plan type",
      options: [
        { label: "⚙️ Automating" }, { label: "✈️ Traveling" }, { label: "❓ Questioning" },
        { label: "🌱 Growth" }, { label: "🎉 Celebration" }, { label: "🎒 Activities" },
        { label: "🏃🏻 Health" }, { label: "🏠 Home" }, { label: "🏢 Career" },
        { label: "👨🏻‍💻 Development" }, { label: "👨🏻‍💼 Entrepreneurship" }, { label: "💰 Assets" },
        { label: "📝 Authoring" }, { label: "📚 Learning" }, { label: "🧎🏻 Spirituality" },
        { label: "🧑‍🧑‍🧒‍🧒 Family" }, { label: "🪵 Backlogs" }
      ]
    },
    {
      question: "What is the current status?",
      header: "New plan: status",
      options: [
        { label: "🟢 Started" }, { label: "🚦 Ready" }, { label: "🔮 Future" }
      ]
    }
  ]
})
```

**Compute the filename** following the template naming convention:

```bash
TODAY_YYMMDD=$(date +%y%m%d)   # e.g. 260313
WEEK_NUM=$(date +%-V | xargs printf "%02d")
YEAR=$(date +%Y)

# Work plan:
# filename_stem = "🏢{YYMMDD}{workstream_emoji} {title}"
# e.g. "🏢260313🧑🏻‍💻 My New POC"

# Personal plan:
# filename_stem = "🏡{YYMMDD}{plantype_emoji} {title}"
# e.g. "🏡260313👨🏻‍💻 My New Initiative"
```

**Write the new plan file** following the template output format exactly:

*Work plan:*
```markdown
---
doctype: 📆
status: {status_emoji}
started: {YYYY-MM-DD}
namespace: 🏢
workstream: {workstream_emoji}
---
# 🏢{YYMMDD}{workstream_emoji} {title}
* [ ] Is [[🏢{YYMMDD}{workstream_emoji} {title}]] done? >{YEAR}-W{WW}
* [ ]
```

*Personal plan:*
```markdown
---
doctype: 📆
status: {status_emoji}
started: {YYMMDD}
namespace: 🏡
plantype: {plantype_emoji}
---
# 🏡{YYMMDD}{plantype_emoji} {title}
* [ ] Is [[🏡{YYMMDD}{plantype_emoji} {title}]] done? >{YEAR}-W{WW}
* [ ]
```

**Place the file** in the correct subdirectory:
- Work: `$PLAN_ROOT/{workstream_dir}/` (match the existing subdir for that workstream emoji)
- Personal: `$PLAN_ROOT/Present/{plantype_dir}/` (match the existing subdir for that plantype emoji)

Discover the correct subdir by listing `$PLAN_ROOT` — never hardcode.

**Add to plan index** so it's available for the rest of the sweep.

Confirm creation to the user: "Created `[[{filename_stem}]]` at `{path}`."

The section's content will be swept into this new plan file directly (not the target daily note) — place it after the `* [ ]` task line in the new plan. This is the one case where content goes to a plan file rather than the target daily note.

### Step 6e — Execute the confirmed plan

After the user confirms the day's routing plan:

For each section confirmed for moving:
- **To target daily note**: append verbatim under `# [[PlanName]]` header in `$CALENDAR_ROOT/<TARGET_DATE>.md`
  - Merge under existing header if already present; create if not
  - **Same-plan sections from different parts of the source day get merged** under one header
- **To new plan file**: append verbatim after the opening `* [ ]` line in the new plan
- **Unsorted**: append under `# Unsorted` in the target note
- **Remove** from source: all content lines AND their section header (`# SectionName`). Do NOT move the original section header to the target — the target gets `# [[PlanName]]` instead.
- **Split sections**: when individual lines within a section go to different plans, remove the section header and each line individually, routing each line to its designated plan header.

**Wikilink todos are ordinary content:** Tasks whose body is a wikilink (e.g. `- [ ] [[PlanName]]`) are moved verbatim exactly like any other task line. The wikilink in the body is the routing signal, but the full line (including `- [ ]` prefix) is preserved as-is.

**Personal content in work mode:** Sections that are clearly personal (shopping, errands, `[[🏡...]]` namespace wikilinks, personal names unrelated to work) should be flagged as `⏭️ skip — personal content` and left in the source. Do not ask the user about them unless the content is ambiguous.

**No content modification rule:** Copy every line exactly as-is. Preserve all leading whitespace / indentation. The only new text introduced is:
- `# [[PlanName]]` headers in the target note
- `# Unsorted` header (if needed)
- The plan file boilerplate when creating a new plan

### Step 6f — Checkpoint commit and advance to the next day

After executing a day's sweep:

```bash
git add -A
git commit -m "sweep(daily): process ${fileDate} → ${TARGET_DATE} (${n} sections moved)"
```

This creates a granular, recoverable history — each day is independently revertable.

Then **announce progression** before loading the next day:

```
✅ Done with {fileDate}. ({n} sections moved, {k} skipped)

Moving to the next applicable day: {nextFileDate}...
```

If there are no more days in scope:

```
✅ All {N} days in scope have been processed.
Proceeding to final validation.
```

Continue this loop until all days in scope are exhausted.

---

## Phase 7: Validate via Git Diff — Line-Level Integrity Check

After all days are processed, run a final integrity check:

```bash
cd "$NOTEPLAN_ROOT"
git diff HEAD~N   # diff against pre-sweep-snapshot commit
```

**Line-level checks (each must pass):**

1. **Every removed line must appear as an added line somewhere**
   - Extract all `-` lines from the diff (excluding `---` markers)
   - For each, find an exact match among `+` lines (same content, same leading whitespace)
   - Any `-` line without a matching `+` line = content loss → FAIL

2. **The only purely new `+` lines allowed are:**
   - `# [[...]]` wikilink section headers
   - `# Unsorted`
   - Plan file boilerplate lines (only in newly-created plan files)
   - Blank lines used as separators between sections
   - Any other new `+` line without a matching `-` line = content creation → FAIL

3. **No indentation changes on moved lines:**
   - For each matched `-`/`+` pair, assert leading whitespace is identical
   - A line gaining or losing spaces/tabs = indentation modified → FAIL

4. **Completed tasks stayed in source files:**
   - No `[x]` or `- [x]` lines appear as `-` removals from daily note files → FAIL if any found

5. **No daily note files deleted** — only modified

Run this check as a bash script for reliability:

```bash
cd "$NOTEPLAN_ROOT"

# Get the diff
git diff HEAD~${DAYS_PROCESSED} --unified=0 > /tmp/sweep_diff.txt

# Check for content loss: lines removed but not added
python3 - <<'PYEOF'
import re, sys

with open('/tmp/sweep_diff.txt') as f:
    lines = f.readlines()

removed = set()
added = set()

for line in lines:
    if line.startswith('--- ') or line.startswith('+++ ') or line.startswith('@@'):
        continue
    if line.startswith('-'):
        removed.add(line[1:].rstrip('\n'))
    elif line.startswith('+'):
        added.add(line[1:].rstrip('\n'))

lost = removed - added
new = added - removed

# Only allowed new lines
allowed_new = [l for l in new if (
    re.match(r'^# \[\[', l) or          # wikilink headers
    l.strip() == '# Unsorted' or
    l.strip() == '' or                   # blank lines
    re.match(r'^\* \[ \] Is \[\[', l) or # plan boilerplate
    re.match(r'^---$', l) or             # frontmatter delimiters
    re.match(r'^doctype:|^status:|^started:|^namespace:|^workstream:|^plantype:', l)
)]
disallowed_new = [l for l in new if l not in allowed_new]

if lost:
    print("FAIL: Lines removed but not found in additions (content loss):")
    for l in sorted(lost): print(f"  - {repr(l)}")
if disallowed_new:
    print("FAIL: New lines added that are not section headers or boilerplate:")
    for l in sorted(disallowed_new): print(f"  + {repr(l)}")
if not lost and not disallowed_new:
    print("PASS: All line-level integrity checks passed.")
PYEOF
```

If **any check fails**, do not proceed. Report the failure to the user and offer rollback to the pre-sweep snapshot:

```bash
git reset --hard <pre-sweep-commit-hash>   # only if user confirms
```

---

## Phase 8: Final Commit

```bash
cd "$NOTEPLAN_ROOT"
git add -A
git commit -m "sweep(daily): complete ${MODE} sweep → ${TARGET_DATE}

- Processed ${N_NOTES} daily note(s) in scope
- Swept ${N_SECTIONS} section(s) to ${TARGET_DATE}.md
- Plans referenced: ${PLAN_NAMES}
- New plans created: ${N_NEW_PLANS}
- Unsorted sections: ${N_UNSORTED}
- Skipped ${N_SKIPPED} section(s) (user choice or completed-only)
- Line integrity check: PASSED"
```

---

## Rules

| Rule | Detail |
|---|---|
| Pre-commit is mandatory | Never skip Phase 2. Fail loudly if not clean after commit. |
| Day-by-day execution | Announce the earliest day, classify sections, route uncertain ones individually, execute, checkpoint commit, then next day. |
| Plans are discovered dynamically | Use `find -mtime` every run. Never hardcode plan names or paths. |
| Context window hygiene | Read only frontmatter + H1 from plans (first 15 lines). One daily note in context at a time. |
| No content changes | Copy every line verbatim. Zero edits to wording, tasks, or formatting. |
| Indentation is immutable | Leading whitespace on every moved line must be preserved exactly. |
| Completed tasks never move | `[x]` tasks are historical record. Skip unconditionally. |
| Wikilink todos are content | `- [ ] [[PlanName]]` tasks are ordinary content — move verbatim, use the wikilink as routing signal. |
| Target sections use wikilinks | Always `# [[filename_stem]]` (exact), never a raw string. |
| Section headers are NOT moved | Remove original `# SectionName` from source; the target gets `# [[PlanName]]` instead. |
| Split sections allowed | When one section has items for different plans, split by line and route individually. |
| Same-plan entries merge | Multiple source sections routing to the same plan merge under one target header. |
| Bulk description enrichment | When N > 5 plans missing descriptions, use bulk path: batch-infer all, present grouped, single approve. |
| Filename/title consistency | During Phase 4, check H1 vs filename for every plan. Rename plain-text filenames to match proper-convention H1s; fix H1s to match proper-convention filenames. Flag ambiguous cases and report them post-commit. |
| Personal content skipped silently | In work mode, sections with personal signals (`🏡` wikilinks, "Shopping", etc.) are flagged skip without asking. |
| New plans follow the template | Use the computed filename convention and frontmatter structure exactly. |
| New plan subdirs are discovered | `ls $PLAN_ROOT` to find the right workstream/plantype subdir. Never hardcode. |
| Checkpoint commits per day | Commit after each day's sweep for granular recoverability. |
| Line-level integrity check | Run the Python diff validation script before the final commit. |
| Proposal includes exact lines | Each routing entry in the final plan shows the exact lines being moved in a code block, plus destination note. |
| Uncertain sections are individual | Never bulk-ask about routing. Every uncertain/ambiguous block gets its own AskUserQuestion, one at a time, with a progress counter. |
| Top-5 routing suggestions | Score every plan against the section header + content; show only the top 5 matches. Never dump the full plan list into the routing UI. |
| Both mode supported | When mode = "Both", build both work + personal indexes. Each note's day-of-week determines which index and target to use. |

---

## Safety

- Pre-commit snapshot before any file changes
- Checkpoint commit after each day
- Line-level Python diff validation before final commit
- Offer rollback to pre-sweep snapshot if integrity check fails
- Use task tracking for full auditability
