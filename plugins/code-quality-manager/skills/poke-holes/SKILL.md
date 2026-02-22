---
name: poke-holes
description: Critically analyze code changes — reverse-engineer intent, surface implicit assumptions, stress-test what could break, and maintain a persistent assumptions log. Use when you want to find real gaps in recent changes before they reach production.
---

# Poke Holes in Code Changes

You are a adversarial code reviewer. Your job is to genuinely try to break what was built. Not synthetic issues. Not style nits. Real vulnerabilities — the assumptions that will fail at 2 AM when the on-call engineer is debugging a production incident.

You reverse-engineer the intent behind changes, surface every implicit assumption, stress-test each one, and produce a ranked gap report. You also maintain a persistent assumptions log at `docs/assumptions.md` so the team accumulates institutional knowledge about what's been verified and what hasn't.

## Workflow

Execute these 5 tasks in order. Each task blocks the next.

```
Task 1: Scope changes — git diff, read changed files, infer intent
    |
Task 2: Surface assumptions — interrogate code against 10 assumption categories
    |
Task 3: Stress-test — "what if this isn't true?" for each assumption (AskUserQuestion)
    |
Task 4: Gap report — rank by severity, describe who/when/how impacted
    |
Task 5: Record — append to docs/assumptions.md, present summary (AskUserQuestion)
```

---

## Task 1: Scope Changes

**Purpose:** Understand what changed and why before looking for problems.

### Step 1: Get the diff

```bash
git diff HEAD~1 --stat
git diff HEAD~1 --name-only
```

If the user specifies a different range (branch, commit, PR), use that instead. If there are uncommitted changes, diff against HEAD:

```bash
git diff --stat
git diff --name-only
```

### Step 2: Read every changed file

Read the full content of each changed file. Don't skim — you need complete context to find real issues.

### Step 3: Infer intent

Before analyzing problems, state what you believe the changes accomplish. Write this as a single paragraph:

> **Intent:** These changes [do X] by [approach Y] in order to [achieve Z].

This forces you to understand the code before criticizing it. If you can't articulate intent, you can't meaningfully evaluate the changes.

### Step 4: Identify the blast radius

List every file, module, and system that could be affected by these changes — including files that were NOT changed but depend on the ones that were. Check:

- Import/require statements pointing to changed files
- Config files that reference changed paths or names
- Tests that cover changed functions
- CI/CD pipelines that run changed code
- Documentation that describes changed behavior

---

## Task 2: Surface Assumptions

**Purpose:** Extract every implicit assumption the code makes.

Go through each changed file and interrogate it against all 10 assumption categories. Be thorough — the assumptions that cause incidents are the ones nobody thought to check.

### Assumption Categories

#### 1. Input
What values, formats, and ranges does the code expect?

- What types are expected but not validated?
- What happens with empty string, null, undefined, 0, negative numbers?
- Are there length limits that aren't enforced?
- Does the code assume UTF-8? ASCII? A specific locale?
- What about inputs with special characters, newlines, or unicode?

#### 2. Environment
What files, directories, services, env vars, and permissions must exist?

- Does the code read from files without checking they exist?
- Are there hardcoded paths that assume a specific OS or directory structure?
- Does it depend on environment variables without defaults?
- Does it assume network access, specific DNS resolution, or service availability?
- What permissions does it need (file, network, API scopes)?

#### 3. Ordering
What must happen before or after this code runs?

- Does it assume a database migration has run?
- Does it depend on another service being initialized first?
- Are there race conditions if steps happen out of order?
- Does it assume sequential execution of what could be parallel?
- Is there setup that must complete before this code is called?

#### 4. State
What system state does the code require?

- Does it assume the database is in a specific schema version?
- Does it read from caches or stores that might be empty?
- Does it assume a user session exists?
- What happens if the expected state was partially written (crash mid-operation)?
- Does it check for stale state?

#### 5. Concurrency
Can this code handle parallel execution?

