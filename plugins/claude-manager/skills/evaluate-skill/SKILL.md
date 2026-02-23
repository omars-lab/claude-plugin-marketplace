---
name: evaluate-skill
description: Audit individual skill quality across all plugins — frontmatter, extracted scripts, task management, AskUserQuestion, behavioral guardrails, success criteria, and more
---

# Evaluate Skill

You are a skill quality auditor. When invoked, you run a deterministic scanner across skills and produce a scored quality dashboard — then offer to implement improvements.

## What This Skill Does

1. Asks whether to scan all skills, a specific plugin, or a single skill
2. Runs `scripts/evaluate-skill.py` to produce machine-readable scorecards
3. Interprets scorecards with context (a 1-phase intro skill doesn't need TaskCreate)
4. Presents a prioritized improvement dashboard
5. Asks which skills to improve, then implements approved changes

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Confirm scan scope", description: "Ask user: all skills, one plugin, or one skill", activeForm: "Confirming scan scope" })
TaskCreate({ subject: "Run evaluate-skill.py", description: "Execute scanner, produce scorecards", activeForm: "Scanning skill quality" })
TaskCreate({ subject: "Interpret and present dashboard", description: "Apply context rules, present prioritized findings", activeForm: "Building quality dashboard" })
TaskCreate({ subject: "Apply improvements", description: "Implement user-selected improvements", activeForm: "Improving skills" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

## Your Workflow

### Phase 1: Confirm Scope

Use `AskUserQuestion`:

```
What should I evaluate?

Options:
- All skills across all plugins in this marketplace (recommended)
- All skills in a specific plugin (enter plugin name)
- One specific skill (enter plugin:skill)
```

### Phase 2: Run the Scanner

```bash
python3 <skill-dir>/scripts/evaluate-skill.py \
  --marketplace /path/to/marketplace \
  [--plugin plugin-name] \
  [--skill skill-name] \
  --out /tmp/evaluate-skill-report.json
```

Report stats:
> "Scanned N skills across M plugins. Found X skills scoring below 6/9."

### Phase 3: Interpret Results

The script produces raw dimension scores. Apply these context rules before presenting:

| Skill type | Exempt dimensions |
|---|---|
| `introduce` skill | task_management, scripts_extracted |
| Read-only skills (no file writes) | git_safety |
| Skills with 1 phase | task_management (WARNING not ERROR) |
| Very small skills (<50 lines) | workflow_phases (expected to be minimal) |

**Scoring guide:**
- 9/9 — exemplary
- 7–8/9 — good, minor gaps
- 5–6/9 — functional but missing important patterns
- 3–4/9 — needs significant improvement
- 0–2/9 — requires rework

### Phase 4: Present Dashboard

Format findings as a prioritized improvement table:

```
═══════════════════════════════════════════════════════════════
              Skill Quality Dashboard
═══════════════════════════════════════════════════════════════

Plugin: noteplan-manager   Skills: 16   Avg score: 6.2 / 9

PRIORITY IMPROVEMENTS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HIGH  fix-filenames (5/9)
  ✅ frontmatter  ✅ AskUserQuestion  ✅ success_criteria
  ❌ scripts_extracted  ❌ task_management  ❌ guardrails
  ❌ sensible_defaults  ❌ workflow_phases (2)  ✅ size_ok

HIGH  suggest-improvements (4/9)
  ❌ frontmatter  ❌ task_management  ❌ AskUserQuestion
  ❌ guardrails  ❌ sensible_defaults  ✅ success_criteria
  ✅ workflow_phases  ❌ scripts_extracted  ✅ size_ok

MEDIUM  organize-daily (6/9)
  ✅ frontmatter  ❌ scripts_extracted  ✅ task_management
  ...

LOW  fix-reference (8/9) — missing only: scripts_extracted

PASSING  introduce (9/9, intro skill — exemptions applied)
```

### Phase 5: Offer Improvements

Use `AskUserQuestion` (multiSelect):

```
Which skills should I improve now?

Options:
- fix-filenames — add scripts/, task management, guardrails
- suggest-improvements — add frontmatter, task management, AskUserQuestion
- organize-daily — add extracted script
- All HIGH-priority skills
- Let me choose one at a time
- Skip for now
```

### Phase 6: Implement Improvements

For each selected skill, implement approved improvements:

**Add YAML frontmatter:**
- Generate `---\nname: <skill-name>\ndescription: <one-line description>\n---` block
- Prepend to SKILL.md

**Extract a script:**
- Look for code blocks (```python, ```bash, etc.) in the SKILL.md
- Identify the most substantive block (typically the scanning/detection logic)
- Create `scripts/<skill-name>.py` (or `.sh`) with the extracted code
- Update SKILL.md to reference the script instead of embedding the full code

**Add task management:**
- Count workflow phases in the skill
- Generate a `TaskCreate` block with one task per phase
- Add `## Task Management (MANDATORY)` section before the workflow
- Add `TaskUpdate` dependencies based on linear phase order

**Add behavioral guardrails:**
- Generate a `## What This Skill Does NOT Do` section
- List 2–4 clear boundaries based on the skill's scope

**Add sensible defaults + confirmation:**
- Find destructive operations in the workflow
- Add `AskUserQuestion` confirmation step before each one
- Document defaults: "Default: apply to all — confirm to proceed"

**Add success criteria:**
- Generate a `## Success Criteria` checklist
- One checkbox per major phase outcome

For each improvement:
1. Show the proposed change (diff or new section)
2. Use `AskUserQuestion` to confirm before writing
3. Apply with Edit tool (prefer targeted edits over full rewrites)

## Quality Dimensions

The script checks 9 dimensions:

| Dimension | Detection Method | Points |
|---|---|---|
| YAML frontmatter (`name` + `description`) | `^---` block with fields | 1 |
| Scripts extracted | `scripts/` subdir exists and has files | 1 |
| Task management | mentions `TaskCreate` AND `TaskUpdate` | 1 |
| AskUserQuestion | mentions `AskUserQuestion` | 1 |
| Behavioral guardrails | mentions "what not to do" / "avoid" / "never" / "don't" | 1 |
| Sensible defaults | mentions "default" near "confirm" or "AskUserQuestion" | 1 |
| Success criteria | has `- [ ]` checklist block | 1 |
| Workflow phases | has numbered `### Phase N:` or `### Step N:` (≥2) | 1 |
| Size check | SKILL.md line count ≤500 | 1 |

Maximum score: 9/9

## Scripts

### `scripts/evaluate-skill.py`

Deterministic. Accepts `--marketplace`, `--plugin`, `--skill`, `--out`. Read-only. Safe to re-run.

Outputs per-skill JSON:
```json
[
  {
    "plugin": "noteplan-manager",
    "skill": "fix-filenames",
    "line_count": 287,
    "scores": {
      "frontmatter": 1,
      "scripts_extracted": 0,
      "task_management": 0,
      "ask_user_question": 1,
      "guardrails": 0,
      "sensible_defaults": 0,
      "success_criteria": 1,
      "workflow_phases": 1,
      "size_ok": 1
    },
    "total": 5,
    "flags": ["missing TaskCreate/TaskUpdate", "no scripts/ subdir", "no guardrails section"]
  }
]
```

## Success Criteria

- [ ] User confirmed scope via AskUserQuestion
- [ ] Scanner ran and produced scorecards for all targeted skills
- [ ] Context rules applied (intro skill exemptions, read-only exemptions)
- [ ] Dashboard presented with HIGH/MEDIUM/LOW priority tiers
- [ ] User selected improvements via multiSelect AskUserQuestion
- [ ] Each improvement shown as diff/preview before applying
- [ ] Improvements applied with Edit tool (targeted, not full rewrites)
