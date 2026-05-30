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

**MANDATORY**: Use `TaskCreate` and `TaskUpdate` for every phase. Create ALL phase tasks at the start of the session (before Phase 2), with `blocked_by` dependencies set. This gives the user live visibility into sweep progress.

**Create all tasks upfront** (before doing anything else):

```javascript
// Example — create all in one shot at session start
t1 = TaskCreate({ title: "Phase 1: Ask mode", status: "in_progress" })
t2 = TaskCreate({ title: "Phase 2: Pre-sweep git pull + commit", status: "todo", blocked_by: [t1.id] })
t3 = TaskCreate({ title: "Phase 3: Build plan + lists + meetings + thoughts index", status: "todo", blocked_by: [t2.id] })
t4 = TaskCreate({ title: "Phase 4: Enrich missing descriptions + contributors", status: "todo", blocked_by: [t3.id] })
t5 = TaskCreate({ title: "Phase 5: Discover daily notes in scope", status: "todo", blocked_by: [t4.id] })
t6 = TaskCreate({ title: "Phase 6: Day-by-day guided sweep", status: "todo", blocked_by: [t5.id] })
t7 = TaskCreate({ title: "Phase 7: Validate via git diff", status: "todo", blocked_by: [t6.id] })
t7b = TaskCreate({ title: "Phase 7b: Post-sweep Unsorted review", status: "todo", blocked_by: [t7.id] })
t8 = TaskCreate({ title: "Phase 8: Final commit + push", status: "todo", blocked_by: [t7b.id] })
t85 = TaskCreate({ title: "Phase 8.5: Self-knowledge + brag sheet capture + push", status: "todo", blocked_by: [t8.id] })
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

Report: "Found N recently-touched plans + M list files + K meeting files + J thought files + R research docs." List all with descriptions.

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

For each research doc in the research index:

1. **Extract domains**: Scan the full body for all URLs. Extract unique hostname domains (strip `www.`, keep the meaningful part: `code.devsnc.com`, `servicenow.com`, `fluidtopics.com`). Write/update the `domains:` frontmatter list — merge with any already present.
2. **Infer description** (if missing): Summarize from H1 + first paragraph + domain list. E.g. `"Mapping available ServiceNow documentation APIs, PPM project hierarchy, and content connectors for the graph builder agent."`. Write to `description:` frontmatter.
3. Include research doc enrichment in the same bulk commit as plan descriptions: `chore(plans/research): add descriptions + domains to N files`

Research docs always use `---` (three dashes) for frontmatter delimiters.

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
1. Section content contains `[[PlanName]]` wikilink matching a plan in the index → `✅ Confident`
2. Section header text closely matches a plan name → `✅ Confident`
3. Section's workstream emoji matches a single plan's workstream → `✅ Confident`
4. Section mentions a person's name that appears in a plan's `contributors` field → `✅ Confident` (e.g. "Dennis 1-1" content matching a plan with `contributors: ["Dennis"]`)
5. Section header contains meeting keywords ("Meeting Notes", "1-1", "Sync", "Catch Up", "Chat with", "Workshop") OR a person's name matching a meeting file in the index → `👤 Meeting candidate` — present meeting routing UI
6. Section header contains "References" or "References:" → `📋 Reference candidate` — present list/reference routing UI
7. Section matches **2+ research signals** (see below) → `🔬 Research candidate` — present research routing UI instead of plan routing
8. Clearly personal content (shopping, errands, `[[🏡...]]` wikilinks in work mode) → `⏭️ Skip` (but see **Personal in Both mode** below)
9. Completed-task-only block → `⏭️ Skip` by default, but see **Completed task routing** below
10. Anything else → `❓ Uncertain`

**Research candidate signals** (classify `🔬` when 2+ apply):

| Signal | Example |
|---|---|
| Section header contains: Research, Deep Dive, Investigating, Exploring, Landscape, Survey, Notes on, Background, Docs for, Overview | `# Researching Docs for Graph Building` |
| 3+ URLs present, concentrated on 1–2 domains | 10 `code.devsnc.com` + `servicenow.com` links |
| Zero `- [ ]` tasks — prose and/or links only | No tasks in section |
| Investigative language: "What does X mean", "context for", "overview of", "how does X work", "important context" | `"What does product mean ..."` |
| Section content domain overlaps with an existing research doc's `domains:` frontmatter | URL from `fluidtopics.com` → matches existing research doc |
| Conclusion language: "decided to use", "conclusion:", "final approach:", "we will use X" | → flag as **concluded** → prefer Deep Dive destination |

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
  👤 {p} meeting candidate(s) — will ask to route to meeting file
  📋 {q} reference candidate(s) — will ask to route to list file
  🔬 {r} research candidate(s) — will ask to route to research doc or deep dive
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
- Personal plan: `$PLAN_ROOT/Present/{plantype_dir}/` (match the existing subdir for that plantype emoji)
- Work meeting: `$NOTES_ROOT/🏢 ServiceNow/👤 Meetings/` (root or `1-1s/` subdir as appropriate)

Discover the correct subdir by listing the directory — never hardcode.

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