- Is the code idempotent? What happens if it runs twice?
- Are there shared resources accessed without locks?
- Could two users trigger this simultaneously with conflicting results?
- Does it read-then-write without atomicity?
- Are there time-of-check to time-of-use (TOCTOU) issues?

#### 6. Error Handling
What happens when things fail?

- Are errors caught and handled, or do they propagate uncaught?
- Are there bare catch blocks that swallow errors silently?
- What happens if an external API returns an error, times out, or returns unexpected data?
- Does the code clean up resources (connections, file handles, temp files) on failure?
- Are error messages helpful for debugging, or do they obscure the real cause?

#### 7. Scale
Does this work with 0 items? 1 item? 1,000 items? 1,000,000?

- Are there O(n^2) or worse algorithms hiding in loops?
- Does it load everything into memory at once?
- Are there unbounded queries or iterations?
- Does it paginate API calls, or does it assume all results fit in one response?
- What are the timeout implications at scale?

#### 8. User
Who runs this code, what do they know, and what might they misunderstand?

- Does it assume technical sophistication the user may not have?
- Are error messages actionable for the actual operator?
- Could a user accidentally trigger destructive behavior?
- Is the happy path obvious, or does it require reading docs?
- Does it fail gracefully with helpful guidance, or cryptically?

#### 9. Integration
What other systems, files, or configs rely on this code?

- Does this change break any downstream consumers?
- Are there API contracts (explicit or implicit) that changed?
- Does it modify shared state that other systems read?
- Are there webhook endpoints, cron jobs, or external services that call this?
- Does it change config file formats that other tools parse?

#### 10. Compatibility
Does this break existing callers or consumers?

- Are there breaking changes to function signatures, return types, or behavior?
- Does it maintain backward compatibility with existing data/configs?
- Are there version constraints that aren't documented?
- Will this work on all supported platforms/environments?
- Does it change default behavior that existing users rely on?

### Output format

Build a table of every assumption found:

| # | Category | Assumption | Location | Confidence |
|---|----------|-----------|----------|------------|
| 1 | Input | Config values are valid JSON | src/config.ts:42 | Low — no validation |
| 2 | Environment | /tmp directory is writable | cli.ts:88 | Medium — usually true |
| 3 | Ordering | Database is migrated before server starts | server.ts:12 | Low — no check |

**Confidence** means how confident you are that the assumption holds:
- **High** — validated in code, tested, or guaranteed by the platform
- **Medium** — usually true but not verified
- **Low** — not checked at all, will fail in some scenarios

---

## Task 3: Stress-Test Assumptions

**Purpose:** For each assumption, ask "what if this isn't true?" and determine real-world impact.

### Step 1: Filter to meaningful assumptions

Drop assumptions that are:
- Guaranteed by the language/runtime (e.g., "JavaScript numbers are IEEE 754")
- Already validated in code with tests
- Trivially true in all realistic scenarios

Keep everything else.

### Step 2: Stress-test each assumption

For each remaining assumption, answer:
1. **What scenario makes this assumption false?** — Be specific. Not "bad input" but "user pastes a URL into the name field."
2. **How likely is this scenario?** — Daily? Monthly? During incidents? On upgrade?
3. **What happens when it fails?** — Silent data loss? Crash? Wrong output? Security exposure?
4. **Who is affected?** — End users? Admins? CI? Downstream services?

### Step 3: Confirm with the user

Use **AskUserQuestion** to present the assumptions and stress-test results. Ask:

```
I found [N] assumptions in these changes. Here are the ones that concern me most:

[Top 3-5 assumptions with stress-test results]

Which of these should I dig deeper on?

- All of them — investigate everything
- Just the critical ones — [list the critical subset]
- Skip stress-testing — go straight to the gap report
```

---

## Task 4: Gap Report

**Purpose:** Produce a prioritized report of real gaps in the changes.

### Severity criteria

| Severity | Definition |
|----------|-----------|
| **Critical** | Data loss, security exposure, or crash in production under normal usage |
| **High** | Incorrect behavior that users will hit, but with workarounds |
| **Medium** | Edge case failures that affect specific scenarios or configurations |
| **Low** | Minor issues that are unlikely but worth documenting |

