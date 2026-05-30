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
3. Build plan index + lists + meetings + thoughts index (blocked by 2)
4. Enrich missing descriptions + contributors (blocked by 3)
5. Discover daily notes in scope (blocked by 4)
6. Day-by-day guided sweep (blocked by 5) — **one sub-task per day** (see below)
7. Validate via git diff (blocked by 6)
7b. Post-sweep Unsorted review (blocked by 7) — only if Unsorted grew during sweep
8. Final commit (blocked by 7b)
8.5. Self-knowledge capture (blocked by 8)

### Per-day task checklist

When starting each day in Phase 6, create a sub-task (or list the checklist inline) with these required steps:

- [ ] Read daily note
- [ ] Classify all sections (confident / uncertain / skip / personal-in-work)
- [ ] Route all uncertain sections (one AskUserQuestion per uncertain section)
- [ ] Present final routing plan and confirm
- [ ] Execute: move all sections, create new plans/meetings if needed
- [ ] Verify source note has only completed tasks + kept content remaining
- [ ] Checkpoint commit

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

## Phase 3: Build Plan Index + Lists Index

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
6. Extract `contributors` if present in frontmatter — used as a routing signal (see Step 6b)

Build a compact plan index (metadata only, no content):

```
[
  {
    "filename_stem": "🏢260302🧑🏻‍💻 POC Establishing A2A Poc",
    "path": "/full/path/to/file.md",
    "workstream_or_plantype": "🧑🏻‍💻",
    "status": "🟢",
    "description": "...",
    "description_missing": true/false,
    "contributors": ["Dennis", "Arish"]   // optional
  }
]
```

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

Report: "Found N recently-touched plans + M list files + K meeting files + J thought files." List all with descriptions.

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
4. Section mentions a person's name that appears in a plan's `contributors` field → `✅ Confident` (e.g. "Dennis 1-1" content matching a plan with `contributors: ["Dennis"]`)
5. Clearly personal content (shopping, errands, `[[🏡...]]` wikilinks in work mode) → `⏭️ Skip` (but see **Personal in Both mode** below)
6. Completed-task-only block → `⏭️ Skip` by default, but see **Completed task routing** below
7. Anything else → `❓ Uncertain`

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

**User notes in AskUserQuestion answers are authoritative context.** When the user provides a free-text note alongside their answer (e.g. "this is billing for Lana's daycare" or "this is part of me understanding servicenow"), treat it as a clarification that should immediately inform your interpretation of the content. If the note suggests a different category or plan than you had scored, re-score the plan index against the user's description and present better-matched options in the next follow-up question. Never ignore user notes.

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

**Templates location:** `$NOTES_ROOT/@Templates/`
- Work plan: `🏢📆 Work Plan.md`
- Personal plan: `🏡📆 Personal Plan.md`
- Work meeting notes: `🏢📝 Work Meeting Notes.md`

Read the appropriate template before writing any new file — always match its frontmatter structure and H1 format exactly. Templates use `--` as YAML frontmatter delimiters (two dashes).

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

# Work meeting notes:
# filename_stem = "🏢 {YYMMDD} {title}"
# e.g. "🏢 260313 Dennis 1-1"
```

**Write the new plan file** following the template output format exactly (read template first to verify current format):

*Work plan:*
```markdown
--
doctype: 📆
status: {status_emoji}
started: {YYYY-MM-DD}
namespace: 🏢
workstream: {workstream_emoji}
--
# 🏢{YYMMDD}{workstream_emoji} {title}
* [ ] Is [[🏢{YYMMDD}{workstream_emoji} {title}]] done? >{YEAR}-W{WW}
* [ ]
```

*Personal plan:*
```markdown
--
doctype: 📆
status: {status_emoji}
started: {YYMMDD}
namespace: 🏡
plantype: {plantype_emoji}
--
# 🏡{YYMMDD}{plantype_emoji} {title}
* [ ] Is [[🏡{YYMMDD}{plantype_emoji} {title}]] done? >{YEAR}-W{WW}
* [ ]
```

*Work meeting notes:*
```markdown
--
doctype: 🗒️
started: {YYMMDD}
namespace: 🏢
--
# 🏢 {YYMMDD} {title}
* [ ] Are Action Items for [[🏢 {YYMMDD} {title}]] done? >{YEAR}-W{WW}
```

**Place the file** in the correct subdirectory:
- Work plan: `$PLAN_ROOT/{workstream_dir}/` (match the existing subdir for that workstream emoji)
- Personal plan: `$PLAN_ROOT/Present/{plantype_dir}/` (match the existing subdir for that plantype emoji)
- Work meeting: `$NOTES_ROOT/🏢 ServiceNow/👤 Meetings/` (root or `1-1s/` subdir as appropriate)

Discover the correct subdir by listing the directory — never hardcode.

**Add to plan/meetings index** so it's available for the rest of the sweep.

Confirm creation to the user: "Created `[[{filename_stem}]]` at `{path}`."

The section's content will be swept into this new plan file directly (not the target daily note) — place it after the `* [ ]` task line in the new plan. This is the one case where content goes to a plan file rather than the target daily note.

### Step 6e — Execute the confirmed plan

After the user confirms the day's routing plan:

For each section confirmed for moving:
- **To target daily note**: append verbatim under `# [[PlanName]]` header in `$CALENDAR_ROOT/<TARGET_DATE>.md`
  - Merge under existing header if already present; create if not
  - **Same-plan sections from different parts of the source day get merged** under one header
  - Prefix the moved block with a `## From {fileDate}` date sub-header so content origin is traceable
