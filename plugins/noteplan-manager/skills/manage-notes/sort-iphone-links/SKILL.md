---
name: sort-iphone-links
description: Triage and move links from iPhone.md to appropriate categorized reference files with metadata enrichment
---

# Sort iPhone Links

You are a NotePlan link triage assistant. When this skill is invoked, you'll parse all links from iPhone.md, classify them by topic, move them to the appropriate reference files with enriched metadata, and clean up the source file.

## What This Skill Does

This skill:
1. **Parses all links** from iPhone.md (~225 `* [ ] Look into:` entries collected via iOS shortcuts)
2. **Classifies links** using domain heuristics, WebFetch, and YouTube MCP tools
3. **Moves links to target reference files** with enriched fix-reference format (checkbox + emoji + markdown link + metadata)
4. **Organizes remaining links** in iPhone.md into topic sections (not a flat list)
5. **Cleans up junk** (about:blank, empty entries, duplicates) with user approval
6. **Validates counts** via git diff to ensure no links are lost

## Note Map Integration

Before running, check for `🗺️ Note Map.md` to get structure context:

```bash
NOTE_MAP="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🗺️ Note Map.md"
```

- **If the map exists**: read the "Key Structural Facts" section to get paths, folder names, and workstream/reference-file lists. Use those discovered values instead of the hardcoded defaults below.
- **If the map is missing**: proceed with the defaults below, then warn:
  > ⚠️  No `🗺️ Note Map.md` found. Run `/noteplan-manager:discover-structure` to generate it and make this skill structure-aware.
- **If structural discrepancy detected** (e.g. a workstream or folder listed in the map no longer exists on disk): report the diff and offer to refresh the map via `/noteplan-manager:discover-structure`.

## Source and Target Files

### Source File

**iPhone.md**: `$NOTEPLAN_ROOT/Notes/🏡 Personal/🏡📋 Lists/iPhone.md`

- Contains ~225 `* [ ] Look into: <URL>  #YYYY-MM-DD` entries
- iOS shortcuts append new links at the **bottom** of the file
- Has a header note about iOS shortcuts automation at the top (preserve this)
- **Do NOT rename this file** - it will break iOS shortcuts automation

### Target Reference Files

All in `$NOTEPLAN_ROOT/Notes/🏡 Personal/🏡📋 Lists/`:

| Target File | Topics |
|---|---|
| `🏡📋 References[GenAI].md` | AI, ML, LLMs, agents, prompt engineering, embeddings |
| `🏡📋 References[AWS].md` | AWS services, architecture, Bedrock, serverless |
| `🏡📋 References[Career].md` | Job postings, career advice, layoff prep, hiring |
| `🏡📋 References[Business].md` | Entrepreneurship, franchises, startups, Amazon FBA |
| `🏡📋 References[Software].md` | Dev tools, GitHub repos, programming, IDEs, code |
| `🏡📋 References[Tools].md` | Productivity tools, desk setups, keyboards, typing |
| `🏡📋 References[Leadership].md` | Leadership articles, management, ScarletInk |
| `🏡📋 References[Motivation].md` | Self-improvement, strategic success, masterclass |
| `🏡📋 References[Good Reads].md` | Long-form articles, newsletters, blogs, essays |
| `🏡📋 References[Entertainment].md` | Entertainment content, media |
| `🏡📋 References[Personal].md` | Personal items, clothing, religious/spiritual, family |
| `🏡📋 References[Services].md` | SaaS services, online platforms, financial tools |
| `🏡📋 References[Work Benefits].md` | ServiceNow-specific benefits |
| `🏡📋 References.md` | General references, education, courses, tutorials |
| `🏡📋 Shopping.md` | Products, e-commerce, Amazon, kitchen, coffee gear, home goods |
| `🏡📋 Activities[Austin].md` | Austin restaurants, local events, parks, family activities |

## Script: classify-urls.py

A standalone classifier is bundled at `plugins/noteplan-manager/skills/sort-iphone-links/classify-urls.py`.

