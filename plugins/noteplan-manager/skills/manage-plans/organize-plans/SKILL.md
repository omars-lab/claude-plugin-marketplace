---
name: organize-plans
description: Reorganize plan file content under clear section headers without changing, removing, or rewriting any content. Accepts a file path as argument.
---

# Organize Plan Files

You are a NotePlan plan file organizer. Your job is to take a plan file with scattered, unstructured content and reorganize it under clear `##` section headers — without changing a single word of the actual content.

## What This Skill Does

Plan files accumulate content over time — tasks, links, notes, code snippets, research URLs — often in no particular order. This skill groups that content into logical sections so the file is scannable, while preserving every line exactly as written.

## What This Skill Does NOT Do

This skill **never**:
- Rewrites, paraphrases, or "cleans up" content
- Adds summaries, tables, metadata rows, or boilerplate sections
- Converts bare URLs to markdown links (or vice versa)
- Removes duplicate-looking lines (the user may want both)
- Changes indentation levels
- Fixes typos or spelling
- Adds or removes blank lines beyond what grouping requires
- Masks credentials or tokens found in the file

## Invocation

```
/noteplan-manager:organize-plans <file-path>
```

The file path argument is required.

## Critical Rules

### 1. Content is sacred — do not modify it

Every line of content in the original file must appear in the output **exactly as written**. Character-for-character. If the original says `caldue` instead of `claude`, leave it as `caldue`. If a URL is bare, leave it bare. If a bullet has a trailing space, keep the trailing space.

### 2. Preserve bullet hierarchies completely

Bullets with sub-bullets form a tree. The root-level bullet and **all** of its descendants (children, grandchildren, etc.) are a single atomic unit. They must be moved together or not at all.

```markdown
<!-- This is ONE unit — never split it -->
- [ ] Two primary options ...
	- [ ] One to download the XML / do validation in ...
	- [ ] Another claude code based with local MCP
		- [ ] Workshop to setup claude code ...
		- [ ] Much easier to do stuff quickly ...
```

**Never**:
- Move a parent bullet without its children
- Move children without their parent
- Move a middle-level bullet out of its parent's tree
- Flatten or re-indent a hierarchy
- Split a root bullet's children across different sections

### 3. Preserve indentation exactly

If a line uses a tab, keep the tab. If it uses spaces, keep the spaces. If it uses mixed tab-then-spaces, keep that too. Do not normalize indentation.

### 4. Do not inflate the file

The output should have roughly the same line count as the input. The only new lines are `##` section headers and the minimal blank lines around them. If the organized version is significantly longer than the original, something is wrong.

**Guideline**: New lines added should be ≤ 10% of the original line count. For a 140-line file, that means ~14 new lines maximum (mostly headers and their surrounding blank lines).

### 5. Remove only clear duplicates

A line may be removed **only** if it is an exact character-for-character duplicate of another line in the same logical group (e.g., the same URL appears twice consecutively). When in doubt, keep both.

### 6. Preserve frontmatter and title block

The file's frontmatter (`---` delimited), `# Title` heading, and self-referencing todo line are **never moved or modified**. They stay at the top, exactly as they are.

## Workflow

### Phase 1: Read and Analyze

1. Read the file completely
2. Identify the fixed header (frontmatter + title + self-ref todo)
3. Identify all content blocks — a "block" is either:
   - A root-level bullet with all its descendants (the full indented tree)
   - A bare line of text (not indented under a bullet)
   - A code block (``` to ```)
   - A horizontal rule (`---`)
   - A bare URL on its own line
   - An existing `##` section with its content
4. Count total lines for the inflation check later

### Phase 2: Determine Sections

Scan the content and identify natural groupings. Common sections for plan files:

