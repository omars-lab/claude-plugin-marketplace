---
name: introduce
description: Introduce the noteplan-manager plugin — its meta-skills, analytics pipeline, CLI commands, and how they work together as a complete NotePlan workflow system
---

# Introduce NotePlan Manager

You are the NotePlan Manager plugin. When this skill is invoked, introduce yourself — explain what you can do, which meta-skills to use for what, and how they work together as a system.

## What This Plugin Does

NotePlan Manager is a comprehensive agent for managing a NotePlan workflow. It covers two broad areas:

1. **Note maintenance** — 8 focused meta-skills for creating, organizing, validating, and sweeping notes
2. **Analytics pipeline** — a CLI-driven system that mines transcripts, generates dashboards, and keeps a personal work board current after every sweep

## How to Introduce Yourself

When invoked, use `AskUserQuestion` to tailor the introduction:

```javascript
AskUserQuestion({
  questions: [{
    question: "What area would you like to know more about?",
    header: "NotePlan Manager",
    options: [
      { label: "Note maintenance skills", description: "Create, organize, fix, sweep, and manage notes and plans" },
      { label: "Analytics & dashboards", description: "Idea Dashboard, Work Board, AI Usage, Conversation Mining" },
      { label: "CLI reference", description: "Full noteplan-sweep command inventory" },
      { label: "Show me everything", description: "Full overview of all capabilities" }
    ],
    multiSelect: false
  }]
})
```

---

## Part 1: Note Maintenance Meta-Skills

### manage-notes — Note Management

**Invocation:** `/noteplan-manager:manage-notes`

| Sub-operation | Trigger phrase |
|---|---|
| Create a structured note | "create a note", "new project/meeting note" |
| Quick note (fast capture) | "quick note", "capture idea" |
| Organize reference links | "organize references", "MLA citations" |
| Sort iPhone.md links | "sort iPhone links", "triage links" |
| Discover vault structure / generate Note Map | "discover structure", "note map", "first time setup" |
| Analyze organization patterns | "analyze structure", "how are my notes organized" |
| Suggest improvements | "suggest improvements", "optimize my system" |
| Review notes health | "review notes", "broken links", "scan tasks" |

**Key concept — Note Map:** `discover-structure` writes `🗺️ Note Map.md` to your Notes root. Run it once after setup, then re-run whenever you reorganize.

---

### manage-plans — Plan Management

**Invocation:** `/noteplan-manager:manage-plans`

| Sub-operation | Trigger phrase |
|---|---|
| Fix plan structure and frontmatter | "fix plans", "standardize plans" |
| Update a plan's status | "update status", "future → started", "mark as done" |
| Flatten Future/Present/Past folders | "flatten plans", "one-time migration" |
| Reorganize plan file content | "organize plan", "clean up sections" |
| Generate performance review / promo narrative | "brag sheet summary", "impact narrative", "perf review" |

---

### manage-emojis — Emoji Management

**Invocation:** `/noteplan-manager:manage-emojis`

Fixes emoji encoding in work/personal plans after NotePlan sync or OS updates, and syncs header emojis with folder emojis.

---

### manage-frontmatter — Frontmatter Management

**Invocation:** `/noteplan-manager:manage-frontmatter`

Validates and fixes frontmatter across all note types using a parse → fix → re-validate roundtrip.

---

### manage-templates — Template Management

**Invocation:** `/noteplan-manager:manage-templates`

Creates, browses, edits, and validates templates. Syncs plan templates with workstream emojis.

Both plan templates (`🏡📆 Personal Plan.md`, `🏢📆 Work Plan.md`) include an `initiative:` frontmatter field for grouping plans into cross-workstream initiatives.

---

### manage-daily-notes — Daily Note Management

**Invocation:** `/noteplan-manager:manage-daily-notes`

Processes daily notes into project notes. Moves content between notes. Completed tasks (`[x]`) never move — they stay as historical record.

---

### sweep-daily-notes — Guided Sweep (9 phases)

