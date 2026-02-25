---
name: condense-plugin
description: Consolidate a plugin's flat skills into focused meta-skills — analyze, propose groupings, move, fix frontmatter, write routers, and validate
---

# Condense Plugin

You are the plugin consolidation assistant for claude-manager. When invoked, restructure a flat-skill plugin into a meta-skill hierarchy by following this 7-phase workflow.

## Background

CEG auto-discovers only `skills/{skill-name}/SKILL.md` (one level deep). Nested SKILL.md files are private implementation docs referenced via relative markdown links from their meta-skill router. This means:

- **Meta-skills** live at `skills/{meta-skill}/SKILL.md` — CEG sees these, users invoke them
- **Sub-skills** live at `skills/{meta-skill}/{sub-skill}/SKILL.md` — private, referenced by the router
- A plugin should have 3–7 meta-skills. Single-sub-skill meta-skills are valid (they grow over time)

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Analyze current skills", description: "List and read all skill descriptions in the target plugin", activeForm: "Analyzing skills" })
TaskCreate({ subject: "Propose groupings", description: "Present candidate meta-skills to user for approval", activeForm: "Proposing groupings" })
TaskCreate({ subject: "Create and move", description: "mkdir and mv each skill into its meta-skill dir", activeForm: "Creating and moving" })
TaskCreate({ subject: "Fix CRLF and frontmatter", description: "Fix line endings and add missing YAML frontmatter", activeForm: "Fixing frontmatter" })
TaskCreate({ subject: "Write meta-skill SKILL.md files", description: "Create router SKILL.md for each meta-skill", activeForm: "Writing meta-skill routers" })
TaskCreate({ subject: "Update introduce skill", description: "Rewrite introduce to reference meta-skill invocations", activeForm: "Updating introduce" })
TaskCreate({ subject: "Validate", description: "Run make validate-plugin PLUGIN=<name> — 0 warnings required", activeForm: "Validating" })
// Set up dependencies
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
TaskUpdate({ taskId: "5", addBlockedBy: ["4"] })
TaskUpdate({ taskId: "6", addBlockedBy: ["5"] })
TaskUpdate({ taskId: "7", addBlockedBy: ["6"] })
```

## Phase 1: Analyze

**Task 1 in_progress**

1. Ask the user which plugin to condense if not already specified
2. List all skills in `plugins/<name>/skills/`
3. For each skill, read its SKILL.md to note:
   - One-line description
   - Whether it has `scripts/`, `operations/`, or `examples/` subdirs
   - Whether its first line is `---` (YAML frontmatter) — if not, it needs CRLF fix + frontmatter
4. Produce a summary table:

```
| Skill | Description | Extras | Has frontmatter? |
|---|---|---|---|
| fix-filenames | Fix filename/heading mismatches | — | ✓ |
| organize-daily | Process daily calendar files | — | ✗ (needs fix) |
```

**Task 1 completed**

## Phase 2: Propose Groupings

**Task 2 in_progress**

Analyze the skills and propose 3–7 meta-skills. Guidelines:
- Group by domain / user intent, not by implementation similarity
- Name meta-skills with `manage-` prefix: `manage-notes`, `manage-plans`, `manage-emojis`
- Single-sub-skill meta-skills are valid (the meta-skill is a stable entry point that grows)
- Flag which skills are risky to move (have lots of subdirs, are depended on by others)

Present to user using `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "Do these meta-skill groupings look right? (Select any to reassign)",
    header: "Proposed groupings",
    options: [
      { label: "Approve all groupings", description: "Proceed with the proposed structure" },
      { label: "Reassign one or more skills", description: "I'll tell you which skills should move to different groups" },
      { label: "Add / rename a meta-skill", description: "The grouping needs adjustment" },
      { label: "Cancel", description: "Stop and let me reconsider the structure" }
    ],
    multiSelect: false
  }]
})
```

Incorporate feedback and re-present until approved.

**Task 2 completed**

## Phase 3: Create and Move

**Task 3 in_progress**

For each meta-skill:

```bash
mkdir -p plugins/<name>/skills/<meta-skill>
```

For each sub-skill being moved:

```bash
mv plugins/<name>/skills/<sub-skill> plugins/<name>/skills/<meta-skill>/<sub-skill>
```

**Special case — meta-skill name collides with existing sub-skill name:**

If a meta-skill is named `manage-templates` and there's already a skill called `manage-templates`:
```bash
mkdir -p plugins/<name>/skills/manage-templates/manage-templates
mv plugins/<name>/skills/manage-templates/SKILL.md plugins/<name>/skills/manage-templates/manage-templates/SKILL.md
mv plugins/<name>/skills/manage-templates/operations plugins/<name>/skills/manage-templates/manage-templates/operations
# then mv other sub-skills in, and create new router SKILL.md
```

**Task 3 completed**

## Phase 4: CRLF + Frontmatter Fix

**Task 4 in_progress**

For every moved SKILL.md flagged in Phase 1 as missing frontmatter:

**Step 1: Fix CRLF**
```python
path = 'plugins/<name>/skills/<meta-skill>/<sub-skill>/SKILL.md'
with open(path, 'rb') as f: data = f.read()
with open(path, 'wb') as f: f.write(data.replace(b'\r\n', b'\n'))
```

**Step 2: Add frontmatter**

Prepend to the file:
```yaml
---
name: <skill-name>
description: <one-line description from Phase 1 analysis>
---

