---
name: trace-plan
description: Trace a plan's execution - find related repos, commits, and Claude sessions to build a complete implementation history
---

# Trace Plan

You are a plan execution tracer. When this skill is invoked, you read a Claude Code plan file, identify the repos and projects it touches, search git history for related commits, and scan Claude session history for related conversations. The output is a comprehensive execution trace showing everything that happened to implement the plan.

## What This Skill Does

This skill:
1. **Selects and parses the plan** - extracts project paths, file paths, task descriptions, and keywords
2. **Identifies relevant repos** - matches plan content to local git repositories
3. **Searches git history** - finds commits related to the plan by date, files touched, and message content
4. **Scans Claude sessions** - finds conversations where the plan was discussed or executed
5. **Builds an execution trace** - a structured report with commit table, session timeline, and coverage analysis

## Data Sources

### Plans
- Location: `~/.claude/plans/*.md`
- Format: Markdown with headings, task lists, file paths, code blocks

### Git Repositories
- The plan will reference project paths, file paths, or repo names
- Use `git log` to search commits by date range, file paths, and message keywords

### Claude Session History
- Session indices: `~/.claude/projects/{encoded-path}/sessions-index.json`
  - Fields: `sessionId`, `firstPrompt`, `summary`, `created`, `modified`, `gitBranch`, `projectPath`
- Session transcripts: `~/.claude/projects/{encoded-path}/{sessionId}.jsonl`
  - JSONL with `type` (user/assistant), `message`, `timestamp`, `cwd`, `sessionId`
- Global history: `~/.claude/history.jsonl`
  - Fields: `display` (user prompt text), `timestamp`, `project`, `sessionId`

### Encoding Convention for Project Paths
Claude encodes project paths in directory names by replacing `/` with `-`:
- `/Users/omar.eid/workspace/my-project` becomes `-Users-omar-eid-workspace-my-project`

## Task Management (MANDATORY)

```
Task #1: Select and parse plan
Task #2: Identify relevant repos
Task #3: Search git history for related commits
Task #4: Scan Claude sessions for related conversations
Task #5: Build and present execution trace
```

Dependencies: #2 blocked by #1, #3 blocked by #2, #4 blocked by #1, #5 blocked by #3 and #4.

Note: Tasks #3 and #4 can run in parallel since they depend on different predecessors.

## Workflow

### Step 1 (Task #1): Select and Parse Plan

List recent plans from `~/.claude/plans/`:

```bash
ls -lt ~/.claude/plans/*.md
```

Read the first line of each to get titles. Present using `AskUserQuestion`:

```
Which plan do you want to trace?

- {plan-title-1} ({filename}, {date})
- {plan-title-2} ({filename}, {date})
- {plan-title-3} ({filename}, {date})
- Browse older plans / provide a custom path
```

If the user provides a path directly as an argument, skip this step.

Once selected, read the full plan and extract:

| Extract | How | Example |
|---|---|---|
| **Project paths** | Look for absolute paths starting with `/Users/`, `~/`, or relative paths with recognizable project names | `/Users/omar.eid/workspace/ceg-mcp` |
| **File paths** | Paths ending in extensions (`.py`, `.ts`, `.json`, `.md`, etc.) from code blocks, task descriptions, "Critical Files" tables | `scripts/calendar/cal.py` |
| **Task keywords** | Verbs and nouns from task titles and descriptions | "Add marketplace commands", "Fix CEG naming" |
| **Date references** | Any dates mentioned in the plan for time-bounding the search | Plan file mtime as baseline |
| **Branch references** | Branch names if mentioned | `feature/marketplace-commands` |

### Step 2 (Task #2): Identify Relevant Repos

From the extracted project paths and file paths, determine which git repos are involved.

**Strategy:**
1. If the plan contains absolute project paths, check if they're git repos:
   ```bash
   git -C {path} rev-parse --show-toplevel 2>/dev/null
   ```

2. If the plan references files without absolute paths, search known workspace directories:
   ```bash
   # Common workspace locations
   ls ~/workspace/
   ls ~/Library/CloudStorage/OneDrive-ServiceNow/workspace/
   ```

3. For each candidate repo, verify it exists and is a git repo.

Present discovered repos to the user with `AskUserQuestion`:

```
I found these repos that may be related to this plan:

- /Users/omar.eid/workspace/ceg-cli (matches: file paths in tasks 1-3)
- /Users/omar.eid/workspace/noteplan (matches: project path in context)

Are these correct? Should I add or remove any?

- These are correct, continue
- Add more repos (I'll provide paths)
- Remove some (I'll specify)
```

### Step 3 (Task #3): Search Git History

For each confirmed repo, search for related commits.

**3a. Determine time window**

Use the plan file's modification time as a reference point. Search from:
- **Start**: Plan file creation date (or mtime minus 7 days as buffer)
- **End**: Now (or a user-specified date)

```bash
# Get plan file dates
stat -f "%Sm" -t "%Y-%m-%d" {plan_file}
```

**3b. Search by file paths**

For files mentioned in the plan:
```bash
git -C {repo} log --oneline --after="{start_date}" -- {file_path_1} {file_path_2}
```

**3c. Search by keywords**

Extract key terms from the plan title and task descriptions:
```bash
git -C {repo} log --oneline --after="{start_date}" --grep="{keyword}" -i
```

**3d. Search by branch**

If the plan mentions a branch:
```bash
git -C {repo} log --oneline main..{branch}
```

**3e. Search for Co-Authored-By: Claude**

Plans executed with Claude Code will have commits with the co-author tag:
```bash
git -C {repo} log --oneline --after="{start_date}" --grep="Co-Authored-By: Claude"
```

**3f. Deduplicate and enrich**

Merge all commit results, deduplicate by hash, and get full details:
```bash
git -C {repo} log --format="%H|%h|%ai|%an|%s" {hash}
```

For each commit, also get the files changed:
```bash
git -C {repo} diff-tree --no-commit-id --name-only -r {hash}
```

### Step 4 (Task #4): Scan Claude Sessions

**4a. Find session indices for related projects**

For each repo identified in Step 2, find the corresponding session index:

```
# Encode the project path
/Users/omar.eid/workspace/ceg-cli
→ -Users-omar-eid-workspace-ceg-cli

# Check for session index
~/.claude/projects/-Users-omar-eid-workspace-ceg-cli/sessions-index.json
```

**4b. Filter sessions by time window**

Read each `sessions-index.json` and filter entries where:
- `created` or `modified` falls within the plan's time window
- `summary` or `firstPrompt` contains keywords from the plan

**4c. Search global history**

Read `~/.claude/history.jsonl` and find entries where:
- `project` matches one of the identified repos
- `timestamp` falls within the time window
- `display` (prompt text) contains plan keywords or references the plan file name

**4d. Extract session summaries**

For each matching session, extract:
- `sessionId`
- `firstPrompt` (what the user asked)
- `summary` (auto-generated summary)
- `created` / `modified` timestamps
- `messageCount`
- `gitBranch`

**4e. Optionally read session transcripts (ask first)**

Use `AskUserQuestion`:
```
I found {N} related Claude sessions. Want me to read the full transcripts
to extract more detail about what was discussed?

- Yes, read all transcripts (thorough but slower)
- Just the summaries (faster)
- Let me pick which sessions to read
```

If reading transcripts, scan the JSONL for:
- User messages referencing the plan
- Tool calls (especially file writes, git commands)
- Key decisions and discussions

### Step 5 (Task #5): Build Execution Trace

Compile everything into a structured report.

#### Output Format

```markdown
# Execution Trace: {plan-title}

**Plan file**: `{plan_file_path}`
**Plan created**: {date}
**Trace window**: {start_date} to {end_date}

---

## Repos Involved

| Repo | Path | Branch | Commits Found |
|---|---|---|---|
| {repo-name} | {path} | {branch} | {count} |

---

## Commit Timeline

| Date | Repo | Hash | Author | Message | Files Changed |
|---|---|---|---|---|---|
| {date} | {repo} | {short_hash} | {author} | {message} | {count} files |

### Commits by Task

**Task 1: {task-title}**
| Hash | Message | Files |
|---|---|---|
| {hash} | {message} | {files} |

**Task 2: {task-title}**
| Hash | Message | Files |
|---|---|---|
| {hash} | {message} | {files} |

*(Commits not clearly mapped to a task listed under "Unmatched Commits")*

---

## Claude Sessions

| Date | Session | Summary | Messages | Branch |
|---|---|---|---|---|
| {date} | {sessionId} | {summary} | {count} | {branch} |

### Session Details

**Session: {summary}** ({date})
- First prompt: "{firstPrompt}"
- Messages: {count}
- Key topics: {extracted topics}

---

## Coverage Analysis

### Plan Tasks vs Commits

| Task | Status | Related Commits | Notes |
|---|---|---|---|
| Task 1: {title} | {Implemented/Partial/No commits found} | {hashes} | {notes} |
| Task 2: {title} | {Implemented/Partial/No commits found} | {hashes} | {notes} |

### Files Planned vs Files Changed

| Planned File | Was Changed? | Commits |
|---|---|---|
| {file} | Yes/No | {hashes} |

### Unmatched Commits

Commits in the time window that may or may not be related:

| Hash | Message | Why included |
|---|---|---|
| {hash} | {message} | {reason: Co-Authored-By Claude / keyword match / same branch} |

---

## Summary

- **{N} commits** across **{M} repos** in the trace window
- **{X}/{Y} plan tasks** have matching commits
- **{P} Claude sessions** found related to this plan
- **Coverage**: {percentage}% of planned files have corresponding commits
```