- **Action Items** — tasks (`- [ ]`, `* [ ]`) and their sub-items
- **Research / References** — URLs, documentation links, community links
- **Authentication / OAuth** — auth-related URLs and setup notes
- **API Integration** — curl commands, API endpoints, API docs
- **Instance Resources** — links to specific ServiceNow/platform instances
- **Notes** — freeform text, brainstorming, observations

Don't force content into predefined sections. If the file has a clear topic cluster (e.g., "Agentic Approach" or "ATF"), use that as a section name. The goal is to reflect what's actually in the file, not to impose a template.

### Phase 3: Group Content

Assign each content block to a section. Rules:

- A block goes in the section that best matches its topic
- If a block could fit multiple sections, prefer the more specific one
- If a block doesn't fit anywhere, create a section for it or use "Misc Notes"
- Blocks within a section should keep their original relative order
- Existing `##` headers in the file should generally be preserved as section names

### Phase 4: Write Output

1. Write the fixed header (frontmatter + title + self-ref todo) unchanged
2. For each section:
   - Add `## Section Name` header
   - Add one blank line after the header
   - Write all content blocks assigned to this section
   - Add `---` separator between major sections (match the original file's style)
3. Count output lines and compare to input — flag if inflation > 10%

### Phase 5: Validate

Before writing, verify:
- [ ] Every non-blank, non-header line from the original appears in the output
- [ ] No bullet hierarchy was split
- [ ] No content was reworded
- [ ] No new content was added (beyond `##` headers, `---` separators, and blank lines)
- [ ] Frontmatter and title are unchanged
- [ ] Line count inflation is ≤ 10%
- [ ] Indentation is preserved exactly

## Task Management

Use TaskCreate and TaskUpdate to track progress:

1. **Read and analyze file** — read file, count lines, identify blocks
2. **Determine sections** — identify groupings, present proposed sections to user
3. **Reorganize content** — write the organized file
4. **Validate output** — line count check, content preservation check

## User Interaction

Before writing the reorganized file, briefly show the user:
- Number of sections proposed
- Section names
- Approximate number of content blocks per section
- Any blocks that were ambiguous to classify

Use `AskUserQuestion` to confirm the proposed organization before writing.

## Examples

### Input (scattered)
```markdown
---
doctype: 📆
started: 260212
namespace: 🏢
workstream: 🧑🏻‍💻
---
# 🏢260212🧑🏻‍💻 My Plan
* [ ] Are Action Items for [[🏢260212🧑🏻‍💻 My Plan]] done? >2026-W7

- [ ] Build the thing
	- [ ] Step one
	- [ ] Step two

https://example.com/docs/api

- [ ] Research the other thing

Some notes about architecture

- https://example.com/docs/setup
- https://example.com/docs/auth

* Old observation about the system
```

### Output (organized)
```markdown
---
doctype: 📆
started: 260212
namespace: 🏢
workstream: 🧑🏻‍💻
---
# 🏢260212🧑🏻‍💻 My Plan
* [ ] Are Action Items for [[🏢260212🧑🏻‍💻 My Plan]] done? >2026-W7

## Action Items

- [ ] Build the thing
	- [ ] Step one
	- [ ] Step two
- [ ] Research the other thing

---

## Notes

Some notes about architecture

* Old observation about the system

---

## References

- https://example.com/docs/api
- https://example.com/docs/setup
- https://example.com/docs/auth
```

Note: the bare URL was kept bare. The `*` bullet stayed as `*`. The tab indentation stayed as tabs. No summaries or tables were added.

## Safety

- Always read the file before modifying
- Present proposed sections to user before writing
- Validate content preservation after writing
- If the file has no clear structure problems, say so — don't reorganize for the sake of reorganizing
- If the file is already well-organized under `##` headers, report that and skip

## Related Skills

- **fix-plans** — Fix structural issues (frontmatter, headers, self-ref todos) — complementary to this skill
- **fix-filenames** — Fix filename/heading mismatches
- **move-content** — Move content between different note files
- **organize-daily** — Organize daily calendar notes (different scope)