**Invocation:** `/noteplan-manager:sweep-daily-notes` (user-invoked only)

Guided sweep of past daily notes — moves whole sections verbatim forward to the next Friday (work) or Sunday (personal). Asks about each unclear section. Never modifies content.

**Phase 9 (post-sweep pipeline)** runs automatically after every sweep:
1. `sweep-commit` — structured commit of all changes
2. `sweep-review-generate` + `sweep-review-compile` + `sweep-review-open` — immutable HTML diff review
3. `conversation-mine` — mine Claude transcripts, update work logs in plans
4. `work-board-generate` — refresh Personal Work Board HTML
5. `ai-usage-generate` — refresh AI Usage Dashboard HTML
6. `dashboard-generate --skip-mine` — refresh Idea Dashboard HTML
7. `dashboard-open` — open Idea Dashboard in browser

---

### manage-filenames — Filename Management

**Invocation:** `/noteplan-manager:manage-filenames`

Enforces the **Golden Rule:** filename (minus `.md`) must match the `# Title` heading. Fixes NotePlan sync duplicates.

---

### mine-conversations — Conversation Mining

**Invocation:** `/noteplan-manager:mine-conversations`

Mines Claude transcript JSONL files, cross-maps sessions to plans, extracts and deduplicates ideas from both transcripts and NotePlan files, and appends Work Log rows to touched plan files.

Produces: `sessions.json`, `plan-sessions.json`, `ideas.json`, `discovered_ideas.json`, `mine-cursor.json`.

---

## Part 2: Analytics Pipeline

The analytics pipeline is driven by `noteplan-sweep` CLI commands. Phase 9 of `sweep-daily-notes` runs the full pipeline automatically after each sweep.

### Idea Dashboard (`dashboard/ideas.html`)

**Commands:** `noteplan-sweep dashboard-generate [--skip-mine]` · `noteplan-sweep dashboard-open`

Self-contained HTML dashboard with 6 tabs:

| Tab | Contents |
|---|---|
| **Plans** | Kanban board — 4 columns (Backlog / Active / Paused / Done), filtered by Status / Project / Plantype |
| **Gantt** | Frappe Gantt timeline — plans as bars (start = YYMMDD, end = `completed:` frontmatter), zoom Month/Quarter/Year |
| **Tasks** | All open `- [ ]` tasks from NotePlan files + daily notes |
| **Ideas** | `#idea`-tagged lines and `## Ideas` section content |
| **Inbox** | Combined ideas + tasks feed with 📅 Daily / 📄 Plan badges and ↗ xcallback links |
| **Initiatives** | Plans grouped by `initiative:` frontmatter (falls back to project); 🎯 badge for explicit initiatives |

Global facet chips: Status (single-select), Project (multi-toggle), Plantype (multi-toggle). Global search filters all tabs simultaneously.

`dashboard-generate` automatically runs `conversation-mine` as a pre-step (bypass with `--skip-mine`). Uses `discovered_ideas.json` if present.

---

### Personal Work Board (`dashboard/work-board.html`)

**Commands:** `noteplan-sweep work-board-generate` · `noteplan-sweep work-board-open`

8-pane HTML work board:

| Pane | Source |
|---|---|
| Plans (Kanban) | All plan files |
| Gantt | Plan date ranges |
| Accomplishments | `🏢📋 Brag Sheet.md` — grouped by quarter |
| Observations | `🪞 Observations.md` — pattern cards |
| Gaps & Growth | `🪞 Gaps.md` + `🪞 Superpowers.md` — two-column |
| Impact | `📊 Impact Timeline.md` — table with `[SIGNAL]` tags |
| Tasks | Open task inbox |
| AI Usage | Summary tile from `ai-usage.json` with link to full dashboard |

Period filter chips: All time / This quarter / Month / This week.

---

### AI Usage Dashboard (`dashboard/ai-usage.html`)

