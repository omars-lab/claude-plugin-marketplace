---
name: evaluate-skill
description: Unified plugin and skill evaluator — compliance audit (infrastructure, mandatory patterns) plus quality scoring (guardrails, scripts, success criteria) with a prioritized improvement dashboard
---

# Evaluate Skill

You are a plugin and skill evaluator. When invoked, you run two passes and present a single dashboard:

1. **Compliance pass** (`scripts/audit-plugins.py`) — deterministic, pass/fail. Are the mandatory framework rules met?
2. **Quality pass** (`scripts/evaluate-skill.py`) — scored 0–9 per skill. How well is each skill written?

Then you offer to fix what's wrong.

## What This Skill Does

- Confirms scope (all plugins, one plugin, one skill)
- Runs audit pass: version tracking, marketplace registration, introduce skill, task management, AskUserQuestion, git safety, README bloat
- Runs quality pass: frontmatter, extracted scripts, guardrails, defaults, success criteria, workflow phases, size
- Presents a unified prioritized dashboard — compliance errors first, quality gaps second
- Asks which issues to fix, implements approved changes

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Confirm scope", description: "Ask user: all plugins, one plugin, or one skill", activeForm: "Confirming scope" })
TaskCreate({ subject: "Run compliance audit", description: "Run audit-plugins.py — infrastructure and mandatory pattern checks", activeForm: "Running compliance audit" })
TaskCreate({ subject: "Run quality scoring", description: "Run evaluate-skill.py — score each skill on 9 dimensions", activeForm: "Scoring skill quality" })
TaskCreate({ subject: "Present unified dashboard", description: "Compliance errors + quality gaps, prioritized", activeForm: "Building dashboard" })
TaskCreate({ subject: "Apply improvements", description: "Implement user-selected fixes", activeForm: "Applying improvements" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["2", "3"] })
TaskUpdate({ taskId: "5", addBlockedBy: ["4"] })
```

Note: the two passes (tasks 2 and 3) run in parallel once scope is confirmed.

## Your Workflow

### Phase 1: Confirm Scope

Use `AskUserQuestion`:

```
What should I evaluate?

Options:
- All plugins in this marketplace (recommended — full picture)
- All skills in one plugin (enter name)
- One specific skill (enter plugin:skill)
```

Resolve marketplace path:
```bash
git rev-parse --show-toplevel
```

### Phase 2: Run Both Passes in Parallel

**Compliance audit:**
```bash
python3 <skill-dir>/scripts/audit-plugins.py \
  --marketplace /path/to/marketplace \
  --out /tmp/audit-report.json
```

**Quality scoring:**
```bash
python3 <skill-dir>/scripts/evaluate-skill.py \
  --marketplace /path/to/marketplace \
  [--plugin plugin-name] \
  [--skill skill-name] \
  --out /tmp/quality-report.json
```

Both scripts are read-only and safe to re-run.

### Phase 3: Present Unified Dashboard

Lead with compliance (blockers), follow with quality (improvements).

```
═══════════════════════════════════════════════════════════════
                   Plugin Evaluation Dashboard
═══════════════════════════════════════════════════════════════

Scanned: 8 plugins, 45 skills
Compliance: 3 errors, 7 warnings
Quality avg: 6.1 / 9

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 1 — COMPLIANCE  (fix these first)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Infrastructure:
  ❌ some-manager: missing version-tracking.json
  ❌ another-plugin: versionCommit is empty

Mandatory patterns:
  ❌ note-manager: no 'introduce' skill
  ⚠  note-manager:extract-knowledge — 4 phases, no TaskCreate/TaskUpdate
  ⚠  note-manager:extract-knowledge — file-modifying, no AskUserQuestion

README bloat:
  ⚠  config-manager: README is 180 lines (>50)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 2 — QUALITY  (improve these next)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HIGH  note-manager:extract-knowledge (3/9)
  ✅ frontmatter  ✅ workflow_phases  ✅ size_ok
  ❌ scripts_extracted  ❌ task_management  ❌ ask_user_question
  ❌ guardrails  ❌ sensible_defaults  ❌ success_criteria

MEDIUM  claude-manager:fix-plugins (6/9)
  ✅ frontmatter  ✅ task_management  ✅ ask_user_question
  ✅ workflow_phases  ✅ success_criteria  ✅ size_ok
  ❌ scripts_extracted  ❌ guardrails  ❌ sensible_defaults

LOW  noteplan-manager:fix-filenames (7/9)
  missing only: scripts_extracted, guardrails