```bash
# Classify a single URL
python3 classify-urls.py https://github.com/some/repo

# Classify all URLs in a markdown file
python3 classify-urls.py --file iPhone.md --format tsv

# Pipe URLs from stdin
echo "https://openai.com/blog/gpt4" | python3 classify-urls.py -

# JSON output for programmatic use
python3 classify-urls.py --file iPhone.md --format json
```

Use this for the initial categorization pass. Claude then reviews low-confidence results and handles YouTube (which requires title inspection to classify correctly).

## Environment Detection

**CRITICAL**: Do NOT use hardcoded paths. Detect the user's NotePlan directory dynamically:

```bash
# Detect NotePlan root directory
NOTEPLAN_ROOT="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"

# Verify it exists
if [ ! -d "$NOTEPLAN_ROOT" ]; then
  echo "NotePlan directory not found at $NOTEPLAN_ROOT"
  exit 1
fi
```

**Use Glob tool for reliable file discovery** (emoji paths can break bash `cd`):
```bash
Glob pattern="**/*Lists*/*.md" path="$NOTEPLAN_ROOT/Notes"
```

## Link Classification Rules

### Tier 1: Domain Heuristics (fast, no API calls)

Match URL domain/path against known patterns. Process ALL links through this tier first:

| Pattern | Category | Target File |
|---|---|---|
| `arxiv.org`, `openai.com`, `anthropic.com`, `huggingface`, `langchain`, `bedrock`, `unsloth`, path contains "ai", "ml", "llm", "rag", "embedding" | GenAI | `References[GenAI].md` |
| `aws.amazon.com` (non-product) | AWS | `References[AWS].md` |
| `jobs.lever.co`, `careers`, `scale.com/careers`, linkedin jobs, `zefi.ai/open-positions` | Career | `References[Career].md` |
| `junglescout`, franchise, startups, `warmly.ai`, `fundmomentum`, `augment.org/mba` | Business | `References[Business].md` |
| `github.com` (repos), `developer.apple.com`, `zed.dev`, `stacking.dev`, `swark.io`, dev tools | Software | `References[Software].md` |
| `keybr.com`, desk setups, keyboard, `worklouder`, `deltahub`, `orbitkey`, macro pads | Tools | `References[Tools].md` |
| `scarletink.com`, leadership articles | Leadership | `References[Leadership].md` |
| `masterclass.com/certificates`, `successblueprints`, self-help | Motivation | `References[Motivation].md` |
| `substack` (non-tech), `fs.blog`, long-form blogs, `brooker.co.za`, `bytebytego` | Good Reads | `References[Good Reads].md` |
| Product pages, e-commerce, `amazon.com/shop`, `williams-sonoma`, `fellowproducts`, `yeti`, coffee equipment, kitchen gadgets, `ugmonk`, `acaia`, `twiice` | Shopping | `Shopping.md` |
| Austin restaurants, `do512`, `austin.eater`, `crossovertx`, `parks.traviscountytx` | Activities (Austin) | `Activities[Austin].md` |
| `disneyworld`, entertainment content | Entertainment | `References[Entertainment].md` |
| Islamic stores, spiritual content, `yaqeeninstitute`, `alhuffadh`, `theislaminstitute`, `eastessence`, `alqamees`, `mywakala`, `studionayma`, `bilalspeaker`, `mouftahelchark`, `shopwithabc`, `cubiiox`, `najam-institute` | Personal | `References[Personal].md` |
| `mullvad.net`, `play.ht`, SaaS platforms, `alpaca.markets` | Services | `References[Services].md` |
| `edx.org`, `mit.edu`, `elvtr.com`, `domestika.org`, `texascoffeeschool`, `ideou.com`, courses | Education/General | `References.md` |
| `about:blank`, empty URLs, broken XML | Junk (delete) | Delete with approval |
| Exact duplicate URLs | Duplicate (delete) | Delete with approval |

### Tier 2: WebFetch (for ambiguous links)

For links not classified by domain heuristics:

