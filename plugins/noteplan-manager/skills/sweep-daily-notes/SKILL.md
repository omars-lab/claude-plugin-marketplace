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

## Tenet: No regex for intent detection

**Intent / semantic detection — IOU detection, voice-note detection, section classification, routing signals, any decision that requires *understanding* what content means — must be done by you reading the content with Read/grep tools, NOT by regex patterns in helper scripts.**

Regex is only for mechanical transforms (date format normalization, indentation preservation, appending a date tag to a line *already* marked as root-level) on lines **you** have already classified. Skills or executor scripts that pattern-match for classification are doing the assistant's job in code.

When this SKILL.md says "detect lines matching X" for classification/routing purposes, you read the section, decide which lines qualify, and pass an explicit per-line set (e.g. `iou_lines: [9, 34, 143, 144]`) to the executor. The executor applies the mechanical transform (append `>SOURCE_DATE` tag) only to the lines you flagged — it does not re-derive intent from the text.

This applies to: IOU classification, voice-note signal detection, "is this section a meeting / research / reference candidate," routing-by-content. None of those should ever live in a regex inside a helper script.

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

**MANDATORY**: Use `TaskCreate` and `TaskUpdate` for every phase. Create ALL phase tasks at the start of the session (before Phase 2), with `blocked_by` dependencies set. This gives the user live visibility into sweep progress.

**Create all tasks upfront** (before doing anything else):

```javascript
// Example — create all in one shot at session start
t0 = TaskCreate({ title: "Phase 0: CLI prerequisites check", status: "in_progress" })
t1 = TaskCreate({ title: "Phase 1: Ask mode", status: "todo", blocked_by: [t0.id] })
t2 = TaskCreate({ title: "Phase 2: Pre-sweep git pull + commit", status: "todo", blocked_by: [t1.id] })
t3 = TaskCreate({ title: "Phase 3: Build plan + lists + meetings + thoughts index", status: "todo", blocked_by: [t2.id] })
t4 = TaskCreate({ title: "Phase 4: Enrich missing descriptions + contributors", status: "todo", blocked_by: [t3.id] })
t5 = TaskCreate({ title: "Phase 5: Discover daily notes in scope", status: "todo", blocked_by: [t4.id] })
t6 = TaskCreate({ title: "Phase 6: Day-by-day guided sweep", status: "todo", blocked_by: [t5.id] })
t7 = TaskCreate({ title: "Phase 7: Validate via git diff", status: "todo", blocked_by: [t6.id] })
t7b = TaskCreate({ title: "Phase 7b: Post-sweep Unsorted review", status: "todo", blocked_by: [t7.id] })
t8 = TaskCreate({ title: "Phase 8: Final commit + push", status: "todo", blocked_by: [t7b.id] })
t85 = TaskCreate({ title: "Phase 8.5: Self-knowledge + brag sheet capture + push", status: "todo", blocked_by: [t8.id] })
t9  = TaskCreate({ title: "Phase 9: Dashboard + review pipeline", status: "todo", blocked_by: [t85.id] })
```

**Before starting each phase**: `TaskUpdate(taskId, { status: "in_progress" })`
**After completing each phase**: `TaskUpdate(taskId, { status: "completed" })`

Never skip this. The task list is the user's primary window into sweep progress.

### Per-day task checklist

When starting each day in Phase 6, create a sub-task with `blocked_by: [t6.id]` and these steps:

- [ ] Read daily note
- [ ] Classify all sections (confident / uncertain / skip / personal-in-work)
- [ ] Route all uncertain sections (one AskUserQuestion per uncertain section)
- [ ] Present final routing plan and confirm
- [ ] Execute: move all sections, create new plans/meetings if needed
- [ ] Verify source note has only completed tasks + kept content remaining
- [ ] Checkpoint commit + push

Mark each sub-task `in_progress` before starting, `completed` when done.

---

## Phase 0: CLI Prerequisites Check

**Run before anything else.** The sweep uses `noteplan-sweep` for all mechanical operations. If it's missing or missing its optional deps, the skill cannot proceed.

### Check 1: Is noteplan-sweep in PATH?

```bash
which noteplan-sweep
```

**If missing:** The CLI needs to be linked from the plugin bin directory.

```bash
# Find where it lives
MARKETPLACE="$HOME/workspace/oeid-claude-plugin-marketplace"
ls "$MARKETPLACE/plugins/noteplan-manager/bin/noteplan-sweep"

# Link it (or add to PATH in your shell profile)
ln -sf "$MARKETPLACE/plugins/noteplan-manager/bin/noteplan-sweep" /usr/local/bin/noteplan-sweep
```

If the link fails or the file doesn't exist, stop and report — sweep cannot run without the CLI.

### Check 2: Is the venv set up? (needed for --use-chrome / Playwright)

```bash
BIN_DIR="$HOME/workspace/oeid-claude-plugin-marketplace/plugins/noteplan-manager/bin"
test -d "$BIN_DIR/.venv" && echo "venv ok" || echo "venv missing"
```

**If venv is missing:** Run setup automatically — this is a one-time install and takes ~30s:

```bash
bash "$BIN_DIR/setup.sh"
```

Setup installs `playwright` + Chromium into the venv. The CLI re-execs with the venv Python transparently — no manual activation needed.

If setup fails, warn the user but continue — the sweep can still run without Playwright (Chrome-based link enrichment will be unavailable).

### Check 3: Quick smoke test

```bash
noteplan-sweep --version
```

If this returns a version string, the CLI is ready. Mark Phase 0 complete and proceed to Phase 1.

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
| Both | Past 3 months | Mon–Sun | All three of the above | 90 days | Per day-of-week | Fri for weekdays, Sun for weekends |

**Both mode**: build work, personal, AND EarlBear plan indexes in Phase 3. For each daily note in Phase 6, apply the correct index and target based on the note's day-of-week (Mon–Fri → work rules; Sat–Sun → personal rules). **EarlBear content can appear on any day** — detect it by `👥` emoji, "EarlBear" keyword, or `[[👥...]]` wikilinks, and route to the **personal target** (next Sunday).

**EarlBear domain** (`👥`): a side business initiative indexed alongside work and personal. Plans live in `👥 EarlBear/📆 Plans/` with workstream subdirs (same structure as work). Naming convention: `👥YYMMDD{workstream} Title.md`, frontmatter `namespace: 👥`. EarlBear content routes to the personal target note (next Sunday) since it's a side project. **Future expansion note**: when EarlBear volume grows, consider adding `👥📋 Lists/`, `👥👤 Meetings/`, and potentially its own target day.

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

## Phase 2: Pre-Sweep Git Pull + Commit — HARD MUST

**Non-negotiable. Do not proceed if this fails.**

First, pull any remote changes:

```bash
cd "$NOTEPLAN_ROOT"
git pull
```

If the pull fails (conflicts, no remote, etc.), **stop and report** — do not proceed until resolved.

Then commit any local uncommitted changes:

```bash
git status
```

If there are any uncommitted changes:

```bash
git add -A
git commit -m "Pre-sweep snapshot ($(date +%Y-%m-%d))"
git push   # push snapshot so remote is up to date before sweep begins
```

If the commit fails, **stop and report**. Confirm the tree is clean before continuing.

---

## Phase 3: Build Plan Index + Lists Index

### Context window hygiene — CRITICAL

**Never read full plan bodies into context.** Extract only:
- For index building: first 15 lines of each file (frontmatter + H1)
- For description inference: first 20 lines (frontmatter + H1 + opening body lines)
- Process one daily note at a time during the sweep — discard after processing

```bash
# Discover plan roots + workstream dirs dynamically — never hardcode paths
noteplan-sweep list-workstreams --mode work      # → work PLAN_ROOT + workstream subdirs
noteplan-sweep list-workstreams --mode personal  # → personal PLAN_ROOT + activity subdirs

LOOKBACK_DAYS=60   # 60 for work, 90 for personal

# Then scan: find "$PLAN_ROOT" -name "*.md" -mtime -${LOOKBACK_DAYS} | sort
# Extract only frontmatter + H1 per plan
head -15 "$plan_file"
```

`list-workstreams` output gives both the PLAN_ROOT and each `[emoji] Name` subdir — use this to build the plan index without hardcoding any directory names.

For each plan file:
1. Parse frontmatter between `---` delimiters
2. Extract `status` — skip 🔴 and 🏁; include 🟢, 🟡, unset
3. Extract `workstream` (work) or `plantype` (personal) — the emoji category
4. Extract `description` if present (may be absent → `description_missing: true`)
5. Extract display name from `# H1`; preserve exact filename stem for wikilinks
6. Extract `contributors` if present in frontmatter — used as a routing signal (see Step 6b)
7. Extract `project` from the file's path — if the plan lives in a **project subfolder** (e.g. `🧑🏻‍💻 Development/🤖 Config Agent/`), record the project subfolder name. Project subfolders are subdirectories within a workstream dir that group related plans. Plans in project subfolders use the **project emoji** in their filename (e.g. `🏢260302🤖 Title.md`) instead of the parent workstream emoji.

Build a compact plan index (metadata only, no content):

```
[
  {
    "filename_stem": "🏢260302🤖 POC Establishing A2A Poc",
    "path": "/full/path/to/file.md",
    "workstream_or_plantype": "🧑🏻‍💻",
    "project": "🤖 Config Agent",          // optional — set when plan is in a project subfolder
    "status": "🟢",
    "description": "...",
    "description_missing": true/false,
    "contributors": ["Dennis", "Arish"]   // optional
  }
]
```

### People Index (persisted in `References[People].md` per namespace)

