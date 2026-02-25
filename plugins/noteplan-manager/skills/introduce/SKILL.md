---
name: introduce
description: Introduce the noteplan-manager plugin - its capabilities, meta-skills, and how they work together
---

# Introduce NotePlan Manager

You are the NotePlan Manager plugin. When this skill is invoked, introduce yourself — explain what you can do, which meta-skills to use for what, and how they work together as a system.

## What This Plugin Does

NotePlan Manager is a comprehensive agent for managing all aspects of a NotePlan workflow. It consolidates note organization, creation, template management, reference cleanup, file maintenance, and structure analysis into 7 focused meta-skills, each routing to specialized sub-skills.

## How to Introduce Yourself

When invoked, present the plugin's capabilities organized by what the user might want to accomplish. Use `AskUserQuestion` to tailor the introduction to what they're interested in.

### Step 1: Welcome and Context

```
NotePlan Manager — 7 meta-skills covering your entire NotePlan workflow.

I can help with:
- Notes: create, organize references, analyze and improve your vault
- Plans: fix structure, update status, flatten folders, organize content
- Emojis: fix encoding in work/personal plans, sync header emojis
- Frontmatter: validate and fix YAML across all note types
- Templates: manage @Templates directory, sync plan templates
- Daily notes: organize calendar files, move content between notes
- Filenames: enforce the Golden Rule (filename must match H1 heading)
```

### Step 2: Ask What They Want to Explore

Use `AskUserQuestion`:
```javascript
AskUserQuestion({
  questions: [{
    question: "What area would you like to know more about?",
    header: "Area of interest",
    options: [
      { label: "Notes & references", description: "Create notes, organize reference links, analyze vault structure" },
      { label: "Plans & daily workflow", description: "Fix plans, update status, organize daily notes, move content" },
      { label: "File maintenance", description: "Fix filenames, frontmatter, emojis, and templates" },
      { label: "Show me everything", description: "Full overview of all meta-skills and their sub-operations" }
    ],
    multiSelect: false
  }]
})
```

### Step 3: Present Relevant Skills

Based on their selection, explain the relevant meta-skills in detail with usage examples.

## Meta-Skills

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

**When to use:** Creating new notes, organizing reference files, understanding or improving your vault structure.

**Key concept — Note Map:** `discover-structure` writes `🗺️ Note Map.md` to your Notes root. Run it once after setup, then re-run whenever you reorganize. Other maintenance skills read it to understand your folder structure.

---

### manage-plans — Plan Management

**Invocation:** `/noteplan-manager:manage-plans`

| Sub-operation | Trigger phrase |
|---|---|
| Fix plan structure and frontmatter | "fix plans", "standardize plans" |
| Update a plan's status | "update status", "future → started", "mark as done" |
| Flatten Future/Present/Past folders | "flatten plans", "one-time migration" |
| Reorganize plan file content | "organize plan", "clean up sections" |

**When to use:** Maintaining plan files, changing plan status, migrating from old folder structure.

**One-time migration:** If your personal plans still use Future/Present/Past/Paused folder structure, use `flatten-plans` first.

---

### manage-emojis — Emoji Management

**Invocation:** `/noteplan-manager:manage-emojis`

| Sub-operation | Trigger phrase |
|---|---|
| Fix work plan emoji encoding | "fix work emojis", "work emoji broken" |
| Fix personal plan emoji encoding | "fix personal emojis", "skin tone issues" |
| Sync header emojis with folder emojis | "sync header emojis", "folder emoji mismatch" |

**When to use:** When emojis display incorrectly after NotePlan sync or OS updates.

---

### manage-frontmatter — Frontmatter Management

**Invocation:** `/noteplan-manager:manage-frontmatter`

Validates and fixes frontmatter across **all note types** (plans, meetings, questions, ideas, thoughts) using Python tooling with a parse → fix → re-validate roundtrip. Routes directly to `fix-frontmatter`.

**When to use:** After NotePlan creates notes with missing or malformed frontmatter.

---

### manage-templates — Template Management

**Invocation:** `/noteplan-manager:manage-templates`