```
WebFetch(url, prompt="Extract the page title and a one-sentence summary of what this page is about. What category does it fit: AI/ML, Career, Business, Software, Tools, Shopping, Education, or Other?")
```

Process in **batches of 5-10** using parallel WebFetch calls for efficiency.

### Tier 3: YouTube MCP (for video links)

For YouTube/youtu.be links:

```
mcp__MCP_DOCKER__get_video_info(url)
```

Use video title, channel, and description to determine category. Process in batches of 5-6 using parallel tool calls.

### Tier 4: Manual/Skip

Links that fail all classification tiers stay in iPhone.md, organized into sections.

## Link Enrichment Format

When moving a link to a target file, convert from the iPhone.md format to the fix-reference enriched format.

**Source format (iPhone.md):**
```markdown
* [ ] Look into: example.com/article  #2024-03-15
```

**Target format (enriched):**

#### YouTube Videos
```markdown
- [ ] 📽️ [**Video Title** (YouTube, YYYY-MM-DD)](https://youtube.com/watch?v=xxxxx)
  - Author: Channel Name | Duration: XX minutes
  - Summary: 1-2 sentence description
  - Date added: 2024-03-15
  - Topics: #topic1 #topic2
```

#### Articles and Blog Posts
```markdown
- [ ] 📝 [**Article Title** (Article, YYYY-MM-DD)](https://example.com/article)
  - Author: Name | Publisher: Domain
  - Summary: 1-2 sentence description
  - Date added: 2024-03-15
  - Topics: #topic1 #topic2
```

#### GitHub Repositories
```markdown
- [ ] 💻 [**Repository Name**](https://github.com/owner/repo)
  - Type: Code Repository | Language: Primary language
  - Summary: Brief description of the repository
  - Date added: 2024-03-15
  - Topics: #github #topic
```

#### Products / Shopping
```markdown
- [ ] 🛒 [**Product Name**](https://store.com/product)
  - Type: Product | Store: Store Name
  - Summary: Brief description
  - Date added: 2024-03-15
  - Topics: #shopping #category
```

#### Generic Web Links
```markdown
- [ ] 🔗 [**Page Title**](https://example.com/page)
  - Type: Website/Resource
  - Summary: Brief description
  - Date added: 2024-03-15
  - Topics: #topic
```

**Emoji Indicators:**
- 📽️ YouTube videos
- 📝 Articles and blog posts
- 📚 Documentation / Courses
- 💻 Code repositories (GitHub, GitLab)
- 🛒 Products / Shopping
- 🔗 Generic web links

**Key rules:**
- Always prefix URL with `https://` if missing
- Preserve the `#YYYY-MM-DD` date as `Date added:` metadata
- Strip UTM parameters and tracking query strings from URLs when possible (keep essential params like `?v=` for YouTube, `?variant=` for products)
- If WebFetch/YouTube MCP fails to get metadata, use a minimal format with just the URL and date

## Git Safety and Task Management

### Task Management (MANDATORY)

This skill **MUST** use task management to track progress. Tasks are not optional.

**BEFORE starting any work, create all 10 tasks with proper dependencies:**

#### Task Creation (Step 0 - Do this FIRST)

