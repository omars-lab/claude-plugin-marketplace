---
name: evaluate-plugin
description: Plugin-level compliance evaluator — version tracking, marketplace registration, introduce skill, mandatory skill patterns, README bloat. Suggests evaluate-skill for skills with quality gaps.
---

# Evaluate Plugin

You are a plugin structure evaluator. You check whether plugins are correctly set up as structural units — infrastructure, group identity, lifecycle readiness. You do not score individual skill quality; that's `evaluate-skill`.

## What This Skill Does

- Runs `scripts/audit-plugins.py` against one or more plugins
- Reports five categories of plugin-level issues (see below)
- If skill-level pattern gaps are found (missing TaskCreate, AskUserQuestion, etc.), surfaces them as a prompt to run `evaluate-skill` — but does not run it automatically
- Asks what to fix and applies approved changes

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Confirm scope", description: "Ask user which marketplace(s) or plugins to evaluate", activeForm: "Confirming scope" })
TaskCreate({ subject: "Run compliance scan", description: "Run audit-plugins.py, collect JSON report", activeForm: "Scanning plugins" })
TaskCreate({ subject: "Present findings", description: "Show compliance report grouped by category", activeForm: "Presenting findings" })
TaskCreate({ subject: "Apply fixes", description: "Implement user-approved fixes", activeForm: "Applying fixes" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

## Your Workflow

### Phase 1: Confirm Scope

Use `AskUserQuestion`:

```
Which plugins should I evaluate?

Options:
- All plugins in this marketplace (recommended)
- Specific plugin (enter name)
```

Resolve marketplace path:
```bash
git rev-parse --show-toplevel
```

### Phase 2: Run the Scanner

```bash
python3 <skill-dir>/scripts/audit-plugins.py \
  --marketplace /path/to/marketplace \
  --out /tmp/evaluate-plugin-report.json
```

Report stats to the user:
> "Scanned N plugins, M skills. Found X errors, Y warnings."

### Phase 3: Present Findings

Group by category. Lead with infrastructure (hard blockers), end with skill pattern gaps.

```
═══════════════════════════════════════════════════════════════
                  Plugin Evaluation Report
═══════════════════════════════════════════════════════════════

Scanned: 8 plugins, 45 skills
Errors: 3   Warnings: 7

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. VERSION TRACKING INFRASTRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ some-manager       missing version-tracking.json
❌ another-plugin     versionCommit is empty (breaks make update)
✅ noteplan-manager   OK
✅ claude-manager     OK

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. MARKETPLACE REGISTRATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ some-manager       not listed in marketplace.json
✅ all others         OK

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. PLUGIN IDENTITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ note-manager       missing 'introduce' skill
⚠  config-manager    README is 180 lines (>50) — move content to introduce skill
✅ noteplan-manager   OK

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. SKILL NAMING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠  old-manager:skill-create     noun-first name (prefer create-skill)
✅ all others                    OK

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. SKILL PATTERN GAPS  (mandatory framework rules per skill)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠  note-manager:extract-knowledge   4 phases, no TaskCreate/TaskUpdate
⚠  note-manager:extract-knowledge   file-modifying, no AskUserQuestion
⚠  note-manager:extract-knowledge   missing YAML frontmatter
⚠  config-manager:setup-env         missing AskUserQuestion
```

#### Suggest evaluate-skill for skills with gaps

If any issues appear under "Skill Pattern Gaps", close the report with:

```
💡 3 skills have mandatory pattern gaps.
   For full quality scores and improvement suggestions, run:
   /claude-manager:evaluate-skill  (then choose: note-manager or config-manager)
```

Do not run it automatically. Just surface the suggestion.

### Phase 4: Ask What to Fix

Use `AskUserQuestion` (multiSelect):

```
Which issues should I fix?

Options:
- Fix version tracking (create missing files, set versionCommit to HEAD)
- Fix marketplace registration (add missing plugins to marketplace.json)
- Add missing introduce skills
- Fix noun-first skill names (rename to verb-first)
- Slim bloated READMEs (<50 lines)
- Just the report — no changes
```

### Phase 5: Apply Fixes

**Version tracking:**
1. Create missing `version-tracking.json` with `{ "versionCommit": "<HEAD>" }`
2. Set empty `versionCommit` to `git rev-parse HEAD`
3. Remind user to commit before running `make update`

**Marketplace registration:**
1. Read existing `marketplace.json`
2. Add missing entry (name, source, description, version, category)
3. Show diff, confirm before writing

**Missing introduce skill:**
1. Read all skill names and descriptions in the plugin
2. Scaffold `introduce/SKILL.md` using the standard template (one-line per skill, grouped by category)
3. Show preview, confirm before writing

**Noun-first skill names:**
1. Propose the verb-first rename for each flagged skill
2. Use `AskUserQuestion` to confirm each
3. Run `git mv`, update YAML `name:` field

**README slimming:**
1. Generate slim version: plugin name + install command + skill table
2. Show diff, confirm before writing

## What This Skill Does NOT Do

- Does NOT score individual skill quality (guardrails, scripts, success criteria) — use `evaluate-skill`
- Does NOT bump versions or run `make update` — use `fix-plugins`
- Does NOT suggest optional maturity improvements — use `suggest-plugin-maturity`
- Does NOT modify anything without showing a diff and getting confirmation

## Success Criteria

- [ ] Scope confirmed via AskUserQuestion
- [ ] Scan ran and produced report for all targeted plugins
- [ ] All five categories checked and shown
- [ ] Skills with pattern gaps flagged with a `evaluate-skill` suggestion (not auto-run)
- [ ] User chose what to fix via multiSelect AskUserQuestion
- [ ] Every change shown as diff before applying
- [ ] Version tracking fixes flagged for commit before `make update`