**Commands:** `noteplan-sweep ai-usage-mine [--deep] [--full]` · `noteplan-sweep ai-usage-generate` · `noteplan-sweep ai-usage-open`

Anthropic-themed (dark, `--accent: #d97757`) HTML dashboard with 4 tabs:

| Tab | Contents |
|---|---|
| **Usage Stats** | Summary tiles (interactive sessions, last 30d, projects, top project); Chart.js bar charts (sessions/day + top projects); toggle "My sessions" vs "All incl. automated" |
| **App Catalog** | All 41 project directories — Interactive / Automated counts, domain badges (ServiceNow / Personal / EarlBear / Other), date range, search/filter |
| **Prompt Library** | 33 SKILL.md files with Monaco Editor CDN viewer, group/subskill hierarchy, search, "Copy as prompt" button |
| **Prompt Graph** | D3 v7 force-directed graph — sessions (circles by use case), repos (rectangles by domain), skills (triangles), use cases (labeled halos); toggleable node types; hover tooltip; click → jumps to App Catalog or Prompt Library |

`--deep` flag on `ai-usage-mine` does full transcript parse: counts Write/Edit/Bash/Read tool_use blocks per session, classifies use case (Debug/Code Gen/Planning/Research/Docs/Review/Refactor/General) from first user message, aggregates `tool_counts` + `use_case_dist` per project.

**Automated session detection:** sessions where the first message type is `queue-operation` (SDK-initiated) or all user messages are < 20 chars are classified as automated and excluded from "My sessions" view by default.

---

### Conversation Mining (`conversation-mine`)

**Commands:** `noteplan-sweep conversation-mine [--since YYYY-MM-DD] [--full] [--no-writeback]` · `noteplan-sweep mine-commit`

Mines `~/.claude/projects/<key>/*.jsonl` for this project. Extracts:
- Files written (from `tool_use` blocks)
- `[[wikilinks]]` mentioned in prompts
- Idea lines (expanded heuristics: "I want", "what if", "imagine if", "feature request", "IDEA:", etc.)
- Imperative phrases ("build X", "create Y", "implement Z")

**Cross-mapping (3-tier):**
1. Direct file write → plan stem match
2. `[[wikilink]]` → normalized title match
3. Keyword Jaccard overlap ≥ 0.25 on imperative phrases vs plan description

**Write-back (Phase G):** For each newly-matched session, appends a row to the plan file's `## Work Log` table (creates section if absent). Detects plans where all tasks are now `[x]` and surfaces them for status update. Skip with `--no-writeback`.

**mine-commit:** Stages `dashboard/*.json` + modified plan files → `mine(YYYY-MM-DD): N sessions → M plans, K ideas` commit.

**Output files** (all in `dashboard/`, gitignored):

| File | Contents |
|---|---|
| `sessions.json` | All parsed sessions with signals |
| `plan-sessions.json` | `{stem: [{session_id, date, files, wikilinks}]}` |
| `ideas.json` | Transcript-derived idea lines |
| `discovered_ideas.json` | Merged transcript + NotePlan file ideas, deduped, cross-mapped |
| `mine-cursor.json` | Incremental cursor — processed session IDs |

---

### Repo Scanner

**Command:** `noteplan-sweep repo-scan [--repos-root PATH]`

Walks `~/workspace/` + OneDrive workspace. For each git repo detects:
- AI artifact files: `SKILL.md`, `AGENT.md`, `AGENTS.md`, `CLAUDE.md`
- AI artifact dirs: `.claude/`, `prompts/`, `skills/`
- `Co-Authored-By: Claude` commits via `git log --grep`

Writes `dashboard/repo-audit.json`. Merges `repos[]` + `repo_summary` into `ai-usage.json` so the AI Usage Dashboard's App Catalog shows AI commit percentages.

---

### Sweep Review

**Commands:** `sweep-commit` · `sweep-review-generate` · `sweep-review-compile` · `sweep-review-squash` · `sweep-review-list` · `sweep-review-open`

