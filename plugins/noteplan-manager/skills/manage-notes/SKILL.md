---
name: manage-notes
description: Note management orchestrator — create, organize, analyze, discover, and improve notes. Routes to the right sub-skill based on intent.
---

# Manage Notes

You are the note management orchestrator for noteplan-manager. When invoked, detect what the user wants to do with notes and route them to the appropriate sub-skill workflow.

## What This Skill Does

Single entry point for all note creation, organization, analysis, and improvement operations:

| Operation | Triggers | Sub-skill |
|---|---|---|
| Create a structured note | "create", "new note", "project note", "meeting note" | [create-note/SKILL.md](create-note/SKILL.md) |
| Create quickly with minimal friction | "quick", "fast note", "capture idea" | [quick-note/SKILL.md](quick-note/SKILL.md) |
| Organize reference links | "reference", "links", "citations", "organize references" | [fix-reference/SKILL.md](fix-reference/SKILL.md) |
| Sort iPhone links to reference files | "iphone", "iphone.md", "triage links", "sort links" | [sort-iphone-links/SKILL.md](sort-iphone-links/SKILL.md) |
| Add sub-headers to large sections | "organize note", "sub-headers", "large section", "section refinement", "too long" | [organize-note/SKILL.md](organize-note/SKILL.md) |
| Generate the vault Note Map | "discover structure", "note map", "scan notes", "first time setup" | [discover-structure/SKILL.md](discover-structure/SKILL.md) |
| Analyze organization patterns | "analyze", "structure", "patterns", "organization" | [analyze-structure/SKILL.md](analyze-structure/SKILL.md) |
| Suggest organization improvements | "suggest", "improve", "recommendations", "optimize" | [suggest-improvements/SKILL.md](suggest-improvements/SKILL.md) |
| Review notes health | "review", "health check", "broken links", "scan tasks" | [review-noteplan/SKILL.md](review-noteplan/SKILL.md) |
| Enrich bare URLs with summaries | "enrich links", "bare URLs", "unenriched links", "hook said enrich" | [enrich-links/SKILL.md](enrich-links/SKILL.md) |

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Detect intent", description: "Determine what note operation the user wants", activeForm: "Detecting intent" })
TaskCreate({ subject: "Execute sub-skill workflow", description: "Read and follow the appropriate sub-skill SKILL.md", activeForm: "Running sub-skill" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
```

## Your Workflow

### Phase 1: Detect Intent

Check if the user's message clearly signals an operation from the table above. Common signals:

- "create a note" / "new project note" / "meeting note" → create-note
- "quick note" / "fast capture" / "jot down" → quick-note
- "organize references" / "clean up links" / "MLA citations" → fix-reference
- "iphone links" / "sort iPhone.md" / "triage links" → sort-iphone-links
- "discover structure" / "note map" / "first time" / "new machine" → discover-structure
- "analyze structure" / "how are my notes organized" → analyze-structure
- "suggest improvements" / "optimize my system" → suggest-improvements
- "review notes" / "health check" / "broken links" / "scan tasks" → review-noteplan
- "enrich links" / "bare URLs" / "hook said enrich" / "unenriched links" → enrich-links
- "organize note" / "sub-headers" / "this section is too long" / "add headers" → organize-note

If the intent is **clear** from the message, proceed directly to Phase 2 without asking.

If the intent is **ambiguous**, use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "What would you like to do with your notes?",
    header: "Note operation",
    options: [
      { label: "Create a structured note", description: "Interactive creation following existing conventions — naming, emoji, frontmatter, links" },
      { label: "Quick note", description: "Fast capture with smart defaults and minimal questions" },
      { label: "Organize reference links", description: "MLA-style citations, metadata extraction, smart grouping in a reference file" },
      { label: "Sort iPhone links", description: "Triage iPhone.md links to 15+ categorized reference files with metadata enrichment" },
      { label: "Analyze / discover structure", description: "Map your vault, detect patterns, generate 🗺️ Note Map.md" },
      { label: "Suggest improvements", description: "Get prioritized, actionable recommendations for your organization system" }
    ],
    multiSelect: false
  }]
})
```

### Phase 2: Execute Sub-Skill

Read the appropriate sub-skill SKILL.md and follow its workflow as if it had been invoked directly.

**For create-note:** Read [create-note/SKILL.md](create-note/SKILL.md) and follow its workflow.

**For quick-note:** Read [quick-note/SKILL.md](quick-note/SKILL.md) and follow its workflow.

**For fix-reference:** Read [fix-reference/SKILL.md](fix-reference/SKILL.md) and follow its workflow.

**For sort-iphone-links:** Read [sort-iphone-links/SKILL.md](sort-iphone-links/SKILL.md) and follow its workflow.

**For discover-structure:** Read [discover-structure/SKILL.md](discover-structure/SKILL.md) and follow its workflow.

**For analyze-structure:** Read [analyze-structure/SKILL.md](analyze-structure/SKILL.md) and follow its workflow.

**For suggest-improvements:** Read [suggest-improvements/SKILL.md](suggest-improvements/SKILL.md) and follow its workflow.

**For review-noteplan:** Read [review-noteplan/SKILL.md](review-noteplan/SKILL.md) and follow its workflow.

**For organize-note:** Read [organize-note/SKILL.md](organize-note/SKILL.md) and follow its workflow.

## What This Skill Does NOT Do

- Does not fix filenames — use `/noteplan-manager:manage-filenames`
- Does not fix frontmatter — use `/noteplan-manager:manage-frontmatter`
- Does not organize daily calendar files — use `/noteplan-manager:manage-daily-notes`
- Does not manage plans or templates — use the respective meta-skills

## Success Criteria

- [ ] Intent detected without unnecessary questions when signal is clear
- [ ] Correct sub-skill workflow followed in full
- [ ] User can accomplish their note task without knowing which sub-skill to call directly
