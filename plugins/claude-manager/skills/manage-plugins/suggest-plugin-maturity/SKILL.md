---
name: suggest-plugin-maturity
description: Optional suggestions to make skills smarter over time — usage tracking, knowledge artifact growth, feedback loops, and maturity scoring
---

# Suggest Plugin Maturity

You are an optional plugin maturity advisor. When this skill is invoked, you analyze skills for opportunities to grow smarter over time — not compliance failures, but investments that pay off with repeated use.

**This skill is advisory only.** Everything here is optional. There are no errors, only opportunities.

## What This Skill Does

1. Scans plugins and skills for three maturity dimensions
2. Scores each skill on a 0–3 maturity scale
3. Presents findings as opportunities, not failures
4. Asks which suggestions to implement

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Confirm scope", description: "Ask user which plugins to analyze", activeForm: "Confirming scope" })
TaskCreate({ subject: "Scan skills for maturity signals", description: "Check each skill for learnings sections, knowledge artifacts, feedback loops", activeForm: "Scanning skills" })
TaskCreate({ subject: "Present maturity report", description: "Show scored suggestions to user", activeForm: "Presenting maturity suggestions" })
TaskCreate({ subject: "Implement selected suggestions", description: "Apply user-approved maturity improvements", activeForm: "Adding maturity patterns" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

## Your Workflow

### Phase 1: Confirm Scope

Use `AskUserQuestion`:

```
Which plugins should I analyze for maturity opportunities?

Options:
- All plugins in the marketplace
- Specific plugin (enter name)
- Only fix-* and sync-* skills (most likely to benefit)
```

### Phase 2: Scan for Maturity Signals

For each skill, check three dimensions:

#### Dimension 1: Usage Tracking (Maturity Level 1)

**What to look for:**
- Does SKILL.md have a "Key Learnings", "Execution History", or "Execution Insights" section?
- Does the skill record what it found and fixed after each run?

**Detection:**
```bash
grep -rl "Key Learnings\|Execution Insights\|Usage History\|Known Edge Cases" skills/*/SKILL.md
```

**Best fit for:** Skills that run repeatedly on similar data — `fix-*`, `organize-*`, `sync-*`, `update-*`

**The pattern:**
```markdown
## Key Learnings & Execution History

### Execution: YYYY-MM-DD
**Scope:** N files processed
**Results:** X fixed, Y skipped, Z conflicts
**Edge cases:**
- Description of unexpected situations encountered
**Recurring pattern:** Description of issues that keep appearing
```

#### Dimension 2: Knowledge Artifact Growth (Maturity Level 2)

**What to look for:**
- Does the skill produce insights that benefit other skills in the same plugin?
- Is there a shared reference file that multiple skills maintain and consume?

**Detection:**
```bash
grep -rl "conventions\|shared.*reference\|canonical\|accumulate\|grows over time" skills/*/SKILL.md
```

**Concrete examples:**

| Skill | Byproduct Knowledge | Could Live At |
|---|---|---|
| `fix-filenames` | Naming conventions, edge cases | `skills/fix-filenames/conventions.md` |
| `fix-work-emojis` + `fix-personal-emojis` | Canonical emoji list, encoding gotchas | Shared emoji reference |
| `analyze-structure` | Folder hierarchy, file counts | Structure snapshot other skills read |

**The pattern:**
```markdown
## Knowledge Artifacts

### Shared Conventions Reference
**Location:** `skills/fix-filenames/conventions.md`
**Updated by:** fix-filenames (when new patterns discovered)
**Read by:** create-note, quick-note, introduce

After each execution, if a new naming pattern is found that isn't documented,
offer to append it to the conventions reference.
```

#### Dimension 3: Feedback Loops / Self-Healing (Maturity Level 3)

**What to look for:**
- Does the skill detect when it's fixing the same issue repeatedly?
- Does it suggest root-cause fixes beyond its own scope?

**Detection:**
```bash
grep -rl "recur\|recurring\|root cause\|self-heal\|feedback\|pattern.*detect" skills/*/SKILL.md
```

**Three sub-levels:**

**Level 3a — Detect Recurrence:**
```markdown
## Recurrence Detection

After each execution, check if the same issues appeared as last time:
- If issue recurs 3+ times → flag as RECURRING and suggest root cause fix
- If a new issue type appears → flag as NEW for tracking
```

**Level 3b — Suggest Root Causes:**
```markdown
## Root Cause Suggestions

When patterns recur, suggest fixes at the source:
- "Same duplicates keep appearing → check NotePlan sync settings"
- "Same emojis keep being wrong → template may be out of date"
```

**Level 3c — Self-Updating (Advanced):**
```markdown
## Self-Healing Updates

After execution, if new patterns warrant it, offer to update SKILL.md:
- "Discovered new folder type not in conventions table. Add? (yes/no)"
```

Use `AskUserQuestion` before any self-modification. Never silently self-edit.

### Phase 3: Present Maturity Report

Format the report clearly as opportunities:

```
═══════════════════════════════════════════════════════════════
              Plugin Maturity Suggestions (Optional)
═══════════════════════════════════════════════════════════════

These are opportunities, not requirements. Each makes your
skills smarter the more you use them.

MATURITY SCORES:
  Level 0: Works correctly (mandatory patterns only)
  Level 1: Tracks what it does (learnings/execution log)
  Level 2: Grows knowledge (shared artifact maintenance)
  Level 3: Self-improves (recurrence detection + root causes)

noteplan-manager: avg 0.7 / 3.0
  fix-reference: ⭐⭐ Level 1 — has Key Learnings section
  fix-filenames: ○ Level 0 — no learnings section
  fix-work-emojis: ○ Level 0 — no learnings section
  ...

claude-manager: avg 0.0 / 3.0
  All skills at Level 0

═══════════════════════════════════════════════════════════════

TOP SUGGESTIONS:

📊 Dimension 1 — Usage Tracking
  fix-filenames: Processes files repeatedly but has no learnings section.
  Fix-work-emojis: Runs on recurring emoji issues with no execution record.
  → Opportunity: Add Key Learnings section. Execution history becomes
    the skill's institutional memory.

📚 Dimension 2 — Knowledge Artifacts
  fix-filenames + create-note: Both need naming conventions, defined separately.
  fix-work-emojis + fix-personal-emojis: Maintain independent emoji lists.
  → Opportunity: Shared reference file that both update and read.

🔄 Dimension 3 — Feedback Loops
  fix-filenames: Level 0 → Could detect recurring issues (Level 3a)
  fix-reference: Level 1 → Could suggest upstream dedup (Level 3b)
  → Opportunity: Move from reactive fixing to proactive prevention.
```

### Phase 4: Ask What to Implement

Use `AskUserQuestion` (multiSelect):

```
Which maturity improvements should I implement?

Options:
- Add learnings sections (scaffold Key Learnings template in selected skills)
- Set up knowledge sharing (identify shared references, create stub files)
- Add recurrence detection (Level 3a: track issues seen before)
- Add root cause suggestions (Level 3b: suggest upstream fixes on recurrence)
- Show me details on a specific suggestion first
- Skip (noted for future)
```

### Phase 5: Implement Approved Suggestions

**Adding learnings sections:**
1. For each selected skill, read current SKILL.md
2. Append `## Key Learnings & Execution History` section with the standard template
3. Show diff and confirm before writing

**Knowledge sharing:**
1. For each identified pair/group, propose a shared reference location
2. Create stub file at proposed location
3. Add `## Knowledge Artifacts` section to relevant skills explaining what they maintain
4. Show all changes and confirm before writing

**Recurrence detection:**
1. Add `## Recurrence Detection` section to selected skills
2. Populate with concrete examples from that skill's domain
3. Show diff and confirm

## Success Criteria

- [ ] User saw maturity scores before any suggestions were presented
- [ ] All three dimensions checked and reported
- [ ] Suggestions clearly marked as optional (no errors shown)
- [ ] User chose which to implement via multiSelect AskUserQuestion
- [ ] Approved improvements applied with diffs shown before writing
- [ ] Each skill's maturity level updated correctly after changes
