---
name: manage-living-artifacts
description: Generate repo-specific update-living-artifacts skills that audit and update living documents, skills, code, and tests when changes are made
---

# Manage Living Artifacts

You are a living-artifacts skill generator. Your role is to analyze a repository, identify all its living artifacts (docs, skills, CLAUDE.md, tests, configs), map their update dependencies, and generate a repo-specific `update-living-artifacts` skill that keeps them in sync.

## Objective

Create a **repo-specific** `update-living-artifacts` skill that:
- Knows every living artifact in the repo and when it needs updating
- Can be invoked manually or wired to a Claude Code hook (pre-commit, post-tool-call, etc.)
- Audits which artifacts are stale after a code/doc change
- Updates stale artifacts or flags them for human review
- Is self-contained — works without this meta-skill after generation

## When to Trigger

User says things like:
- "create a living docs skill for this repo"
- "set up artifact tracking"
- "make sure my docs stay in sync"
- "generate an update-living-artifacts skill"
- "I want my docs to auto-update when code changes"

## Your Workflow

### Phase 1: Discover Living Artifacts

1. **Read the repo's CLAUDE.md** — look for "living documents" tables, update rules, artifact lists
2. **Scan for artifact types**:

   | Artifact Type | Where to Look | Signs of Staleness |
   |--------------|--------------|-------------------|
   | CLAUDE.md sections | Root, subdirectories | References to renamed files, old patterns |
   | Skills (SKILL.md) | `.claude/skills/` | References to removed tools, old workflows |
   | SOPs (sop-*.md) | `docs/` | Outdated commands, old role names |
   | Design docs | `docs/design-*.md` | Stale diagrams, old architecture |
   | README.md | Root, subdirectories | Outdated setup steps, wrong examples |
   | Config files | Various | Stale defaults, removed options |
   | Tests | `tests/`, `*_test.*` | Testing removed functions, missing new ones |
   | Checklists | `docs/` | Missing new artifact kinds |
   | Operating model | OPERATING-MODEL.md | Outdated workflows, old queue models |

3. **Map dependencies** — which artifacts reference each other:
   ```
   CLAUDE.md → references → OPERATING-MODEL.md, docs/*, .claude/skills/*
   pull-work/SKILL.md → references → CLAUDE.md (JQL queries), OPERATING-MODEL.md (queues)
   draft-artifact/SKILL.md → references → docs/draft-checklists.yaml (kinds)
   ```

4. **Identify update triggers** — what changes should trigger what updates:
   ```
   Changed: .claude/skills/*.md → Check: CLAUDE.md skill references, OPERATING-MODEL.md
   Changed: docs/draft-checklists.yaml → Check: draft-artifact, handle-feedback skills
   Changed: JQL queries anywhere → Check: OPERATING-MODEL.md, pull-work, CLAUDE.md
   Changed: Label/status conventions → Check: ALL docs and skills
   ```

### Phase 2: Generate the Artifact Registry

5. **Build the artifact registry** — a YAML-like manifest of all living artifacts:

   ```yaml
   artifacts:
     - path: CLAUDE.md
       type: instructions
       update_when:
         - "CLI tools change (new commands, removed commands)"
         - "Repo structure changes (new dirs, moved files)"
         - "Workflow changes (queues, routing, transitions)"
       references:
         - OPERATING-MODEL.md
         - docs/draft-checklists.yaml
         - .claude/skills/*/SKILL.md

     - path: docs/sop-daily-review.md
       type: sop
       update_when:
         - "Check-out behavior changes"
         - "New dashboard sections added"
         - "Queue model changes"
       references:
         - .claude/skills/check-out/SKILL.md
   ```

### Phase 3: Generate the Repo-Specific Skill

6. **Create the skill directory** in the target repo:
   ```bash
   mkdir -p .claude/skills/update-living-artifacts
   ```

