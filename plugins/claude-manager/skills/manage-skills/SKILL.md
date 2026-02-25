---
name: manage-skills
description: Skill lifecycle orchestrator — create, evaluate, and update skills in any plugin. Routes to the right sub-skill based on intent.
---

# Manage Skills

You are the skill lifecycle orchestrator for claude-manager. When invoked, detect what the user wants to do with skills and route them to the appropriate sub-skill workflow.

## What This Skill Does

Single entry point for all skill operations:

| Operation | Triggers | Sub-skill |
|---|---|---|
| Create a new skill | "create", "new skill", "add skill" | [create-skill/SKILL.md](create-skill/SKILL.md) |
| Evaluate skill quality | "evaluate", "score", "quality", "improve" | [evaluate-skill/SKILL.md](evaluate-skill/SKILL.md) |
| Update an existing skill | "update", "edit", "modify", "change" | [update-skill/SKILL.md](update-skill/SKILL.md) |

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Detect intent", description: "Determine what skill operation the user wants", activeForm: "Detecting intent" })
TaskCreate({ subject: "Execute sub-skill workflow", description: "Read and follow the appropriate sub-skill SKILL.md", activeForm: "Running sub-skill" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
```

## Your Workflow

### Phase 1: Detect Intent

First, check if the user's message clearly signals an operation from the table above. Common signals:

- "create a skill" / "new skill" / "add skill to <plugin>" → create-skill
- "evaluate skill" / "score this skill" / "improve skill quality" → evaluate-skill
- "update skill" / "edit SKILL.md" / "modify the skill" → update-skill

If the intent is **clear** from the message, proceed directly to Phase 2 without asking.

If the intent is **ambiguous**, use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "What would you like to do with skills?",
    header: "Skill operation",
    options: [
      { label: "Create a new skill", description: "Add a skill to an existing plugin with proper SKILL.md structure, task management, and framework compliance" },
      { label: "Evaluate skill quality", description: "Score skills on 9 dimensions (frontmatter, task management, guardrails, scripts, success criteria) and implement improvements" },
      { label: "Update an existing skill", description: "Navigate to and safely edit an existing skill's SKILL.md with context-aware editing" }
    ],
    multiSelect: false
  }]
})
```

### Phase 2: Execute Sub-Skill

Read the appropriate sub-skill SKILL.md and follow its workflow as if it had been invoked directly.

**For create-skill:** Read [create-skill/SKILL.md](create-skill/SKILL.md) and follow its workflow.

**For evaluate-skill:** Read [evaluate-skill/SKILL.md](evaluate-skill/SKILL.md) and follow its workflow.

**For update-skill:** Read [update-skill/SKILL.md](update-skill/SKILL.md) and follow its workflow.

## What This Skill Does NOT Do

- Does not handle plugin-level operations (create plugin, fix version drift) — use `/claude-manager:manage-plugins`
- Does not configure CLAUDE.md or MCP — use `/claude-manager:manage-claude-config`
- Does not rewrite entire SKILL.md files — targeted edits only (via update-skill)

## Success Criteria

- [ ] Intent detected without unnecessary questions when signal is clear
- [ ] Correct sub-skill workflow followed in full
- [ ] User can complete the operation without knowing which sub-skill to call directly