```javascript
// Task #1: Pre-commit pending changes
TaskCreate({
  subject: "Pre-commit pending changes",
  description: "Auto-commit all pending changes to create a clean baseline checkpoint.\n\nActions:\n- Run git status --short\n- git add -A && git commit with descriptive message\n- Record commit hash as CHECKPOINT_COMMIT\n\nThis is an auto-commit. Do NOT prompt the user.",
  activeForm: "Pre-committing pending changes"
})

// Task #2: Read iPhone.md and parse all links
TaskCreate({
  subject: "Read iPhone.md and parse all links",
  description: "Read iPhone.md and extract all links.\n\nActions:\n- Read entire iPhone.md file\n- Parse each '* [ ] Look into:' line into {url, date, line_number}\n- Detect new links at bottom (last ~10 entries, most recent dates)\n- Count total links\n- Identify junk entries: about:blank, empty URLs, broken XML\n- Identify exact duplicate URLs\n- Report: total links, new links, junk, duplicates",
  activeForm: "Parsing iPhone.md links"
})

// Task #3: Classify links
TaskCreate({
  subject: "Classify links using domain heuristics and tools",
  description: "Classify each link into a target category.\n\nActions:\n- Tier 1: Run all links through domain heuristic matching\n- Tier 2: For unclassified links, batch WebFetch (5-10 parallel) to get page titles and summaries\n- Tier 3: For YouTube links, batch get_video_info to determine topic\n- Tier 4: Mark remaining as 'uncategorizable' (stays in iPhone.md)\n- Build classification report: {url, date, category, target_file, confidence, title_if_known}",
  activeForm: "Classifying links"
})

// Task #4: Read target reference files
TaskCreate({
  subject: "Read target reference files to understand existing content",
  description: "Read all target reference files to:\n- Understand existing section structure\n- Check for duplicate URLs already present in targets\n- Determine where to append new links (end of file or specific section)\n- Flag any links from iPhone.md that already exist in a target file",
  activeForm: "Reading target reference files"
})

// Task #5: Present proposed moves for approval
TaskCreate({
  subject: "Present proposed moves for user approval",
  description: "Use AskUserQuestion to present the classification results.\n\nPresent in groups:\n1. NEW links (recently added at bottom) - show first for visibility\n2. Confident moves (domain heuristic matches) - grouped by target file\n3. Tool-assisted moves (WebFetch/YouTube classified) - with titles\n4. Junk entries (about:blank, empty, broken) - propose deletion\n5. Duplicates - propose keeping earliest, deleting rest\n6. Uncategorizable - will be organized into sections in iPhone.md\n\nShow counts: 'Moving X links to Y files, deleting Z junk, keeping W in iPhone.md'\n\nCollect user decisions before proceeding.",
  activeForm: "Presenting proposed moves"
})

// Task #6: Execute approved moves
TaskCreate({
  subject: "Execute approved moves to target files",
  description: "For each approved move:\n1. Enrich link to fix-reference format (fetch metadata if not already done)\n2. Append enriched link to target file (at end of file or appropriate section)\n3. Remove original line from iPhone.md\n\nProcess in batches by target file to minimize file writes.\nUse parallel WebFetch/YouTube calls for metadata enrichment.\n\nTrack: {target_file: count_added} for validation.",
  activeForm: "Moving links to target files"
})

// Task #7: Organize remaining iPhone.md links into sections
TaskCreate({
  subject: "Organize remaining iPhone.md links into sections",
  description: "Links staying in iPhone.md should be grouped into topic sections.\n\nSections are created based on what actually remains, not predefined. Possible sections:\n- ## Shopping & Products\n- ## Coffee & Kitchen\n- ## Home & DIY\n- ## Health & Fitness\n- ## Islamic & Spiritual\n- ## Miscellaneous\n\nPreserve the header note about iOS shortcuts at the top.\nKeep # iPhone as the title.\nDo NOT create empty sections.",
  activeForm: "Organizing remaining iPhone.md links"
})

// Task #8: Clean up iPhone.md
TaskCreate({
  subject: "Clean up iPhone.md (delete junk, deduplicate)",
  description: "With user approval from Task #5:\n- Delete about:blank entries\n- Delete empty 'Look into:' entries\n- Deduplicate: remove exact URL duplicates (keep the one with earliest date)\n\nTrack count of deleted lines for validation.",
  activeForm: "Cleaning up iPhone.md"
})

// Task #9: Validate link counts via git diff
TaskCreate({
  subject: "Validate link counts via git diff",
  description: "CRITICAL validation step.\n\nActions:\n- Run git diff --stat to see per-file changes\n- Count links removed from iPhone.md\n- Count links added across all target files\n- Count links approved for deletion (junk + duplicates)\n- Verify: removed_from_iphone = added_to_targets + approved_deletions\n- Verify: target files only have additions (no existing content modified)\n- Verify: iPhone.md deletions + reorganization only\n\nIf counts don't balance: STOP and report discrepancy.\nIf validation passes: show per-file summary.",
  activeForm: "Validating link counts"
})

// Task #10: Create git commit
TaskCreate({
  subject: "Create git commit",
  description: "Only proceed if Task #9 validation passes.\n\nCommit message format:\nfeat(noteplan): Sort iPhone links to categorized reference files\n\n- Moved X links from iPhone.md to Y reference files\n- Deleted Z junk/duplicate entries\n- Organized W remaining links into sections\n\nPer-file breakdown:\n- References[GenAI].md: +N links\n- References[Career].md: +N links\n- ...\n- iPhone.md: -X links moved, -Z deleted, W remaining\n\nValidated via git diff: removed = added + deleted\nSkill: sort-iphone-links\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>",
  activeForm: "Creating git commit"
})
```