## From {YYYY-MM-DD}
{content verbatim}
```

**Path B — Deep Dive plan** (concluded research, decision reached, goal achieved):

- Filename: `🏢{YYMMDD}🤿 {Title}.md` (work) / `🏡{YYMMDD}🔍 {Title}.md` (personal — use Discovering emoji)
- Location: `Plans/🤿 Deep Dives/` (discover the subdir — never hardcode)
- Use the standard plan template (`🏢📆 Work Plan.md`) with `workstream: 🤿`
- Add `domains:` field to frontmatter (same auto-extraction as research notes)
- Content placed after the `* [ ]` boilerplate line (same as any new plan)

**Appending to an existing research doc** (when user routes to an existing `🔬` entry):
- Append content under `## From {fileDate}` sub-header (same as plans)
- **Also update `domains:` frontmatter**: extract URL domains from the newly appended content, merge (set union) with existing `domains:` list, rewrite frontmatter in-place
- Do NOT rewrite `description:` on append — only set at creation

Add the new research doc to the research index so it's available for the rest of the sweep.

### Step 6e — Execute the confirmed plan

After the user confirms the day's routing plan:

For each section confirmed for moving:
- **To target daily note**: append verbatim under `# [[PlanName]]` header in `$CALENDAR_ROOT/<TARGET_DATE>.md`
  - Merge under existing header if already present; create if not
  - **Same-plan sections from different parts of the source day get merged** under one header
  - Prefix the moved block with a `## From {fileDate}` date sub-header so content origin is traceable
