---
name: introduce
description: Explain servicenow-manager plugin capabilities and available skills
---

# servicenow-manager: Introduction

You are introducing the `servicenow-manager` plugin. Give the user a clear overview of what this plugin does and how to use it.

## What This Plugin Does

`servicenow-manager` provides ServiceNow-specific tooling for building and maintaining Tampermonkey userscripts that automate ServiceNow browser workflows.

## Skills

### Tampermonkey

| Skill | What it does |
|---|---|
| `tampermonkey-servicenow` | ServiceNow-specific Tampermonkey guidance, including real-world script examples and ServiceNow-specific patterns |

## When to Use This Plugin

- Building a new Tampermonkey script for ServiceNow (transcript extraction, lab downloads, form automation)
- Referencing existing ServiceNow userscript patterns
- Looking for ServiceNow-specific Tampermonkey conventions and gotchas

## Common Workflows

```
ServiceNow automation script:
  /servicenow-manager:tampermonkey-servicenow
  → Provides ServiceNow-specific guidance + real-world script reference
  → Use alongside /script-manager:tampermonkey-create for the full workflow
```

## User Interaction

Use `AskUserQuestion` to ask the user which area they want to explore:

- ServiceNow Tampermonkey patterns and gotchas
- Real-world script examples and structure
- Specific ServiceNow API/selector patterns

## Related Plugins

- **script-manager** — General Tampermonkey userscript creation workflow