```

Verify with:
```bash
head -1 plugins/<name>/skills/<meta-skill>/<sub-skill>/SKILL.md
# Must output: ---
```

**Task 4 completed**

## Phase 5: Write Meta-Skill SKILL.md Files

**Task 5 in_progress**

For each meta-skill, create `plugins/<name>/skills/<meta-skill>/SKILL.md`.

### Router Pattern (2+ sub-skills)

```markdown
---
name: manage-<domain>
description: <Domain> orchestrator — <brief>. Routes to the right sub-skill based on intent.
---

# Manage <Domain>

You are the <domain> orchestrator for <plugin>. When invoked, detect what the user wants and route them to the appropriate sub-skill workflow.

## What This Skill Does

| Operation | Triggers | Sub-skill |
|---|---|---|
| <Operation> | "trigger1", "trigger2" | [sub-skill/SKILL.md](sub-skill/SKILL.md) |

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Detect intent", ... })
TaskCreate({ subject: "Execute sub-skill workflow", ... })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
```

## Your Workflow

### Phase 1: Detect Intent
[signal → sub-skill mapping]
If ambiguous → AskUserQuestion with one option per sub-skill

### Phase 2: Execute Sub-Skill
**For <sub-skill>:** Read [sub-skill/SKILL.md](sub-skill/SKILL.md) and follow its workflow.

## What This Skill Does NOT Do
[guardrails]

## Success Criteria
- [ ] Intent detected without unnecessary questions when signal is clear
- [ ] Correct sub-skill workflow followed in full
```

### Direct Pattern (1 sub-skill — no routing needed)

```markdown
---
name: manage-<domain>
description: <one-line description>
---

# Manage <Domain>

You are the <domain> skill for <plugin>. When invoked, read and follow the [sub-skill/SKILL.md](sub-skill/SKILL.md) workflow directly.

## What This Skill Does

[Brief description]

Read [sub-skill/SKILL.md](sub-skill/SKILL.md) and follow its workflow.

## What This Skill Does NOT Do
[guardrails pointing to sibling meta-skills]
```

**Task 5 completed**

## Phase 6: Update `introduce`

**Task 6 in_progress**

Rewrite `plugins/<name>/skills/introduce/SKILL.md` to:

1. Change the skill count in the welcome message (e.g., "21 skills" → "7 meta-skills")
2. Replace per-skill tables with one row per meta-skill + bullet list of sub-operations
3. Update invocation examples to use meta-skill names:
   - Before: `/plugin:fix-filenames`
   - After: `/plugin:manage-filenames`
4. Update the "How Skills Work Together" dependency graph to show meta-skills

**Task 6 completed**

## Phase 7: Validate

**Task 7 in_progress**

```bash
make validate-plugin PLUGIN=<name>
```

Expected: 0 errors, 0 warnings.

Common issues to fix if validation fails:
- Missing `name`/`description` in frontmatter → add to SKILL.md
- Non-verb skill name → meta-skills use `manage-` prefix which is fine
- `introduce` skill missing → ensure it's still at top level
- Version not bumped → update `.claude-plugin/plugin.json`

Version bump guidelines:
- Adding meta-skills to an existing plugin → **minor bump** (e.g., 2.0.0 → 2.1.0)
- Restructuring all skills (public API changes) → **major bump** (e.g., 2.1.0 → 3.0.0)

**Task 7 completed**

## What This Skill Does NOT Do

- Does not create new skills — use `/claude-manager:manage-skills` → create-skill
- Does not evaluate individual skill quality — use `/claude-manager:manage-skills` → evaluate-skill
- Does not install the plugin after restructuring — run `make install PLUGIN=<name>` manually
