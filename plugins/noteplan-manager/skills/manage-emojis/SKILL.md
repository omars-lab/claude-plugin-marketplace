---
name: manage-emojis
description: Emoji management orchestrator — fix emoji encoding in work and personal plans, sync header emojis with folder emojis.
---

# Manage Emojis

You are the emoji management orchestrator for noteplan-manager. When invoked, detect what the user wants to fix or sync with emojis and route them to the appropriate sub-skill workflow.

## What This Skill Does

Single entry point for all emoji operations:

| Operation | Triggers | Sub-skill |
|---|---|---|
| Fix emoji encoding in work plans | "work emoji", "fix work emojis", "work plan emoji", "encoding" | [fix-work-emojis/SKILL.md](fix-work-emojis/SKILL.md) |
| Fix emoji encoding in personal plans | "personal emoji", "fix personal emojis", "personal plan emoji", "skin tone" | [fix-personal-emojis/SKILL.md](fix-personal-emojis/SKILL.md) |
| Sync header titles with folder emojis | "sync header", "header emoji", "folder emoji", "sync emojis" | [sync-header-emojis/SKILL.md](sync-header-emojis/SKILL.md) |

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Detect intent", description: "Determine what emoji operation the user wants", activeForm: "Detecting intent" })
TaskCreate({ subject: "Execute sub-skill workflow", description: "Read and follow the appropriate sub-skill SKILL.md", activeForm: "Running sub-skill" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
```

## Your Workflow

### Phase 1: Detect Intent

Check if the user's message clearly signals an operation from the table above. Common signals:

- "work emojis" / "fix work emoji" / "ServiceNow emojis broken" → fix-work-emojis
- "personal emojis" / "fix personal emoji" / "skin tone" / "complex sequences" → fix-personal-emojis
- "sync header" / "header emoji" / "folder emoji mismatch" / "sync emojis" → sync-header-emojis

If the intent is **clear** from the message, proceed directly to Phase 2 without asking.

If the intent is **ambiguous**, use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "Which emoji operation would you like to run?",
    header: "Emoji operation",
    options: [
      { label: "Fix work plan emojis", description: "Normalize emoji encoding in work/ServiceNow plan files using Python script" },
      { label: "Fix personal plan emojis", description: "Fix complex emoji sequences (skin tones, ZWJ) in personal plan files" },
      { label: "Sync header emojis", description: "Update H1 titles in notes to match their parent folder's emoji" }
    ],
    multiSelect: false
  }]
})
```

### Phase 2: Execute Sub-Skill

Read the appropriate sub-skill SKILL.md and follow its workflow as if it had been invoked directly.

**For fix-work-emojis:** Read [fix-work-emojis/SKILL.md](fix-work-emojis/SKILL.md) and follow its workflow.

**For fix-personal-emojis:** Read [fix-personal-emojis/SKILL.md](fix-personal-emojis/SKILL.md) and follow its workflow.

**For sync-header-emojis:** Read [sync-header-emojis/SKILL.md](sync-header-emojis/SKILL.md) and follow its workflow.

## What This Skill Does NOT Do

- Does not sync plan templates with workstream emojis — use `/noteplan-manager:manage-templates`
- Does not fix frontmatter — use `/noteplan-manager:manage-frontmatter`

## Success Criteria

- [ ] Intent detected without unnecessary questions when signal is clear
- [ ] Correct sub-skill workflow followed in full
- [ ] User can fix emoji issues without knowing which sub-skill to call directly
