---
name: manage-plugins
description: Plugin lifecycle orchestrator — create, evaluate, fix, uninstall, and improve plugins. Routes to the right sub-skill based on intent.
---

# Manage Plugins

You are the plugin lifecycle orchestrator for claude-manager. When invoked, detect what the user wants to do with plugins and route them to the appropriate sub-skill workflow.

## What This Skill Does

Single entry point for all plugin operations:

| Operation | Triggers | Sub-skill |
|---|---|---|
| Create a new plugin | "create", "scaffold", "new plugin" | [create-plugin/SKILL.md](create-plugin/SKILL.md) |
| Evaluate compliance | "evaluate", "audit", "check structure" | [evaluate-plugin/SKILL.md](evaluate-plugin/SKILL.md) |
| Fix version drift / update | "fix", "update", "out of date", "version" | [fix-plugins/SKILL.md](fix-plugins/SKILL.md) |
| Uninstall a plugin | "uninstall", "remove", "delete plugin" | (handled inline — see below) |
| Suggest maturity improvements | "mature", "smarter", "usage tracking" | [suggest-plugin-maturity/SKILL.md](suggest-plugin-maturity/SKILL.md) |
| Summarize AI usage | "summarize usage", "how do I use AI" | [summarize-ai-usage/SKILL.md](summarize-ai-usage/SKILL.md) |
| Condense flat skills into meta-skills | "condense", "consolidate", "restructure", "meta-skills" | [condense-plugin/SKILL.md](condense-plugin/SKILL.md) |

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Detect intent", description: "Determine what plugin operation the user wants", activeForm: "Detecting intent" })
TaskCreate({ subject: "Execute sub-skill workflow", description: "Read and follow the appropriate sub-skill SKILL.md", activeForm: "Running sub-skill" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
```

## Your Workflow

### Phase 1: Detect Intent

First, check if the user's message clearly signals an operation from the table above. Common signals:

- "create a plugin" / "new plugin" / "scaffold" → create-plugin
- "fix plugins" / "update plugins" / "version drift" / "plugins out of date" → fix-plugins
- "evaluate plugin" / "audit" / "check compliance" → evaluate-plugin
- "uninstall" / "remove plugin" → uninstall (inline)
- "suggest improvements" / "maturity" / "smarter skills" → suggest-plugin-maturity
- "how do I use AI" / "summarize my AI usage" → summarize-ai-usage
- "condense plugin" / "consolidate skills" / "restructure" / "meta-skills" → condense-plugin

If the intent is **clear** from the message, proceed directly to Phase 2 without asking.

If the intent is **ambiguous**, use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "What would you like to do with plugins?",
    header: "Plugin operation",
    options: [
      { label: "Create a new plugin", description: "Scaffold directory structure, plugin.json, introduce skill, marketplace registration" },
      { label: "Fix / update plugins", description: "Detect version drift, bump versions, run make update" },
      { label: "Evaluate compliance", description: "Check plugin structure, marketplace registration, naming conventions" },
      { label: "Uninstall a plugin", description: "Remove plugin from installed_plugins.json and cache" },
      { label: "Suggest maturity improvements", description: "Usage tracking, knowledge artifacts, feedback loops" },
      { label: "Summarize AI usage", description: "First-person narrative of how you use AI across all plugins" },
      { label: "Condense plugin to meta-skills", description: "Restructure a flat-skill plugin into a focused meta-skill hierarchy" }
    ],
    multiSelect: false
  }]
})
```

### Phase 2: Execute Sub-Skill

Read the appropriate sub-skill SKILL.md and follow its workflow as if it had been invoked directly.

**For create-plugin:** Read [create-plugin/SKILL.md](create-plugin/SKILL.md) and follow its workflow.

**For fix-plugins:** Read [fix-plugins/SKILL.md](fix-plugins/SKILL.md) and follow its workflow.

**For evaluate-plugin:** Read [evaluate-plugin/SKILL.md](evaluate-plugin/SKILL.md) and follow its workflow.

**For suggest-plugin-maturity:** Read [suggest-plugin-maturity/SKILL.md](suggest-plugin-maturity/SKILL.md) and follow its workflow.

**For summarize-ai-usage:** Read [summarize-ai-usage/SKILL.md](summarize-ai-usage/SKILL.md) and follow its workflow.

**For condense-plugin:** Read [condense-plugin/SKILL.md](condense-plugin/SKILL.md) and follow its workflow.

**For uninstall** (handled inline):

1. Ask which plugin to uninstall using `AskUserQuestion`
2. Confirm: "Uninstall `<plugin-name>@<marketplace>`? This removes it from your installed plugins."
3. Run uninstall:
   ```bash
   env -u CLAUDECODE claude plugin uninstall <plugin-name>@<marketplace> --scope user
   ```
4. Verify it's gone:
   ```bash
   cat ~/.claude/plugins/installed_plugins.json | python3 -m json.tool
   ```
5. Report: "✅ `<plugin-name>` uninstalled. It can be reinstalled with: `make install PLUGIN=<plugin-name>`"

## What This Skill Does NOT Do

- Does not evaluate individual skill quality — use `/claude-manager:manage-skills` → evaluate-skill
- Does not configure MCP servers or CLAUDE.md — use `/claude-manager:manage-claude-config`
- Does not run make targets without user confirmation

## Success Criteria

- [ ] Intent detected without unnecessary questions when signal is clear
- [ ] Correct sub-skill workflow followed in full
- [ ] User can complete the operation without knowing which sub-skill to call directly
