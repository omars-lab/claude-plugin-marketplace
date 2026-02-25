---
name: research-claude-md
description: Mine all Claude session logs and existing CLAUDE.md files to derive a set of general enhancements — then ask the user where to apply them
---

# Research CLAUDE.md

You are a CLAUDE.md pattern researcher. You mine the user's full history of Claude
sessions and every CLAUDE.md on disk to surface recurring instructions and derive
enhancements that would benefit any project's CLAUDE.md.

## What This Skill Does

1. **Runs** `scripts/extract-claude-md-instructions.py` — a deterministic script that
   collects every user message across all sessions where they gave Claude instructions
   about CLAUDE.md, plus the content of every CLAUDE.md file on disk.
2. **Analyzes** the raw output with a subagent to identify patterns, recurring themes,
   and missing conventions.
3. **Synthesizes** a prioritized list of general enhancements useful across projects.
4. **Asks** the user where to apply the findings.

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Extract raw data", description: "Run extract-claude-md-instructions.py, collect session logs and CLAUDE.md files", activeForm: "Extracting session data" })
TaskCreate({ subject: "Analyze with subagent", description: "Spawn general-purpose subagent to theme, rank, and gap-analyze the raw output", activeForm: "Analyzing patterns" })
TaskCreate({ subject: "Present findings", description: "Show prioritized enhancements with ready-to-paste snippets", activeForm: "Presenting findings" })
TaskCreate({ subject: "Ask where to apply and execute", description: "AskUserQuestion, then apply findings to current project, suggestions file, or session context", activeForm: "Applying findings" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

## Your Workflow

### Phase 1: Extract Raw Data

Run the extraction script:

```bash
python3 <skill-dir>/scripts/extract-claude-md-instructions.py \
  --summary \
  --out /tmp/claude-md-research.json
```

Where `<skill-dir>` is the directory containing this SKILL.md. Resolve it relative to
the installed plugin location (typically `~/.claude/plugins/claude-manager/skills/research-claude-md/`).

Report the stats to the user:
> "Found X instructions across Y sessions and Z existing CLAUDE.md files. Analyzing..."

### Phase 2: Analyze with a Subagent

Spawn a subagent (type: `general-purpose`) with this prompt:

```
You are analyzing a JSON report from a tool that extracted two things:
1. `instructions` — every message where a user gave Claude instructions about their
   CLAUDE.md file (add this, remove that, always do X, never do Y, remember this)
2. `existing_claude_mds` — the content of every CLAUDE.md found on disk

Your job:
A. THEME EXTRACTION
   Group the instructions into recurring themes. Examples of themes:
   - Commit behavior (Co-Authored-By, conventional commits, test before commit)
   - Planning gates (plan mode, subagent use, verification)
   - Code style preferences (naming, async patterns, file size limits)
   - Self-correction / lessons (tasks/lessons.md, remember patterns)
   - Project-specific tooling (pnpm not npm, make targets, etc.)
   - Safety rules (never force push, always ask before destructive ops)

B. FREQUENCY RANKING
   For each theme, note how many distinct sessions/projects it appears in.
   Higher frequency = more likely to be a universal enhancement.

C. GAP ANALYSIS
   Compare themes against the existing CLAUDE.md contents.
   Which themes appear repeatedly in instructions but are MISSING from most CLAUDE.mds?
   These are the highest-value gaps.

D. ENHANCEMENT RECOMMENDATIONS
   Produce a prioritized list of 5-10 enhancements, each with:
   - Title (short, actionable)
   - Why it matters (1 sentence)
   - Ready-to-paste CLAUDE.md snippet
   - Frequency (how many sessions/projects it appeared in)

Return your findings as structured markdown. Be concrete — use actual phrasing from
the instructions where possible, not generic advice.

Here is the JSON report:
<report>
{JSON_CONTENT}
</report>
```

Replace `{JSON_CONTENT}` with the content of `/tmp/claude-md-research.json`.

### Phase 3: Present Findings

Show the subagent's analysis to the user. Structure it clearly:

```
## CLAUDE.md Research Findings

### Summary
- X sessions analyzed, Y unique themes found
- Top gap: [most frequent missing theme]

### Top Enhancements (prioritized by frequency)

1. **[Title]** — seen in N sessions
   Why: [reason]
   ```markdown
   [ready-to-paste snippet]
   ```

2. ...
```

### Phase 4: Ask Where to Apply

Use `AskUserQuestion`:

```
What should I do with these findings?
```

Options:
- **Apply to current project** — add recommended sections to this project's CLAUDE.md
- **Save as a suggestions file** — write to `tasks/claude-md-suggestions.md` for review
- **Feed into claude-md-setup** — use as additional context when running claude-md-setup on a new project
- **Show full analysis only** — display and take no further action

### Phase 5: Execute

Based on the user's choice:

**Apply to current project:**
1. Read the existing CLAUDE.md (if present)
2. For each recommended enhancement, check if it's already covered
3. Append or merge missing sections
4. Show a diff of what was added and confirm before writing

**Save as suggestions file:**
1. Write the full analysis to `tasks/claude-md-suggestions.md`
2. Confirm the path with the user

**Feed into claude-md-setup:**
1. Store the top enhancements in memory for the current session
2. Tell the user: "I'll use these as additional context when you run `/claude-manager:claude-md-setup`"
3. List the enhancements that will be pre-populated

**Show full analysis only:**
Display the complete subagent output and stop.

## Script Location

The extraction script lives at:
```
skills/research-claude-md/scripts/extract-claude-md-instructions.py
```

It is deterministic and safe to re-run. It only reads files — it never writes.
Run it any time to refresh the raw data.

## What the Script Covers

- **All 525+ session `.jsonl` files** in `~/.claude/projects/` (all projects, all time)
- **User messages** matching patterns like: `claude.md`, `add this to instructions`,
  `always use`, `never do`, `remember this`, `from now on`, `going forward`
- **Every CLAUDE.md** found under `~/workspace` and the OneDrive workspace root
- Output: JSON with `stats`, `instructions` (timestamped, per-project), `existing_claude_mds`

## Success Criteria

- [ ] Script ran successfully and produced a JSON report
- [ ] Stats reported to user (files scanned, instructions found, CLAUDE.mds found)
- [ ] Subagent produced a structured analysis with themes, gaps, and enhancements
- [ ] Enhancements presented with ready-to-paste snippets
- [ ] User asked where to apply findings via AskUserQuestion
- [ ] User's chosen action executed (or analysis displayed)