#### Set Up Task Dependencies

**After creating all 10 tasks, set up dependencies:**

```javascript
// Task #2 depends on #1 (need clean baseline)
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })

// Task #3 depends on #2 (need parsed links to classify)
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })

// Task #4 depends on #3 (read targets after classification to check for existing URLs)
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })

// Task #5 depends on #4 (need target file context for proposal)
TaskUpdate({ taskId: "5", addBlockedBy: ["4"] })

// Tasks #6 and #7 depend on #5 (need user approval), can run in PARALLEL
TaskUpdate({ taskId: "6", addBlockedBy: ["5"] })
TaskUpdate({ taskId: "7", addBlockedBy: ["5"] })

// Task #8 depends on #6 and #7 (clean up after moves and reorganization)
TaskUpdate({ taskId: "8", addBlockedBy: ["6", "7"] })

// Task #9 depends on #8 (validate after all changes)
TaskUpdate({ taskId: "9", addBlockedBy: ["8"] })

// Task #10 depends on #9 (commit only if validation passes)
TaskUpdate({ taskId: "10", addBlockedBy: ["9"] })
```

#### Task Dependency Flow

```
#1  Pre-commit pending changes
 └─► #2  Read iPhone.md and parse all links
      └─► #3  Classify links (domain heuristics + WebFetch/YouTube)
           └─► #4  Read target reference files
                └─► #5  Present proposed moves for approval
                     ├─► #6  Execute approved moves (parallel)
                     └─► #7  Organize remaining iPhone.md links (parallel)
                          └─► #8  Clean up iPhone.md
                               └─► #9  Validate link counts via git diff
                                    └─► #10 Create git commit
```

Tasks #6 and #7 can run in parallel after #5 approval.

#### Update Task Status During Workflow

**ALWAYS update task status as you progress:**

```javascript
// When starting a task
TaskUpdate({ taskId: "1", status: "in_progress" })

// When completing a task
TaskUpdate({ taskId: "1", status: "completed" })

// List tasks to show progress
TaskList()
```

## Workflow

When invoked, **ALWAYS follow this exact workflow:**

### Step 0: Task Setup (MANDATORY FIRST STEP)

Before doing ANY work, create all 10 tasks with dependencies:

```
1. Create 10 tasks (see Task Management section)
2. Set up task dependencies using TaskUpdate
3. Run TaskList to show workflow to user
4. Mark Task #1 as in_progress to begin work
```

**Display task plan to user:**
```
Sort iPhone Links - Task Workflow (10 Tasks)

#1  Pre-commit pending changes [STARTING]
 └─► #2  Parse iPhone.md links
      └─► #3  Classify links
           └─► #4  Read target files
                └─► #5  Present moves for approval
                     ├─► #6  Execute moves
                     └─► #7  Organize remaining links
                          └─► #8  Clean up junk/duplicates
                               └─► #9  Validate counts
                                    └─► #10 Create commit

Ready to begin!
```

### Step 1 (Task #1): Pre-commit Pending Changes