- **To existing plan file (direct)**: append verbatim after existing content in the plan, under a `## From {fileDate}` sub-header
- **To new plan file**: append verbatim after the opening `* [ ]` line in the new plan (no date sub-header needed — the plan's `started:` field captures this)
- **To meeting file**: append verbatim under a `## {YYYY-MM-DD} Notes` sub-header in the meeting file
- **Unsorted**: append under `# Unsorted` in the target note (no date sub-header needed in Unsorted)
- **Remove** from source: all content lines AND their section header (`# SectionName`). Do NOT move the original section header to the target — the target gets `# [[PlanName]]` instead.
- **Split sections**: when individual lines within a section go to different plans, remove the section header and each line individually, routing each line to its designated plan header.
- **Leave a swept breadcrumb in the source note**: after all sections for a day are moved, append a brief sweep-log block at the end of the source daily note so the user can see where things went. Use `[[YYYY-MM-DD]]` wikilinks for daily note references so they're clickable in NotePlan. Format:
  ```
  ---
  *Swept {YYYY-MM-DD}:*
  - → [[PlanName1]]: {section1 name}, {section2 name}
  - → [[PlanName2]]: {section3 name}
  - → [[{TARGET_DATE_ISO}]] Errands: {count} errand task(s)
  - → [[{TARGET_DATE_ISO}]] Unsorted: {section name}
  - → [[{MEETING_DATE_ISO}]]: {meeting/1-1 section name}
  ```
  Where `{TARGET_DATE_ISO}` is `YYYY-MM-DD` (e.g. `[[2026-03-15]]`). Only list destinations where content was actually moved. Skip skipped sections. The breadcrumb is the one exception to "no new content in source" — it is allowed because it is a reference to swept content, not content itself. Update the `is_allowed_new` check in Phase 7 to permit lines matching `^- → ` and `^\*Swept ` patterns.

**Wikilink todos are ordinary content:** Tasks whose body is a wikilink (e.g. `- [ ] [[PlanName]]`) are moved verbatim exactly like any other task line. The wikilink in the body is the routing signal, but the full line (including `- [ ]` prefix) is preserved as-is.

**Personal content in work mode:** Sections that are clearly personal (shopping, errands, `[[🏡...]]` namespace wikilinks, personal names unrelated to work) should be flagged as `⏭️ skip — personal content` and left in the source. Do not ask the user about them unless the content is ambiguous.

**No content modification rule:** Copy every line exactly as-is. Preserve all leading whitespace / indentation. The only new text introduced is:
- `# [[PlanName]]` headers in the target note
- `## From {fileDate}` sub-headers when appending to an existing plan or target daily note
- `## {YYYY-MM-DD} Notes` sub-headers when appending to a meeting file
- `# Unsorted` header (if needed)
- The plan file boilerplate when creating a new plan

**Permitted task annotations (the only allowed content additions to moved lines):**

When moving a block, two types of metadata may be appended to **root-level task lines only** (lines with no leading whitespace / indentation — i.e. direct children of the section, not nested sub-tasks):

1. **Date scheduling tag** — append `>{YYYY-MM-DD}` (the target note's date, e.g. `>2026-03-20`) so the task surfaces in NotePlan's calendar view for that week and doesn't get buried silently in a plan file.
   - Format: `- [ ] Original task text >YYYY-MM-DD` (one space before `>`, **hyphens required**)
   - **CRITICAL**: NotePlan date format is `>YYYY-MM-DD` (with hyphens), NOT `>YYYYMMDD`. Tags without hyphens are silently ignored by NotePlan and will not surface in the calendar.
   - Use the **target note's date** (next Friday for work, next Sunday for personal)
   - Only on `- [ ]` or `* [ ]` lines at root indentation level

2. **Hash tags** — append relevant `#tag` labels to root-level task lines when a clear categorical tag is warranted (e.g. `#errand`, `#meeting`, `#followup`). Only add tags that are already present in the surrounding plan file or that are clearly implied by the routing destination. Never invent tags.

All other lines (nested tasks, prose, URLs, code blocks) are moved strictly verbatim with zero modification.

### Step 6f — Repair broken date tags, checkpoint commit, and advance

**Date tag repair (run after each day's sweep):** Before committing, scan ALL files touched in this day's sweep (source + targets) for broken date scheduling tags in `>YYYYMMDD` format (no hyphens) and fix them to `>YYYY-MM-DD`. This catches both newly-added tags from this sweep and any pre-existing broken tags in the files:

```bash
# Fix >YYYYMMDD to >YYYY-MM-DD in all touched files
python3 -c "
import re, sys
for path in sys.argv[1:]:
    with open(path) as f: text = f.read()
    fixed = re.sub(r'>(\d{4})(\d{2})(\d{2})', r'>\1-\2-\3', text)
    if fixed != text:
        with open(path, 'w') as f: f.write(fixed)
        print(f'Fixed date tags in {path}')
" "${TOUCHED_FILES[@]}"
```

After repair:

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
    # Skip JSON/backup files — they track system state, not user content
    if current_file.endswith('.json') or 'Backup' in current_file:
        continue
    # Skip today's note (it may have new content added post-sweep)
    if today_date and today_date in current_file:
        continue

    content = line[1:].rstrip()  # strip trailing whitespace for comparison
    if line.startswith('-'):
        removed.add(content)
    elif line.startswith('+'):
        # Normalize permitted task annotations before comparison:
        # strip trailing >YYYY-MM-DD or >YYYYMMDD date tags and #hashtags appended during the move
        # so these additions don't falsely trigger "content loss" failures
        normalized = re.sub(r'(\s+(>\d{4}-\d{2}-\d{2}|>\d{8}|#\w+))+$', '', content)
        added.add(normalized)

# today_date = current date as YYYYMMDD string, exclude from diff
today_date = __import__('datetime').date.today().strftime('%Y%m%d')

lost = removed - added
new = added - removed

# Section headers removed from source are expected — sweep removes them intentionally
lost = {l for l in lost if not re.match(r'^#', l.strip())}

# Only allowed new lines (non-content additions)
def is_allowed_new(l):
    return (
        re.match(r'^# \[\[', l) or          # wikilink section headers
        l.strip() == '# Unsorted' or
        l.strip() == '' or                   # blank lines
        re.match(r'^\* \[ \] Is \[\[', l) or # plan boilerplate
        re.match(r'^---$', l) or             # frontmatter delimiters
        re.match(r'^(doctype|status|started|namespace|workstream|plantype|contributors|description):', l) or
        re.match(r'^# [🏡🏢🔁]', l) or      # H1 for new plan files
        re.match(r'^## From \d{4}', l) or   # date annotation sub-headers
        re.match(r'^## \d{4}-\d{2}-\d{2}', l) or  # meeting date headers
        re.match(r'^#', l.strip()) or        # any section header in Unsorted context
        re.match(r'^\- → ', l) or            # swept breadcrumb destination lines
        re.match(r'^\*Swept \d{4}-\d{2}-\d{2}', l)  # swept breadcrumb header
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

---

## Phase 7b: Post-Sweep Unsorted Review

After the integrity check passes, review the accumulated `# Unsorted` content in the target notes. New plans and lists created during the sweep may now be good homes for content that couldn't be routed earlier.

**Steps:**

1. Read the `# Unsorted` section of each target note (Friday and/or Sunday)
2. For each block in Unsorted, re-score against the **full current index** (plans + lists + meetings — including newly created ones from this sweep)
3. Present re-routing suggestions:
   ```
   📋 Unsorted review: {N} blocks, {K} have potential matches now:

     Block 1: "- [ ] Make a hifz plan..." → [[🏡260304👨🏻‍💻 Claude Artifacts Planner]] (new plan from today)
     Block 2: "- [ ] Share recruiter saad" → no new match, stays Unsorted
   ```
4. Ask once per target note:
   ```javascript
   AskUserQuestion({
     questions: [{
       question: "Re-route matched Unsorted items, or leave them all?",
       header: "Unsorted review",
       options: [
         { label: "Route all suggested matches", description: "Move the K matched blocks out of Unsorted" },
         { label: "Review individually", description: "Ask about each match one at a time" },
         { label: "Leave Unsorted as-is", description: "Skip this step" }
       ]
     }]
   })
   ```
5. If "Route all" or individual review: move matched blocks out of Unsorted, append them under the appropriate `# [[PlanName]]` header in the same target note
6. **Commit** the Unsorted re-routing: `git commit -m "sweep(daily): re-route Unsorted → ${N} blocks moved to plans"`

This phase only runs if there are Unsorted items AND the full index grew during the sweep (new plans/lists created).

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

## Phase 8.5: Self-Knowledge Capture

During the sweep you've read many daily notes and observed the user's ideas, collaborators, interests, and patterns. After the final commit, synthesize what you've learned and update three structured files in the user's Reflections directory.

**Target directory:** `$NOTES_ROOT/🏡 Personal/🏡💭 Thoughts/🪞 Reflections/🏡💭💻 GenAI Thoughts/`

**Files to update (append a dated entry — do not overwrite prior entries):**

| File | What to write |
|---|---|
| `Observations.md` | Factual observations: who they work with, what they're building, recurring topics, work style |
| `Gaps.md` | Friction points, untracked areas, ideas that never became plans, recurring stuck tasks |
| `Superpowers.md` | Strengths, domains of expertise, high-engagement topics, distinctive thinking patterns |

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
- Commit after writing: `git commit -m "reflect(sweep): add {YYYY-MM-DD} self-knowledge observations"`

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
| Date annotation on moved blocks | When appending to an existing plan or target daily note, prefix each moved block with `## From {fileDate}` so content origin is traceable. Omit for new plan files (the `started:` field serves this purpose). |
| User notes are authoritative | Free-text notes in AskUserQuestion answers override scoring. Re-score the plan index against the user's clarification before presenting the next question. |
| Post-sweep Unsorted review | After integrity check, re-score Unsorted blocks against the full updated index (including new plans). Offer to re-route matched blocks. Only runs if Unsorted content exists and new plans were created. |
| Templates must be read first | Before creating any new plan, meeting, or list file, read the corresponding template from `@Templates/` to ensure correct frontmatter structure and H1 format. |
| New plans follow the template | Use the computed filename convention and frontmatter structure exactly. |
| New plan subdirs are discovered | `ls $PLAN_ROOT` to find the right workstream/plantype subdir. Never hardcode. |
| Checkpoint commits per day | Commit after each day's sweep for granular recoverability. |
| Line-level integrity check | Run the Python diff validation script before the final commit. |
| Proposal includes exact lines | Each routing entry in the final plan shows the exact lines being moved in a code block, plus destination note. |
| Uncertain sections are individual | Never bulk-ask about routing. Every uncertain/ambiguous block gets its own AskUserQuestion, one at a time, with a progress counter. |
| Top-5 routing suggestions | Score every plan against the section header + content; show only the top 5 matches. Never dump the full plan list into the routing UI. |
| Both mode supported | When mode = "Both", build both work + personal indexes. Each note's day-of-week determines which index and target to use. |
| Thoughts directory indexed | Index `🏡💭 Thoughts/💡 Ideas/` alongside plans and lists. Present as routing option for raw ideas, braindumps, and speculative product/startup thinking. |
| Meeting planning → next business day | When routing unscheduled meeting tasks from Unsorted (e.g. "Figure out meetings — Jeff, Khusbha, etc."), place them in the **next business day's daily note** (create it if needed), not in a general backlog. |
| Self-knowledge capture | After each sweep's final commit (Phase 8.5), append dated observations to `🪞 Reflections/🏡💭💻 GenAI Thoughts/Observations.md`, `Gaps.md`, and `Superpowers.md`. Only write what's verifiable from the notes read. |
| Swept breadcrumbs in source | After sweeping a daily note, append a `---` separator and a brief `*Swept YYYY-MM-DD:*` log at the end of the source file listing each destination wikilink and the section names routed there. This lets the user trace where content went without opening the target files. Update the Phase 7 `is_allowed_new` check to permit `^- → ` and `^\*Swept ` patterns. |
| NotePlan date format is `>YYYY-MM-DD` | Date scheduling tags MUST use hyphens (`>2026-03-20`), never compact (`>20260320`). Tags without hyphens are silently ignored by NotePlan. Step 6f runs a repair pass after each day to fix any broken tags in touched files. |
| Raw links are routing signals | Inspect URL domains during classification. ServiceNow instance/docs links route to matching work plans. Learning/reference URLs route to `📋 Lists/References[...]` when standalone. Standalone raw links are `❓ Uncertain` — present with domain context. |

---

## Safety

- Pre-commit snapshot before any file changes
- Checkpoint commit after each day
- Line-level Python diff validation before final commit
- Offer rollback to pre-sweep snapshot if integrity check fails
- Use task tracking for full auditability
