---
name: manage-repo-security
description: Install git hooks, secret scanning, and test gates on any repository. Enforces gitleaks pre-commit scanning and pre-push test runs. Use when setting up a new repo, auditing an existing repo's security posture, or adding test gates.
---

# Manage Repo Security

You are the repo security skill for code-quality-manager. When invoked, detect what the user wants and route to the appropriate workflow.

## What This Skill Does

Single entry point for repo security setup and auditing:

| Operation | Triggers | Sub-skill |
|---|---|---|
| Install hooks + scanning | "install hooks", "add secret scanning", "secure this repo", "set up hooks" | [install-hooks/SKILL.md](install-hooks/SKILL.md) |
| Audit security posture | "audit", "check hooks", "are hooks installed" | (handled inline — see Audit section) |

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Detect intent", description: "Determine what security operation the user wants", activeForm: "Detecting intent" })
TaskCreate({ subject: "Execute workflow", description: "Install hooks or audit security", activeForm: "Running workflow" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
```

## Inline: Audit Security Posture

When the user asks to audit/check a repo's security:

1. Check for git hooks:
   ```bash
   ls -la .git/hooks/pre-commit .git/hooks/pre-push 2>/dev/null
   ```

2. Check hook contents (do they enforce gitleaks? tests?):
   ```bash
   cat .git/hooks/pre-commit 2>/dev/null
   cat .git/hooks/pre-push 2>/dev/null
   ```

3. Check for gitleaks:
   ```bash
   which gitleaks && gitleaks version
   ```

4. Check for Makefile targets:
   ```bash
   grep -E 'secret-scan|test' Makefile 2>/dev/null
   ```

5. Check `.gitignore` for `.env`:
   ```bash
   grep '\.env' .gitignore
   ```

6. Report findings and offer to fix any gaps via [install-hooks/SKILL.md](install-hooks/SKILL.md).

## What This Skill Does NOT Do

- Does not improve documentation — use `/code-quality-manager:manage-docs`
- Does not generate Makefiles from scratch — use `/code-quality-manager:manage-makefiles`
- Does not analyze code changes — use `/code-quality-manager:poke-holes`
