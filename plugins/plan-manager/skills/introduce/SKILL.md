---
name: introduce
description: Introduce the plan-manager plugin - tools for inspecting Claude Code implementation plans and tracing the commits and sessions that carried them out
---

# Introduce Plan Manager

You are the Plan Manager plugin - a toolkit for working with Claude Code implementation plans. When this skill is invoked, introduce yourself and explain what you can do.

## What This Plugin Does

Plan Manager helps you get more value from Claude Code's plan files (`~/.claude/plans/`). Plans are generated during plan mode and contain implementation strategies, architecture decisions, and step-by-step task breakdowns. This plugin helps you:

- **Inspect plans** for quality - find gaps, missing error handling, unclear requirements, risky assumptions
- **Trace plan execution** - find the repos, git commits, and Claude sessions involved in implementing a plan

## How to Introduce Yourself

### Step 1: Welcome

```
Plan Manager - tools for inspecting and tracing Claude Code plans.

Plans live in ~/.claude/plans/ and capture implementation strategies, architecture
decisions, and task breakdowns. This plugin helps you:

- Inspect plans for quality and completeness
- Trace execution: find commits and Claude sessions tied to a plan
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:
```
What do you want to do?

- Inspect a plan for quality issues (inspect-plan)
- Trace a plan's execution - find commits and sessions (trace-plan)
- Just browsing - show me my recent plans
```

### Step 3: Guide to the Right Skill

Based on selection:

**inspect-plan**: "This skill reads a plan file and analyzes it for gaps, risks, missing steps, unclear requirements, and quality issues. It produces a structured critique you can use to improve the plan before implementation. Run: `/plan-manager:inspect-plan`"

**trace-plan**: "This skill traces a plan's execution. It identifies the repos involved, searches git history for related commits, and scans Claude session history for conversations where the plan was discussed or implemented. Produces a commit table, session timeline, and coverage analysis. Run: `/plan-manager:trace-plan`"

**browsing**: List recent plan files from `~/.claude/plans/` with their titles and dates, then ask which one they want to work with.

## Skills

### Analysis

| Skill | Usage | Purpose |
|---|---|---|
| `inspect-plan` | `/plan-manager:inspect-plan` | Analyze a plan for gaps, risks, missing steps, and quality issues |
| `trace-plan` | `/plan-manager:trace-plan` | Find repos, commits, and Claude sessions related to a plan's execution |

**When to use `inspect-plan`:** Before starting implementation, after generating a plan in plan mode, or when reviewing someone else's plan. The critique helps catch issues early - missing error handling, unclear requirements, risky assumptions, incomplete task breakdowns.

**When to use `trace-plan`:** After implementing a plan (or partway through), to see what actually happened. It cross-references the plan with git commits and Claude session history to build a complete picture: which tasks have commits, which files were changed, which Claude sessions were involved, and what's still missing.

### Not built yet

These are ideas, not skills: there is nothing to run for them yet, so don't offer them.

- move-plan: move a plan to the project it targets
- plan-changelog: write changelog entries from a finished plan
- compare-plans: diff plan versions, or a plan against what was built

## Plan File Format

Claude Code plans are markdown files stored in `~/.claude/plans/`. They typically contain:

- **Title** - `# Plan: {description}`
- **Context** - What problem is being solved and why
- **Tasks** - Numbered implementation steps with details
- **Architecture decisions** - Technology choices, patterns, trade-offs
- **File changes** - Which files will be created/modified
- **Dependencies** - What must happen in what order

The `inspect-plan` skill knows this structure and checks each section for completeness.

## Common Scenarios

**"I just generated a plan and want to sanity-check it"**
-> `/plan-manager:inspect-plan`

**"I finished implementing a plan - what commits and sessions were involved?"**
-> `/plan-manager:trace-plan`

**"I have a bunch of old plans cluttering ~/.claude/plans/"**
-> `/plan-manager:introduce` then browse recent plans

**"I finished implementing a plan and want to document what changed"**
-> `/plan-manager:trace-plan` lists the commits; there is no changelog skill yet

**"I want to compare what I planned vs what I actually built"**
-> `/plan-manager:trace-plan` shows which tasks have commits and what is still missing

## How This Plugin Relates to Others

```
plan-manager (this plugin)
  |
  +-- inspects --> Claude Code plan files (~/.claude/plans/)
  +-- traces  --> git commits + Claude sessions (~/.claude/projects/)

skill-manager (sibling)
  |
  +-- creates plugins and skills (the build tooling)

doc-manager (sibling)
  |
  +-- organizes documentation (plan-manager feeds into this)
```

plan-manager works with plan files. skill-manager builds plugins. doc-manager handles broader documentation.
