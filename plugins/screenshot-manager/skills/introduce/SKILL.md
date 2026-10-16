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
Screenshot Manager — 6 skills for your Screenshots folder.

I can help with:
- Organizing Desktop screenshots into NotePlan plan-named subdirs with meeting-note cross-references (organize-by-plan)
- Moving Desktop screenshots and project folders into one iCloud folder per git repo, grouped by company, and keeping a fingerprint.md in each folder so new screenshots file themselves (organize-by-project)
- Finding misplaced files and importing Desktop screenshots using OCR + date proximity (suggest-groupings)
- Prefixing directories with their earliest screenshot date for chronological sorting (sort-dirs)
- Extracting URLs from browser screenshots (extract-urls)
- Picking out screenshots that show a reusable Claude technique and moving them into the Techniques folder (suggest-techniques)
```

### Step 2: Ask What They Want to Do

Use `AskUserQuestion` (at most 4 options, so related skills share one):
```
What would you like to do?

- File my Desktop screenshots and folders (organize-by-project, organize-by-plan, suggest-techniques)
- Tidy a Screenshots folder I already have (suggest-groupings, sort-dirs)
- Pull web addresses out of screenshots (extract-urls)
- Learn about all skills
```

If they pick the first, ask one follow-up: one folder per git repo (organize-by-project), by NotePlan plan (organize-by-plan), or just the Claude technique shots (suggest-techniques).

### Step 3: Present Relevant Skills

Based on their selection, explain the relevant skills with usage examples.

## Skills

### `organize-by-plan` — Organize Desktop screenshots by NotePlan plan

**Invocation:** `/screenshot-manager:organize-by-plan`

**What it does:** OCRs all Desktop screenshots and uses **Claude Vision as primary classifier** (OCR text as context) to match each screenshot to the best active NotePlan plan across all four domains (🏢 ServiceNow, 🏡 Personal, ☕️ NaqshCoffee, 👥 EarlBear). Renames files to a compact sortable form (`YYYYMMDD-HHMMSS {slug}.png`), moves them into `~/Desktop/Screenshots/{domain-emoji} {plan-title}/`, and:
- Creates/updates a per-subdir `INDEX.md` with OCR excerpts and plan wikilinks
- Clusters screenshots by meeting session, links to existing NotePlan meeting notes (or creates placeholder stubs)
- Appends linked file paths + OCR excerpts to each meeting note's `## Screenshots` section
- Routes screenshots that match a **topic folder** (one kind of screenshot regardless of plan, such as every chat with a given assistant tool) into that folder before plan matching. Ask for a new one in plain words ("put all X chats in their own folder"). The list is kept with your screenshots in `.topic-folders.json`.

**Key philosophy:** Directories are **semantic** (named after active plans), not event-snapshots. All screenshots related to `🏡 Developing OCR Tooling` go into the same subdir regardless of date. This is the **opposite** philosophy of `suggest-groupings` — choose one or the other for a given Screenshots root.

**Target root:** `~/Desktop/Screenshots/` (separate from the OneDrive root used by `suggest-groupings`)

**Requires:** `screenshot-ocr` conda env (auto-created if missing). NotePlan plans with frontmatter (`description`, `status`, `started`).

**When to use:** You have Desktop screenshots piling up and want them cross-referenced with your active work plans and meeting notes in NotePlan.

---

### `organize-by-project` — File the Desktop by git repo

**Invocation:** `/screenshot-manager:organize-by-project`

**What it does:** Lists every git repo under `~/Workspace/git*` as a project, then moves Desktop screenshots and Desktop folders into `CloudDesktop/projects/<company>/<project>/` in iCloud. A screenshot is placed by a project's name on screen (repo name or a hand-written alias); the rest get a look at the image itself. Company-wide material goes in the company's own folder. You approve a plan table first, and every move batch has an undo.

**Looks inside folders:** a folder whose name matches no repo is not skipped. Its screenshots are read: a folder where one project's name dominates moves whole, a folder where only some shots name a project gives up just those, and a folder with no names gets a few sample images checked. Folders of folders (`Debugging/`, `Developing/` and any like them) are matched one subfolder at a time.

**Remembers each folder in `fingerprint.md`:** every folder with 3 or more screenshots gets a `fingerprint.md` listing the sites, paths and words its screenshots show, with dates, plus a **Guidance** section. When a screenshot is unclear, it reads the Guidance first, asks you if that doesn't settle it, and writes your answer into Guidance, so the next run already knows. A site or path that only one folder has is a hint for new screenshots, never a decision on its own.

**Asks many questions at once in Obsidian:** when more than a few groups of screenshots are unclear, it writes a review doc in `CloudDesktop/projects/_review/`: each group's pictures side by side, what it saw on each, and a tick box per choice. You tick one box per group, leave a review-md comment when a box isn't enough, and tell Claude you're done; it reads the ticks back as answers, folder rules and key-file decisions.

**Keeps back:** folders with key or secret files (or named for keys), screenshots it can't place, and folders that aren't project work, all listed for you.

**When to use:** Your Desktop mixes screenshots and folders from many projects and you want each project's material in one place, next to the code it belongs to.

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

### `suggest-techniques` — Pick Claude technique screenshots

**Invocation:** `/screenshot-manager:suggest-techniques`

**What it does:** Learns the bar from the screenshots already in `~/Desktop/📸 Screenshots of Techniques/`. Then it reads every Desktop screenshot with Vision (OCR as context) and labels each one `technique`, `claude-not-technique` or `other`, with a 0–5 score, a mechanism tag (hooks, recap, tasks, statusline, prompting, …) and a one-line reason. Screenshots taken within 2 minutes of each other are judged as one group. After you approve, it moves the chosen files and records each one in `techniques.json`.

**When to use:** Your Desktop has a mix of Claude screenshots and everything else, and you want to keep the ones that show a technique worth repeating.

**Next:** `/technique-manager:recreate-technique` turns each approved screenshot into a Claude-style HTML page, and `/technique-manager:package-gallery` zips them all.

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

**Project organization (one folder per git repo):**
```
organize-by-project  →  Desktop screenshots + folders → iCloud CloudDesktop/projects/<company>/<project>/
```

**Technique curation (independent, feeds technique-manager):**
```
suggest-techniques  →  Desktop → 📸 Screenshots of Techniques (+ techniques.json)
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
| `organize-by-project` | `~/Library/Mobile Documents/com~apple~CloudDocs/CloudDesktop/projects/` (iCloud) |
| `suggest-techniques` | `~/Desktop/📸 Screenshots of Techniques/` |

Each skill confirms its path via `AskUserQuestion` before doing anything.

## Common Scenarios

**"My Screenshots folder doesn't sort chronologically"**
→ `/screenshot-manager:sort-dirs`

**"I have Desktop screenshots piling up and want to file them, cross-referenced with my work plans"**
→ `/screenshot-manager:organize-by-plan`

**"I have Desktop screenshots to file by event/session context"**
→ `/screenshot-manager:suggest-groupings`

**"My Desktop is full of screenshots and folders from different projects"**
→ `/screenshot-manager:organize-by-project`

**"Some screenshots seem to be in the wrong directory"**
→ `/screenshot-manager:suggest-groupings`

**"I screenshot a browser tab and need the URL back"**
→ `/screenshot-manager:extract-urls`

**"Which of my Desktop screenshots show a Claude technique worth keeping?"**
→ `/screenshot-manager:suggest-techniques`

**"I want all URLs from a whole directory of screenshots"**
→ `/screenshot-manager:extract-urls` (choose directory scope)