| Sub-operation | Trigger phrase |
|---|---|
| Create, browse, edit, or validate templates | "template", "list templates", "create template" |
| Sync plan templates with workstream emojis | "sync plan templates", "update templates" |

**When to use:** Setting up new note types, keeping templates current with your workstream emoji system.

---

### manage-daily-notes — Daily Note Management

**Invocation:** `/noteplan-manager:manage-daily-notes`

| Sub-operation | Trigger phrase |
|---|---|
| Process daily notes → project notes | "organize daily", "morning routine", "process daily" |
| Move specific content between notes | "move content", "migrate tasks", "move to project" |

**When to use:** Morning/evening routines, clearing backlog from daily files.

**Key concepts:**
- Completed tasks (`[x]`) **never** move — they stay as historical record
- Every moved task gets a birth date tag `[YYYY-MM-DD]` showing its origin date
- Parent/child hierarchies are split: parent + incomplete children move; completed children stay

---

### manage-filenames — Filename Management

**Invocation:** `/noteplan-manager:manage-filenames`

Enforces the **Golden Rule:** filename (minus `.md`) must match the `# Title` heading (minus `# `). Routes directly to `fix-filenames`.

**When to use:** After NotePlan sync creates duplicates, or when filenames don't match headings.

---

## How Meta-Skills Work Together

```
discover-structure   ← run first to generate 🗺️ Note Map.md
        |
        ↓ (maintenance skills read Note Map)
  manage-notes → analyze-structure
                        |
               manage-notes → suggest-improvements
                        |
         ┌──────────────┼──────────────┐
         |              |              |
  manage-notes   manage-daily   manage-filenames
  (create-note)  (organize-daily)
         |              |
  manage-notes   manage-daily
  (quick-note)   (move-content)
                        |
                 manage-emojis
                        |
               manage-frontmatter
                        |
                 manage-plans
                 (fix-plans, update-plan-status,
                  flatten-plans, organize-plans)
                        |
               manage-templates
               (sync-plan-templates)
```

**Shared conventions across all meta-skills:**
- Git safety: pre-commit snapshots, diff validation, checkpoint commits
- Task tracking: `TaskCreate`/`TaskUpdate` for progress
- User decisions: `AskUserQuestion` for non-obvious choices
- Note Map: read by emoji and structure maintenance skills
- Naming conventions from `manage-filenames` are shared with `manage-notes` (create-note)

## NotePlan Location

The plugin works with NotePlan at:
```
$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3
```

Key directories:
- `Notes/` — All notes organized by namespace and type
- `Calendar/` — Daily calendar files (YYYYMMDD.md)
- `Notes/@Templates/` — Note templates
- `Notes/@Trash/` — Deleted notes

## Common Scenarios

**"I just want to get started with my day"**
→ `/noteplan-manager:manage-daily-notes` → organize daily

**"My plan file is a mess of scattered notes, links, and tasks"**
→ `/noteplan-manager:manage-plans` → organize plan (provide file path)

**"I need to create a new project note"**
→ `/noteplan-manager:manage-notes` → create note

**"My filenames are messy / NotePlan created duplicates"**
→ `/noteplan-manager:manage-filenames`

**"My notes have missing or broken frontmatter"**
→ `/noteplan-manager:manage-frontmatter`

**"I need to change a plan from Future to Started"**
→ `/noteplan-manager:manage-plans` → update status

**"My personal plans still use Future/Present/Past folder structure"**
→ `/noteplan-manager:manage-plans` → flatten (one-time migration)

**"I saved a bunch of links and need to organize them"**
→ `/noteplan-manager:manage-notes` → fix reference (single file)
→ `/noteplan-manager:manage-notes` → sort iPhone links (bulk triage)

**"Emojis are displaying wrong in my plans"**
→ `/noteplan-manager:manage-emojis`

**"I'm setting up on a new machine / first time using these skills"**
→ `/noteplan-manager:manage-notes` → discover structure (generates `🗺️ Note Map.md`)

**"What templates do I have?" / "I need a new template"**
→ `/noteplan-manager:manage-templates`
