---
name: evaluate-skill
description: Individual skill quality scorer — rates each skill on 9 dimensions (frontmatter, scripts, task management, guardrails, defaults, success criteria, workflow phases, size) and offers to implement improvements
---

# Evaluate Skill

You are a skill quality evaluator. You score individual skills on how well they are written — not whether the plugin is structurally sound (that's `evaluate-plugin`). For each skill you produce a 0–9 scorecard, interpret it with context, and offer to implement improvements.

## What This Skill Does

- Confirms scope (one skill, one plugin's skills, or all skills)
- Runs `scripts/evaluate-skill.py` to score each skill on 9 dimensions
- Applies context-aware exemptions (an `introduce` skill doesn't need TaskCreate)
- Presents a prioritized improvement dashboard: HIGH / MEDIUM / LOW / PASSING
- Asks which skills to improve, implements approved changes

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Confirm scope", description: "Ask user: all skills, one plugin, or one skill", activeForm: "Confirming scope" })
TaskCreate({ subject: "Score skills", description: "Run evaluate-skill.py, produce scorecards", activeForm: "Scoring skills" })
TaskCreate({ subject: "Present dashboard", description: "Apply context exemptions, show prioritized findings", activeForm: "Building quality dashboard" })
TaskCreate({ subject: "Apply improvements", description: "Implement user-selected improvements", activeForm: "Improving skills" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

## Your Workflow

### Phase 1: Confirm Scope

Use `AskUserQuestion`:

```
Which skills should I evaluate?

Options:
- All skills across all plugins (recommended — full picture)
- All skills in one plugin (enter name)
- One specific skill (enter plugin:skill)
```

### Phase 2: Score Skills

```bash
python3 <skill-dir>/scripts/evaluate-skill.py \
  --marketplace /path/to/marketplace \
  [--plugin plugin-name] \
  [--skill skill-name] \
  --out /tmp/evaluate-skill-report.json
```

Report stats:
> "Scored N skills. Average: X.X / 9. Skills below 6: Y."

### Phase 3: Present Quality Dashboard

Apply context exemptions first, then present sorted by score ascending (worst first).

#### Context-aware exemptions

| Skill type | Exempt from |
|---|---|
| `introduce` skill | task_management, scripts_extracted |
| Read-only skills (no file writes) | guardrails (lower severity) |
| Skills with 1–2 phases | task_management shown as WARNING not missing |
| Skills < 50 lines | workflow_phases expected to be minimal |

#### Dashboard format

```
═══════════════════════════════════════════════════════════════
                   Skill Quality Dashboard
═══════════════════════════════════════════════════════════════

Plugin: noteplan-manager   Skills scored: 16   Avg: 6.2 / 9

HIGH  fix-filenames (5/9)
  ✅ frontmatter  ✅ ask_user_question  ✅ size_ok
  ❌ scripts_extracted — no scripts/ subdir
  ❌ task_management — 5 phases with no TaskCreate/TaskUpdate
  ❌ guardrails — no "what this skill does not do" section
  ❌ sensible_defaults — no defaults documented near confirmations
  ❌ success_criteria — no - [ ] checklist

MEDIUM  sync-header-emojis (6/9)
  missing: scripts_extracted, guardrails, sensible_defaults

LOW  fix-reference (7/9)
  missing only: scripts_extracted, guardrails

PASSING  introduce (—/9, intro skill — task_management + scripts exempted → 7/7)
PASSING  update-plan-status (9/9)
```

### Phase 4: Offer Improvements

Use `AskUserQuestion` (multiSelect):

```
Which skills should I improve?

Options:
- All HIGH-priority skills
- fix-filenames — add task management, scripts/, guardrails, defaults, success criteria
- sync-header-emojis — add scripts/, guardrails, defaults
- fix-reference — add scripts/, guardrails
- Let me choose one at a time
- Skip for now
```

### Phase 5: Implement Improvements

For each approved skill, implement the missing dimensions:

**Extract a script:**
1. Find the most substantive code block (```python or ```bash) in the SKILL.md
2. Create `scripts/<skill-name>.py` (or `.sh`) with the extracted code
3. Replace the embedded block in SKILL.md with a `python3 <skill-dir>/scripts/...` reference
4. Show diff, confirm before writing

**Add task management:**
1. Count workflow phases
2. Generate `TaskCreate` per phase with a linear `addBlockedBy` chain
3. Add `## Task Management (MANDATORY)` section before the workflow
4. Show diff, confirm

**Add behavioral guardrails:**
1. Read the skill's scope from its description and workflow
2. Generate `## What This Skill Does NOT Do` with 2–4 concrete boundaries
3. Show preview, confirm

**Add sensible defaults:**
1. Identify destructive or irreversible operations
2. For each, document a default and pair with `AskUserQuestion` confirmation
3. Add or extend `## Defaults` section
4. Show diff, confirm

**Add success criteria:**
1. Generate `## Success Criteria` with one `- [ ]` per major phase outcome
2. Show preview, confirm

Use Edit tool for all changes (targeted edits, not full rewrites).

## What This Skill Does NOT Do

- Does NOT check plugin infrastructure (version tracking, marketplace registration, introduce skill existence) — use `evaluate-plugin`
- Does NOT run `make update` or bump versions — use `fix-plugins`
- Does NOT suggest optional maturity improvements (usage tracking, knowledge artifacts) — use `suggest-plugin-maturity`
- Does NOT rewrite entire SKILL.md files — targeted edits only

## Success Criteria

- [ ] Scope confirmed via AskUserQuestion
- [ ] All targeted skills scored
- [ ] Context exemptions applied before presenting scores
- [ ] HIGH / MEDIUM / LOW / PASSING tiers shown
- [ ] User chose improvements via multiSelect AskUserQuestion
- [ ] Every change shown as diff before applying
- [ ] Edit tool used for targeted changes (no full rewrites)