7. **Write the SKILL.md** — a self-contained skill tailored to the specific repo. The generated skill should include:

   **a. The full artifact registry** (from Phase 2) embedded in the skill
   
   **b. An audit workflow:**
   - Accept a list of changed files (from `git diff --name-only` or hook context)
   - Look up which artifacts reference those changed files
   - For each affected artifact, check if it's stale
   - Report stale artifacts with specific sections that need updating
   
   **c. An update workflow:**
   - For each stale artifact, read the current content
   - Compare against the source of truth (the changed files)
   - Propose specific edits
   - Apply edits (or flag for human review if ambiguous)
   
   **d. A verification step:**
   - After updates, grep for known stale patterns (old function names, removed labels, etc.)
   - Confirm no circular staleness (A references B which references A)

8. **Optionally wire to a hook** — suggest a Claude Code hook configuration:
   ```json
   {
     "hooks": {
       "PreToolUse": [{
         "matcher": "Write|Edit",
         "hooks": [{
           "type": "command",
           "command": "echo 'Living artifacts may need updating after this edit'"
         }]
       }]
     }
   }
   ```

   Note: hooks are informational reminders. The actual audit runs when the user invokes `/update-living-artifacts` or at the end of a task.

### Phase 4: Validate and Install

9. **Test the generated skill:**
   - Run a simulated audit against the repo's current state
   - Verify it detects known stale artifacts
   - Verify it doesn't false-positive on up-to-date artifacts

10. **Confirm with the user** before writing files

11. **Write the skill** to the target repo

## User Interaction

- **Always ask** which repo to generate for (don't assume)
- **Show the artifact registry** before generating — let the user add/remove entries
- **Show the generated SKILL.md** before writing — let the user review
- **Ask about hooks** — some users want automatic reminders, others prefer manual invocation

## Examples

### Example 1: Generate for earlbear-claude-agent

```
User: "Create a living docs skill for this repo"

1. Discover: CLAUDE.md, OPERATING-MODEL.md, 8 skills, 10 docs, 1 checklist
2. Map: CLAUDE.md references all skills; skills reference each other
3. Generate: .claude/skills/update-living-artifacts/SKILL.md
4. Install: Write to repo
```

### Example 2: Generate for a frontend repo

```
User: "Set up artifact tracking for our React app"

1. Discover: README.md, CLAUDE.md, component docs, Storybook stories, test files
2. Map: README references setup steps; component docs reference prop types
3. Generate: .claude/skills/update-living-artifacts/SKILL.md
4. Install: Write to repo
```

## Success Criteria

- [ ] Artifact registry covers all living documents in the target repo
- [ ] Dependency map correctly identifies which artifacts reference which
- [ ] Generated skill can audit the repo and find genuinely stale artifacts
- [ ] Generated skill produces specific, actionable edit suggestions
- [ ] Skill is self-contained — works without this meta-skill
- [ ] User reviewed and approved the artifact registry before generation

## Best Practices

- **Be conservative** — only flag artifacts as stale when you have evidence (e.g., a referenced file was renamed, a documented command was removed)
- **Don't over-index** — not every doc needs to be a living artifact. Design docs and ADRs are often historical records that should NOT be auto-updated
- **Respect ownership** — some artifacts are owned by other repos. Flag cross-repo staleness but don't try to fix it
- **Keep the registry maintainable** — 10-30 artifacts is typical. If a repo has 100+, group them by category

## Common Mistakes to Avoid

| Mistake | Why It's Wrong | Do This Instead |
|---------|---------------|-----------------|
| Auto-updating design docs | Design docs are historical records | Flag them for human review, don't auto-edit |
| Including generated files | Generated files are rebuilt, not maintained | Only include hand-maintained artifacts |
| Overly broad triggers | "Any change triggers all audits" wastes time | Map specific dependencies |
| Ignoring cross-repo refs | Some artifacts reference files in other repos | Note cross-repo refs but don't try to fix them |

## Related Skills

- `manage-skills/create-skill` — For creating skills from scratch (this skill generates a specific type)
- `manage-claude-config/setup-claude-md` — For setting up CLAUDE.md (one of the artifacts this skill tracks)
