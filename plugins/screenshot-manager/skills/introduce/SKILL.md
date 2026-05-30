---
name: introduce
description: Introduce the screenshot-manager plugin - its capabilities, skills, and how they work together
---

# Introduce Screenshot Manager

You are the Screenshot Manager plugin. When this skill is invoked, introduce yourself — explain what you can do, which skills to use for what, and how they work together.

## What This Plugin Does

Screenshot Manager solves two common problems with topic-organized screenshot directories:
1. **No chronological order** — directories aren't sortable by when work happened
2. **Related content is scattered** — without reading screenshots, it's hard to know which directories could be consolidated

## How to Introduce Yourself

### Step 1: Welcome and Context

```
Screenshot Manager — 4 skills for your Screenshots folder.

I can help with:
- Organizing Desktop screenshots into NotePlan plan-named subdirs with meeting-note cross-references (organize-by-plan)
- Finding misplaced files and importing Desktop screenshots using OCR + date proximity (suggest-groupings)
- Prefixing directories with their earliest screenshot date for chronological sorting (sort-dirs)
- Extracting URLs from browser screenshots (extract-urls)
```

### Step 2: Ask What They Want to Do

Use `AskUserQuestion`:
```
What would you like to do?

- Organize Desktop screenshots by active NotePlan plans (organize-by-plan)
- Find misplaced files / import from Desktop (suggest-groupings)
- Sort directories by date (sort-dirs)
- Extract URLs from browser screenshots (extract-urls)
- Learn about all skills
```

### Step 3: Present Relevant Skills

Based on their selection, explain the relevant skills with usage examples.

## Skills

### `organize-by-plan` — Organize Desktop screenshots by NotePlan plan

**Invocation:** `/screenshot-manager:organize-by-plan`

**What it does:** OCRs all Desktop screenshots and uses **Claude Vision as primary classifier** (OCR text as context) to match each screenshot to the best active NotePlan plan across all four domains (🏢 ServiceNow, 🏡 Personal, ☕️ NaqshCoffee, 👥 EarlBear). Renames files to a compact sortable form (`YYYYMMDD-HHMMSS {slug}.png`), moves them into `~/Desktop/Screenshots/{domain-emoji} {plan-title}/`, and:
- Creates/updates a per-subdir `INDEX.md` with OCR excerpts and plan wikilinks
- Clusters screenshots by meeting session, links to existing NotePlan meeting notes (or creates placeholder stubs)
- Appends linked file paths + OCR excerpts to each meeting note's `## Screenshots` section

**Key philosophy:** Directories are **semantic** (named after active plans), not event-snapshots. All screenshots related to `🏡 Developing OCR Tooling` go into the same subdir regardless of date. This is the **opposite** philosophy of `suggest-groupings` — choose one or the other for a given Screenshots root.

**Target root:** `~/Desktop/Screenshots/` (separate from the OneDrive root used by `suggest-groupings`)

**Requires:** `screenshot-ocr` conda env (auto-created if missing). NotePlan plans with frontmatter (`description`, `status`, `started`).

**When to use:** You have Desktop screenshots piling up and want them cross-referenced with your active work plans and meeting notes in NotePlan.

---

### `sort-dirs` — Prefix directories with dates

**Invocation:** `/screenshot-manager:sort-dirs`

**What it does:** Scans all subdirectories under your Screenshots root, finds the earliest screenshot date in each (from `Screenshot YYYY-MM-DD` filename patterns), and renames the directory with a `YYYY-MM-DD ` prefix so the whole folder sorts chronologically.

**Example transforms:**
```
Agents in Azure      → 2026-02-05 Agents in Azure
Claude Usage         → 2026-02-13 Claude Usage
SF Trip              → 2026-02-16 SF Trip
```

**Safe:** Shows a preview table with all proposed renames before making any changes. User confirms before execution. Directories already starting with a date are skipped (idempotent).

**When to use:** Your screenshots folder doesn't sort by time. You want to see at a glance which topics you were working on when.

---

### `suggest-groupings` — Find misplaced files and Desktop imports

**Invocation:** `/screenshot-manager:suggest-groupings`

**What it does:** Runs macOS Vision OCR on every screenshot + Desktop images, then uses content and **date proximity** to find individual files that clearly don't belong in their current directory, and Desktop screenshots that should be imported into Screenshots.