**Storage:** The People Index is persisted across sessions in dedicated reference files — one per namespace:
- Work: `$NOTES_ROOT/🏢 ServiceNow/📋 Lists/🏢📋 References[People].md`
- EarlBear: `$NOTES_ROOT/👥 EarlBear/📋 Lists/👥📋 References[People].md` *(create dir if absent)*
- NaqshCoffee: `$NOTES_ROOT/☕️ NaqshCoffee/📋 Lists/☕️📋 References[People].md` *(create dir if absent)*
- Personal: omitted for now (personal contacts don't typically have plan associations)

**At Phase 3 start:** Read the existing file(s) to pre-load the People Index. Then enrich it by scanning `contributors:` frontmatter across all plans (inverting the map). Merge both sources — the file is authoritative for domain (work/EarlBear/personal), plan frontmatter is authoritative for which plans a person is on.

**At Phase 8 (final commit):** Write the merged, updated People Index back to the file(s) and include in the final commit. Format:
```markdown
---
doctype: 📋
namespace: 🏢
description: People I collaborate with and the initiatives they're associated with
---
# 🏢📋 References[People]

## Arish
- Domain: 🏢 ServiceNow
- Plans: [[🏢260302🤖 POC Establishing A2A Poc]], [[🏢260129💡 Assisting esgenius]]

## Dennis
- Domain: 🏢 ServiceNow
- Plans: [[🏢260220⚗️ Building an ATF Creation POC]]
```

**Use this information when organizing:** When restructuring sections in daily notes or plan files (e.g. deciding sub-headers, grouping tasks), consult the People Index to understand which initiative a collaborator's name implies. A task mentioning "Arish" near A2A content is more likely about the A2A POC than esgenius.

After building the plan index, construct a **People Index** by inverting every `contributors` list:

```python
people_index = {}  # person_name (lowercase) → list of plan entries

for plan in plan_index:
    for name in plan.get("contributors", []):
        key = name.lower()
        if key not in people_index:
            people_index[key] = []
        people_index[key].append({
            "name": name,
            "plan": plan["filename_stem"],
            "workstream": plan["workstream_or_plantype"],
            "namespace": plan.get("namespace", "🏢"),
            "description": plan.get("description", "")
        })
```

Report the result: `"People index built: {N} people across {M} plans."` List each person with their associated plan(s) so the user can see the full map at a glance.

**New person detection (during Phase 6 routing):** When a section mentions a person's name (via `I owe {Name}`, `{Name} /`, `Sync with {Name}`, `- [ ] {Name}`, or a section header containing a name) and that name is NOT in the People Index, ask before routing:

```javascript
AskUserQuestion({
  questions: [{
    question: `"{Name}" is a new person — what domain do they work with you on?`,
    header: `New person: ${name}`,
    options: [
      { label: "ServiceNow (work)", description: "Route content to a work plan" },
      { label: "EarlBear (side business)", description: "Route content to EarlBear plans" },
      { label: "Personal friend / family", description: "Route to personal staging note" },
      { label: "Other / skip", description: "Leave unrouted for now" }
    ],
    multiSelect: false
  }]
})
```

After the user answers, add the person to the appropriate plan's `contributors:` frontmatter (if they select a specific plan during routing) and **update the People Index in-memory** for the rest of the session. This prevents asking about the same person twice in one session.

### Lists Index (extend the plan index with reference list files)

Also index recently-modified **list files** from the Lists directories alongside plans:
- Work: `$NOTES_ROOT/🏢 ServiceNow/📋 Lists/`
- Personal: `$NOTES_ROOT/🏡 Personal/🏡📋 Lists/`

```bash
LIST_ROOT_WORK="$NOTES_ROOT/🏢 ServiceNow/📋 Lists"
LIST_ROOT_PERSONAL="$NOTES_ROOT/🏡 Personal/🏡📋 Lists"

find "$LIST_ROOT" -name "*.md" -mtime -${LOOKBACK_DAYS} | sort
```

For each list file, infer a one-sentence description from the H1 + first 3–5 non-empty body lines. Add to the index with `"type": "list"` (vs `"type": "plan"` for plans). Lists are presented as routing options in Step 6c alongside plans — useful for reference URLs, research notes, and backlog items.

### Meetings Index (extend the plan index with meeting note files)

Also index **meeting note files** from the Meetings directories:
- Work: `$NOTES_ROOT/🏢 ServiceNow/👤 Meetings/` (recursively — includes `1-1s/`, `Workshops/`, root-level meetings)

```bash
MEETINGS_ROOT_WORK="$NOTES_ROOT/🏢 ServiceNow/👤 Meetings"

find "$MEETINGS_ROOT_WORK" -name "*.md" -mtime -${LOOKBACK_DAYS} | sort
```

For each meeting file, extract the H1 + date from the filename. Add to the index with `"type": "meeting"`. Meeting files are **strongly preferred** for routing when:
- The section header contains a person's name that matches a meeting file (e.g. `# Dennis 1-1` → search for files with "Dennis" in the name under `1-1s/`)
- The section content looks like raw meeting notes (bulleted talking points, no clear task structure, names present)
- The section's first line contains a date or a name + activity keyword ("sync", "1-1", "catch up", "meeting", "chat")

When a meeting file match is found, route to the **actual meeting file** (append under a `## YYYY-MM-DD Notes` date header) rather than the target daily note.

### Thoughts Index (extend routing options with personal Ideas and Reflections files)

Also index **Ideas files** from the personal Thoughts directory:
- Personal: `$NOTES_ROOT/🏡 Personal/🏡💭 Thoughts/💡 Ideas/`

```bash
THOUGHTS_IDEAS_ROOT="$NOTES_ROOT/🏡 Personal/🏡💭 Thoughts/💡 Ideas"
find "$THOUGHTS_IDEAS_ROOT" -name "*.md" | sort
```

For each file, extract H1 + first 3–5 non-empty body lines. Add to the index with `"type": "thought"`. Thoughts files are presented as routing options when:
- A section looks like a raw idea, braindump, or speculative thinking (no clear task structure, hypothetical language, product/startup concepts)
- A section's content matches a recurring topic (AI, entrepreneurship, personal projects) without fitting a concrete plan

The **self-knowledge reflection files** (`Observations.md`, `Gaps.md`, `Superpowers.md`) in `🪞 Reflections/🏡💭💻 GenAI Thoughts/` are NOT routing targets — they are written by the sweep assistant itself in Phase 8.5.

### Threads Index (extend routing options with evolving open questions / theses)

**The canonical home for open questions and theses the user develops over time is `🏡💭 Thoughts/🧵 Threads/`** — one note per evolving question (e.g. "Will ServiceNow Lay Folks Off?"). A *thread* differs from a one-shot *idea*: a thread accumulates evidence, links, and dated reflection across many sweeps; an idea is a single capture. Always index Threads so the user knows where their developing thoughts live and they're a routing target.

```bash
THREADS_ROOT="$NOTES_ROOT/🏡 Personal/🏡💭 Thoughts/🧵 Threads"   # create on first use if absent
find "$THREADS_ROOT" -name "*.md" 2>/dev/null | sort
```

For each thread file, extract H1 (the question) + frontmatter (`status: open|resolved`, `started`). Add to the index with `"type": "thread"`. A thread note's structure:

```markdown
---
doctype: 💭
status: open
started: {first-thought date YYYY-MM-DD}
namespace: 🏡
description: {the open question in one line}
---
# 🏡💭 {The Question?}

{one-line framing — "An evolving thread tracking ..."}

## {YYYY-MM-DD}   ← the SOURCE calendar date the thinking occurred (provenance)
- {captured lines, verbatim}
```

**Provenance is the point** — every addition is stamped with the **source calendar date** under its own `## YYYY-MM-DD` heading, so "when did I first / last think this?" is always answerable. First-thought date = the `started:` frontmatter; each sweep appends a new dated entry rather than overwriting.

### Research Index (extend routing options with research docs and deep dives)

Also index **research documents** from the Research directories and the Deep Dives workstream:
- Work research: `$NOTES_ROOT/🏢 ServiceNow/🔬 Research/`
- Work deep dives (concluded research): `$NOTES_ROOT/🏢 ServiceNow/📆 Plans/🤿 Deep Dives/`
- Personal research: `$NOTES_ROOT/🏡 Personal/🏡🔬 Research/` — **create this directory if it does not exist**

```bash
RESEARCH_ROOT_WORK="$NOTES_ROOT/🏢 ServiceNow/🔬 Research"
DEEP_DIVES_ROOT_WORK="$NOTES_ROOT/🏢 ServiceNow/📆 Plans/🤿 Deep Dives"
RESEARCH_ROOT_PERSONAL="$NOTES_ROOT/🏡 Personal/🏡🔬 Research"

find "$RESEARCH_ROOT_WORK" "$DEEP_DIVES_ROOT_WORK" "$RESEARCH_ROOT_PERSONAL" -name "*.md" 2>/dev/null | sort
```

For each research file, extract H1 + frontmatter (especially `description` and `domains`). Add to the index with `"type": "research"`. Deep dive plans have `"subtype": "deep_dive"` and a `status` field — completed deep dives (`🏁`) are shown as a historical reference, not a primary routing target.

Research index entry shape:
```json
{
  "filename_stem": "🔬 Researching Docs for Graph Building",
  "path": "/full/path.md",
  "type": "research",
  "subtype": "note",          // "note" | "deep_dive"
  "namespace": "🏢",
  "status": "🟢",
  "description": "...",
  "domains": ["code.devsnc.com", "servicenow.com/docs"],
  "description_missing": false
}
```

**Domain scoring**: `domains` extracted from frontmatter are used as routing signals in Step 6b/6c — a section containing a URL whose domain appears in a research doc's `domains` list scores **+4** toward that research doc.

### EarlBear Index (always indexed alongside work + personal)

Also index **EarlBear plan files** from the EarlBear plans directory:
- EarlBear: `$NOTES_ROOT/👥 EarlBear/📆 Plans/`

```bash
EARLBEAR_PLAN_ROOT="$NOTES_ROOT/👥 EarlBear/📆 Plans"
EARLBEAR_MEETINGS_ROOT="$NOTES_ROOT/👥 EarlBear/👥👤 Meetings"
NAQSH_PLAN_ROOT="$NOTES_ROOT/☕️ NaqshCoffee/📆 Plans"
NAQSH_MEETINGS_ROOT="$NOTES_ROOT/☕️ NaqshCoffee/☕️👤 Meetings"

find "$NAQSH_PLAN_ROOT" -name "*.md" -mtime -${LOOKBACK_DAYS} 2>/dev/null | sort
find "$NAQSH_MEETINGS_ROOT" -name "*.md" -mtime -${LOOKBACK_DAYS} 2>/dev/null | sort

find "$EARLBEAR_PLAN_ROOT" -name "*.md" -mtime -${LOOKBACK_DAYS} 2>/dev/null | sort
find "$EARLBEAR_MEETINGS_ROOT" -name "*.md" -mtime -${LOOKBACK_DAYS} 2>/dev/null | sort
```

For each EarlBear plan file, extract frontmatter + H1 (same as work plans). Add to the index with `"namespace": "👥"`. EarlBear plans use the same workstream subdir pattern as work plans — discover subdirs dynamically. EarlBear meeting files use `"type": "meeting"` with `"namespace": "👥"` — route EarlBear meeting content to `👥👤 Meetings/`, not `📆 Plans/`.

EarlBear index entry shape:
```json
{
  "filename_stem": "👥260326🧑🏻‍💻 Auto Deck Generation",
  "path": "/full/path.md",
  "type": "plan",
  "namespace": "👥",
  "workstream_or_plantype": "🧑🏻‍💻",
  "status": "🟢",
  "description": "...",
  "description_missing": false
}
```

**EarlBear detection signals** for routing (used in Step 6b):
- Section header contains "EarlBear" or "Earl Bear" (case-insensitive)
- Section content contains `[[👥...]]` wikilink
- `👥` emoji in section header or content
- Section mentions "Saad" (EarlBear co-founder) without matching a work meeting

**NaqshCoffee domain** (`☕️`): a creative business initiative (coffee brand + Islamic design/Bikar). Plans live in `☕️ NaqshCoffee/📆 Plans/` with workstream subdirs (same structure as EarlBear). Naming convention: `☕️YYMMDD{workstream} Title.md`, frontmatter `namespace: ☕️`. NaqshCoffee content routes to the personal target note (next Sunday) alongside EarlBear content.

**NaqshCoffee detection signals** (used in Step 6b):
- Section header contains "NaqshCoffee", "Naqsh", "Bikar", or "Coffee House" (case-insensitive)
- Section content contains `[[☕️...]]` wikilink
- `☕️` emoji in section header or content
- Section mentions Islamic design, geometric patterns, or Arabic coffee brand names

Report: "Found N recently-touched plans + M list files + K meeting files + J thought files + R research docs + E EarlBear plans — People index: P people across Q plans." List all with descriptions, then list the People Index grouped by person.

---

## Phase 4: Enrich Plans + Research Docs Missing Descriptions + Filename/Title Consistency Check

### Filename/Title Consistency Check (run alongside description enrichment)

While processing plans for missing descriptions, also check for H1/filename mismatches and fix them:

1. **For each plan**, compare `filename_stem` against the H1 heading
2. **Rename file → match H1** when the filename is a plain/untitled string (no `🏢YYMMDD` or `🏡YYMMDD` prefix) but the H1 has a proper convention
3. **Fix H1 → match filename** when the filename has proper convention but H1 differs (e.g. different emoji, extra " 2" suffix, or alternate wording) — this is safer because filenames are the canonical wikilink reference
4. **Flag as ambiguous** (don't auto-fix) when: neither has proper convention, the mismatch is a trailing `?`, it's a date-format filename (`YYYY-MM-DD ...`), or the name difference is significant enough to need human judgment
5. **Commit all fixes** together with the description enrichment in a single `chore(plans): add description frontmatter …; fix N H1 titles and M filenames` commit

**Never silently drop `?` from a filename H1 without noting it.** Report ambiguous cases to the user after the commit so they can run `/noteplan-manager:manage-filenames` for a deeper pass.

### Contributors Enrichment (run alongside descriptions)

While reading plan bodies for description inference, also scan for contributor names:

1. Look for **people's names** appearing as:
   - `- [ ] Sync with {Name}`, `- [ ] Meet with {Name}`, `- [ ] Ask {Name}`
   - `{Name} / ` prefix at the start of a bullet
   - `@mention` style references
2. Collect distinct first names or handles found across the first 20 lines
3. If any contributors found and the plan's frontmatter has no `contributors:` field, add it:
   ```yaml
   contributors: ["Dennis", "Arish"]
   ```
4. Contributors are a strong routing signal in Step 6b — if a daily note section mentions a name that appears as a contributor in a plan, that's a `✅ Confident` match signal.

Include contributor additions in the same bulk commit as descriptions. Do not prompt separately unless the user asks.

---

### Research Doc Enrichment (run alongside plan enrichment)

Use `noteplan-sweep enrich-research-doc` to extract domains and infer descriptions for research docs in one shot:

```bash
# Enrich a research doc: extract URL domains → update domains: frontmatter, infer description if missing
noteplan-sweep enrich-research-doc "$RESEARCH_DOC_PATH"
```

This command:
1. Scans the full body for all URLs, extracts unique hostnames, merges into `domains:` frontmatter
2. Infers a `description:` if absent (from H1 + first paragraph + domain list)
3. Rewrites frontmatter in-place using `---` (three dashes) delimiters

Run for every research doc in the research index that has `description_missing: true` or whose `domains:` list is empty. Include in the same bulk commit as plan descriptions: `chore(plans/research): add descriptions + domains to N files`

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

**Pre-parse: strip separator headers.** Before scanning for sweepable sections, detect headers that are visual separators rather than real section names. These include: `# ---`, `# ===`, `# ___`, `# ***`, `# ------`, or any `#` followed only by punctuation/whitespace. When found, **remove the separator header** and treat the lines below it as continuation of the previous section (or as top-level orphan tasks if no prior section exists). Report stripped separators in the announcement:
```
⚠️ Stripped {n} separator header(s): "# ---" at line {L} — content treated as orphan tasks
```

**Pre-parse: split orphan mixed-domain tasks.** When top-level tasks (no section header) exist and contain items from clearly different domains (e.g. a work MCP task + a personal home repair task), split them into separate synthetic blocks before classification. Use domain signals: personal keywords (home, family, shopping, errands, spigot, vacuum), work keywords (ServiceNow, MCP, POC, meeting), wikilinks. Each synthetic block is classified independently.

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
0. Section contains one or more **interpersonal "I owe / owe [person]"** style lines (e.g. `- [ ] I owe Anna the ARB doc`, `- [ ] i Owe Jeff goals`, `- [ ] Reply to Shikar`, `- [ ] Send Anna responses`) → `🔴 High-priority IOU` — route to the **next business day note** (not a plan file, not the weekly target). These are interpersonal commitments that need immediate visibility. **Per the no-regex tenet at the top of this skill: YOU read each line and decide whether it is an IOU, considering wording, context, and who's owed what.** Do not delegate this decision to a regex in any helper script. Pass the resulting line numbers explicitly as `iou_lines: [...]` in the move spec — the executor uses that list to append the source-date tag, but never re-derives IOU intent. Each IOU group gets its own breadcrumb row with destination `[[{NEXT_BUSINESS_DAY}]] Unsorted`. Next business day is today if it's Mon–Fri before end of day, otherwise the next Monday (or next working day skipping weekends).
1. Section content contains `[[PlanName]]` wikilink matching a plan in the index → `✅ Confident`
2. Section header text closely matches a plan name → `✅ Confident`
3. Section's workstream emoji matches a single plan's workstream → `✅ Confident`
4. Section mentions a person's name found in the **People Index** — this is a **scoring hint, not a direct route**. Use it to boost the score of every plan that person is associated with. If the person maps to exactly one plan and no other signals conflict → `✅ Confident`. If the person maps to 2+ plans, add their plans to the top-5 candidate list weighted by the person's presence, then let other signals (wikilinks, emoji, content keywords) break the tie → `❓ Uncertain` with their plans surfaced first. **Never route solely by person name if they appear in multiple plans.**
   - Example: "Arish" → boosts both `POC Establishing A2A Poc` and `Assisting esgenius`; wikilink or workstream emoji resolves which one.
   - Example: "Dennis" → boosts `Building an ATF Creation POC` (only plan he's on) → `✅ Confident` if no conflicts.
5. Section header contains meeting keywords ("Meeting Notes", "1-1", "Sync", "Catch Up", "Chat with", "Workshop") OR a person's name matching a meeting file in the index → `👤 Meeting candidate` — present meeting routing UI. When presenting, also show that person's plans from the People Index as context ("Dennis works on: ATF Creation POC").
6. Section header contains "References" or "References:" → `📋 Reference candidate` — present list/reference routing UI
7. Section header or content contains EarlBear signals ("EarlBear", "Earl Bear", `👥` emoji, `[[👥...]]` wikilink, "Saad" without a work meeting match) → route to EarlBear plan index; if no match, `❓ Uncertain` with EarlBear plans surfaced first
8. Section matches **2+ research signals** (see below) → `🔬 Research candidate` — present research routing UI instead of plan routing
9. Section contains a **voice note block** (see below) → `🎤 Voice note` — run voice note processing before routing
9b. Section reads as an **open question / thesis the user is developing** (interrogative framing — "will X happen", "should I…?", "what are the leading indicators of…"; speculative-but-recurring; tracks an evolving belief rather than proposing a concrete task) → `🧵 Thread candidate` — route to a matching existing thread in `🧵 Threads/`, or offer to create one. This is distinct from a one-shot `💡 Idea`: a thread is something the user will keep adding to over time. When routing, append the lines under a dated `## {source-date}` heading in the thread note (provenance).
10. Clearly personal content (shopping, errands, `[[🏡...]]` wikilinks in work mode) → `⏭️ Skip` (but see **Personal in Both mode** below)
11. Completed-task-only block → `⏭️ Skip` by default, but see **Completed task routing** below
12. Anything else → `❓ Uncertain`

**Research candidate signals** (classify `🔬` when 2+ apply):

| Signal | Example |
|---|---|
| Section header contains: Research, Deep Dive, Investigating, Exploring, Landscape, Survey, Notes on, Background, Docs for, Overview | `# Researching Docs for Graph Building` |
| 3+ URLs present, concentrated on 1–2 domains | 10 `code.devsnc.com` + `servicenow.com` links |
| Zero `- [ ]` tasks — prose and/or links only | No tasks in section |
| Investigative language: "What does X mean", "context for", "overview of", "how does X work", "important context" | `"What does product mean ..."` |
| Section content domain overlaps with an existing research doc's `domains:` frontmatter | URL from `fluidtopics.com` → matches existing research doc |
| Conclusion language: "decided to use", "conclusion:", "final approach:", "we will use X" | → flag as **concluded** → prefer Deep Dive destination |

**Voice note signals** (classify `🎤` when 2+ apply):

| Signal | Example |
|---|---|
| A single task/line >200 chars with <3 sentence boundaries | `- [ ] there's some more cloth artifact POC's. I need to do one thought is that Claude artifacts.of they call an MCP...` (500+ chars, stream of consciousness) |
| `￼` object replacement character (U+FFFC) | Voice dictation artifact from iOS/macOS |
| Phonetic misspellings of technical terms | "Jason" → JSON, "bite stream" → byte stream, "cloth" → Claude, "Ayham" → I am, "bases 64" → base64 |
| Filler phrases: "you know", "I don't know", "like" used as connectors | "but you know they're gonna expect" |
| Missing/inconsistent punctuation with run-on connectors | "and and", "so if we had an MCP that like vendor" |
| All lowercase or inconsistent capitalization patterns | Voice transcription default |

**Voice note processing pipeline** (run BEFORE routing):

1. **Detect**: Flag lines/blocks matching 2+ voice note signals
2. **Break into thoughts**: Split the stream-of-consciousness into logical sentences/ideas using context clues (topic shifts, "the other thought is", "so if we", "one thought is")
3. **Fix voice-to-text errors**: Apply phonetic→technical corrections. Common mappings:
   - `Jason` → `JSON`, `Ayham` → `I am`, `bite` → `byte`, `cloth` → `Claude`
   - `bases 64` / `base 64` → `base64`, `vender`/`vendor` (in tech context) → `render`
   - `we bet` → `we'd`, `gonna` → `going to`
   - Strip filler: "you know", "like" (as filler, not comparison), "I don't know"
   - Remove `￼` object replacement characters
4. **Structure**: Convert into tasks (`- [ ]`) or bullets (`-`) based on intent:
   - Actionable items → `- [ ]`
   - Ideas/questions → `-` with `?` suffix
   - Multi-part thoughts → nested bullets
5. **Present before/after** for confirmation:

```javascript
AskUserQuestion({
  questions: [{
    question: `🎤 Voice note detected in "${sectionHeader}":\n\n**Raw transcription:**\n\`\`\`\n${rawText.substring(0, 300)}...\n\`\`\`\n\n**Cleaned + structured:**\n\`\`\`\n${cleanedText}\n\`\`\`\n\nUse the cleaned version for routing?`,
    header: `Voice note: "${sectionHeader}"`,
    options: [
      { label: "Use cleaned version", description: "Route the structured text instead of the raw transcription" },
      { label: "Keep raw", description: "Route the original transcription as-is" },
      { label: "⏭️ Skip", description: "Leave this section in the source note" }
    ],
    multiSelect: false
  }]
})
```

6. **Route**: After confirmation, the cleaned (or raw) content proceeds to normal classification and routing. The voice note processing is a **pre-routing transformation**, not a routing decision itself.

**Important**: Voice note cleaning is the ONE exception to the "no content changes" rule. The user explicitly confirms the transformation via AskUserQuestion. The raw transcription is preserved in the swept breadcrumb table's Summary column for traceability.

**Cross-day consolidation**: While classifying sections across multiple days, track research candidates in a topic map keyed by dominant domain/keyword cluster (e.g., `servicenow-docs`, `a2a-protocol`, `eval-frameworks`). When two candidates from different days share a cluster, flag them as **consolidation candidates** and present them together during routing:
```
🔬 Consolidation candidate: 3 research blocks across 2026-03-19/20/25 all relate to "ServiceNow docs / graph building"
Route all to one research doc?
```

**Completed task routing:** Completed `[x]` blocks are historical record and normally stay in source. However, when an entire section is `[x]`-only AND there is a confident plan match, offer to move them to a `## Done` or `## Completed` section in the matched plan file. Present this as an optional action at the end of the day's routing plan — never auto-move completed tasks without confirmation.

