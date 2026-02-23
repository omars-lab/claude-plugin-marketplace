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
Screenshot Manager — 3 skills for your Screenshots folder.

I can help with:
- Prefixing directories with their earliest screenshot date (sortable chronology)
- Finding misplaced files and importing Desktop screenshots using OCR + date proximity
- Extracting URLs from browser screenshots
```

### Step 2: Ask What They Want to Do

Use `AskUserQuestion`:
```
What would you like to do?

- Sort directories by date (sort-dirs)
- Find misplaced files / import from Desktop (suggest-groupings)
- Extract URLs from browser screenshots (extract-urls)
- Learn about all skills
```

### Step 3: Present Relevant Skills

Based on their selection, explain the relevant skills with usage examples.

## Skills

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

```
suggest-groupings  →  fix misplaced files and import Desktop screenshots
sort-dirs          →  prefix all directories with dates for chronological sorting
extract-urls       →  pull URLs out of any screenshot, any time (independent)
```

**Recommended workflow:**
```
1. /screenshot-manager:suggest-groupings  -- clean up misplaced files first
2. /screenshot-manager:sort-dirs          -- then prefix dirs with dates
3. /screenshot-manager:extract-urls       -- on demand, whenever you need URLs back
```

`extract-urls` is independent — run it any time on any screenshot without needing to run the other skills first.

## Screenshots Location

Default root: `~/Library/CloudStorage/OneDrive-ServiceNow/📸 Screenshots`

Both skills start by confirming the root path via `AskUserQuestion` before doing anything.

## Common Scenarios

**"My Screenshots folder doesn't sort chronologically"**
→ `/screenshot-manager:sort-dirs`

**"I have Desktop screenshots piling up and want to file them"**
→ `/screenshot-manager:suggest-groupings`

**"Some screenshots seem to be in the wrong directory"**
→ `/screenshot-manager:suggest-groupings`

**"I want to do both organization + sorting"**
→ Run `suggest-groupings` first, then `sort-dirs`

**"I screenshot a browser tab and need the URL back"**
→ `/screenshot-manager:extract-urls`

**"I want all URLs from a whole directory of screenshots"**
→ `/screenshot-manager:extract-urls` (choose directory scope)
