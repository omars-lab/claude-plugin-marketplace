---
name: manage-templates
description: Template management orchestrator — create, browse, edit, and validate templates; sync plan templates with workstream emojis.
---

# Manage Templates

You are the template management orchestrator for noteplan-manager. When invoked, detect what the user wants to do with templates and route them to the appropriate sub-skill workflow.

## What This Skill Does

Single entry point for all template operations:

| Operation | Triggers | Sub-skill |
|---|---|---|
| Create, browse, edit, or validate templates | "template", "list templates", "create template", "edit template", "browse templates" | [manage-templates/SKILL.md](manage-templates/SKILL.md) |
| Sync plan templates with workstream emojis | "sync plan templates", "sync templates", "workstream templates", "update templates" | [sync-plan-templates/SKILL.md](sync-plan-templates/SKILL.md) |

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Detect intent", description: "Determine what template operation the user wants", activeForm: "Detecting intent" })
TaskCreate({ subject: "Execute sub-skill workflow", description: "Read and follow the appropriate sub-skill SKILL.md", activeForm: "Running sub-skill" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
```

## Your Workflow

### Phase 1: Detect Intent

Check if the user's message clearly signals an operation from the table above. Common signals:

- "template" / "list templates" / "create template" / "edit template" / "browse" → manage-templates
- "sync plan templates" / "update templates" / "workstream emoji" → sync-plan-templates

If the intent is **clear** from the message, proceed directly to Phase 2 without asking.

If the intent is **ambiguous**, use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "What would you like to do with templates?",
    header: "Template operation",
    options: [
      { label: "Manage templates", description: "Create, browse, edit, organize, or validate templates in @Templates directory" },
      { label: "Sync plan templates", description: "Keep plan templates in sync with current workstream/activity emojis" }
    ],
    multiSelect: false
  }]
})
```

### Phase 2: Execute Sub-Skill

Read the appropriate sub-skill SKILL.md and follow its workflow as if it had been invoked directly.

**For manage-templates:** Read [manage-templates/SKILL.md](manage-templates/SKILL.md) and follow its workflow.

**For sync-plan-templates:** Read [sync-plan-templates/SKILL.md](sync-plan-templates/SKILL.md) and follow its workflow.

## What This Skill Does NOT Do

- Does not fix emoji encoding in plan files — use `/noteplan-manager:manage-emojis`
- Does not create regular notes — use `/noteplan-manager:manage-notes`

## Success Criteria

- [ ] Intent detected without unnecessary questions when signal is clear
- [ ] Correct sub-skill workflow followed in full
- [ ] User can complete the template operation without knowing which sub-skill to call directly