Auto-commit all pending changes to create a clean baseline:

```bash
cd "$NOTEPLAN_ROOT"

# Check current state
git status --short

# Stage and commit everything
git add -A
git commit -m "$(cat <<'EOF'
chore(noteplan): Auto-commit pending changes before iPhone link sorting

Auto-committed by sort-iphone-links skill to create clean baseline.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"

# Record checkpoint
CHECKPOINT_COMMIT=$(git rev-parse HEAD)
```

**This is an auto-commit. Do NOT prompt the user.**

### Step 2 (Task #2): Parse iPhone.md

Read the entire file and extract all links:

1. **Preserve header**: Lines 1-4 (title + notes about iOS shortcuts) are preserved as-is
2. **Parse each link line**: Extract `{url, date_tag, line_number}` from `* [ ] Look into: <URL>  #YYYY-MM-DD`
3. **Detect new links**: Check bottom 10 entries for recent dates (within last 2 weeks)
4. **Identify junk**: `about:blank`, empty URLs (just `* [ ] Look into:` with no URL), broken XML
5. **Identify duplicates**: Group by normalized URL (strip tracking params), flag exact duplicates
6. **Report**:
   ```
   Parsed iPhone.md:
   - Total link entries: 225
   - New links (recent): 5
   - Junk entries: 3 (2x about:blank, 1x empty)
   - Duplicate URLs: 4 (2 pairs)
   - Links to classify: 218
   ```

### Step 3 (Task #3): Classify Links

Process in three tiers:

**Tier 1: Domain heuristics** (process all links):
- Match URL against the domain pattern table
- Expected to classify ~60-70% of links

**Tier 2: WebFetch** (batch process unclassified):
- Take unclassified links in batches of 5-10
- Use parallel WebFetch calls:
  ```
  WebFetch(url, "Extract the page title and a one-sentence summary. What category: AI/ML, Career, Business, Software, Tools, Shopping, Education, Personal, or Other?")
  ```

**Tier 3: YouTube MCP** (for video links):
- Collect all YouTube/youtu.be URLs
- Process in batches of 5-6 using parallel `get_video_info` calls
- Use video title and description to determine category

**Build classification report:**
```
Classification Results:
- GenAI: 12 links → References[GenAI].md
- Shopping: 28 links → Shopping.md
- Career: 8 links → References[Career].md
- ...
- Uncategorizable: 15 links → stays in iPhone.md
- Junk: 3 → delete
- Duplicates: 4 → delete
```

### Step 4 (Task #4): Read Target Reference Files

For each target file that will receive links:
- Read the file to understand existing structure
- Check if any iPhone.md URLs already exist in the target (avoid duplicates)
- Identify the best insertion point (end of file, or within an existing section)

### Step 5 (Task #5): Present Proposed Moves

Use `AskUserQuestion` to present the plan:

```
Proposed iPhone Link Triage:

NEW LINKS (recently added):
  5 links from last 2 weeks → classified as [categories]

MOVES (by target file):
  References[GenAI].md:     +12 links
  Shopping.md:              +28 links
  References[Career].md:    +8 links
  References[Software].md:  +10 links
  References[Personal].md:  +15 links
  Activities[Austin].md:    +5 links
  References[Business].md:  +6 links
  [... other files ...]

CLEANUP:
  Delete 3 junk entries (about:blank, empty)
  Delete 4 duplicate URLs (keep earliest)

REMAINING in iPhone.md:
  15 uncategorizable links → organized into sections

Total: 225 links → 195 moved + 7 deleted + 23 remaining

Approve this plan?
```

Options:
- **Approve all** - Execute as proposed
- **Review by category** - Show links per category for fine-grained approval
- **Skip cleanup** - Move links but don't delete junk

### Step 6 (Task #6): Execute Approved Moves

For each target file, process all approved links:

1. **Enrich each link** to fix-reference format:
   - For YouTube: call `get_video_info` if not already done
   - For articles: call `WebFetch` if not already done
   - For products: use domain as store name
   - For GitHub: extract owner/repo from URL
   - Strip UTM/tracking parameters from URLs
   - Add `https://` prefix if missing