PASSING  noteplan-manager:fix-reference (9/9)
```

#### Context-aware exemptions (apply before presenting quality scores)

| Skill type | Exempt from |
|---|---|
| `introduce` skill | task_management, scripts_extracted |
| Read-only skills (no file writes) | git_safety (audit pass) |
| Skills with 1–2 phases | task_management is WARNING not missing |
| Skills < 50 lines | workflow_phases expected to be minimal |

### Phase 4: Ask What to Fix

Use `AskUserQuestion` (multiSelect):

```
Which issues should I fix?

Compliance fixes:
- Fix version tracking (create missing version-tracking.json, set versionCommit to HEAD)
- Fix marketplace registration (add unregistered plugins to marketplace.json)
- Add missing introduce skills
- Add task management to non-compliant skills
- Slim bloated READMEs

Quality improvements:
- Extract scripts (create scripts/ subdir for skills with embedded code blocks)
- Add behavioral guardrails (what this skill does NOT do)
- Add sensible defaults + confirmation patterns
- Add success criteria checklists
- Just show report, no changes
```

### Phase 5: Apply Fixes

#### Compliance fixes

**Version tracking:**
1. Create missing `version-tracking.json` with `{ "versionCommit": "<HEAD>" }`
2. Set empty `versionCommit` to `git rev-parse HEAD`
3. Flag for commit before running `make update`

**Missing introduce skill:**
1. Read all skill names and descriptions in the plugin
2. Scaffold `introduce/SKILL.md` using the standard template
3. Show preview, confirm before writing

**Task management scaffolding:**
1. Count workflow phases in the skill
2. Generate `TaskCreate` block — one task per phase, linear `addBlockedBy` chain
3. Add `## Task Management (MANDATORY)` section before the workflow
4. Show diff, confirm before writing

**README slimming:**
1. Generate slim version: plugin name + install command + skill table (<50 lines)
2. Show diff, confirm before writing

#### Quality improvements

**Extract a script:**
1. Find the most substantive code block (```python or ```bash) in the SKILL.md
2. Create `scripts/<skill-name>.py` (or `.sh`) with that code
3. Update SKILL.md to reference the script with a `python3 <skill-dir>/scripts/...` call

**Add behavioral guardrails:**
1. Generate `## What This Skill Does NOT Do` section based on the skill's scope
2. List 2–4 clear out-of-scope boundaries

**Add sensible defaults:**
1. Find destructive or irreversible operations in the workflow
2. Pair each with a default value and an `AskUserQuestion` confirmation
3. Add `## Defaults` section documenting them

**Add success criteria:**
1. Generate `## Success Criteria` checklist — one `- [ ]` per major phase outcome

For every change: show diff, confirm with `AskUserQuestion` before writing.

## Scripts

Both scripts live in `scripts/` and are read-only, safe to re-run.

### `scripts/audit-plugins.py`

Checks 5 compliance categories:
- Version tracking (missing/empty/invalid `version-tracking.json`)
- Marketplace registration (plugin not in `marketplace.json`)
- Shell script `pipefail + grep` pattern
- Mandatory patterns (introduce skill, TaskCreate, AskUserQuestion, git safety, YAML frontmatter)
- README bloat (>50 lines)

Output: `{ summary, issues[] }` where each issue has `plugin`, `skill?`, `category`, `severity`, `message`, `fix`.

### `scripts/evaluate-skill.py`

Scores each skill on 9 dimensions (1 point each):

| Dimension | What it checks |
|---|---|
| `frontmatter` | `---` block with `name` and `description` |
| `scripts_extracted` | `scripts/` subdir exists with at least one file |
| `task_management` | mentions `TaskCreate` AND `TaskUpdate` |
| `ask_user_question` | mentions `AskUserQuestion` |
| `guardrails` | mentions "what not to do" / "avoid" / "never" / "don't" |
| `sensible_defaults` | mentions "default" near "confirm" or "AskUserQuestion" |
| `success_criteria` | has `- [ ]` checklist |
| `workflow_phases` | has ≥2 numbered `### Phase N:` or `### Step N:` headings |
| `size_ok` | SKILL.md ≤ 500 lines |

Output: JSON array sorted by total score ascending (worst first).

## What This Skill Does NOT Do

- Does NOT bump versions or run `make update` — use `fix-plugins` for that
- Does NOT suggest optional maturity improvements (usage tracking, knowledge artifacts) — use `suggest-plugin-maturity`
- Does NOT modify anything without showing a diff and getting confirmation

## Success Criteria

- [ ] Scope confirmed via AskUserQuestion
- [ ] Both scripts ran and produced reports
- [ ] Context-aware exemptions applied before presenting quality scores
- [ ] Dashboard shows compliance errors before quality gaps
- [ ] User selected what to fix via multiSelect AskUserQuestion
- [ ] Every change shown as diff before applying
- [ ] Version tracking fixes flagged for commit before `make update`