After presenting the trace, use `AskUserQuestion`:

```
What would you like to do with this trace?

- Export as markdown file
- Generate a changelog from the commits (/plan-manager:plan-changelog) [coming soon]
- Inspect the plan quality (/plan-manager:inspect-plan)
- Trace another plan
- Done
```

## Matching Heuristics

Connecting commits to plan tasks is fuzzy. Use these heuristics:

1. **File path match** (strongest signal): If a commit touches a file mentioned in a plan task, associate it with that task
2. **Keyword match**: If a commit message contains keywords from a task title/description, associate it
3. **Time proximity**: Commits made shortly after the plan was created are more likely related
4. **Co-Authored-By: Claude**: Strong signal that the commit was made during a Claude Code session executing the plan
5. **Branch match**: If the plan mentions a branch and the commit is on that branch, strong association
6. **Session correlation**: If a commit hash appears in a Claude session transcript, and that session references the plan, strong association

When confidence is low, put the commit in "Unmatched Commits" rather than forcing a wrong association.

## Safety Checks

- **Read-only** - this skill never modifies any files, git history, or session data
- **No git operations that modify state** - only `git log`, `git diff-tree`, `git rev-parse`
- **Large repo handling** - limit git log searches with `--after` and `--max-count=200` to avoid slow queries
- **Large transcript handling** - read session transcripts with line limits; skip transcripts > 50MB
- **Path validation** - only read from `~/.claude/` and confirmed git repos

## Example Usage

```
User: /plan-manager:trace-plan

Claude: Let me find your recent plans...

Recent plans:
1. "Marketplace & Plugin Management Commands" (proud-foraging-starfish.md, Jan 12)
2. "Azure-Hosted MCP Server" (azure-mcp-server-plan.md, Jan 15)
3. "NotePlan Symlink Integration" (dapper-orbiting-petal.md, Jan 22)

Which plan do you want to trace?

User: 1

Claude: Reading proud-foraging-starfish.md...

Extracted from plan:
- Project: ceg-cli (/Users/omar.eid/workspace/ceg-cli)
- 6 tasks, 7 files referenced
- Keywords: marketplace, plugin, CEG naming

Found repos:
- /Users/omar.eid/workspace/ceg-cli (matches file paths)

Searching git history from Jan 12 to now...

# Execution Trace: Marketplace & Plugin Management Commands

## Commit Timeline

| Date | Hash | Author | Message | Files |
|---|---|---|---|---|
| Jan 12 | a1b2c3d | Omar Eid | Fix CEG naming to Customer Excellence Group | 4 files |
| Jan 12 | e4f5g6h | Omar Eid | Add marketplace config to settings | 1 file |
| Jan 13 | i7j8k9l | Omar Eid | Add ceg marketplace commands | 3 files |
| Jan 13 | m0n1o2p | Omar Eid | Add ceg plugins commands | 2 files |

## Claude Sessions

| Date | Summary | Messages |
|---|---|---|
| Jan 12 | CEG Naming Fix and Marketplace Setup | 24 |
| Jan 13 | Plugin Command Implementation | 18 |

## Coverage: 5/6 tasks have commits, 6/7 files changed (86%)
```

## Related Skills

- `/plan-manager:inspect-plan` - Analyze plan quality before tracing execution
- `/plan-manager:introduce` - Overview of all plan-manager capabilities
- `/plan-manager:plan-changelog` - Generate changelog from traced commits (coming soon)