2. **Append to target file**:
   - Add enriched links at the end of the file
   - If file has sections, add under the most relevant existing section (or create a new one)

3. **Remove from iPhone.md**:
   - Delete the original `* [ ] Look into:` line

4. **Track counts**: `{target_file: count_added}` for validation

### Step 7 (Task #7): Organize Remaining iPhone.md Links

Links staying in iPhone.md should be grouped into meaningful sections:

1. **Analyze remaining links** to determine natural groupings
2. **Create sections** based on what actually remains (do NOT create empty sections)
3. **Preserve the header** (lines 1-4 with iOS shortcuts note)
4. **Format**:
   ```markdown
   # iPhone
   * *Note - renaming this will break the iOS shortcuts automation ...*
   * Edit: vscode://file/...

   ## Shopping & Products
   * [ ] Look into: ...

   ## Home & DIY
   * [ ] Look into: ...

   ## Miscellaneous
   * [ ] Look into: ...
   ```

### Step 8 (Task #8): Clean Up iPhone.md

With user approval from Task #5:
- Delete `about:blank` entries
- Delete empty `* [ ] Look into:` entries (no URL)
- Deduplicate: for exact URL duplicates, keep the one with the earliest `#YYYY-MM-DD` date

Track count of deleted lines.

### Step 9 (Task #9): Validate Link Counts

**CRITICAL validation step:**

```bash
cd "$NOTEPLAN_ROOT"

# Show per-file changes
git diff --stat

# Count specific changes
git diff "Notes/🏡 Personal/🏡📋 Lists/iPhone.md" | grep "^-\* \[ \] Look into:" | wc -l  # removed
git diff "Notes/🏡 Personal/🏡📋 Lists/" | grep "^+- \[ \]" | wc -l  # added to targets
```

**Verify the equation:**
```
Links removed from iPhone.md = Links added to target files + Links deleted (junk + duplicates)
```

**Also verify:**
- Target files: only additions, no existing content modified
- iPhone.md: deletions (moved/deleted links) + reorganization (sections added)
- No link content changed (URLs preserved exactly)

**If counts don't balance:** STOP and report the discrepancy. Do NOT proceed to commit.

**Show validation summary:**
```
Validation Results:

iPhone.md:
  - Lines removed: 195 (moved) + 7 (deleted) = 202
  - Lines remaining: 23 (organized into 3 sections)

Target files:
  - References[GenAI].md:     +12 links (48 lines added)
  - Shopping.md:              +28 links (112 lines added)
  - ...
  Total: +195 links across 12 files

Balance check: 202 removed = 195 moved + 7 deleted [PASS]
No existing content modified in target files [PASS]
```

### Step 10 (Task #10): Create Git Commit

**Only proceed if Task #9 validation passes.**

```bash
cd "$NOTEPLAN_ROOT"

# Stage all changes
git add "Notes/🏡 Personal/🏡📋 Lists/"

# Create commit
git commit -m "$(cat <<'EOF'
feat(noteplan): Sort iPhone links to categorized reference files

- Moved 195 links from iPhone.md to 12 reference files
- Deleted 7 junk/duplicate entries
- Organized 23 remaining links into sections

Per-file breakdown:
- References[GenAI].md: +12 links
- Shopping.md: +28 links
- References[Career].md: +8 links
- References[Software].md: +10 links
- References[Personal].md: +15 links
- [... other files ...]

iPhone.md: -202 links (195 moved, 7 deleted), 23 remaining in 3 sections

Validated via git diff: removed (202) = added (195) + deleted (7)
Skill: sort-iphone-links

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

**Adjust the commit message to reflect actual counts.**

**Complete Task #10 and show final summary:**

```javascript
TaskUpdate({ taskId: "10", status: "completed" })
TaskList()
```

```
Sort iPhone Links Complete!

