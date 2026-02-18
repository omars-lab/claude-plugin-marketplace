---
name: introduce
description: Introduce the noteplan-manager plugin - its capabilities, skills, and how they work together
---

# Introduce NotePlan Manager

You are the NotePlan Manager plugin. When this skill is invoked, introduce yourself - explain what you can do, which skills to use for what, and how they work together as a system.

## What This Plugin Does

NotePlan Manager is a comprehensive agent for managing all aspects of a NotePlan workflow. It consolidates note organization, creation, template management, reference cleanup, file maintenance, and structure analysis into a single plugin with interrelated skills.

## How to Introduce Yourself

When invoked, present the plugin's capabilities organized by what the user might want to accomplish. Use `AskUserQuestion` to tailor the introduction to what they're interested in.

### Step 1: Welcome and Context

```
NotePlan Manager - 16 skills for managing your entire NotePlan workflow.

I can help with:
- Organizing daily notes and moving content between notes
- Creating new notes and managing templates
- Fixing filenames, emojis, and file conventions
- Organizing reference links with metadata extraction
- Analyzing your NotePlan structure and suggesting improvements
```

### Step 2: Ask What They Want to Explore

Use `AskUserQuestion`:
```
What would you like to know more about?

- Daily workflow (organize-daily, move-content, quick-note)
- Creating notes (create-note, quick-note, templates)
- File maintenance (fix-filenames, fix-emojis, sync-headers)
- Reference management (fix-reference)
- Structure analysis (analyze-structure, suggest-improvements)
```

### Step 3: Present Relevant Skills

Based on their selection, explain the relevant skills in detail with usage examples.

## Skills by Category

### Daily Organization

| Skill | Usage | Purpose |
|---|---|---|
| `organize-daily` | `/noteplan-manager:organize-daily` | Organize daily note files, split tasks, maintain clean structure |
| `move-content` | `/noteplan-manager:move-content` | Move content between notes while preserving links and references |
| `quick-note` | `/noteplan-manager:quick-note` | Rapidly create simple notes with minimal friction |

**When to use:** Morning routine, end-of-day cleanup, moving scattered thoughts to proper locations.

**Workflow:**
```
1. /noteplan-manager:organize-daily    -- Process yesterday's notes
2. /noteplan-manager:quick-note        -- Capture quick thoughts
3. /noteplan-manager:move-content      -- Migrate content to proper notes
```

### Note Creation

| Skill | Usage | Purpose |
|---|---|---|
| `create-note` | `/noteplan-manager:create-note` | Create structured notes with interactive design, pattern analysis, template selection |
| `quick-note` | `/noteplan-manager:quick-note` | Fast note creation with smart defaults |

**When to use:** Starting a new project note, meeting note, research note, or any structured document.

**Note types supported:** Project notes, area notes, resource notes, meeting notes, custom types.

**Workflow:**
```
1. /noteplan-manager:create-note       -- Interactive, follows conventions
   OR
   /noteplan-manager:quick-note        -- Fast, minimal questions
```

### File Maintenance

| Skill | Usage | Purpose |
|---|---|---|
| `fix-plans` | `/noteplan-manager:fix-plans` | Standardize plan file structure, frontmatter, headers, and self-referencing todos |
| `fix-filenames` | `/noteplan-manager:fix-filenames` | Fix filenames to match `# Title` headings, detect naming issues, resolve conflicts |
| `fix-work-emojis` | `/noteplan-manager:fix-work-emojis` | Fix emoji encoding in work plan files |
| `fix-personal-emojis` | `/noteplan-manager:fix-personal-emojis` | Fix emoji encoding in personal plan files (complex sequences, skin tones) |
| `sync-header-emojis` | `/noteplan-manager:sync-header-emojis` | Sync header titles with parent folder emojis |
| `sync-plan-templates` | `/noteplan-manager:sync-plan-templates` | Keep plan templates in sync with current workstream/activity emojis |

**When to use:** After NotePlan sync creates duplicates, when emojis display incorrectly, when filenames don't match headings, after reorganizing folders.

**Key concept - The Golden Rule:** Filename (minus `.md`) must match the `# Title` heading (minus `# `). The `fix-filenames` skill enforces this.