**Personal in Both mode:** When processing work-day notes (Mon–Fri) in **Both** mode, sections that are clearly personal side projects (apps, personal repos, personal names unrelated to work) should not be silently skipped. Instead:
- Flag them as `⏭️ personal side project (work note)`
- At the end of day classification, present a single bulk question: "These sections appear to be personal content in a work-day note — route to personal target (20XXXXXX.md), Unsorted in work target, or skip?"
- Apply the user's bulk answer to all personal-in-work sections for that day

**For sections that seem substantial** (more than 3 lines, contain tasks, describe a distinct topic), also flag as "could be new plan."

**Sections may be split by line** when individual items within a section reference different plans (e.g. a `# POCs` block with two different `[[PlanName]]` wikilinks). Split these and classify each line individually.

**Same-plan entries are merged in the target** — multiple sections routing to the same plan get merged under one `# [[PlanName]]` header.

**Raw link classification:** When a section or line contains raw URLs (not inside a task or prose), inspect the URL domain and path to inform routing:

| URL pattern | Signal | Suggested routing |
|---|---|---|
| `*.service-now.com`, `*.servicenow.com` | ServiceNow instance/docs | Match to the relevant work plan (MCP, A2A, esgenius, etc.) by inspecting the path (`/sys_script_include`, `/rm_story`, `/atf`, etc.) |
| `docs.google.com`, `icloud.com/notes` | External reference/doc | Route with the parent task, or to the relevant `📋 Lists/References[...]` file if it's a standalone reference |
| `github.com`, `code.devsnc.com` | Repo/code reference | Route with parent task or to the relevant plan's reference section |
| `youtube.com`, `learning.*` | Learning resource | Route to plan OR to `📋 Lists/References[Playlist - ...]` if standalone |
| `calendly.com`, `*.zoom.us` | Scheduling link | Route with the meeting/1-1 content |
| `claude.ai/chat/*`, `claude.ai/artifacts/*` | Claude session/artifact | Route with the parent task — these are working context |
| Personal/shopping URLs (amazon, facebook marketplace, redfin) | Personal reference | Route to personal target or skip |

For standalone raw links (not under any task), classify them as `❓ Uncertain` and present them to the user with the inspected domain as context. Standalone ServiceNow links are especially valuable — they often represent instance configurations, scripts, or documentation worth preserving in a plan or reference list.

Announce the classification before routing:

```
📅 {fileDate} — {n} sweepable section(s):
  ✅ {k} confident match(es) — will auto-route
  👥 {e} EarlBear match(es) — will route to EarlBear plans / personal target
  👤 {p} meeting candidate(s) — will ask to route to meeting file
  📋 {q} reference candidate(s) — will ask to route to list file
  🔬 {r} research candidate(s) — will ask to route to research doc or deep dive
  🎤 {v} voice note(s) — will clean + confirm before routing
  ❓ {m} uncertain section(s) — will ask individually
  ⏭️  {j} skip(s) — personal/completed
```

### Step 6c — Route uncertain sections one at a time

**For every `❓ Uncertain` section, ask individually with AskUserQuestion — one question per section, no bulk prompts.**

#### Scoring: top-5 plan suggestions

Before presenting the routing question, score every plan in the index against the section's content and header. Use the following signals (additive):

**Scoring applies to plans, lists, meetings, and research docs** — all are scored together. Additional signals for research docs:

| Signal | Score |
|---|---|
| Section content contains `[[filename_stem]]` exact wikilink match | +10 |
| Section header text contains a word from the plan/research filename stem (case-insensitive) | +5 |
| Section content contains a word from the plan/research filename stem (case-insensitive, ≥ 4 chars) | +3 |
| Plan's workstream/plantype emoji appears in section header or content | +2 |
| Plan/research doc has `status: 🟢` (active) | +1 |
| Section URL domain matches a research doc's `domains:` frontmatter entry | +4 per matching domain |
| Research doc keyword appears in section header (Research, Deep Dive, Investigating, etc.) | +3 |

Select the **top 5 results** across all index types by score (break ties by recency). Always append the fixed options below.

**For `🔬 Research candidate` sections**, use a dedicated routing question that surfaces research destinations first:

```javascript
AskUserQuestion({
  questions: [{
    question: `Research section "${sectionHeader}" from ${fileDate}:\n\n${sectionPreview}\n\nSuggested destinations (scored by domain + keyword match):`,
    header: `Route research: "${sectionHeader}" (${currentIndex}/${totalResearch})`,
    options: [
      // Top 3 research docs / deep dives from research index (domain-scored):
      ...top3Research.map((r, i) => ({
        label: `[[${r.filename_stem}]]`,
        description: `#${i+1} · ${r.subtype === 'deep_dive' ? '🤿 Deep Dive (concluded)' : '🔬 Research'} · ${r.description ?? '(no description)'}`
      })),
      { label: "🔬 New Research note", description: `Create 🔬 {Title}.md in 🔬 Research/ — ongoing investigation, reference material` },
      { label: "🤿 New Deep Dive plan", description: `Create 🏢{YYMMDD}🤿 {Title}.md — concluded research, decision reached` },
      { label: "📥 Unsorted", description: "Place under # Unsorted in the target note" },
      { label: "⏭️ Skip — leave it here", description: "Don't move this section" }
    ],
    multiSelect: false
  }]
})
```

**For `👤 Meeting candidate` sections**, use a dedicated meeting routing UI:

```javascript
AskUserQuestion({
  questions: [{
    question: `Meeting section "${sectionHeader}" from ${fileDate}:\n\n${sectionPreview}\n\nSuggested destinations:`,
    header: `Route meeting: "${sectionHeader}" (${currentIndex}/${totalMeetings})`,
    options: [
      // Top 3 meeting files matching person name / event name:
      ...top3Meetings.map((m, i) => ({
        label: `[[${m.filename_stem}]]`,
        description: `#${i+1} · 👤 Meeting · ${m.description ?? '(no description)'}`
      })),
      { label: "👤 New Meeting note", description: `Create 🏢 {YYMMDD} {Title}.md in 👤 Meetings/` },
      { label: "📥 Unsorted", description: "Place under # Unsorted in the target note" },
      { label: "⏭️ Skip — leave it here", description: "Don't move this section" }
    ],
    multiSelect: false
  }]
})
```

If **"👤 New Meeting note"** is selected → go to **Step 6d: Create New Plan/Research Doc** (meeting path — use `🏢📝 Work Meeting Notes.md` template), then return to routing.

**For `📋 Reference candidate` sections**, use a dedicated list/reference routing UI:

```javascript
AskUserQuestion({
  questions: [{
    question: `Reference section "${sectionHeader}" from ${fileDate}:\n\n${sectionPreview}\n\nSuggested destinations:`,
    header: `Route reference: "${sectionHeader}" (${currentIndex}/${totalReferences})`,
    options: [
      // Top 3 list files scored by keyword match:
      ...top3Lists.map((l, i) => ({
        label: `[[${l.filename_stem}]]`,
        description: `#${i+1} · 📋 List · ${l.description ?? '(no description)'}`
      })),
      { label: "📋 New List/Reference file", description: `Create 🏢📋 References[{Qualifier}].md in 📋 Lists/` },
      { label: "📥 Unsorted", description: "Place under # Unsorted in the target note" },
      { label: "⏭️ Skip — leave it here", description: "Don't move this section" }
    ],
    multiSelect: false
  }]
})
```

If **"📋 New List/Reference file"** is selected → ask for a qualifier name, then create `🏢📋 References[{Qualifier}].md` (work) or `🏡📋 References[{Qualifier}].md` (personal) in the appropriate Lists directory. Use minimal frontmatter:
```markdown
---
doctype: 📋
namespace: 🏢
---
# 🏢📋 References[{Qualifier}]
```

**For `❓ Uncertain` sections**, use the standard plan routing question with the full top-5 (plans + research + lists mixed by score):

```javascript
AskUserQuestion({
  questions: [{
    question: `Section "${sectionHeader}" from ${fileDate}:\n\n${sectionPreview}\n\nTop suggested destinations (scored by content match):`,
    header: `Route: "${sectionHeader}" (${currentIndex}/${totalUncertain})`,
    options: [
      ...top5.map((p, i) => ({
        label: `[[${p.filename_stem}]]`,
        description: `#${i+1} match · ${p.type === 'research' ? '🔬 ' : ''}${p.description || `(${p.workstream_or_plantype ?? p.type} — no description)`}`
      })),
      { label: "🆕 Create a new plan", description: "This section deserves its own plan file" },
      { label: "👤 New Meeting note", description: "Create a meeting note file" },
      { label: "📋 New List/Reference file", description: "Create a reference list file" },
      { label: "🔬 New Research note", description: "Create a standalone research doc" },
      { label: "📥 Unsorted", description: "Place under # Unsorted in the target note" },
      { label: "⏭️ Skip — leave it here", description: "Don't move this section" }
    ],
    multiSelect: false
  }]
})
```

> **Note:** If none of the top-5 match the user's intent, the user can choose "🆕 Create a new plan/file", "🔬 New Research note", or "📥 Unsorted". The full index is never dumped into the routing UI.

**User notes in AskUserQuestion answers are authoritative context.** When the user provides a free-text note alongside their answer (e.g. "this is billing for Lana's daycare" or "this is part of me understanding servicenow"), treat it as a clarification that should immediately inform your interpretation of the content. If the note suggests a different category or plan than you had scored, re-score the plan index against the user's description and present better-matched options in the next follow-up question. Never ignore user notes.

**Search before asking — resolve ambiguity with web context:** Before presenting a routing question for an uncertain section, if the section contains a URL, person name, or topic you can't confidently identify, **use WebSearch to look it up first**. For example:
- A URL like `dotenvx.com` → WebSearch "dotenvx" → identifies it as a dotenv encryption tool → route to `References[Software]` confidently
- A person's name like "Sebastian Raschka" → WebSearch → identifies as ML/LLM researcher → route to `References[AI]` confidently
- A project name like "cloudhead.io" → WebSearch → identifies as an open-source developer portfolio → route to `References[Software]` confidently

If the search gives a **clear, confident answer** → route it directly without asking the user.
If the search produces **ambiguous or multiple valid routings** → include the search findings in the routing question so the user has full context.

**Capture clarifications in descriptions:** When the user routes a section and explains why (via a user note or direct answer), update that destination's `description:` frontmatter to reflect the new context. This prevents the same ambiguity from arising in future sweeps. For example: if the user says "this belongs in the A2A POC because it's about external agent hookup", update the A2A plan's description to mention external agent hookup if it doesn't already. Write the description update inline when executing the section move — do not defer.

Show a **progress counter** in the header (`1/3`, `2/3`, etc.) so the user knows how many uncertain sections remain.

If **"🆕 Create a new plan"** is selected → go to **Step 6d: Create New Plan/Research Doc**, then return to routing.
If **"👤 New Meeting note"** is selected → go to **Step 6d: Create New Plan/Research Doc** (meeting path), then return to routing.
If **"📋 New List/Reference file"** is selected → ask for qualifier, create the list file, then return to routing.
If **"🔬 New Research note"** or **"🤿 New Deep Dive plan"** is selected → go to **Step 6d: Create New Plan/Research Doc** (research path), then return to routing.

After all uncertain sections are routed, **present the complete day plan** (confident + newly routed).

**HARD MUST — show the line-level diff-view table BEFORE every confirmation AskUserQuestion.** `AskUserQuestion` cannot render a table or a diff, so the user is routing blind unless you print the mapping in the chat message first. Before *any* "Execute / Confirm" question for a day (and before any per-section routing question where it aids clarity), emit a plain-text diff-view table in the chat that shows, for every sweepable line/section: the **source line number(s)**, the **exact content** (verbatim, truncated only if very long), the **→ destination** (`[[wikilink]]` or target-note + section), and any **enrichment/tag** that will be applied. Never ask the user to confirm a move they cannot see. If you catch yourself jumping straight to the confirmation question without having printed this table, stop and print it first.

Diff-view table format (one row per source line/section):

```
### 📅 Diff preview — Calendar/{fileDate}.md

