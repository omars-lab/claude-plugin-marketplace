---
name: audit-plugins
description: Check plugin compliance with mandatory framework standards — version tracking, marketplace registration, introduce skill, task management, AskUserQuestion, git safety, README bloat
---

# Audit Plugins

You are a Claude plugin compliance auditor. When this skill is invoked, you run a deterministic scan of one or more marketplaces and report compliance gaps against the mandatory framework standards.

## What This Skill Does

- Runs `scripts/audit-plugins.py` — a deterministic scanner producing a JSON compliance report
- Reports five categories of issues: version tracking, marketplace registration, skill naming, mandatory patterns, and README bloat
- Asks which issues to fix
- Does NOT version-bump or run `make update` — that's `update-plugins`

## Task Management (MANDATORY)

Create all tasks upfront before starting:

```javascript
TaskCreate({ subject: "Confirm marketplace paths", description: "Ask user which marketplace(s) to audit", activeForm: "Confirming scope" })
TaskCreate({ subject: "Run audit-plugins.py", description: "Execute deterministic scanner, collect JSON report", activeForm: "Running compliance scan" })
TaskCreate({ subject: "Present findings", description: "Show structured compliance report to user", activeForm: "Presenting audit results" })
TaskCreate({ subject: "Apply fixes", description: "Execute user-approved fixes", activeForm: "Applying fixes" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

## Your Workflow

### Phase 1: Confirm Scope

Use `AskUserQuestion`:

```
Which marketplace(s) should I audit?

Default: <git-root> (oeid-claude-plugins)
Options:
- Just the default OEID marketplace
- Add another marketplace (provide path)
- I'll specify all paths
```

Resolve `<git-root>` with:
```bash
git rev-parse --show-toplevel
```

### Phase 2: Run the Scanner

Run `scripts/audit-plugins.py` from the skill directory:

```bash
python3 <skill-dir>/scripts/audit-plugins.py \
  --marketplace /path/to/marketplace \
  --out /tmp/audit-plugins-report.json
```

The script is read-only and safe to re-run. It produces a JSON report with:
- `summary` — counts per category
- `issues` — list of `{plugin, skill?, category, severity, message, fix}`

Report stats to the user:
> "Scanned N plugins, M skills. Found X errors, Y warnings."

### Phase 3: Present Findings

Structure the report into five categories:

#### Category 1: Version Tracking Infrastructure

Issues that cause `make update` to silently fail:

| Issue | Severity |
|---|---|
| Missing `version-tracking.json` | ERROR |
| Empty `versionCommit` in tracking file | ERROR |
| Invalid `versionCommit` (not in git history) | ERROR |
| Plugin not in `marketplace.json` | ERROR |
| `grep` without `\|\| true` in shell scripts | WARNING |
| `version-tracking.json` shows as false positive change | WARNING |

#### Category 2: Skill Naming Conventions

Skill directory names should use verb-first kebab-case:

| Issue | Severity |
|---|---|
| Skill name starts with noun (e.g. `skill-create`, `plugin-audit`) | WARNING |
| Skill name is not kebab-case | WARNING |

#### Category 3: Mandatory Pattern Compliance

| Check | Severity |
|---|---|
| Plugin missing `introduce` skill | ERROR |
| Skill with 3+ phases, no `TaskCreate`/`TaskUpdate` | ERROR |
| Skill with 1-2 phases, no `TaskCreate`/`TaskUpdate` | WARNING |
| Skill missing `AskUserQuestion` | ERROR (if file-modifying) / WARNING (read-only) |
| File-modifying skill missing git safety | ERROR |
| YAML frontmatter missing `name` or `description` | WARNING |

#### Category 4: README Bloat

| Check | Severity |
|---|---|
| README > 50 lines and plugin has `introduce` skill | WARNING |
| README > 50 lines and plugin lacks `introduce` skill | INFO (introduce is the bigger issue) |

### Phase 4: Ask What to Fix

Use `AskUserQuestion` (multiSelect):

```
Which issues should I fix?

Options:
- Fix version tracking (create missing version-tracking.json, fix empty versionCommit)
- Fix marketplace registration (add unregistered plugins to marketplace.json)
- Fix skill naming (rename noun-first skills to verb-first)
- Add missing introduce skills (scaffold introduce for each plugin lacking one)
- Add task management (scaffold TaskCreate/TaskUpdate in skills missing it)
- Slim READMEs (trim to <50 lines, point to introduce skill)
- Just show report, no changes
```

### Phase 5: Apply Fixes

For each approved fix category:

**Version tracking fixes:**
1. Create missing `version-tracking.json` with `{ "versionCommit": "<HEAD>" }`
2. For empty `versionCommit`, set to current HEAD: `git rev-parse HEAD`
3. Alert user to commit the new files before running `make update`

**Marketplace registration:**
1. Read existing `marketplace.json`
2. For each unregistered plugin, add entry with name, source, description, version, category
3. Show diff and confirm before writing

**Skill naming:**
1. For each noun-first skill, propose verb-first rename
2. Use `AskUserQuestion` to confirm each rename
3. Run `git mv` for confirmed renames
4. Update YAML frontmatter `name:` field

**Missing introduce skills:**
1. For each plugin lacking `introduce`, read all its skill names and descriptions
2. Scaffold an `introduce/SKILL.md` using the standard template
3. Show preview and confirm before writing

**Task management scaffolding:**
1. For each non-compliant skill, generate a `TaskCreate` block matching its workflow phases
2. Add `## Task Management (MANDATORY)` section at the top of the workflow
3. Show diff and confirm before writing

**README slimming:**
1. For each bloated README, show current content
2. Generate slim version: plugin name + install command + skill table
3. Confirm before writing

## Scripts

### `scripts/audit-plugins.py`

Deterministic. Accepts `--marketplace` (path) and `--out` (JSON output path). Read-only. Safe to re-run.

Outputs:
```json
{
  "marketplace": "/path/to/marketplace",
  "scanned_at": "ISO-8601",
  "summary": { "plugins": 8, "skills": 45, "errors": 3, "warnings": 12 },
  "issues": [
    {
      "plugin": "some-manager",
      "skill": null,
      "category": "version_tracking",
      "severity": "ERROR",
      "message": "Missing version-tracking.json",
      "fix": "Run make version-init or create .claude-plugin/version-tracking.json"
    }
  ]
}
```

## Success Criteria

- [ ] Script ran and produced JSON report
- [ ] All five categories checked and reported
- [ ] User saw issue counts before any fixes
- [ ] User chose which categories to fix via AskUserQuestion
- [ ] Approved fixes applied with diffs shown before writing
- [ ] Version tracking fixes flagged for commit before `make update`

## What This Skill Does NOT Do

- Does NOT bump versions or run `make update` → use `update-plugins`
- Does NOT suggest optional maturity improvements → use `suggest-plugin-maturity`
- Does NOT audit individual skill quality → use `evaluate-skill`
