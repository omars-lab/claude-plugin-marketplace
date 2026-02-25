---
name: manage-plans
description: Plan management orchestrator — fix, update, flatten, and organize plan files. Routes to the right sub-skill based on intent.
---

# Manage Plans

You are the plan management orchestrator for noteplan-manager. When invoked, detect what the user wants to do with plan files and route them to the appropriate sub-skill workflow.

## What This Skill Does

Single entry point for all plan file operations:

| Operation | Triggers | Sub-skill |
|---|---|---|
| Fix plan structure and frontmatter | "fix plans", "standardize plans", "plan structure", "missing frontmatter" | [fix-plans/SKILL.md](fix-plans/SKILL.md) |
| Update a plan's status | "status", "future", "started", "done", "paused", "change status" | [update-plan-status/SKILL.md](update-plan-status/SKILL.md) |
| Flatten Future/Present/Past folder structure | "flatten", "migrate", "future/present/past", "one-time migration" | [flatten-plans/SKILL.md](flatten-plans/SKILL.md) |
| Reorganize plan file content under sections | "organize plan", "reorganize", "sections", "scattered content" | [organize-plans/SKILL.md](organize-plans/SKILL.md) |

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Detect intent", description: "Determine what plan operation the user wants", activeForm: "Detecting intent" })
TaskCreate({ subject: "Execute sub-skill workflow", description: "Read and follow the appropriate sub-skill SKILL.md", activeForm: "Running sub-skill" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
```

## Your Workflow

### Phase 1: Detect Intent

Check if the user's message clearly signals an operation from the table above. Common signals:

- "fix plans" / "plan structure" / "missing frontmatter" / "standardize" → fix-plans
- "update status" / "change to started" / "mark as done" / "future → started" → update-plan-status
- "flatten plans" / "migrate from future/present/past" / "one-time migration" → flatten-plans
- "organize plan" / "reorganize" / "clean up sections" / "scattered content" → organize-plans

If the intent is **clear** from the message, proceed directly to Phase 2 without asking.

If the intent is **ambiguous**, use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "What would you like to do with your plan files?",
    header: "Plan operation",
    options: [
      { label: "Fix plan structure", description: "Standardize frontmatter, headers, and self-referencing todos across plan files" },
      { label: "Update plan status", description: "Change status of one or more plans (frontmatter, H1 emoji, filename, completed date)" },
      { label: "Flatten folder structure", description: "One-time migration: remove Future/Present/Past folders, move plans to flat workstream layout" },
      { label: "Reorganize plan content", description: "Group scattered content under clear section headers without changing any content" }
    ],
    multiSelect: false
  }]
})
```

### Phase 2: Execute Sub-Skill

Read the appropriate sub-skill SKILL.md and follow its workflow as if it had been invoked directly.

**For fix-plans:** Read [fix-plans/SKILL.md](fix-plans/SKILL.md) and follow its workflow.

**For update-plan-status:** Read [update-plan-status/SKILL.md](update-plan-status/SKILL.md) and follow its workflow.

**For flatten-plans:** Read [flatten-plans/SKILL.md](flatten-plans/SKILL.md) and follow its workflow.

**For organize-plans:** Read [organize-plans/SKILL.md](organize-plans/SKILL.md) and follow its workflow.

## What This Skill Does NOT Do

- Does not fix general frontmatter (non-plan note types) — use `/noteplan-manager:manage-frontmatter`
- Does not fix emojis — use `/noteplan-manager:manage-emojis`
- Does not fix filenames — use `/noteplan-manager:manage-filenames`

## Success Criteria

- [ ] Intent detected without unnecessary questions when signal is clear
- [ ] Correct sub-skill workflow followed in full
- [ ] User can complete the plan operation without knowing which sub-skill to call directly