| Src line(s) | Content | → Destination | Tag/enrich |
|---|---|---|---|
| 3–6 | `- [ ] Build AI feature catalog ...` | `[[🏢260302🧑🏻‍💻 ...Agentic AI Landscape]]` | >TARGET |
| 9   | `- [ ] [[🏢...MCP]]` | `[[🏢260302🧑🏻‍💻 POC ...MCP]]` | >TARGET |
| 12  | `https://...` | `[[🏢📋 References[...]]]` | enrich |

Stays: line 14 `[x] ...` (completed) · Skip: `# Shopping` (personal)
```

**CRITICAL — one row per section, one destination per row.** Each section/line must appear on its own row with exactly one destination. Never group multiple sections into a single entry, and never list multiple destinations for one section. If 10 sections are being swept, the table must have 10 rows.

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

### Step 6d — Create New Plan / Research Doc (optional sub-flow)

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
    // Discover live: noteplan-sweep list-workstreams --mode personal
    // Source of truth: ls "$NOTES_ROOT/🏡 Personal/🏡📆 Plans/Present/"
    {
      question: "What kind of plan is this?",
      header: "New plan: plan type",
      options: [
        { label: "📝 Authoring" }, { label: "⚙️ Automating" }, { label: "🏢 Career" },
        { label: "🧰 Craftsmanship" }, { label: "👨🏻‍💻 Development" }, { label: "🔍 Discovering" },
        { label: "👨🏻‍💼 Entrepreneurship" }, { label: "🌱 Growth" }, { label: "🏃🏻 Health" },
        { label: "📚 Learning" }, { label: "🧮 Managing" }, { label: "🗑️ Organizing" },
        { label: "🧎🏻 Spirituality" }, { label: "📊 Tracking" }
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

**Templates location:** `$NOTES_ROOT/@Templates/`
- Work plan: `🏢📆 Work Plan.md`
- Personal plan: `🏡📆 Personal Plan.md`
- Work meeting notes: `🏢📝 Work Meeting Notes.md`

Read the appropriate template before writing any new file — use the template's H1 format and frontmatter fields as reference. **Templates use `--` (two dashes) as their own delimiters**, but **all plan/meeting files you create must use `---` (three dashes)**. Do not copy the `--` delimiter from the template into the new file.

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

# EarlBear plan:
# filename_stem = "👥{YYMMDD}{workstream_emoji} {title}"
# e.g. "👥260313🧑🏻‍💻 Auto Deck Generation"

# Work meeting notes:
# filename_stem = "🏢 {YYMMDD} {title}"
# e.g. "🏢 260313 Dennis 1-1"
```

**Write the new plan file** using the structure below — always `---` (three dashes) for frontmatter delimiters:

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

*EarlBear plan:*
```markdown
---
doctype: 📆
status: {status_emoji}
started: {YYMMDD}
namespace: 👥
workstream: {workstream_emoji}
---
# 👥{YYMMDD}{workstream_emoji} {title}
* [ ] Is [[👥{YYMMDD}{workstream_emoji} {title}]] done? >{YEAR}-W{WW}
* [ ]
```

*Work meeting notes:*
```markdown
---
doctype: 🗒️
started: {YYMMDD}
namespace: 🏢
---
# 🏢 {YYMMDD} {title}
* [ ] Are Action Items for [[🏢 {YYMMDD} {title}]] done? >{YEAR}-W{WW}
```

**Place the file** in the correct subdirectory:
- Work plan: `$PLAN_ROOT/{workstream_dir}/` (match the existing subdir for that workstream emoji)
- Work plan in a project subfolder: `$PLAN_ROOT/{workstream_dir}/{project_dir}/` — when a plan clearly belongs to an existing project subfolder (e.g. `🤖 Config Agent/`, `⚗️ Experiments/`, `💡 esgenius/` under `🧑🏻‍💻 Development/`), place it there and use the **project emoji** in the filename instead of the workstream emoji
- Personal plan: `$PLAN_ROOT/Present/{plantype_dir}/` (match the existing subdir for that plantype emoji)
- EarlBear plan: `$NOTES_ROOT/👥 EarlBear/📆 Plans/{workstream_dir}/` (create subdir if needed)
- EarlBear meeting: `$NOTES_ROOT/👥 EarlBear/👥👤 Meetings/`
- Work meeting: `$NOTES_ROOT/🏢 ServiceNow/👤 Meetings/` (root or `1-1s/` subdir as appropriate)

Discover the correct subdir by listing the directory — never hardcode. When a workstream dir has project subfolders, list those too and present them as placement options when creating a new plan.

**Add to plan/meetings index** so it's available for the rest of the sweep.

Confirm creation to the user: "Created `[[{filename_stem}]]` at `{path}`."

The section's content will be swept into this new plan file directly (not the target daily note) — place it after the `* [ ]` task line in the new plan. This is the one case where content goes to a plan file rather than the target daily note.

#### Research Doc Creation Path

When the user selects **"🔬 New Research note"** or **"🤿 New Deep Dive plan"**:

**Path A — Research note** (ongoing investigation, reference material, not yet concluded):

Ask for a title only — all other fields are auto-inferred:

```javascript
AskUserQuestion({ questions: [{ question: "What is this research about?", header: "New research note: title", freeText: true }] })
```

- Filename: `🔬 {Title}.md` (no date prefix — research docs are evergreen)
- Location: work → `🔬 Research/`; personal → `🏡🔬 Research/` (create dir if absent)
- Auto-extract `domains:` from URL content in the section being routed
- Auto-infer `description:` from H1 + section content summary
- Write with full frontmatter (`---` three dashes):

```markdown
---
doctype: 🔬
status: 🟢
started: {YYMMDD}
namespace: 🏢  // or 🏡
description: {auto-inferred one-sentence summary}
domains:
  - {extracted-domain-1}
  - {extracted-domain-2}
---
# 🔬 {Title}

## References
{content verbatim — URLs and reference material}
```

**Path B — Deep Dive plan** (concluded research, decision reached, goal achieved):

- Filename: `🏢{YYMMDD}🤿 {Title}.md` (work) / `🏡{YYMMDD}🔍 {Title}.md` (personal — use Discovering emoji)
- Location: `Plans/🤿 Deep Dives/` (discover the subdir — never hardcode)
- Use the standard plan template (`🏢📆 Work Plan.md`) with `workstream: 🤿`
- Add `domains:` field to frontmatter (same auto-extraction as research notes)
- Content placed after the `* [ ]` boilerplate line (same as any new plan)

**Appending to an existing research doc** (when user routes to an existing `🔬` entry):
- Classify the content and append under the matching semantic section (`## References`, `## Findings`, `## Next Steps`, etc.) — same rules as plans
- **Also update `domains:` frontmatter**: extract URL domains from the newly appended content, merge (set union) with existing `domains:` list, rewrite frontmatter in-place
- Do NOT rewrite `description:` on append — only set at creation

Add the new research doc to the research index so it's available for the rest of the sweep.

### Step 6e — Execute the confirmed plan

After the user confirms the day's routing plan:

**Use `noteplan-sweep` CLI for ALL file operations from the very first command.** Do not write ad-hoc Python or bash scripts for operations the CLI can handle. The CLI is the canonical tool for this skill — use it from the start, not as a fallback.

If you encounter an operation the CLI cannot perform (a **CLI gap**):
1. Use a minimal custom script to fill the gap — document what you did and why
2. Add an item to the Phase 8.5 task to implement that operation in the CLI before the next sweep
3. Record it in the Gaps section of `🪞 Reflections/🏡💭💻 GenAI Thoughts/Gaps.md`

**CLI gap example from 2026-04-12**: After `move-section` appended content to plan files under `## Unsorted`, it introduced `## From YYYY-MM-DD` provenance sub-headers. A Python script was needed to strip them. This is now a tracked CLI gap — the CLI should support `--no-from-header` or strip them natively.

```bash
# Classify content into a semantic section, then append (no date subheader)
noteplan-sweep create-section "$TARGET_FILE" "## SectionName"   # creates section if absent
noteplan-sweep append-section "$TARGET_FILE" "## SectionName" /tmp/section_content.txt

# Clear the source after all sections are moved
noteplan-sweep clear-source "$SOURCE_NOTE" --keep-completed

# Add a breadcrumb row to the source
noteplan-sweep add-breadcrumb "$SOURCE_NOTE" "$FILE_DATE" "SectionName" "one-line summary" "[[PlanName]]"
```

**Semantic section routing — no `## From` date subheaders.** The date origin of every task is already captured in its `>YYYY-MM-DD` scheduling tag. Adding a `## From YYYY-MM-DD` subheader is redundant. Instead, classify each block of content by *what question it answers* and append it to the matching semantic section within the plan:

| Content type | Target section |
|---|---|
| Goals, vision, what the outcome should be | `## Goals` |
| Specific capabilities, features, what it should do | `## Capabilities` or `## Features` |
| External services, APIs, MCPs to integrate | `## Integrations` |
| Reference URLs, docs, starting points | `## References` |
| Blocked work, waiting-on items | `## Blocked` |
| Concrete next steps, implementation tasks | `## Next Steps` |
| People to sync with, follow-ups, meeting notes | `## Collaborators` |

**How to route to a semantic section:**
1. Read the first 15 lines of the target plan to see what sections already exist
2. Match the content to the best existing section, or pick the most fitting name from the table above
3. If the section doesn't exist yet: `noteplan-sweep create-section "$TARGET" "## SectionName"`
4. Append: `noteplan-sweep append-section "$TARGET" "## SectionName" content.txt`
5. Same-plan content from different parts of the source day merges under the same section

For each section confirmed for moving:
- **To target daily note or existing plan file**: route to the matching semantic `##` section (see table above), create if needed
- **To new plan file**: append verbatim after the opening `* [ ]` line (no section needed — content seeds the first section)
- **To existing research doc**: append under `## References` or the most fitting section; also update `domains:` frontmatter with any new URL domains (set union, rewrite frontmatter in-place)
- **To new research note**: content placed after the opening H1
- **To meeting file**: append verbatim under a `## {YYYY-MM-DD} Notes` sub-header (date IS meaningful for meetings — it identifies the session)
- **Unsorted**: append under `# Unsorted` in the target note
- **Remove** from source: all content lines AND their section header (`# SectionName`). Do NOT move the original section header to the target — the target gets `# [[PlanName]]` instead.
- **Split sections**: when individual lines within a section go to different plans, remove the section header and each line individually, routing each line to its designated plan header.
- **Leave a swept breadcrumb in the source note**: after all sections for a day are moved, append a markdown table at the end of the source daily note so the user can trace where content went. Use `[[YYYY-MM-DD]]` wikilinks for daily note references and `[[PlanName]]` wikilinks for plan references so they're clickable in NotePlan. Format:
  ```
  ---
  | Swept | Section | Summary | Destination |
  |-------|---------|---------|-------------|
  | {YYYY-MM-DD} | PlanName | brief description of what moved | [[PlanName]] |
  | {YYYY-MM-DD} | Errands | {count} errand tasks | [[{TARGET_DATE_ISO}]] |
  | {YYYY-MM-DD} | Unsorted | brief description | [[{TARGET_DATE_ISO}]] |
  | {YYYY-MM-DD} | 1-1 Notes | meeting notes | [[MeetingFile]] |
  ```
  Where `{TARGET_DATE_ISO}` is `YYYY-MM-DD` (e.g. `[[2026-03-15]]`). Only list destinations where content was actually moved. Skip skipped sections. The breadcrumb is the one exception to "no new content in source" — it is allowed because it is a reference to swept content, not content itself.

  **Summary column — write item-level detail, not just a count.** The sweep review portal reads the Summary column to show what was moved. Write summaries that enumerate the key items:
  - ✅ `I owe Anna ARB review; I owe Anthropic eval harness; I owe Anna a PRD (5 items)` — lists first 2–3 items + total count
  - ✅ `ARB governance, security model, diagrams` — comma-separated key topics
  - ✅ `Langfuse options C/D, config agent, evals` — specific items, not vague
  - ❌ `ARB tasks (3 items)` — too vague; the portal can't show what was moved without the diff
  - ❌ `various tasks` — useless; always write actual item text

  For IOU sections, list each person by name: `I owe Anna ARB review; I owe Anthropic eval harness; I owe Jeff goals (5 items)`.
  For meeting/collaboration sections, name the people and topic: `Arish docs, Anthropic followup`.
  For reference sections, list the technology/tool names: `React DevTools, Privacy SP, Anthropic glasswing`.

  **CRITICAL — one row per section, one destination per row.** Every row must map exactly one section to exactly one destination. Never group multiple sections into a single row (e.g. `Section A + Section B + Section C → [[dest1]] [[dest2]] [[dest3]]`). If 10 sections are swept, write 10 rows. This rule applies equally to the pre-execution routing proposal table shown to the user for confirmation. Grouping obscures the sweep audit trail and makes it impossible to trace individual sections.

  **Why this matters for the sweep review portal:** The portal's diff modal is built around the one-row-one-section model. Each row's modal asks: "did the lines from THIS section of THIS source note land at the destination?" When multiple calendar dates sweep content to the same destination plan file (expected), each date gets its OWN breadcrumb row — the portal shows each date's contribution separately. If sections are grouped, the portal cannot tell which lines came from which section, and the verification breaks.

  **When the source note is swept again on a later date**: check if a breadcrumb table already exists. If so, **append new rows** to the existing table rather than creating a second table. This ensures the full sweep history for a note is visible in one table.

  Update the `is_allowed_new` check in Phase 7 to permit lines matching `^\| ` (table rows) and `^\| Swept ` (table header).

