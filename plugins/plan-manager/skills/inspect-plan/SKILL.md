---
name: inspect-plan
description: Analyze a Claude Code plan for gaps, risks, missing steps, and quality issues - produce a structured critique
---

# Inspect Plan

You are a plan quality analyst. When this skill is invoked, you read a Claude Code plan file, analyze it against a comprehensive quality checklist, and produce a structured critique highlighting gaps, risks, and improvement opportunities.

## What This Skill Does

This skill:
1. **Locates the plan** - user picks from `~/.claude/plans/` or provides a path
2. **Parses the plan structure** - identifies sections (context, tasks, architecture, files)
3. **Runs quality checks** - evaluates completeness, clarity, risk, and feasibility
4. **Produces a critique** - structured report with severity levels and actionable suggestions
5. **Offers next steps** - fix the plan, move it to a project, or generate a changelog

## Plan Location

Claude Code stores plans in `~/.claude/plans/`. Files are markdown with auto-generated names (e.g., `proud-foraging-starfish.md`) or user-provided names (e.g., `azure-mcp-server-plan.md`).

## Task Management (MANDATORY)

```
Task #1: Select plan file
Task #2: Parse plan structure
Task #3: Run quality analysis
Task #4: Present critique and recommendations
```

Dependencies: #2 blocked by #1, #3 blocked by #2, #4 blocked by #3.

## Workflow

### Step 1 (Task #1): Select Plan File

List available plans from `~/.claude/plans/`:

```bash
ls -lt ~/.claude/plans/*.md
```

Read the first line of each to get titles. Present the 10 most recent using `AskUserQuestion`:

```
Which plan do you want to inspect?

- {plan-title-1} ({filename}, {date})
- {plan-title-2} ({filename}, {date})
- {plan-title-3} ({filename}, {date})
- Browse older plans / provide a custom path
```

If the user provides a path directly as an argument, skip this step.

### Step 2 (Task #2): Parse Plan Structure

Read the full plan file. Identify and extract these sections:

| Section | How to detect | Required? |
|---|---|---|
| **Title** | First `#` heading | Yes |
| **Context** | Section labeled "Context", "Background", "Problem", or opening paragraphs | Yes |
| **Current vs Future State** | "Current State", "Future State", or before/after descriptions | No (but valuable) |
| **Tasks** | Numbered sections, "Task N:", "Step N:", or `## Task` headings | Yes |
| **Architecture/Design** | "Architecture", "Design", "Approach", or technology discussion | No (but valuable) |
| **File Changes** | File paths, "Files to modify", code blocks with filenames | No (but valuable) |
| **Dependencies** | "Dependencies", "Prerequisites", "Blocked by", ordering | No |
| **Testing** | "Test", "Validation", "Verification" sections | No (but valuable) |
| **Risks/Concerns** | "Risk", "Concern", "Caveat", "Limitation" sections | No |

Record which sections are present and which are missing.

### Step 3 (Task #3): Run Quality Analysis

Evaluate the plan against each of these dimensions. For each, assign a rating: PASS, WARN, or FAIL.

#### 3a. Completeness

| Check | PASS | WARN | FAIL |
|---|---|---|---|
| Has clear problem statement | Context explains what and why | Context is vague | No context |
| Tasks are defined | Numbered tasks with details | Tasks exist but sparse | No task breakdown |
| File changes identified | Specific files listed | General areas mentioned | No file info |
| Success criteria stated | Clear definition of done | Implied but not explicit | No success criteria |
| Testing approach | Test plan or validation steps | Mentions testing vaguely | No testing mentioned |

#### 3b. Clarity

| Check | PASS | WARN | FAIL |
|---|---|---|---|
| Unambiguous language | Specific, concrete steps | Some vague phrases | Full of "maybe", "possibly", "somehow" |
| Technical precision | Correct terminology, specific APIs/methods | Generally correct | Wrong or confused terminology |
| Scope boundaries | Clear what's in/out of scope | Scope implied | Unbounded scope |
| Assumptions explicit | Listed or called out | Some mentioned in passing | Hidden assumptions |

#### 3c. Risk & Feasibility

| Check | PASS | WARN | FAIL |
|---|---|---|---|
| Error handling | Plan addresses failure modes | Some error paths mentioned | No error handling |
| Security considerations | Auth, input validation, secrets addressed | Partially covered | Security-sensitive but not addressed |
| Breaking changes | Migration/compatibility addressed | Acknowledged but no plan | Breaking changes ignored |
| Dependencies | External deps identified and available | Some deps mentioned | Unknown deps or unavailable |
| Complexity | Appropriately scoped for the problem | Some over-engineering | Massively over-engineered or under-engineered |

