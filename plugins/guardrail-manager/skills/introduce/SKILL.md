---
name: introduce
description: Introduces the guardrail-manager plugin and routes the person to the right skill. Use when someone asks what this plugin does, how to get warned about other Claude Code sessions in the same checkout, how to add a "did the review step run" reminder to a repo, why a git -X ours/theirs command was denied, or which skill turns those guardrails on.
---

# Introduce Guardrail Manager

You are the `guardrail-manager` plugin. When this skill is invoked, explain what you do and why you
exist, then route the person to the right skill.

## What This Plugin Does

Guardrail Manager ships **advisory hooks that fire everywhere but do nothing until a repo opts in**
with a small conf file under `.claude/hooks/`, plus **one blocking guard that is on by default**.
It exists because three mistakes kept recurring and none is caught by a linter, a test, or CI:

1. **Several Claude Code sessions in one checkout.** They share uncommitted files, the index, and
   the current branch. One session switches branch, another commits on it. One session stages
   `git add -A` and ships the other's half-finished work. A `git restore .` wipes work that was never
   its own.
2. **A review step the session knew about and skipped.** The transcript shows the session touched
   sensitive content, a generated file, a data ledger, and the matching review or check never ran
   before the turn ended.
3. **A conflict resolved by taking one side.** `git merge -X theirs`, `git checkout --ours`,
   `-s ours`: one command, one side's work gone, and the log looks like a clean merge. In a shared
   checkout that side is usually another session's.

Four hooks, all Python 3 standard library, all exit 0. The first three only add context; the
fourth is the one that denies a tool call:

- **concurrent-session-guard** (SessionStart, UserPromptSubmit): counts other transcripts touched
  in the last N minutes under the same project directory, names each with its branch and age, and
  restates the shared-tree rules. Rate-limited so it repeats only when the count grows or a
  reminder interval passes. A git worktree has its own cwd and is correctly not flagged.
- **remind-commit-branch** (PreToolUse on Bash): before `git commit|merge|push|rebase|cherry-pick`,
  and only while another session is active, adds the current branch and the other sessions as
  context so the commit lands on the intended branch.
- **policy-review-reminder** (Stop): one INI section per policy. Fires when `SIGNAL_REGEX` matches
  the transcript and `DONE_REGEX` does not. Delivers the message on stderr, as a systemMessage, or
  as a block decision so Claude has to act on it once before stopping.
- **block-git-ours-theirs** (PreToolUse on Bash): returns `permissionDecision: deny` for any git
  invocation carrying `-X ours|theirs`, `--strategy-option=…`, `-s ours`, `--strategy ours`,
  `checkout|restore|merge-file --ours|--theirs`, or a `merge.<x>.driver` config — including
  inside `sh -c "…"`. `git diff --ours` stays allowed. **On with no conf at all**; opt a repo or
  the machine out with `git-conflicts.conf` `ENABLED=0`. The tenet it enforces: work every
  conflict by hand, both sides kept, gates re-run.
- **git-settings-guard** (SessionStart + PreToolUse on Bash): at session start, and before
  git commands (at most every ten minutes per problem), reports a checkout whose
  `core.bare` is true or whose `core.hooksPath` is absolute, outside the repo or missing, with
  the exact fix. It never changes the setting. It denies a `git config` that would set
  `core.bare true` or a repo `core.hooksPath` that is absolute, `~`, `$VAR` or `../`
  (`--global`/`--system` hooks folders are allowed). **On with no conf**; opt out with
  `git-settings.conf` `ENABLED=0`.

The plugin has two skills:

- **introduce**: this skill; discovery and routing.
- **configure-guardrails**: audit a repo for which guardrails apply, then write the conf files.

## How to Introduce Yourself

### Step 1: Explain

```
Guardrail Manager: advisory hooks for the mistakes tests never catch.

- Warns when other Claude Code sessions are active in this same checkout
- Restates the branch before a git commit or push while that is true
- Reminds about a review step the transcript shows this session skipped
- Denies git commands that resolve a conflict with -X ours/theirs, -s ours, checkout --ours/--theirs
- The reminders are silent until a repo opts in; the conflict guard is on by default; every hook has a selftest
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:

```
What do you want to set up?

- Warn me when another session shares this checkout   (configure-guardrails, concurrent-session)
- Remind me to run a review before I stop              (configure-guardrails, policy-review)
- Audit this repo and suggest which guardrails apply   (configure-guardrails, audit)
- Turn the session warning on for every repo at once   (configure-guardrails, global)
- Why was my git -X theirs denied, and how do I opt out (configure-guardrails, git-conflicts)
```

### Step 3: Guide to the Right Skill

| They want... | Skill | Command |
|---|---|---|
| Another session clobbered my work, stop that | configure-guardrails | `/guardrail-manager:configure-guardrails` |
| I committed on the wrong branch again | configure-guardrails | `/guardrail-manager:configure-guardrails` |
| Nag me to run the privacy review before publishing | configure-guardrails | `/guardrail-manager:configure-guardrails` |
| Remind me to run the boundary check after touching the ledger | configure-guardrails | `/guardrail-manager:configure-guardrails` |
| Which of these hooks should this repo have? | configure-guardrails | `/guardrail-manager:configure-guardrails` |
| My `git merge -X theirs` was denied | work the conflict by hand; opt out only via `git-conflicts.conf` | `/guardrail-manager:configure-guardrails` |
| Is the hook working? | run the selftest | `python3 <plugin>/hooks/<hook>.py --selftest` |

## Plugin Map

```
guardrail-manager (this plugin)
  ├── introduce            — this skill
  ├── configure-guardrails — audit a repo, write .claude/hooks/*.conf, verify with --selftest
  hooks/
    ├── concurrent-session-guard.py — SessionStart + UserPromptSubmit
    ├── remind-commit-branch.py     — PreToolUse (Bash)
    ├── policy-review-reminder.py   — Stop
    ├── block-git-ours-theirs.py    — PreToolUse (Bash), deny
    ├── git-settings-guard.py       — SessionStart + PreToolUse (Bash), report + deny
    ├── _conf.py      — KEY=value and INI loaders, repo conf with global fallback
    ├── _sessions.py  — other_active_sessions(): scan ~/.claude/projects/<slug>/
    └── _selftest.py  — subprocess harness used by every --selftest
  examples/
    ├── concurrent-session.conf
    ├── policy-review.conf
    └── git-conflicts.conf          — opt-out only; the guard needs no conf to run
```

## Requirements

- Python 3 (standard library only).
- Conf files live in `<repo>/.claude/hooks/`. `concurrent-session.conf` and `git-conflicts.conf`
  also honour a global fallback at `~/.claude/hooks/<name>`.
