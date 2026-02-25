---
name: manage-daily-notes
description: Daily note management orchestrator — organize daily calendar files and move content between notes.
---

# Manage Daily Notes

You are the daily note management orchestrator for noteplan-manager. When invoked, detect what the user wants to do with daily notes and route them to the appropriate sub-skill workflow.

## What This Skill Does

Single entry point for daily note operations:

| Operation | Triggers | Sub-skill |
|---|---|---|
| Process daily notes and move tasks to project notes | "organize daily", "process daily", "morning routine", "end of day" | [organize-daily/SKILL.md](organize-daily/SKILL.md) |
| Move specific content between notes | "move content", "migrate content", "move tasks", "move to project" | [move-content/SKILL.md](move-content/SKILL.md) |

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Detect intent", description: "Determine what daily note operation the user wants", activeForm: "Detecting intent" })
TaskCreate({ subject: "Execute sub-skill workflow", description: "Read and follow the appropriate sub-skill SKILL.md", activeForm: "Running sub-skill" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
```

## Your Workflow

### Phase 1: Detect Intent

Check if the user's message clearly signals an operation from the table above. Common signals:

- "organize daily" / "process daily notes" / "morning routine" / "clean up daily" → organize-daily
- "move content" / "move tasks" / "migrate tasks" / "move to project note" → move-content

If the intent is **clear** from the message, proceed directly to Phase 2 without asking.

If the intent is **ambiguous**, use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "What would you like to do with your daily notes?",
    header: "Daily note operation",
    options: [
      { label: "Organize daily notes", description: "Scan daily calendar files from past 14 days, move incomplete tasks to project notes, add birth dates" },
      { label: "Move specific content", description: "Move targeted content between two specific notes, preserving task hierarchies and metadata" }
    ],
    multiSelect: false
  }]
})
```

### Phase 2: Execute Sub-Skill

Read the appropriate sub-skill SKILL.md and follow its workflow as if it had been invoked directly.

**For organize-daily:** Read [organize-daily/SKILL.md](organize-daily/SKILL.md) and follow its workflow.

**For move-content:** Read [move-content/SKILL.md](move-content/SKILL.md) and follow its workflow.

## What This Skill Does NOT Do

- Does not reorganize plan file *content* under sections — use `/noteplan-manager:manage-plans` → organize-plans
- Does not fix frontmatter or filenames — use the respective meta-skills

## Success Criteria

- [ ] Intent detected without unnecessary questions when signal is clear
- [ ] Correct sub-skill workflow followed in full
- [ ] User can complete the daily note operation without knowing which sub-skill to call directly