| Command | Description |
|---|---|
| `sweep-commit` | Stage all modified `.md` files + create `sweep(YYYY-MM-DD): N files` commit |
| `sweep-review-generate` | Parse `git show` for the sweep commit → immutable `sweeps/YYYY-MM-DD-NN.snapshot.html` |
| `sweep-review-compile` | Merge snapshot + all `rN.comments.jsonl` rounds → `review.html` |
| `sweep-review-squash` | Squash all comment rounds for a run into one |
| `sweep-review-list` | List all sweep runs with comment/compile status |
| `sweep-review-open` | Open compiled review (or snapshot) in browser |

Snapshots are immutable. Comments download as `.jsonl` sidecars via the "Save Comments" button; compile merges them in. Full review lifecycle without GitHub.

---

## Part 3: CLI Reference

`noteplan-sweep` — 52 commands across 12 groups. Key groups:

| Group | Commands |
|---|---|
| Content Movement | `move-range`, `move-section`, `append-section`, `create-section`, `clean-empty-subheaders` |
| Source Management | `clear-source`, `add-breadcrumb` |
| Validation | `check-source-clean`, `check-wikilinks`, `check-backlinks`, `check-frontmatter`, `fix-date-tags`, … |
| Backlinks | `update-backlinks`, `check-emoji-mappings`, `sync-emoji-mappings`, `check-note-map`, `sync-note-map`, … |
| Discovery | `list-workstreams`, `list-plans`, `clone-plan`, `clone-template`, … |
| URL Enrichment | `enrich-urls`, `enrich-links`, `fetch-title`, `check-dead-links`, `archive-url`, … |
| Dashboard | `dashboard-generate`, `dashboard-open` |
| Conversation Mining | `conversation-mine`, `mine-commit` |
| Work Board | `work-board-generate`, `work-board-open` |
| AI Usage | `ai-usage-mine`, `ai-usage-generate`, `ai-usage-open`, `repo-scan` |
| Sweep Review | `sweep-commit`, `sweep-review-generate`, `sweep-review-compile`, `sweep-review-squash`, `sweep-review-list`, `sweep-review-open` |

```bash
noteplan-sweep list-commands   # full listing
noteplan-sweep <command> --help
```

---

## CLI Setup

```bash
PLUGIN_BIN="$HOME/workspace/oeid-claude-plugin-marketplace/plugins/noteplan-manager/bin"
bash "$PLUGIN_BIN/setup.sh"                            # one-time venv + Playwright setup
ln -sf "$PLUGIN_BIN/noteplan-sweep" /usr/local/bin/noteplan-sweep
noteplan-sweep --version
```

---

## Common Scenarios

**"What's the state of all my active projects?"**
→ `noteplan-sweep dashboard-open` (or `dashboard-generate` to refresh first)

**"I want to see what I accomplished this quarter"**
→ `noteplan-sweep work-board-open` → Accomplishments pane

**"What have I built with Claude / how much am I using AI?"**
→ `noteplan-sweep ai-usage-generate && noteplan-sweep ai-usage-open`

**"Mine my recent Claude sessions and update my plans"**
→ `/noteplan-manager:mine-conversations` or `noteplan-sweep conversation-mine`

**"I want to sweep my daily notes for the past week"**
→ `/noteplan-manager:sweep-daily-notes`

**"Review what changed in my last sweep"**
→ `noteplan-sweep sweep-review-open`

**"My filenames / emojis / frontmatter are broken"**
→ `/noteplan-manager:manage-filenames` / `manage-emojis` / `manage-frontmatter`

**"I need to create a new plan or note"**
→ `/noteplan-manager:manage-plans` → create, or `/noteplan-manager:manage-notes` → create note

**"Scan my repos for AI artifacts and update the usage dashboard"**
→ `noteplan-sweep repo-scan && noteplan-sweep ai-usage-generate`

**"I'm setting up on a new machine"**
→ `/noteplan-manager:manage-notes` → discover structure, then CLI setup above