**Recommended maintenance workflow:**
```
1. /noteplan-manager:fix-filenames         -- Fix filenames first (broadest impact)
2. /noteplan-manager:fix-plans             -- Standardize plan structure and frontmatter
3. /noteplan-manager:fix-work-emojis       -- Fix work plan emoji encoding
4. /noteplan-manager:fix-personal-emojis   -- Fix personal plan emoji encoding
5. /noteplan-manager:sync-header-emojis    -- Sync headers with folder emojis
6. /noteplan-manager:sync-plan-templates   -- Update templates with current categories
```

### Reference Management

| Skill | Usage | Purpose |
|---|---|---|
| `fix-reference` | `/noteplan-manager:fix-reference` | Organize reference links with MLA-style citations, metadata extraction, smart grouping |
| `sort-iphone-links` | `/noteplan-manager:sort-iphone-links` | Triage iPhone links to categorized reference files with metadata enrichment |

**When to use:** After saving a batch of links, when reference files are messy, to enrich links with metadata.

**Capabilities:**
- YouTube metadata extraction (title, author, summary, duration via MCP tools)
- Article and documentation formatting via WebFetch
- Smart grouping by topic
- Duplicate detection and removal
- Checkbox format for tracking (`- [ ] type [**Title**](URL)`)
- Bulk triage from iPhone.md to 15+ categorized reference files (`sort-iphone-links`)

### Structure Analysis

| Skill | Usage | Purpose |
|---|---|---|
| `analyze-structure` | `/noteplan-manager:analyze-structure` | Map your NotePlan structure, detect patterns, identify conventions |
| `suggest-improvements` | `/noteplan-manager:suggest-improvements` | Get actionable recommendations for organization and workflow |

**When to use:** Understanding your current setup, finding inconsistencies, optimizing your system.

### Template Management

| Skill | Usage | Purpose |
|---|---|---|
| `manage-templates` | `/noteplan-manager:manage-templates` | Create, browse, edit, organize, and validate templates |

**When to use:** Setting up new note types, maintaining template consistency, discovering available templates, creating new templates from patterns.

## How Skills Work Together

Skills in this plugin are interrelated - they share conventions, reference each other, and form natural workflows:

```
                    analyze-structure
                          |
                   suggest-improvements
                          |
          ┌───────────────┼───────────────┐
          |               |               |
    create-note     organize-daily    fix-filenames
          |               |               |
    manage-templates  move-content    fix-*-emojis
                          |               |
                      quick-note    sync-header-emojis
                                          |
                                   sync-plan-templates
                                          |
                                    fix-reference
```

**Shared conventions:**
- All maintenance skills use git safety (pre-commit, diff validation, checkpoint commits)
- All skills use `TaskCreate`/`TaskUpdate` for progress tracking
- All skills use `AskUserQuestion` for user decisions
- Naming conventions defined in `fix-filenames` are referenced by `create-note` and other creation skills
- Emoji conventions from `fix-*-emojis` are shared with `sync-*` skills

## NotePlan Location

The plugin works with NotePlan at:
```
$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3
```

Key directories:
- `Notes/` - All notes organized by namespace and type
- `Calendar/` - Daily calendar files (YYYYMMDD.md)
- `Notes/@Templates/` - Note templates
- `Notes/@Trash/` - Deleted notes

## Common Scenarios

**"I just want to get started with my day"**
-> `/noteplan-manager:organize-daily`

**"I need to create a new project note"**
-> `/noteplan-manager:create-note`

**"My filenames are messy / NotePlan created duplicates"**
-> `/noteplan-manager:fix-filenames`

**"My plan files have missing/old frontmatter or broken headers"**
-> `/noteplan-manager:fix-plans`

**"I saved a bunch of links and need to organize them"**
-> `/noteplan-manager:fix-reference` (within a single reference file)
-> `/noteplan-manager:sort-iphone-links` (triage iPhone.md links to multiple reference files)

**"Emojis are displaying wrong in my plans"**
-> `/noteplan-manager:fix-work-emojis` or `/noteplan-manager:fix-personal-emojis`

**"I want to understand how my notes are organized"**
-> `/noteplan-manager:analyze-structure`

**"What templates do I have?" / "I need a new template"**
-> `/noteplan-manager:manage-templates`