- **To existing plan file (direct)**: append verbatim after existing content in the plan, under a `## From {fileDate}` sub-header
- **To new plan file**: append verbatim after the opening `* [ ]` line in the new plan (no date sub-header needed — the plan's `started:` field captures this)
- **To existing research doc**: append verbatim under `## From {fileDate}` sub-header; also update `domains:` frontmatter with any new URL domains from the appended content (set union, rewrite frontmatter in-place)
- **To new research note**: content is placed after the opening H1 in the new research doc (Step 6d handled creation)
- **To meeting file**: append verbatim under a `## {YYYY-MM-DD} Notes` sub-header in the meeting file
- **Unsorted**: append under `# Unsorted` in the target note (no date sub-header needed in Unsorted)
- **Remove** from source: all content lines AND their section header (`# SectionName`). Do NOT move the original section header to the target — the target gets `# [[PlanName]]` instead.
- **Split sections**: when individual lines within a section go to different plans, remove the section header and each line individually, routing each line to its designated plan header.
- **Leave a swept breadcrumb in the source note**: after all sections for a day are moved, append a markdown table at the end of the source daily note so the user can trace where content went. Use `[[YYYY-MM-DD]]` wikilinks for daily note references and `[[PlanName]]` wikilinks for plan references so they're clickable in NotePlan. Format:
  ```
  ---
  | Swept | Section | Summary | Destination |
  |-------|---------|---------|-------------|
  | {YYYY-MM-DD} | PlanName | {section1 name}, {section2 name} | [[PlanName1]] |
  | {YYYY-MM-DD} | Errands | {count} errand tasks | [[{TARGET_DATE_ISO}]] Errands |
  | {YYYY-MM-DD} | Unsorted | {section name} | [[{TARGET_DATE_ISO}]] Unsorted |
  | {YYYY-MM-DD} | 1-1 Notes | meeting notes | [[{MEETING_DATE_ISO}]] |
  ```
  Where `{TARGET_DATE_ISO}` is `YYYY-MM-DD` (e.g. `[[2026-03-15]]`). Only list destinations where content was actually moved. Skip skipped sections. The breadcrumb is the one exception to "no new content in source" — it is allowed because it is a reference to swept content, not content itself.

  **When the source note is swept again on a later date**: check if a breadcrumb table already exists. If so, **append new rows** to the existing table rather than creating a second table. This ensures the full sweep history for a note is visible in one table.

  Update the `is_allowed_new` check in Phase 7 to permit lines matching `^\| ` (table rows) and `^\| Swept ` (table header).

**Wikilink todos are ordinary content:** Tasks whose body is a wikilink (e.g. `- [ ] [[PlanName]]`) are moved verbatim exactly like any other task line. The wikilink in the body is the routing signal, but the full line (including `- [ ]` prefix) is preserved as-is.

**Personal content in work mode:** Sections that are clearly personal (shopping, errands, `[[🏡...]]` namespace wikilinks, personal names unrelated to work) should be flagged as `⏭️ skip — personal content` and left in the source. Do not ask the user about them unless the content is ambiguous.

**No content modification rule:** Copy every line exactly as-is. Preserve all leading whitespace / indentation. The only new text introduced is:
- `# [[PlanName]]` headers in the target note
- `## From {fileDate}` sub-headers when appending to an existing plan, research doc, or target daily note
- `## {YYYY-MM-DD} Notes` sub-headers when appending to a meeting file
- `# Unsorted` header (if needed)
- The plan file boilerplate when creating a new plan
- The research doc frontmatter + H1 when creating a new research note or deep dive

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
    # Skip today's note (it may have new content added post-sweep)
    if today_date and today_date in current_file:
        continue

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

5. For each block the user routes: move it out of Unsorted and append it under the appropriate `# [[PlanName]]` header in the same target note (with a `## From Unsorted` sub-header)
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

---

## Phase 8: Final Commit + Push

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

**Also update `🏡📋 Habits.md`** in `$NOTES_ROOT/🏡 Personal/🏡📋 Lists/`:

1. Read the current `🏡📋 Habits.md` file
2. Scan notes read during this sweep for habit signals:
   - **Observed habits**: tasks done repeatedly, check-ins with habit trackers, routine references (prayer, exercise, journaling) → update the `## ✅ Current Habits (Observed)` table with the `Last Seen` date and a frequency estimate
   - **Aspired habits**: tasks phrased as "I want to…", "Start doing…", or explicit habit goals not yet consistent → add rows to `## 🌱 Habits I Want to Build` if not already present
   - **Habit reflections**: self-commentary about habits, scope overload signals, seasonal resets (Ramadan, New Year, etc.) → append to `## 💡 Habit Reflection Notes`
3. Write the updated file back (preserve existing entries — only add new rows or update `Last Seen` / frequency on existing ones)

**Also update the Brag Sheets** using TaskCreate to make the update visible:

1. Create two tasks before updating:
   ```javascript
   TaskCreate({ title: "Update work brag sheet (sweep {YYYY-MM-DD})", status: "in_progress" })
   TaskCreate({ title: "Update personal brag sheet (sweep {YYYY-MM-DD})", status: "in_progress" })
   ```

2. **Work brag sheet** — `$NOTES_ROOT/🏢 ServiceNow/📋 Lists/🏢📋 Brag Sheet.md`
   - Create if it doesn't exist with header:
     ```markdown
     # 🏢📋 Brag Sheet

     A running log of work achievements, impact, and value delivered.
     Updated each sweep — use this at review time to justify your impact.
     ```
   - Append under a `## {YYYY} Q{Q}` quarter header (create if absent), then a `### {YYYY-MM-DD} Sweep` sub-header:
     ```markdown
     ### {YYYY-MM-DD} Sweep

     - [concrete achievement bullet — what was built, shipped, or unblocked]
     - [collaborator impact — e.g. "Supported Dennis in ATF eval design"]
     - [metric or milestone if visible — e.g. "A2A POC moved to pilot framing"]
     ```
   - Write **only verifiable, concrete achievements** from the notes read — no speculation
   - Focus on: shipped features/POCs, unblocked collaborators, delivered demos, architectural decisions made, external recognition

3. **Personal brag sheet** — `$NOTES_ROOT/🏡 Personal/🏡📋 Lists/🏡📋 Brag Sheet.md`
   - Create if it doesn't exist with header:
     ```markdown
     # 🏡📋 Brag Sheet

     A running log of personal achievements, milestones, and skills developed.
     Updated each sweep.
     ```
   - Same format: `## {YYYY} Q{Q}` → `### {YYYY-MM-DD} Sweep`
   - Focus on: personal projects launched/progressed, new tools built, family milestones, spiritual growth, skills deepened

4. Mark both brag sheet tasks `completed` after writing.

- Commit and push after writing all reflection files and brag sheets:
  ```bash
  git add -A
  git commit -m "reflect(sweep): add {YYYY-MM-DD} self-knowledge observations + habits update"
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
| Date annotation on moved blocks | When appending to an existing plan or target daily note, prefix each moved block with `## From {fileDate}` so content origin is traceable. Omit for new plan files (the `started:` field serves this purpose). |
| User notes are authoritative | Free-text notes in AskUserQuestion answers override scoring. Re-score the plan index against the user's clarification before presenting the next question. |
| Post-sweep Unsorted review | After integrity check, review EVERY Unsorted block individually — one AskUserQuestion per block with top-3 plan suggestions. Ask "keep or move?" for each. Runs whenever any Unsorted content exists. |
| Templates must be read first | Before creating any new plan, meeting, or list file, read the corresponding template from `@Templates/` to verify the H1 format and frontmatter fields. |
| New plans use `---` delimiters | Created plan/meeting files MUST use `---` (three dashes) for frontmatter. Templates themselves use `--` (two dashes) — do not copy that into the created file. |
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
| Habits tracking in sweep | Phase 8.5 also updates `🏡📋 Habits.md`: scan swept notes for habit signals (observed habits, aspired habits, habit reflections). Update `Last Seen` and frequency on existing rows; add new rows for newly spotted habits. |
| Brag sheets via tasks | Phase 8.5 updates two brag sheets using TaskCreate: `🏢📋 Brag Sheet.md` (work) and `🏡📋 Brag Sheet.md` (personal). Create a task per sheet before updating, mark completed after. Only concrete, verifiable achievements from the swept notes. |
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

---

## Safety

- Pre-commit snapshot before any file changes
- Checkpoint commit after each day
- Line-level Python diff validation before final commit
- Offer rollback to pre-sweep snapshot if integrity check fails
- Use task tracking for full auditability