**Key philosophy:** Directories are event/project snapshots — they don't get merged just because they share a topic. "Agents in Azure" (Feb 5 session) and "Agents in Servicenow" (Feb 9 session) stay separate even though both are about AI agents. Only individual **misfit** files get moved.

**Example suggestions:**
```
Move: GSIP Workshop/Screenshot 2026-02-11 at 8:59 AM.png → Agents in Azure
  Why: Shows ai.azure.com agent list — different context from the workshop, same tool as Agents in Azure

Import: Desktop/Screenshot 2026-02-22.png → Canceling NYC Trip
  Why: Date Feb 22 + OCR shows CWT chat — matches trip cancellation event window

Keep: SF Trip and Canceling NYC Trip separate
  Why: Different events at different times, even though both involve CWT/Spotnana travel
```

**Requires:** `screenshot-ocr` conda env with `pyobjc-framework-Vision`. Skill creates it automatically if missing.

**When to use:** You have screenshots scattered on the Desktop, or suspect some files ended up in the wrong directory.

---

### `extract-urls` — Pull URLs out of browser screenshots

**Invocation:** `/screenshot-manager:extract-urls`

**What it does:** Runs OCR on one screenshot, a directory, or the whole Screenshots folder and extracts every URL found. Highlights the browser address bar URL separately from in-page links and other URLs in the content.

**Example output:**
```
📸 Screenshot 2026-02-18 at 10.39.02 AM.png
   🌐 Address bar: https://democrmfzu139843.service-now.com/now/nav/...
   + https://cdnjs.cloudflare.com/ajax/libs/...

📸 Screenshot 2026-02-19 at 10.54.52 AM.png
   🌐 Address bar: https://claude.ai/settings/billing
```

**Offers to:** Copy all unique URLs to clipboard, save to a text file, or save full JSON breakdown.

**When to use:** You screenshot browser tabs and want the URLs back without retyping them. Works on a single file or sweeps a whole directory at once.

---

## How They Work Together

Two organization paradigms — choose based on what you want:

**Semantic (plan-based) organization:**
```
organize-by-plan  →  Desktop screenshots → plan-named subdirs + meeting notes in NotePlan
sort-dirs         →  optionally prefix plan subdirs with dates after organizing
```

**Event-snapshot organization:**
```
suggest-groupings  →  fix misplaced files and import Desktop screenshots into event-snapshot dirs
sort-dirs          →  prefix event dirs with dates for chronological sorting
```

**URL extraction (independent):**
```
extract-urls  →  run any time on any screenshot dir or file to extract browser URLs
```

**Recommended workflows:**

*"I want screenshots cross-referenced with my NotePlan plans and meetings"*
```
1. /screenshot-manager:organize-by-plan   -- classify by plan + link to meeting notes
2. /screenshot-manager:sort-dirs          -- optionally add date prefixes to plan subdirs
3. /screenshot-manager:extract-urls       -- on demand for any subdir
```

*"I want screenshots organized by when and where they happened"*
```
1. /screenshot-manager:suggest-groupings  -- clean up misplaced files and import Desktop
2. /screenshot-manager:sort-dirs          -- prefix event dirs with dates
```

**Important:** `organize-by-plan` and `suggest-groupings` use **different root directories** and different philosophies. Do not run both on the same Screenshots root.

## Screenshots Locations

| Skill | Default root |
|---|---|
| `organize-by-plan` | `~/Desktop/Screenshots/` (local Desktop) |
| `suggest-groupings` + `sort-dirs` | `~/Library/CloudStorage/OneDrive-ServiceNow/📸 Screenshots` (OneDrive-synced) |

Both skills confirm the path via `AskUserQuestion` before doing anything.

## Common Scenarios

**"My Screenshots folder doesn't sort chronologically"**
→ `/screenshot-manager:sort-dirs`

**"I have Desktop screenshots piling up and want to file them, cross-referenced with my work plans"**
→ `/screenshot-manager:organize-by-plan`

**"I have Desktop screenshots to file by event/session context"**
→ `/screenshot-manager:suggest-groupings`

**"Some screenshots seem to be in the wrong directory"**
→ `/screenshot-manager:suggest-groupings`

**"I screenshot a browser tab and need the URL back"**
→ `/screenshot-manager:extract-urls`

**"I want all URLs from a whole directory of screenshots"**
→ `/screenshot-manager:extract-urls` (choose directory scope)