**Wikilink todos are ordinary content:** Tasks whose body is a wikilink (e.g. `- [ ] [[PlanName]]`) are moved verbatim exactly like any other task line. The wikilink in the body is the routing signal, but the full line (including `- [ ]` prefix) is preserved as-is.

**Personal content in work mode:** Sections that are clearly personal (shopping, errands, `[[🏡...]]` namespace wikilinks, personal names unrelated to work) should be flagged as `⏭️ skip — personal content` and left in the source. Do not ask the user about them unless the content is ambiguous.

**No content modification rule:** Copy every line exactly as-is. Preserve all leading whitespace / indentation. The only new text introduced is:
- `# [[PlanName]]` headers in the target note
- `## SectionName` semantic sub-headers in plan files (Goals, Capabilities, Integrations, References, etc.)
- `## {YYYY-MM-DD} Notes` sub-headers when appending to a **meeting file** (date is meaningful for meetings)
- `# Unsorted` header (if needed)
- The plan file boilerplate when creating a new plan
- The research doc frontmatter + H1 when creating a new research note or deep dive

**Do NOT introduce `## From YYYY-MM-DD` subheaders.** The date origin is already on every task via its `>YYYY-MM-DD` scheduling tag — duplicating it as a section header adds noise. Use semantic sections instead.

**Do NOT remove pre-existing semantic headers.** When cleaning plan files or staging notes, only strip `## From YYYY-MM-DD` provenance headers. All other pre-existing headers carry semantic meaning and must be preserved — even if they don't match the naming conventions above. Examples of headers to KEEP: `## Hifz Planner`, `# Watson Cowork Plugins`, `# AI Consultant`, `## For Evals`, `## Repairs`. If a better header name is known (e.g. you can match it to an existing plan), you may *promote* the header to a wikilink (`# [[PlanName]]`), but never silently delete a semantic header without replacing it.

**Permitted task annotations (the only allowed content additions to moved lines):**

When moving a block, two types of metadata may be appended to **root-level task lines only** (lines with no leading whitespace / indentation — i.e. direct children of the section, not nested sub-tasks):