Task #1:  Pre-commit pending changes
Task #2:  Parsed 225 links from iPhone.md
Task #3:  Classified links (180 by domain, 25 by WebFetch, 12 by YouTube, 8 manual)
Task #4:  Read 12 target reference files
Task #5:  User approved 195 moves + 7 deletions
Task #6:  Moved 195 links to target files with enriched metadata
Task #7:  Organized 23 remaining links into 3 sections
Task #8:  Deleted 7 junk/duplicate entries
Task #9:  Validated: 202 removed = 195 moved + 7 deleted
Task #10: Created git commit [HASH]

All tasks completed!
```

## Safety Checks

- **Pre-commit**: Always auto-commit pending changes before making any modifications
- **Preserve iPhone.md header**: Never modify the first few lines (iOS shortcuts note)
- **Don't rename iPhone.md**: The filename is used by iOS shortcuts automation
- **URL preservation**: Never modify the actual URL, only add markdown link syntax
- **User approval**: Always present proposed moves and get explicit approval before executing
- **Count validation**: Always verify removed = added + deleted before committing
- **No content loss**: Every removed link must appear in a target file or be explicitly approved for deletion
- **Target file safety**: Only append to target files, never modify existing content
- **Single commit**: All changes in one atomic commit for easy revert if needed

## Handling Edge Cases

### Links Already in Target Files
If a URL from iPhone.md already exists in a target file:
- Skip the move (don't create duplicates)
- Remove from iPhone.md (it's already where it belongs)
- Count as "already present" in validation

### Failed WebFetch/YouTube Calls
If metadata extraction fails for a link:
- Use minimal format: `- [ ] 🔗 [**domain.com**](https://domain.com/path)` with date added
- Don't block the entire workflow on one failed fetch
- Report failures in the summary

### Links with Existing Markdown
Some iPhone.md entries already have markdown links:
```
* [ ] Look into: [How to disassemble...](youtube.com/...) #2024-04-12
```
- Extract URL from the markdown link
- Use the existing title as the enriched title
- Preserve user's context

### Broken/Invalid URLs
- `about:blank` → delete with approval
- Empty entries → delete with approval
- XML fragments → delete with approval
- Google search URLs → classify by search query content or mark as junk

### UTM Parameter Stripping
Strip these query parameters when enriching URLs:
- `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`, `utm_id`
- `fbclid`, `gclid`, `gad_source`, `gbraid`
- `hsa_*` parameters
- `tw_source`, `tw_adid`
- `campaign_id`, `ad_id`, `adset_id`
- Keep essential params: `?v=` (YouTube), `?variant=` (products), `#section` (anchors)

## Example Transformation

### Before (iPhone.md entry):
```markdown
* [ ] Look into: blog.langchain.dev/evaluating-llms-with-openevals/  #2025-03-02
```

### After (in References[GenAI].md):
```markdown
- [ ] 📝 [**Evaluating LLMs with OpenEvals** (Article, 2025-03-02)](https://blog.langchain.dev/evaluating-llms-with-openevals/)
  - Author: LangChain Team | Publisher: blog.langchain.dev
  - Summary: Overview of OpenEvals framework for evaluating large language models
  - Date added: 2025-03-02
  - Topics: #langchain #llm #evaluation #openevals
```

### Before (iPhone.md entry):
```markdown
* [ ] Look into: youtu.be/yJ6AxxlVNwA  #2026-01-31
```

### After (in appropriate target file):
```markdown
- [ ] 📽️ [**Video Title Here** (YouTube, YYYY-MM-DD)](https://youtu.be/yJ6AxxlVNwA)
  - Author: Channel Name | Duration: XX minutes
  - Summary: Brief description from video metadata
  - Date added: 2026-01-31
  - Topics: #topic1 #topic2
```

## Related Skills

- **fix-reference** - Organize and enrich links within a single reference file (this skill moves links between files)
- **fix-filenames** - Fix filenames to match heading conventions
- **analyze-structure** - Analyze NotePlan structure and detect patterns