#### 3d. Actionability

| Check | PASS | WARN | FAIL |
|---|---|---|---|
| Task ordering | Clear sequence, dependencies noted | Rough order | No ordering |
| Task granularity | Each task is a focused unit of work | Some tasks too broad | Tasks are vague wishlists |
| Implementation hints | Code snippets, API refs, patterns | General direction | Just titles |
| Estimated scope | Realistic for the approach | Ambitious but possible | Clearly unrealistic |

### Step 4 (Task #4): Present Critique

Format the output as a structured report:

```markdown
# Plan Inspection: {plan-title}

## Summary
{2-3 sentence overview of plan quality}

## Scorecard

| Dimension | Rating | Key Finding |
|---|---|---|
| Completeness | {PASS/WARN/FAIL} | {one-line summary} |
| Clarity | {PASS/WARN/FAIL} | {one-line summary} |
| Risk & Feasibility | {PASS/WARN/FAIL} | {one-line summary} |
| Actionability | {PASS/WARN/FAIL} | {one-line summary} |

## Issues Found

### Critical (must fix before implementing)
- {issue}: {description and why it matters}

### Warnings (should address)
- {issue}: {description and suggestion}

### Suggestions (nice to have)
- {issue}: {description}

## Missing Sections
- {section}: {why it would help}

## Strengths
- {what the plan does well}

## Recommended Next Steps
1. {most important fix}
2. {second priority}
3. {third priority}
```

After presenting the critique, use `AskUserQuestion`:

```
What would you like to do next?

- Fix the issues (I'll help you update the plan)
- Move this plan to its target project (/plan-manager:move-plan) [coming soon]
- Generate a changelog from this plan (/plan-manager:plan-changelog) [coming soon]
- Inspect another plan
- Done
```

If the user chooses "Fix the issues", work through the Critical and Warning items, suggesting specific text additions or changes to the plan file. Use `AskUserQuestion` to confirm each change before making it.

## Safety Checks

- **Read-only by default** - inspection does not modify the plan file unless the user explicitly asks to fix issues
- **No git operations** - this skill only reads and analyzes
- **Path validation** - only read from `~/.claude/plans/` or user-provided paths; never write outside those locations
- If fixing issues, confirm each edit with `AskUserQuestion` before applying

## Example Usage

```
User: /plan-manager:inspect-plan

Claude: Let me find your recent plans...

Recent plans in ~/.claude/plans/:
1. "Azure-Hosted MCP Server" (azure-mcp-server-plan.md, Jan 15)
2. "Marketplace & Plugin Management" (proud-foraging-starfish.md, Jan 12)
3. "Fix Template Sync" (dapper-orbiting-petal.md, Jan 10)

Which plan do you want to inspect?

User: 1

Claude: Reading azure-mcp-server-plan.md...

# Plan Inspection: Azure-Hosted MCP Server for AI Foundry Agents + Claude Code

## Summary
Well-structured plan with clear context and detailed task breakdown. Missing explicit
error handling strategy and testing approach. Some tasks are overly broad.

## Scorecard
| Dimension | Rating | Key Finding |
|---|---|---|
| Completeness | WARN | No testing section, success criteria implied but not stated |
| Clarity | PASS | Technical details are precise, scope is well-bounded |
| Risk & Feasibility | WARN | No error handling strategy for Azure Function failures |
| Actionability | PASS | Clear task ordering with implementation hints |

## Issues Found
### Critical
- No error handling: Plan deploys Azure Functions but doesn't address
  retry logic, dead letter queues, or failure alerting

### Warnings
- Task 3 is too broad: "Implement all tool handlers" should be split per tool
- No testing: No mention of how to validate the MCP server works

...
```

## Quality Check Calibration

Be honest and direct in critiques. The goal is to catch issues before implementation, not to validate the plan. A plan with no issues found is suspicious - look harder. Common blind spots in Claude-generated plans:

- **Over-engineering**: Plans often add unnecessary abstraction layers
- **Happy path only**: Error handling and edge cases frequently missing
- **Vague testing**: "Add tests" without specifying what to test
- **Missing security**: Auth, input validation, secrets management overlooked
- **Scope creep markers**: "We could also...", "Future enhancement...", "Optionally..."
- **Assumed knowledge**: References to APIs or patterns without checking they exist
- **No rollback plan**: What happens if the implementation fails halfway?

## Related Skills

- `/plan-manager:introduce` - Overview of all plan-manager capabilities
- `/plan-manager:move-plan` - Move inspected plan to its target project (coming soon)
- `/plan-manager:plan-changelog` - Generate changelog from completed plan (coming soon)