1. **Date scheduling tag** — append `>{YYYY-MM-DD}` (the target note's date, e.g. `>2026-03-20`) so the task surfaces in NotePlan's calendar view for that week and doesn't get buried silently in a plan file.
   - Format: `- [ ] Original task text >YYYY-MM-DD` (one space before `>`, **hyphens required**)
   - **CRITICAL**: NotePlan date format is `>YYYY-MM-DD` (with hyphens), NOT `>YYYYMMDD`. Tags without hyphens are silently ignored by NotePlan and will not surface in the calendar.
   - Use the **target note's date** (next Friday for work, next Sunday for personal)
   - Only on `- [ ]` or `* [ ]` lines at root indentation level

1. **IOU source-date tag** — for lines **you classified as IOUs in Step 6b** (passed to the executor as `iou_lines: [...]`), ALSO append the **source note's date** as a second `>YYYY-MM-DD` tag. This stamps when the obligation was first recorded, preserving provenance even after the daily note is swept.
   - Format: `- [ ] I owe Anna the ARB doc >2026-04-24 >2026-04-13` (target date first, source date second)
   - Derive the source date from the Calendar filename: `20260413.md` → `>2026-04-13`
   - Both tags appear on the line: the target date drives NotePlan scheduling, the source date documents when the IOU was written
   - **Classification is yours, not the executor's** (see tenet at top of this skill). The executor receives an explicit `iou_lines` list and applies the source-date tag only to those exact line numbers; it does not pattern-match for `i owe` itself.
   - Apply to **root-level IOU lines only** — do not tag nested sub-tasks

2. **Hash tags** — append relevant `#tag` labels to root-level task lines when a clear categorical tag is warranted (e.g. `#errand`, `#meeting`, `#followup`). Only add tags that are already present in the surrounding plan file or that are clearly implied by the routing destination. Never invent tags.

All other lines (nested tasks, prose, URLs, code blocks) are moved strictly verbatim with zero modification.

### Step 6f — Repair broken date tags, checkpoint commit, and advance

**Date tag repair (run after each day's sweep):** Before committing, scan ALL files touched in this day's sweep (source + targets) for broken date scheduling tags in `>YYYYMMDD` format (no hyphens) and fix them to `>YYYY-MM-DD`. This catches both newly-added tags from this sweep and any pre-existing broken tags in the files:

```bash
# Fix >YYYYMMDD to >YYYY-MM-DD in all touched files
for path in "${TOUCHED_FILES[@]}"; do
    noteplan-sweep fix-date-tags "$path"
done
```

After repair:

```bash
git add -A
git commit -m "sweep(daily): process ${fileDate} → ${TARGET_DATE} (${n} sections moved)"
git pull --rebase   # pull before push to handle concurrent edits (e.g. phone sync)
# If rebase produces conflicts: resolve them, then git rebase --continue before pushing
git push
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
    # CRITICAL: handle both plain paths (+++ b/path) and quoted paths (+++ "b/path")
    # Git quotes paths containing non-ASCII characters (e.g. emoji filenames).
    # Without this, current_file stays as the previous file, causing lines to be
    # silently skipped under the wrong file filter (e.g. today_date filter).
    if line.startswith('+++ '):
        rest = line[4:].strip().strip('"')
        if rest.startswith('b/'):
            current_file = rest[2:]
        continue
    if line.startswith('--- ') or line.startswith('@@') or line.startswith('diff ') or line.startswith('index '):
        continue
    # Skip JSON/backup files — they track system state, not user content
    if current_file.endswith('.json') or 'Backup' in current_file:
        continue
    # Note: do NOT skip today's note — IOUs are routed there legitimately.
    # The check will naturally pass since moved lines appear in both removed + added sets.

    content = line[1:].rstrip()  # strip trailing whitespace for comparison
    # Normalize permitted task annotations (trailing date tags + hashtags) on BOTH sides
    # so date-forwarding (e.g. >2026-03-16 → >2026-03-20) doesn't cause false "content loss" failures
    normalized = re.sub(r'(\s+(>\d{4}-\d{2}-\d{2}|>\d{8}|#\w+))+$', '', content)
    if line.startswith('-'):
        removed.add(normalized)
    elif line.startswith('+'):
        added.add(normalized)

# today_date = current date as YYYYMMDD string, exclude from diff
today_date = __import__('datetime').date.today().strftime('%Y%m%d')

lost = removed - added
new = added - removed

# Section headers removed from source are expected — sweep removes them intentionally
lost = {l for l in lost if not re.match(r'^#', l.strip())}

# Only allowed new lines (non-content additions)
VOICE_NOTE_CLEANED_LINES = set()  # populated when voice note cleaning occurs — these are expected new lines

def is_allowed_new(l):
    if l in VOICE_NOTE_CLEANED_LINES:
        return True  # voice note cleaning exception
    return (
        re.match(r'^# \[\[', l) or          # wikilink section headers
        l.strip() == '# Unsorted' or
        l.strip() == '' or                   # blank lines
        re.match(r'^\* \[ \] Is \[\[', l) or # plan boilerplate
        re.match(r'^---$', l) or             # frontmatter delimiters
        re.match(r'^(doctype|status|started|namespace|workstream|plantype|contributors|description):', l) or
        re.match(r'^# [🏡🏢🔁]', l) or      # H1 for new plan files
        re.match(r'^## \d{4}-\d{2}-\d{2}', l) or  # meeting date headers (## YYYY-MM-DD Notes)
        re.match(r'^## (Goals|Capabilities|Features|Integrations|References|Blocked|Next Steps|Collaborators)', l) or  # semantic section headers
        re.match(r'^#', l.strip()) or        # any section header in Unsorted context
        re.match(r'^\| ', l) or              # swept breadcrumb table rows
        re.match(r'^\- → ', l) or            # swept breadcrumb destination lines (legacy)
        re.match(r'^\*Swept \d{4}-\d{2}-\d{2}', l)  # swept breadcrumb header (legacy)
    )

disallowed_new = [l for l in new if l.strip() and not is_allowed_new(l)]

if lost:
    print("FAIL: Content lines removed but not found in additions:")
    for l in sorted(lost): print(f"  - {repr(l)}")
if disallowed_new:
    print("FAIL: New content lines added that are not section headers or boilerplate:")
    for l in sorted(disallowed_new)[:20]: print(f"  + {repr(l)}")
if not lost and not disallowed_new:
    print("PASS: All line-level integrity checks passed.")
PYEOF
```

If **any check fails**, do not proceed. Report the failure to the user and offer rollback to the pre-sweep snapshot:

```bash
git reset --hard <pre-sweep-commit-hash>   # only if user confirms
```

**Additional source-clean validation (after diff check passes):** Confirm each swept source note has no remaining open tasks:

```bash
# Verify every source note was fully cleared
for source in "${SWEPT_SOURCE_FILES[@]}"; do
    noteplan-sweep check-source-clean "$source"
done
```

Exit code `1` means open tasks remain — report the specific lines to the user before proceeding to Phase 7b.

---

## Phase 7b: Post-Sweep Unsorted Review

After the integrity check passes, review ALL accumulated `# Unsorted` content in the target notes — section by section, one at a time. Do this for every Unsorted block regardless of whether new plans were created.

**Steps:**

1. Read the `# Unsorted` section of each target note (Friday and/or Sunday)
2. Split into individual blocks — each contiguous group of lines separated by blank lines, or each top-level task and its sub-tasks, counts as one block
3. For each block, re-score against the **full current index** (plans + lists + meetings — including newly created ones from this sweep)
4. **Ask about every block individually** — one `AskUserQuestion` per block, with a progress counter:

   ```javascript
   AskUserQuestion({
     questions: [{
       question: `Unsorted block (${currentIndex}/${totalBlocks}) from ${targetNote}:\n\n${blockPreview}\n\nSuggested: ${topMatch?.filename_stem ?? "no match found"}`,
       header: `Unsorted review: ${targetNote} (${currentIndex}/${totalBlocks})`,
       options: [
         // Show top-3 plan matches (scored) if any:
         ...top3.map(p => ({ label: `[[${p.filename_stem}]]`, description: p.description ?? `(${p.workstream_or_plantype})` })),
         { label: "📥 Keep in Unsorted", description: "Leave this block where it is" },
         { label: "🗑️ Delete", description: "This content is no longer relevant" }
       ],
       multiSelect: false
     }]
   })
   ```

5. For each block the user routes: move it out of Unsorted and append it under the appropriate `# [[PlanName]]` header in the same target note, routed to the matching semantic section within that plan
6. For "Keep in Unsorted": leave untouched
7. For "Delete": remove from the target note entirely
8. After processing all blocks for all target notes:
   ```bash
   git add -A
   git commit -m "sweep(daily): Unsorted review → ${N} blocks routed, ${K} kept, ${D} deleted"
   git pull --rebase
   git push
   ```

This phase runs whenever there are any Unsorted items in either target note — not only when new plans were created.

### Categorized Unsorted sub-sections

After all individual block routing is complete, **restructure the remaining Unsorted content** into categorized sub-sections. This makes the Unsorted section scannable rather than a flat dump.

**Standard categories** (use only the ones that have content):

| Category | Emoji | What goes here |
|---|---|---|
| References & Reading | `## 📋 References & Reading` | URLs, articles, tools to read, learning resources |
| Comms | `## 💬 Comms` | People to reply to, follow-ups, messages to send |
| Family & Events | `## 👨‍👩‍👧‍👦 Family & Events` | Family tasks, events, school, social |
| Home & Admin | `## 🏠 Home & Admin` | Home repairs, bills, accounts, admin tasks |
| Work Quick Tasks | `## 💼 Work Quick Tasks` | Small work items that don't fit a plan |
| Ideas | `## 💡 Ideas` | Raw ideas, brainstorms, things to explore |

**Rules:**
- Only create categories that have ≥1 item — don't add empty sections
- Items that were routed to plans or deleted are NOT included
- Items the user chose to "Keep in Unsorted" are categorized
- Present the restructured Unsorted to the user for confirmation before writing
- If all items were routed/deleted and nothing remains, remove the `# Unsorted` header entirely

---

## Phase 8: Final Commit + Push

**Before committing: write back the updated People Index.**

If any new people were identified during Phase 6 (new person domain question was answered, or new plan `contributors:` were added), rewrite the relevant `References[People].md` file(s):
- Work: `$NOTES_ROOT/🏢 ServiceNow/📋 Lists/🏢📋 References[People].md`
- EarlBear: `$NOTES_ROOT/👥 EarlBear/📋 Lists/👥📋 References[People].md`

Format: one `## {Name}` section per person with `Domain:`, `Role:`, and `Plans:` fields (wikilinks). Merge new entries with existing — never overwrite existing entries without confirmation.

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
git pull --rebase   # resolve any conflicts before pushing
git push
```

### Self-update trigger

If during this sweep any file operation was performed with ad-hoc inline Python instead of `noteplan-sweep`, add an item to Phase 8.5 to implement that operation in the CLI:

1. Identify which operation was missing (e.g. `noteplan-sweep foo-bar`)
2. Implement it in `~/workspace/oeid-claude-plugin-marketplace/plugins/noteplan-manager/bin/noteplan_sweep/`
3. Add the subcommand to `noteplan-sweep` entrypoint's `DISPATCH` dict
4. Commit to plugin repo + bump version (patch) + reinstall (`make update` in plugin repo)
5. Update the relevant plan file task to `[x]`

This ensures the CLI stays complete and the next sweep doesn't re-invent the same operation.

---

## Phase 8.5: Self-Knowledge Capture

### The Dual Mandate — Scribe and Guide

Phase 8.5 holds two roles simultaneously. Both are mandatory on every sweep — for **all three domains** (work, personal, EarlBear). Neither role is optional. Neither domain is skipped if content was swept.

---

#### Context: Who This Is For

Omar is running a **deliberate dual track**:

- **🏢 Work (ServiceNow)**: Staff / Senior Staff IC is the target level. The path is through scope expansion — owning architecture-level decisions, governance processes, cross-team coordination, and Anthropic-adjacent frontier work. No current role friction; this is a high-energy window. Use it.
- **👥 EarlBear**: A real business bet with a long time horizon, not a hobby. The goal is EarlBear becoming the primary focus — but the timeline depends on co-founder (Saad) commitment calibration and first revenue validation. The trigger for prioritization shift is not yet defined.
- **🏡 Personal**: Family (Yara, wife), spiritual practice, health. These ground the system — they should not be perpetually deprioritized in favor of the two tracks above.

**What Omar has asked AI to help with (in his own words):**
1. Stay sharp on the frontier — never caught off guard by a new AI capability
2. Build the career case systematically — consolidate evidence, flag next-level work, articulate it when it counts
3. Keep EarlBear moving when ServiceNow is intense — maintain momentum even during busy weeks
4. Help with hard prioritization calls — say no to the right things, yes to what compounds

These four mandates shape what the guide writes every sweep.

---

**Scribe** — record faithfully what happened, per domain:
- 🏢 Work: brag sheet + impact timeline (signal-tagged) + Observations/Gaps/Superpowers
- 🏡 Personal: personal brag sheet + personal Observations (growth, projects, habits, family, spiritual)
- 👥 EarlBear: progress log (what was built, decided, validated with Saad or customers)

**Guide** — coach toward growth, per domain, using the context above:

**🏢 Work guide lens:**
- Track the Staff IC signal pattern: ARB ownership, architecture decisions, cross-team coordination, frontier-adjacent work → reinforce when in that mode, flag when it's been absent
- Surface the energy window: no-friction periods are finite → encourage visibility and credibility asset building (external demos, Anthropic relationship, precedent-setting governance work)
- Check frontier exposure: is Omar staying ahead of what's changing in AI, or is the week all execution with no learning signal?
- Career case: flag which brag sheet entries this sweep are genuinely Staff-level vs. routine IC work

**🏡 Personal guide lens:**
- Flag when personal/family commitments are repeatedly deferred — especially Yara, health, spiritual practice
- Note when EarlBear work is bleeding into personal time without producing EarlBear progress
- Flag when personal energy seems low (sparse notes, deferred everything, no habits visible)
- Suggest one personal investment per sweep if the balance is off

**👥 EarlBear guide lens:**
- Watch the build-vs-validate ratio: building features without customer validation is the primary EarlBear risk
- Flag when EarlBear has been absent for 2+ sweeps — momentum loss is the co-founder alignment risk
- Saad check: is Saad mentioned in recent EarlBear progress? If not, flag co-founder alignment as the next step, not more building
- Suggest one concrete EarlBear action per sweep even during heavy ServiceNow periods — even small moves keep the flywheel turning

**🔀 Prioritization guide lens (cross-domain):**
- When both ServiceNow and EarlBear are active and intense, flag scope overload explicitly
- Identify which track is getting underserved this week and name it directly
- If personal is repeatedly taking the hit, name that too

Write each assessment as a direct recommendation (not a question). One note per domain per sweep. Skip a domain's guide note only if zero notes from that domain were swept.

The scribe sees what is. The guide sees what's needed. The sweep assistant must do both, for all three domains.

---

During the sweep you've read many daily notes and observed the user's ideas, collaborators, interests, and patterns. After the final commit, synthesize what you've learned and update three structured files in the user's Reflections directory.

**Target directory:** `$NOTES_ROOT/🏡 Personal/🏡💭 Thoughts/🪞 Reflections/🏡💭💻 GenAI Thoughts/`

**Files to update (append a dated entry — do not overwrite prior entries):**

| File | What to write |
|---|---|
| `Observations.md` | Factual observations: who they work with, what they're building, recurring topics, work style. Also includes career trajectory notes and domain guide assessments. |
| `Gaps.md` | Friction points, untracked areas, ideas that never became plans, recurring stuck tasks |
| `Superpowers.md` | Strengths, domains of expertise, high-engagement topics, distinctive thinking patterns |

**Monthly direction checkpoint** — on the first sweep of each calendar month, also write a checkpoint file:

```
$NOTES_ROOT/🏡 Personal/🏡💭 Thoughts/🪞 Reflections/🏡💭💻 GenAI Thoughts/📅 Direction Checkpoints/{YYYY-MM}.md
```

Create the `📅 Direction Checkpoints/` directory if it doesn't exist. Each checkpoint file is a standalone document — one per month:

```markdown
---
date: {YYYY-MM-01}
type: direction-checkpoint
---

# Direction Checkpoint — {Month YYYY}

## Dual-Track Snapshot

### 🏢 ServiceNow (Staff IC target)
- What the last month of work signals: {1-3 bullets from impact timeline entries}
- Staff-level signals present: {list of SCOPE+/LEADERSHIP/INNOVATION entries}
- Staff-level signals missing: {which signal types were absent this month}
- Energy window status: {high / moderate / depleted — based on note density and content}

### 👥 EarlBear (long-term primary goal)
- Progress this month: {what was built, decided, validated}
- Build-vs-validate balance: {which mode dominated}
- Saad alignment: {mentioned in progress? Last co-founder touchpoint visible in notes?}
- Momentum: {growing / steady / stalled}

### 🏡 Personal (grounding system)
- Family / spiritual / health presence: {visible in notes? deferred?}
- Balance signal: {personal investment appears proportionate / personal is being squeezed}

## Direction Assessment

- Is the dual track on course? {yes / drifting — explain}
- What's compounding well? {1-2 specific things gaining momentum}
- What's at risk of stalling? {1-2 specific things that need attention}

## Guidance for the Coming Month

- 🏢 Work: {1 concrete focus that advances the Staff IC case}
- 👥 EarlBear: {1 concrete milestone — measurable, not vague}
- 🏡 Personal: {1 commitment to protect, not defer}
- 🔀 If overloaded: {what to deprioritize first}
```

**Rules for checkpoints:**
- Write on the **first sweep of the month** only — detect by checking if a file for the current `{YYYY-MM}` already exists
- Draw only from: impact timeline entries, brag sheet entries, EarlBear progress log, and Observations from the past 30 days — no speculation
- The guidance section is a direct recommendation, not a question
- Commit checkpoint files separately with: `git commit -m "reflect(checkpoint): {YYYY-MM} direction checkpoint"`

**What to observe passively while sweeping:**

- **Collaborators**: names recurring across multiple days → consistent colleagues
- **Domains of interest**: recurring topics across daily notes → what they're focused on
- **Work style**: spikes on POCs? Fragmentary ideation? Many started plans with no next steps?
- **Gap signals**: sections that can't be routed (no matching plan = untracked area); recurring tasks that never complete
- **Superpower signals**: dense, detailed, confident notes in specific areas → expertise
- **Career trajectory**: open job applications, recurring career questions ("should I become X?"), salary/role explorations → direction of career gravitational pull
- **Completion patterns**: which task types actually get done vs. accumulate indefinitely; tasks deferred to distant past dates reveal the intention-execution gap
- **Learning deferred**: bought/bookmarked courses and resources not yet started → gap between acquiring and acting on learning material
- **Scope overload signals**: self-identified overwhelm tasks ("I am trying to do too much"), explicitly deferred items, domains that never produce completed tasks → unsustainable breadth
- **Publishing intent**: recurring aspirations to blog, post, share publicly that keep getting deferred → unblocking opportunity
- **Relationship maintenance pressure**: recurring "reply to / follow up with" tasks for same people → relationship investment under time pressure
- **Energy map**: days with dense, structured notes vs. sparse ones → actual working rhythms vs. ideal-self assumptions
- **Financial awareness**: subscription audits, upcoming large expenses, payment obligations → growing financial consciousness
- **Spiritual integration**: faith-related tasks woven into technical work → a coherent worldview, not compartmentalized

**Entry format** (append under a `## {YYYY-MM-DD} Sweep` date header in each file):

```markdown
## {YYYY-MM-DD} Sweep

- [observation or gap or superpower bullet]
- [another bullet]
```

**Rules for this phase:**
- Write with care and respect — avoid negative framings. "Has a growing backlog of ideas that aren't yet tracked in plans" > "tends to forget things"
- Be specific: "Consistently collaborates with Dennis on ATF work" not "works with people"
- Only write what's verifiable from the notes you actually read — no speculation
- Keep entries concise: 3–7 bullets per file per sweep
- Create the file if it doesn't exist yet (plain markdown, no frontmatter needed)

**Also update `🏡📋 Habits.md`** in `$NOTES_ROOT/🏡 Personal/🏡📋 Lists/`:

1. Read the current `🏡📋 Habits.md` file
2. Scan notes read during this sweep for habit signals:
   - **Observed habits**: tasks done repeatedly, check-ins with habit trackers, routine references (prayer, exercise, journaling) → update the `## ✅ Current Habits (Observed)` table with the `Last Seen` date and a frequency estimate
   - **Aspired habits**: tasks phrased as "I want to…", "Start doing…", or explicit habit goals not yet consistent → add rows to `## 🌱 Habits I Want to Build` if not already present
   - **Habit reflections**: self-commentary about habits, scope overload signals, seasonal resets (Ramadan, New Year, etc.) → append to `## 💡 Habit Reflection Notes`
3. Write the updated file back (preserve existing entries — only add new rows or update `Last Seen` / frequency on existing ones)

**Also update the Brag Sheets and Impact Timeline** using TaskCreate to make the update visible:

1. Create tasks before updating:
   ```javascript
   TaskCreate({ title: "Update work brag sheet + impact timeline (sweep {YYYY-MM-DD})", status: "in_progress" })
   TaskCreate({ title: "Update personal brag sheet (sweep {YYYY-MM-DD})", status: "in_progress" })
   TaskCreate({ title: "Update EarlBear progress log (sweep {YYYY-MM-DD})", status: "in_progress" })
   ```

2. **Work brag sheet** — `$NOTES_ROOT/🏢 ServiceNow/📋 Lists/🏢📋 Brag Sheet.md`
   - Create if it doesn't exist with header:
     ```markdown
     # 🏢📋 Brag Sheet

     A running log of work achievements, impact, and value delivered.
     Updated each sweep — use this at review time to justify your impact.
     ```
   - Append under a `## {YYYY} Q{Q}` quarter header (create if absent), then a `### {YYYY-MM-DD} Sweep` sub-header
   - Write **only verifiable, concrete achievements** from the notes read — no speculation
   - Focus on: shipped features/POCs, unblocked collaborators, delivered demos, architectural decisions made, external recognition
   - **Tag each entry with a next-level signal** when applicable:
     - `[SCOPE+]` — decision or action taken at a scope above individual contributor (cross-team, org-wide, customer-facing)
     - `[LEADERSHIP]` — owned a process, led a review, guided collaborators, set direction
     - `[INNOVATION]` — novel technical approach, pioneering use of new technology, frontier-adjacent work
     - `[VISIBILITY]` — external recognition, demo to leadership, cross-org exposure, Anthropic collaboration
     - `[IMPACT]` — unblocked others, accelerated a timeline, moved a milestone, shipped something used by others
   - Example entry format:
     ```markdown
     ### {YYYY-MM-DD} Sweep

     - **[SCOPE+][LEADERSHIP]** Owned ARB process for AXIS Config Agent end-to-end — PRD, architecture diagrams, security model, and institutional review accountability
     - **[INNOVATION]** Designed eval stress test mode for parallel agent load testing with session ID logging for post-run debugging
     - **[IMPACT]** Unblocked Chandran on deployment by routing A2A hardening tasks and consolidating sandbox provisioning steps
     ```

3. **Work impact timeline** — `$NOTES_ROOT/🏢 ServiceNow/📋 Lists/🏢📋 Impact Timeline.md`
   - Create if it doesn't exist:
     ```markdown
     # 🏢📋 Impact Timeline

     A structured, career-framing record of contributions over time.
     Used to build next-level cases and performance review narratives.
     Maintained alongside the Brag Sheet — brag sheet = activity log, impact timeline = career narrative.
     ```
   - Append under `## {YYYY} Q{Q}` → `### {Month YYYY}`:
     ```markdown
     ### {Month YYYY}

     | Initiative | What was delivered | Next-level signal | Evidence |
     |---|---|---|---|
     | AXIS Config Agent ARB | Owned arch review end-to-end | SCOPE+ / LEADERSHIP | PRD, arch diagrams, ARB responses |
     | A2A POC Hardening | Advanced from exploration to 100-project pilot target | IMPACT | Pilot framing doc, Anthropic collaboration |
     | Eval Harness Design | Designed stress test mode + session ID logging | INNOVATION | Eval harness doc, implementation plan |
     ```
   - Only include items with at least one next-level signal — purely routine items stay in the brag sheet only
   - This file is the primary input for `/noteplan-manager:generate-impact-narrative`

4. **Personal brag sheet** — `$NOTES_ROOT/🏡 Personal/🏡📋 Lists/🏡📋 Brag Sheet.md`
   - Create if it doesn't exist with header:
     ```markdown
     # 🏡📋 Brag Sheet

     A running log of personal achievements, milestones, and skills developed.
     Updated each sweep.
     ```
   - Same format: `## {YYYY} Q{Q}` → `### {YYYY-MM-DD} Sweep`
   - Focus on: personal projects launched/progressed, new tools built, family milestones, spiritual growth, skills deepened

5. **EarlBear progress log** — `$NOTES_ROOT/👥 EarlBear/📋 Lists/👥📋 Progress Log.md`
   - Create if it doesn't exist:
     ```markdown
     # 👥📋 Progress Log

     A running log of EarlBear progress — what was built, decided, or validated each sweep.
     ```
   - Append under `## {YYYY} Q{Q}` → `### {YYYY-MM-DD} Sweep`
   - Focus on: features shipped, customer development conversations, product decisions, infra milestones, co-founder alignment
   - Only write if EarlBear content was swept this session — skip if no EarlBear notes in scope

6. Mark all three tasks `completed` after writing.

7. **Trajectory assessments** — one per domain swept

   After writing new entries, read recent history for each domain and write a brief trajectory note. This is a **direct recommendation** — write it, don't ask the user about it.

   **🏢 Work trajectory** — append to `## {YYYY-MM-DD} Career Trajectory Note` in `Observations.md`:

   Read the last 8–12 entries from `🏢📋 Impact Timeline.md`. Assess signal distribution:

   | Pattern | Suggestion |
   |---|---|
   | All `[IMPACT]`, no `[SCOPE+]` | Seek a cross-team initiative to own end-to-end |
   | No `[LEADERSHIP]` in 2+ sweeps | Look for a process, review, or mentoring opportunity to own |
   | No `[VISIBILITY]` in 3+ sweeps | Present a piece of work externally — demo, Slack post, write-up |
   | No `[INNOVATION]` in 3+ sweeps | Propose a novel approach to an existing problem |
   | Heavy `[SCOPE+]`/`[LEADERSHIP]` but no `[IMPACT]` | Focus on shipping something concrete this period |
   | Well-distributed signals | Healthy profile — note what's working, keep the mix |

   ```markdown
   ## {YYYY-MM-DD} Career Trajectory Note

   - Signal distribution this quarter: SCOPE+: N, LEADERSHIP: N, INNOVATION: N, VISIBILITY: N, IMPACT: N
   - Pattern: {e.g. "Strong IMPACT and INNOVATION, limited VISIBILITY"}
   - Suggestion: {1–2 concrete work directions for the coming weeks}
   ```

   Skip only if fewer than 3 impact timeline entries exist.

   **🏡 Personal trajectory** — append to `## {YYYY-MM-DD} Personal Growth Note` in `Observations.md`:

   Assess from personal notes swept this session:
   - Are personal projects moving or stalling? (tasks that keep deferring signal scope overload or low priority)
   - Is there balance? (work tasks bleeding into personal days, family/health tasks deprioritized repeatedly)
   - Are spiritual or family commitments being honored? (prayer, family activities, health habits appearing or absent)
   - Are learning goals progressing? (bookmarked resources and courses — are they being used?)

   ```markdown
   ## {YYYY-MM-DD} Personal Growth Note

   - Energy investment: {what domains are getting attention — e.g. "heavy EarlBear, light family time"}
   - Stall detected: {what's being deferred repeatedly — e.g. "fitness tasks accumulating for 3 sweeps"}
   - Suggestion: {1 concrete focus for personal energy this period}
   ```

   Skip if no personal notes were swept this session.

   **👥 EarlBear trajectory** — append to `## {YYYY-MM-DD} EarlBear Growth Note` in `Observations.md`:

   Assess from EarlBear notes swept this session:
   - Build vs. validate balance: Is the work mostly technical (building) or customer-facing (validating)?
   - Product momentum: Did anything ship, get demoed, or get validated with a real user this period?
   - Co-founder alignment: Is Saad mentioned alongside progress, or is work happening in isolation?
   - Scope: Is EarlBear progressing or is it stuck in the same phase across multiple sweeps?

   ```markdown
   ## {YYYY-MM-DD} EarlBear Growth Note

   - Mode: {Build-heavy / Validate-heavy / Balanced}
   - Momentum: {shipped / demoed / stalled}
   - Suggestion: {1 concrete next step for EarlBear — e.g. "Get one user to test the intake flow before building more features"}
   ```

   Skip if no EarlBear notes were swept this session.

- Commit and push after writing all reflection files and brag sheets:
  ```bash
  git add -A
  git commit -m "reflect(sweep): add {YYYY-MM-DD} self-knowledge observations + brag sheets + impact timeline"
  git pull --rebase   # resolve any conflicts before pushing
  git push
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
| Completed tasks never move (default) | `[x]` tasks are historical record. Skip unconditionally unless the user asks to move a completed block to an existing plan's Done section. |
| Completed block routing (optional) | When a section is `[x]`-only AND there is a confident plan match, offer to append it to `## Done` / `## Completed` in the plan file. Never auto-move without confirmation. |
| Wikilink todos are content | `- [ ] [[PlanName]]` tasks are ordinary content — move verbatim, use the wikilink as routing signal. |
| Target sections use wikilinks | Always `# [[filename_stem]]` (exact), never a raw string. |
| Section headers are NOT moved | Remove original `# SectionName` from source; the target gets `# [[PlanName]]` instead. |
| Split sections allowed | When one section has items for different plans, split by line and route individually. |
| Same-plan entries merge | Multiple source sections routing to the same plan merge under one target header. |
| Bulk description enrichment | When N > 5 plans missing descriptions, use bulk path: batch-infer all, present grouped, single approve. |
| Contributors enrichment | During Phase 4, also extract contributor names from plan bodies and write them as `contributors:` frontmatter. Use contributors as a routing signal in Step 6b. |
| Lists files indexed | Index recently-modified list files from `📋 Lists/` alongside plans. Show them as routing options for reference URLs and research notes. |
| Filename/title consistency | During Phase 4, check H1 vs filename for every plan. Rename plain-text filenames to match proper-convention H1s; fix H1s to match proper-convention filenames. Flag ambiguous cases and report them post-commit. |
| Personal in Both mode — ask | In Both mode, personal side projects in work-day notes should not be silently skipped. Batch-ask once per day: route to personal target, work Unsorted, or skip. |
| Meeting notes routing | Route meeting/1-1 content to the actual meeting file in `👤 Meetings/`, not to Unsorted. Search by person name, event name, or date. Raw prose blocks and bullet talking-points may also be meeting notes even without explicit headers. |
| Meetings indexed | Index recently-modified meeting files alongside plans and lists. Show them in routing UI with highest priority when section content matches a person's name or meeting keyword. |
| Semantic section routing | When appending to an existing plan or target daily note, route content to the matching semantic `##` section (Goals, Capabilities, Integrations, References, etc.). The `>YYYY-MM-DD` tag on each task already records origin date — do not add `## From` date subheaders. |
| User notes are authoritative | Free-text notes in AskUserQuestion answers override scoring. Re-score the plan index against the user's clarification before presenting the next question. |
| Post-sweep Unsorted review | After integrity check, review EVERY Unsorted block individually — one AskUserQuestion per block with top-3 plan suggestions. Ask "keep or move?" for each. Runs whenever any Unsorted content exists. |
| Templates must be read first | Before creating any new plan, meeting, or list file, read the corresponding template from `@Templates/` to verify the H1 format and frontmatter fields. |
| New plans use `---` delimiters | Created plan/meeting files MUST use `---` (three dashes) for frontmatter. Templates themselves use `--` (two dashes) — do not copy that into the created file. |
| New plan subdirs are discovered | `ls $PLAN_ROOT` to find the right workstream/plantype subdir. Never hardcode. |
| Checkpoint commits per day | Commit after each day's sweep for granular recoverability. |
| Line-level integrity check | Run the Python diff validation script before the final commit. |
| Proposal includes exact lines | Each routing entry in the final plan shows the exact lines being moved in a code block, plus destination note. |
| Diff-view before every confirmation | HARD MUST: before any "Execute/Confirm" AskUserQuestion for a day, print a plain-text diff-view table in chat mapping source line number(s) → exact content → destination → tag/enrich. AskUserQuestion can't render a diff, so confirming without this table means the user routes blind. Never jump straight to the confirm question. |
| Uncertain sections are individual | Never bulk-ask about routing. Every uncertain/ambiguous block gets its own AskUserQuestion, one at a time, with a progress counter. |
| Top-5 routing suggestions | Score every plan against the section header + content; show only the top 5 matches. Never dump the full plan list into the routing UI. |
| Both mode supported | When mode = "Both", build both work + personal indexes. Each note's day-of-week determines which index and target to use. |
| Thoughts directory indexed | Index `🏡💭 Thoughts/💡 Ideas/` alongside plans and lists. Present as routing option for raw ideas, braindumps, and speculative product/startup thinking. |
| Threads — developing thoughts | The canonical home for open questions / theses the user develops over time is `🏡💭 Thoughts/🧵 Threads/` (one note per question, e.g. "Will ServiceNow Lay Folks Off?"). Index it in Phase 3. Classify a section as `🧵 Thread candidate` when it reads as an evolving open question/thesis (not a one-shot idea, not an actionable task). Route to a matching thread or offer to create one. |
| Threads — provenance dating | Every thread note records `started:` (first-thought date) and appends each addition under a `## {source calendar date}` heading so "when did I first/last think this?" is answerable. Append dated entries; never overwrite. A thread accumulates across many sweeps; a `💡 Idea` is a single capture. |
| Meeting planning → next business day | When routing unscheduled meeting tasks from Unsorted (e.g. "Figure out meetings — Jeff, Khusbha, etc."), place them in the **next business day's daily note** (create it if needed), not in a general backlog. |
| Self-knowledge capture | After each sweep's final commit (Phase 8.5), append dated observations to `🪞 Reflections/🏡💭💻 GenAI Thoughts/Observations.md`, `Gaps.md`, and `Superpowers.md`. Only write what's verifiable from the notes read. |
| Habits tracking in sweep | Phase 8.5 also updates `🏡📋 Habits.md`: scan swept notes for habit signals (observed habits, aspired habits, habit reflections). Update `Last Seen` and frequency on existing rows; add new rows for newly spotted habits. |
| Brag sheets via tasks | Phase 8.5 updates three brag sheets using TaskCreate: `🏢📋 Brag Sheet.md` (work), `🏡📋 Brag Sheet.md` (personal), `👥📋 Progress Log.md` (EarlBear, if EarlBear content was swept). Create a task per sheet before updating, mark completed after. Only concrete, verifiable achievements from the swept notes. |
| Scribe and guide | Phase 8.5 plays two roles simultaneously: **scribe** (faithfully record what happened — brag sheet, impact timeline, observations) and **guide** (assess career trajectory, spot missing signals, suggest concrete work directions for the next period). Both roles are mandatory every work sweep. |
| Next-level signal tagging | Work brag sheet entries MUST be tagged with signal types when applicable: `[SCOPE+]` (cross-team/org decisions), `[LEADERSHIP]` (owned process or guided others), `[INNOVATION]` (frontier/novel technical approach), `[VISIBILITY]` (external recognition, leadership exposure), `[IMPACT]` (unblocked others, shipped, moved milestone). Multiple tags allowed per entry. |
| Impact Timeline maintained | Phase 8.5 also appends to `🏢📋 Impact Timeline.md` — a structured career-framing table. Only entries with at least one next-level signal qualify. This file is the primary input for `/noteplan-manager:generate-impact-narrative`. |
| Trajectory assessed for all three domains | Phase 8.5 writes a trajectory note per domain to `Observations.md`: work (signal distribution + suggestion), personal (energy balance + stall detection + suggestion), EarlBear (build-vs-validate + momentum + suggestion). Skip a domain's note only if zero notes from that domain were swept this session. |
| Git pull before sweep | Phase 2 must run `git pull` before the pre-sweep commit. Stop if pull fails. |
| Git push after every commit | After every commit in the sweep (pre-sweep, checkpoint, Unsorted re-route, final, reflect), run `git push` immediately. |
| Tasks are mandatory, not optional | Create ALL phase tasks with dependencies at session start using TaskCreate. Mark `in_progress` before each phase, `completed` after. The task list is the user's primary visibility window. |
| Swept breadcrumbs in source | After sweeping a daily note, append a markdown table (`| Swept | Section | Summary | Destination |`) at the end of the source file so the user can trace where content went. If a breadcrumb table already exists (note swept before), append new rows to it — do not create a second table. `is_allowed_new` allows `^\| ` (table rows). **Section names in the table must NOT include `#` prefixes** — strip the heading marker so cells don't render as headings in NotePlan (e.g. `Chandran Meeting Notes` not `# Chandran Meeting Notes`). |
| Search before asking | Before presenting a routing question for an uncertain section, use WebSearch to identify unknown URLs, names, or topics. If the search gives a confident answer, route directly. If ambiguous, include findings in the routing question. After the user decides, update the destination's `description:` frontmatter to capture the clarification for future sweeps. |
| Integrity check — normalize both sides | The `removed` and `added` sets in the Phase 7 integrity check must both be normalized (strip trailing `>YYYY-MM-DD` tags and `#hashtags`) before comparison. Date-forwarding during sweeps (e.g. `>2026-03-16` → `>2026-03-20`) should not cause false "content loss" failures. |
| Integrity check — quoted diff paths | Git quotes paths containing non-ASCII characters (emoji filenames). The `+++ ` line may be `+++ "b/path"` instead of `+++ b/path`. Always handle both forms when tracking `current_file` in the diff parser. |
| Verbatim moves — read from source | When executing content moves via Python, always read lines directly from the source file rather than hardcoding them as strings. Hardcoded strings silently lose `\xa0` non-breaking spaces and other non-standard whitespace that NotePlan embeds in rich text exports. |
| NotePlan date format is `>YYYY-MM-DD` | Date scheduling tags MUST use hyphens (`>2026-03-20`), never compact (`>20260320`). Tags without hyphens are silently ignored by NotePlan. Step 6f runs a repair pass after each day to fix any broken tags in touched files. |
| Raw links are routing signals | Inspect URL domains during classification. ServiceNow instance/docs links route to matching work plans. Learning/reference URLs route to `📋 Lists/References[...]` when standalone. Standalone raw links are `❓ Uncertain` — present with domain context. |
| Research candidate classification | When a section matches 2+ research signals (labeled header, 3+ URLs, zero tasks, investigative language, domain overlap with existing research doc), classify as `🔬 Research candidate` and present the research routing UI instead of the standard plan routing UI. |
| Research vs Deep Dive distinction | `🔬 Research/` = active/ongoing investigation (evergreen reference). `🤿 Deep Dives/` = concluded research where a decision was reached or goal achieved. Default to Research during sweep; suggest Deep Dive only when conclusion language is detected. |
| Research docs indexed | Index `🔬 Research/` (work + personal) and `Plans/🤿 Deep Dives/` alongside plans/lists/meetings. Research docs' `domains:` frontmatter scores +4 per URL domain match in a section. |
| Research doc frontmatter | Research notes use `---` (three dashes) and include: `doctype: 🔬`, `status`, `started`, `namespace`, `description` (auto-inferred), `domains` (auto-extracted from URL content). Enrich missing descriptions + domains in Phase 4 alongside plans. |
| Personal research folder | `🏡 Personal/🏡🔬 Research/` — create on first use if absent. Same indexing and routing as work research. |
| Research doc domains update on append | When appending to an existing research doc, extract URL domains from the new content and merge (set union) into the doc's `domains:` frontmatter. Rewrite frontmatter in-place. |
| Cross-day research consolidation | Track research candidates across all days in a topic/domain cluster map. When two or more candidates share a cluster, present them as a single consolidation question before individual routing. |
| Separator headers stripped | Headers that are visual separators (`# ---`, `# ===`, `# ___`, `# ***`, or `#` followed only by punctuation) are removed during pre-parse. Content below them becomes orphan tasks or continues the previous section. |
| Orphan tasks split by domain | Top-level tasks with no section header are split into separate synthetic blocks when they span different domains (work vs personal). Each block is classified independently. |
| Meeting candidate classification | Sections with meeting keywords in the header ("Meeting Notes", "1-1", "Sync", "Catch Up", "Chat with", "Workshop") or matching a person name in the meetings index are classified as `👤 Meeting candidate` with a dedicated routing UI. |
| Meeting note creation first-class | The routing UI includes `👤 New Meeting note` as a distinct option (not just `🆕 Create plan`). Uses `🏢📝 Work Meeting Notes.md` template. Available in both meeting candidate UI and uncertain section UI. |
| Reference candidate classification | Sections with "References" or "References:" in the header are classified as `📋 Reference candidate` with a dedicated list/reference routing UI that surfaces list files first. |
| List/reference file creation first-class | The routing UI includes `📋 New List/Reference file` as a distinct option. Creates `🏢📋 References[{Qualifier}].md` or `🏡📋 References[{Qualifier}].md` with minimal frontmatter. |
| EarlBear indexed | `👥 EarlBear/📆 Plans/` is always indexed alongside work + personal plans. EarlBear content detected by `👥` emoji, "EarlBear" keyword, `[[👥...]]` wikilinks, or "Saad" name. Routes to personal target (next Sunday). |
| EarlBear plan naming | Uses work-like convention: `👥YYMMDD{workstream} Title.md`, `namespace: 👥`, workstream subdirs under `📆 Plans/`. Same frontmatter as work plans but with `namespace: 👥`. |
| EarlBear meetings indexed | `👥 EarlBear/👥👤 Meetings/` is indexed alongside work meetings. EarlBear meeting files use `👥 YYMMDD Title.md` naming with `namespace: 👥`. Route EarlBear meeting content here, not to `📆 Plans/`. |
| EarlBear future expansion | When EarlBear volume grows, consider adding `👥📋 Lists/`, `👥🔬 Research/`, and potentially its own sweep mode with a dedicated target day. Revisit each sweep. |
| People Index — storage | Persisted in `🏢📋 References[People].md` (work) and `👥📋 References[People].md` (EarlBear). Read at Phase 3 start; written back at Phase 8. Each entry: person name, domain (🏢/👥/personal), role, and a list of associated plan wikilinks. |
| People Index — building | Phase 3: invert `contributors:` from all plan frontmatter into a `{person → [plans]}` map. Merge with the stored file. Display the full map to the user after Phase 3. |
| People Index — routing | Person name in a section is a **scoring hint**, not a hard route. Boosts associated plans in scoring. If person maps to exactly one plan → `✅ Confident`. If 2+ plans → `❓ Uncertain` with their plans surfaced first; other signals (wikilinks, emoji, content) break the tie. |
| People Index — new person | When a person appears in a section who is NOT in the People Index, ask: ServiceNow / EarlBear / personal friend / other. Answer determines which plan index to search for routing. After routing, add person to matched plan's `contributors:` frontmatter and update the index file. |
| People Index — organize signal | When reorganizing a large note or plan file into sub-headers, consult the People Index: a person's presence in a task block is a signal for which initiative/sub-section it belongs to. |
| Voice note detection | Lines >200 chars with <3 sentence boundaries, `￼` characters, phonetic misspellings, filler phrases, or run-on connectors are classified as `🎤 Voice note`. Requires 2+ signals. |
| Voice note processing | Voice notes are cleaned before routing: break into sentences, fix phonetic→technical errors (JSON, byte, base64, Claude), strip filler, structure into tasks/bullets. Present before/after via AskUserQuestion. User confirms cleaned or raw version. |
| Voice note is the one content edit exception | Voice note cleaning is the only case where content is modified during sweep. The raw transcription is preserved in the breadcrumb table Summary column for traceability. User must explicitly confirm the transformation. |
| Categorized Unsorted sub-sections | After Phase 7b routing, restructure remaining Unsorted items into categorized sub-sections (📋 References, 💬 Comms, 👨‍👩‍👧‍👦 Family, 🏠 Home, 💼 Work, 💡 Ideas). Only create categories with ≥1 item. Present restructured layout for confirmation. |
| Project subfolders supported | Workstream dirs can contain **project subfolders** (e.g. `🧑🏻‍💻 Development/🤖 Config Agent/`) to group related plans. Plans in project subfolders use the **project emoji** in their filename (e.g. `🏢260302🤖 Title.md`) instead of the parent workstream emoji. The `workstream` frontmatter still reflects the parent workstream (`🧑🏻‍💻`). When routing content, prefer project subfolder matches when the section's content/wikilinks clearly relate to a specific project. When creating new plans, list project subfolders as placement options. Discover project subfolders dynamically — never hardcode. |
| Ad-hoc script temp dir | When writing ad-hoc Python scripts during the sweep (for operations the CLI doesn't yet support), write them to `$NOTEPLAN_ROOT/.sweep-scripts/{TIMESTAMP}/` and log the filename + purpose. After the sweep completes, evaluate these scripts for CLI extension candidates. |
| Self-healing after sweep | After completing a sweep, if gaps/improvements were identified, offer to update the skill source at `~/workspace/oeid-claude-plugin-marketplace/`. Never edit cache files. Workflow: edit SKILL.md → bump version → git push → `make update`. Do not self-heal mid-sweep. |
| Skill source is the git repo | The authoritative skill source is `~/workspace/oeid-claude-plugin-marketplace/plugins/noteplan-manager/skills/sweep-daily-notes/SKILL.md`. The cache at `~/.claude/plugins/cache/` is read-only and overwritten on reinstall. |

---

## Phase 9: Dashboard + Review Pipeline

Phase 9 runs after Phase 8.5 on every sweep. It generates the sweep review diff, mines conversations, refreshes all dashboards, and opens the final output. All steps run sequentially; failures are non-blocking (log and continue).

### 9.1 — Sweep commit + review

```bash
cd "$NOTEPLAN_ROOT"

# Commit any remaining uncommitted changes (idempotent — no-op if clean)
noteplan-sweep sweep-commit

# Generate immutable HTML diff snapshot for this sweep
noteplan-sweep sweep-review-generate

# Show the diff range (base commit → HEAD) used for this snapshot
noteplan-sweep sweep-review-diff-range

# Flag thin-coverage files (B-16 risk — sections swept in prior runs may not appear in this diff)
noteplan-sweep sweep-diff-coverage
```

If `sweep-diff-coverage` reports any **⚠ THIN** files, show the user:
> "⚠ Some calendar files have thin diff coverage — sections may have been swept in a prior run and won't appear in the diff. The audit uses disk-confirmation (B-16) to handle these automatically. No manual action needed unless you want to re-generate with a wider `--base-commit`."

```bash
# Run data quality audit — authoritative row classification
noteplan-sweep sweep-review-audit
```

If the audit reports **anomaly count > 0**, run diagnose to get root cause labels:

```bash
noteplan-sweep sweep-review-diagnose --show anomaly
```

Diagnose output labels each row as one of: `B-14 new_file`, `B-13 claimed`, `B-16 disk_confirmed`, `V-47 scope miss`, or `genuine anomaly`. Only rows labelled **genuine anomaly** need user attention — present those to the user. All other labels are automatically resolved by the audit.

```bash
# Compile snapshot + any existing comments into review.html
noteplan-sweep sweep-review-compile

# Open the compiled review in browser
noteplan-sweep sweep-review-open
```

### 9.2 — Conversation mining

```bash
# Parse Claude transcripts, cross-map to plans, write discovered_ideas.json
noteplan-sweep conversation-mine
```

### 9.3 — Dashboard refresh

```bash
# Rebuild the conversation knowledge graph (fast: ~0.5s + 0.2s)
noteplan-sweep graph-extract             # Session/Plan/Repo/Skill/UseCase/App nodes + edges
noteplan-sweep graph-build               # validate + write embedding_meta to graph.json

# Regenerate Insights Hub (brag, observations, gaps, impact, AI tile, hub nav tiles)
noteplan-sweep work-board-generate

# Regenerate Contributions dashboard (commit heatmap, work logs, shipped plans)
noteplan-sweep contributions-generate

# Regenerate AI Usage dashboard (injects updated graph.json into D3 pane)
noteplan-sweep ai-usage-generate

# Regenerate Plans Dashboard (uses discovered_ideas.json from step 9.2, --skip-mine)
noteplan-sweep dashboard-generate --skip-mine

# Open Insights Hub in browser (central gallery)
noteplan-sweep work-board-open
```

### 9.4 — Repo scan + Embedding (weekly, not every sweep)

Run once per week or after adding a new AI-assisted project:

```bash
# Re-scan repos to pick up new AI-assisted projects
noteplan-sweep repo-scan
noteplan-sweep ai-usage-generate         # re-generate to include new repo data
noteplan-sweep contributions-generate    # re-generate to include updated AI commit data

# Optional: embed nodes for vector search (requires LM Studio running)
# noteplan-sweep graph-embed
# noteplan-sweep graph-query-vec "config agent planning sessions"
```

### Phase 9 checklist

- [ ] `sweep-commit` — changes committed
- [ ] `sweep-review-generate` — diff snapshot written to `sweeps/`
- [ ] `sweep-review-diff-range` — diff range logged, commits shown
- [ ] `sweep-diff-coverage` — thin-coverage files flagged (if any)
- [ ] `sweep-review-audit` — row classification verified, anomaly count checked
- [ ] *(if anomaly > 0)* `sweep-review-diagnose --show anomaly` — root cause labels shown; only genuine anomalies escalated to user
- [ ] `sweep-review-compile` — compiled review HTML ready
- [ ] `sweep-review-open` — review opened in browser
- [ ] `conversation-mine` — transcripts mined, discovered_ideas.json updated
- [ ] `graph-extract` + `graph-build` — conversation graph rebuilt
- [ ] `work-board-generate` — Insights Hub HTML refreshed
- [ ] `contributions-generate` — Contributions HTML refreshed
- [ ] `ai-usage-generate` — AI Usage HTML refreshed (with fresh graph)
- [ ] `dashboard-generate --skip-mine` — Plans Dashboard HTML refreshed
- [ ] `work-board-open` — Insights Hub visible in browser
- [ ] *(weekly)* `repo-scan` — repos re-scanned for new AI projects

---

## Safety

- Pre-commit snapshot before any file changes
- Checkpoint commit after each day
- Line-level Python diff validation before final commit
- Offer rollback to pre-sweep snapshot if integrity check fails
- Use task tracking for full auditability

---

## Self-Healing: Updating This Skill

This skill lives in a git-managed plugin marketplace. When the skill encounters a gap, bug, or feature request during a sweep, it can update itself.

**Source location** (the ONLY place to edit):
```bash
PLUGIN_REPO="$HOME/workspace/oeid-claude-plugin-marketplace"
SKILL_PATH="$PLUGIN_REPO/plugins/noteplan-manager/skills/sweep-daily-notes/SKILL.md"
VERSION_PATH="$PLUGIN_REPO/plugins/noteplan-manager/.claude-plugin/plugin.json"
```

**DO NOT edit files under `~/.claude/plugins/cache/`** — cache files are overwritten on reinstall.

### When to self-heal

After completing a sweep, if the assistant identified:
- A classification gap (section type not handled)
- A routing UI improvement (missing option, better defaults)
- A new rule discovered during user interaction
- A false positive in the integrity check
- A new domain/category for Unsorted sub-sections

...then offer to update the skill:

```javascript
AskUserQuestion({
  questions: [{
    question: `During this sweep, I identified ${N} potential skill improvements:\n\n${improvements.map(i => `- ${i}`).join('\n')}\n\nShould I update the sweep skill?`,
    header: "Self-heal",
    options: [
      { label: "Update + reinstall", description: "Edit SKILL.md, bump version, push, reinstall" },
      { label: "Skip for now", description: "Note improvements but don't modify the skill" }
    ],
    multiSelect: false
  }]
})
```

### Self-heal workflow

1. **Edit** the source SKILL.md at `$SKILL_PATH` (never the cache)
2. **Bump the version** in `$VERSION_PATH` (patch for fixes, minor for new features):
   ```bash
   cd "$PLUGIN_REPO"
   # Read current version, increment appropriately
   python3 -c "
   import json
   with open('plugins/noteplan-manager/.claude-plugin/plugin.json') as f:
       data = json.load(f)
   v = data['version'].split('.')
   v[1] = str(int(v[1]) + 1)  # minor bump
   v[2] = '0'
   data['version'] = '.'.join(v)
   with open('plugins/noteplan-manager/.claude-plugin/plugin.json', 'w') as f:
       json.dump(data, f, indent=2, ensure_ascii=False)
   print(f'Bumped to {data[\"version\"]}')"
   ```
3. **Commit and push** the plugin repo:
   ```bash
   cd "$PLUGIN_REPO"
   git add plugins/noteplan-manager/
   git commit -m "feat(noteplan-manager): <describe change>"
   git push
   ```
4. **Reinstall** using `make update`:
   ```bash
   cd "$PLUGIN_REPO"
   make update
   ```
5. **Verify** the new version is installed:
   ```bash
   ls ~/.claude/plugins/cache/oeid-claude-plugins/noteplan-manager/
   ```
6. Report: "Skill updated to vX.Y.Z. Restart Claude Code to apply."

### What NOT to self-heal

- Do not modify the skill mid-sweep — finish the sweep first, then update
- Do not change routing logic without user confirmation
- Do not remove rules — only add or refine
- Do not update if the user says "Skip for now"