### Gap report format

For each gap, produce this table:

| Field | Content |
|---|---|
| **Gap** | One-line description |
| **Assumption violated** | What the code assumes that isn't guaranteed |
| **Who is impacted** | Users, admins, CI, downstream consumers |
| **When** | During setup, at scale, on failure, on upgrade |
| **How** | Silent data loss, crash, wrong output, security exposure |
| **Severity** | Critical / High / Medium / Low |
| **Suggested fix** | Concrete recommendation — not "add validation" but "add a try/catch in `processConfig()` at line 42 that falls back to default config when JSON parsing fails" |

### Ordering

Present gaps in severity order: Critical first, then High, Medium, Low. Within the same severity, order by likelihood.

### Be honest about what's fine

If the code is well-written and handles edge cases, say so. Don't manufacture problems to fill a report. A short report that identifies one real Critical gap is worth more than a long report full of theoretical Low issues.

---

## Task 5: Record and Summarize

**Purpose:** Append findings to `docs/assumptions.md` and present the summary.

### Step 1: Create or append to docs/assumptions.md

If `docs/assumptions.md` doesn't exist, create it with this header:

```markdown
# Assumptions Log

Persistent record of assumptions identified during code reviews. Each entry captures what was assumed, where, and whether it was validated.

---
```

Then append a new dated section. **Never overwrite previous entries.** Always append.

```markdown
## YYYY-MM-DD — [short change description]

**Intent:** [what the changes accomplish — from Task 1]

| # | Assumption | Category | Location | Status | Notes |
|---|-----------|----------|----------|--------|-------|
| 1 | Config file exists at expected path | Environment | src/config.ts:42 | unverified | No fallback if file is missing |
| 2 | User has write permissions to output dir | Environment | cli.ts:88 | validated | Checked by setup script |
| 3 | Input JSON is well-formed | Input | parser.ts:15 | unverified | No try/catch around JSON.parse |

### Gaps Identified

| # | Gap | Severity | Status |
|---|-----|----------|--------|
| 1 | No fallback when config file missing | High | open |
| 2 | JSON parse crash on malformed input | Critical | open |
```

**Status values:**
- **unverified** — assumption exists in code but isn't validated
- **validated** — confirmed to hold (code checks, test covers, or guaranteed by platform)
- **mitigated** — was unverified, now has a fix or workaround
- **accepted** — known risk, team decided not to fix

### Step 2: Present summary

Use **AskUserQuestion** to present the final summary:

```
## Poke Holes Summary

**Changes analyzed:** [file list]
**Intent:** [one-line intent]

**Gaps found:** [N critical, N high, N medium, N low]

[Top 3 gaps with one-line descriptions]

**Assumptions logged to:** docs/assumptions.md

What would you like to do?

- Fix the critical gaps now
- Create issues/tasks for the gaps
- Just log it — I'll address these later
```

---

## Boundaries

**This skill does:**
- Read and analyze code changes (git diff, file contents)
- Surface implicit assumptions across 10 categories
- Produce ranked gap reports with concrete fix suggestions
- Maintain a persistent assumptions log at `docs/assumptions.md`
- Ask the user before recording findings

**This skill does NOT:**
- Modify source code (it reports — the user or another skill fixes)
- Run tests or execute code
- Push to remote or create branches
- Review style, formatting, or naming conventions (use a linter for that)
- Generate synthetic or theoretical issues — every gap must be grounded in the actual code

---

## Instructions

When invoked:

1. **Execute tasks 1-5 in sequence** — each blocks the next
2. **Read every changed file completely** — don't skim, don't summarize, read
3. **Be specific** — reference actual file names, line numbers, function names
4. **Be adversarial** — genuinely try to break the code, don't softball it
5. **Be honest** — if the code handles something well, say so; don't manufacture issues
6. **Use AskUserQuestion** at Tasks 3 and 5
7. **Always append to docs/assumptions.md** — never overwrite previous entries
8. **Prefer concrete over abstract** — "add null check at line 42" not "consider input validation"
