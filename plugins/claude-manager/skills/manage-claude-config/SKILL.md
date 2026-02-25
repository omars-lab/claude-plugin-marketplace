---
name: manage-claude-config
description: Claude configuration orchestrator — configure MCP servers, status line, and CLAUDE.md files. Routes to the right sub-skill based on intent.
---

# Manage Claude Config

You are the Claude configuration orchestrator for claude-manager. When invoked, detect what the user wants to configure and route them to the appropriate sub-skill workflow.

## What This Skill Does

Single entry point for all Claude configuration operations:

| Operation | Triggers | Sub-skill |
|---|---|---|
| Configure MCP servers | "MCP", "token cost", "tool restrictions", "disable tools" | [configure-mcp/SKILL.md](configure-mcp/SKILL.md) |
| Configure status line | "status line", "statusline", "token bar" | [configure-statusline/SKILL.md](configure-statusline/SKILL.md) |
| Fix / minimize CLAUDE.md | "fix claude.md", "audit claude.md", "bloated", "clean up" | [fix-claude-md/SKILL.md](fix-claude-md/SKILL.md) |
| Research CLAUDE.md patterns | "research", "patterns", "session history", "what have I asked" | [research-claude-md/SKILL.md](research-claude-md/SKILL.md) |
| Generate CLAUDE.md from scratch | "setup", "generate", "new claude.md", "create claude.md" | [setup-claude-md/SKILL.md](setup-claude-md/SKILL.md) |

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Detect intent", description: "Determine what configuration operation the user wants", activeForm: "Detecting intent" })
TaskCreate({ subject: "Execute sub-skill workflow", description: "Read and follow the appropriate sub-skill SKILL.md", activeForm: "Running sub-skill" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
```

## Your Workflow

### Phase 1: Detect Intent

First, check if the user's message clearly signals an operation from the table above. Common signals:

- "MCP" / "token overhead" / "disable tools" / "opt-in alias" → configure-mcp
- "status line" / "statusline" / "configure status" → configure-statusline
- "fix claude.md" / "audit claude.md" / "bloated instructions" / "clean up CLAUDE.md" → fix-claude-md
- "research claude.md" / "what patterns" / "mine session history" → research-claude-md
- "setup claude.md" / "generate CLAUDE.md" / "new project instructions" → setup-claude-md

If the intent is **clear** from the message, proceed directly to Phase 2 without asking.

If the intent is **ambiguous**, use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "What would you like to configure?",
    header: "Configuration",
    options: [
      { label: "MCP servers", description: "Audit token cost, restrict tools, create opt-in aliases to reduce context overhead" },
      { label: "Status line", description: "Wire ~/.claude/settings.json to the plugin's statusline script, configure display options" },
      { label: "Fix CLAUDE.md", description: "Audit and minimize an existing CLAUDE.md — remove bloat, keep only constraint-level instructions" },
      { label: "Research CLAUDE.md patterns", description: "Mine session logs and existing CLAUDE.md files to surface recurring preferences" },
      { label: "Generate CLAUDE.md", description: "Create a new CLAUDE.md for a project from scratch" }
    ],
    multiSelect: false
  }]
})
```

### Phase 2: Execute Sub-Skill

Read the appropriate sub-skill SKILL.md and follow its workflow as if it had been invoked directly.

**For configure-mcp:** Read [configure-mcp/SKILL.md](configure-mcp/SKILL.md) and follow its workflow.

**For configure-statusline:** Read [configure-statusline/SKILL.md](configure-statusline/SKILL.md) and follow its workflow.

**For fix-claude-md:** Read [fix-claude-md/SKILL.md](fix-claude-md/SKILL.md) and follow its workflow.

**For research-claude-md:** Read [research-claude-md/SKILL.md](research-claude-md/SKILL.md) and follow its workflow.

**For setup-claude-md:** Read [setup-claude-md/SKILL.md](setup-claude-md/SKILL.md) and follow its workflow.

## Recommended Sequence for New Projects

When setting up Claude configuration for a new project, the recommended order is:

1. `/claude-manager:manage-claude-config` → **research-claude-md** — surface preferences from session history
2. `/claude-manager:manage-claude-config` → **setup-claude-md** — generate the file using research findings as context
3. `/claude-manager:manage-claude-config` → **configure-mcp** — optimize token cost after project setup

## What This Skill Does NOT Do

- Does not create or update plugins/skills — use `/claude-manager:manage-plugins` or `/claude-manager:manage-skills`
- Does not modify any config files without explicit user confirmation
- Does not run destructive operations silently

## Success Criteria

- [ ] Intent detected without unnecessary questions when signal is clear
- [ ] Correct sub-skill workflow followed in full
- [ ] User can complete the operation without knowing which sub-skill to call directly
