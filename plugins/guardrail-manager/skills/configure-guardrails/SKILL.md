---
name: configure-guardrails
description: Audits a repository for which guardrail-manager hooks apply and writes the opt-in conf files (concurrent-session.conf, policy-review.conf) under .claude/hooks, then proves each hook with its selftest. Use when someone says "warn me when another session is in this checkout", "remind me to run the privacy review before I stop", "I keep committing on the wrong branch", "add a stop reminder for <check>", or asks which guardrails a repo should have. For an explanation of the plugin rather than a setup, use introduce.
---

# Configure Guardrails

Turn the guardrail-manager hooks on for a repo, or for the whole machine, by writing the conf
files they read. The hooks are already wired on their events by the plugin; nothing fires until a
conf exists.

## Modes

Decide the mode from what the person said. If it is unclear, use `AskUserQuestion`:

```
What should I set up?

- Audit: read this repo and tell me which guardrails apply   (AUDIT)
- Concurrent-session warning for this repo                    (CONFIGURE concurrent-session)
- Concurrent-session warning for every repo on this machine  (CONFIGURE global)
- A "review step skipped" reminder                            (CONFIGURE policy-review)
```

Track the work with `TaskCreate` (one task per conf file written, plus one VERIFY task) and mark
each `completed` only after its selftest passes and the VERIFY probe below shows the hook firing.

## AUDIT

1. Note the repo root and whether `.claude/hooks/` exists.
2. Concurrent sessions: list `~/.claude/projects/<slug>/*.jsonl` for this repo's slug (the cwd
   with `/` replaced by `-`). Two or more files touched in the last day means several sessions
   use this checkout and `concurrent-session.conf` applies.
3. Policy reviews: look for review steps that exist as a skill, Makefile target, or script but
   are not enforced by a hook or CI. Signals worth a policy: content that ships publicly
   (privacy or role review), generated files that must be rebuilt, data files with an invariant
   checked by a script, anything a CLAUDE.md says "always run before ...".
4. Existing hooks: read `.claude/settings.json` Stop hooks. A repo-local "reminder" script that
   greps the transcript is a policy-review candidate; port it and remove the local script.
5. Report a table: guardrail, evidence, recommended conf, and ask which to write.

## CONFIGURE concurrent-session

Write `<repo>/.claude/hooks/concurrent-session.conf` from the plugin's
`examples/concurrent-session.conf`. Defaults are right for most repos:

```
ENABLED=1
ACTIVE_WINDOW_MIN=10
REMIND_EVERY_MIN=30
COMMIT_REMINDER=1
INCLUDE_SUBDIR_SESSIONS=1
```

For **global**, write the same file to `~/.claude/hooks/concurrent-session.conf`. A repo conf
overrides the global one, so a repo can set `ENABLED=0` to opt out.

Then run:

```
python3 "<plugin root>/hooks/concurrent-session-guard.py" --selftest
python3 "<plugin root>/hooks/remind-commit-branch.py" --selftest
python3 "<plugin root>/hooks/block-git-ours-theirs.py" --selftest
```

To see it live, open a second session in the same checkout and send a prompt: the first
prompt after the second session appears prints the warning.

## CONFIGURE policy-review

Write `<repo>/.claude/hooks/policy-review.conf`, one section per policy:

```
[<name>]
SIGNAL_REGEX = <what the transcript contains when the policy is in play>
DONE_REGEX   = <what the transcript contains when the review already ran>
MESSAGE      = <what to say; indented continuation lines allowed>
# optional: MESSAGE_FILE = docs/<file>.md   CHANNEL = stderr|system|block   ENABLED = 0
```

Writing good regexes:

- Signal broad, done narrow. A false reminder costs a line; a missed one costs the incident.
- Test both against the current transcript: `grep -ciE '<regex>' "$transcript_path"`.
- `DONE_REGEX` should match the review's own vocabulary (the skill name, the make target,
  a phrase only its output contains), not something the person might type casually.
- Pick `CHANNEL = block` only when Claude, not the person, is the one who must act, since it
  re-enters the turn once.

Then run `python3 "<plugin root>/hooks/policy-review-reminder.py" --selftest`, and confirm the
conf parses:

```
python3 -c "import configparser,sys; p=configparser.ConfigParser(interpolation=None); p.optionxform=str; p.read('.claude/hooks/policy-review.conf'); print(p.sections())"
```

## VERIFY: prove the hook fires where it is installed

A green `--selftest` proves the script works with a hand-built payload. It does not prove the
plugin is enabled for this repo, that the conf is where the hook looks, or that the event is
wired. Prove that with a throwaway headless session from the configured repo, then read what
the hook wrote. Track it as its own task; the conf task is not complete until this passes.

1. Run a one-purpose probe whose whole instruction is one harmless command:

   ```
   cd <repo> && claude -p "run: echo probe" --max-turns 1
   ```

   For `remind-commit-branch` (PreToolUse, Bash) the command must match the commit regex
   without changing anything: `claude -p "run: git commit --dry-run" --max-turns 1`. Both
   session hooks only speak when another session is active in the same checkout, so keep an
   interactive session open there while the probe runs, or expect silence.

2. Find the probe transcript: `ls -t ~/.claude/projects/<slug>/*.jsonl | head -1`, where the
   slug is the repo's absolute path with every non-alphanumeric character replaced by `-`.

3. Read the hook entries. Every hook that produced output is stored as a line whose
   `attachment.type` is `hook_success`, with `hookEvent`, `stdout`, and `stderr`:

   ```
   python3 -c "import json,sys
   for n,l in enumerate(open(sys.argv[1]),1):
       a=json.loads(l).get('attachment') or {}
       if a.get('type','').startswith('hook'): print(n,a.get('hookEvent'),repr(a.get('stdout','')[:120]),repr(a.get('stderr','')[:120]))" "<transcript>"
   ```

   A firing hook looks like: a `UserPromptSubmit` or `SessionStart` entry whose `stdout`
   starts with `[concurrent-session-guard]`; a `Stop` entry whose `stderr` starts with
   `[policy-review:<section>]` (or `stdout` holding `{"systemMessage": ...}` for
   `CHANNEL = system`); a `PreToolUse` entry whose `stdout` is the `additionalContext` JSON.

   Silence looks like: no entry for that event at all. A quiet hook leaves nothing in the
   transcript, so distinguish "ran and had nothing to say" from "never ran" with the side
   effect below.

4. Check the guard's marker, which the session hooks write even when quiet:

   ```
   cat "${TMPDIR:-/tmp}/guardrail-session-<probe session id>"
   ```

   The file holds the count of other sessions seen (`0` when alone). Present means the hook
   ran with a conf it could read; absent means the plugin is not enabled here, the conf is
   missing or `ENABLED=0`, or the event is not wired. `claude --debug` prints which hooks
   were registered.

5. For a policy review, the probe transcript has to contain the signal for the hook to fire.
   Put the signal phrase in the probe instruction (`claude -p "say: <signal phrase>, then
   stop" --max-turns 1`) and expect the `[policy-review:<section>]` stderr line; a second
   probe that also contains the done phrase must be silent.

## Porting an existing repo-local reminder hook

When a repo already has a Stop hook that greps the transcript for a signal and a done marker:

1. Copy its two regexes and its message into a section of `policy-review.conf` unchanged.
2. Remove the script's entry from `.claude/settings.json` and delete the script, plus any
   helper only it used.
3. Make sure the plugin is enabled for the repo (`enabledPlugins` in the repo's settings, or
   installed globally).
4. Run the selftest and, if the old script had one, keep its cases as a comment in the conf.

## Rules

- Never edit the plugin's hooks to special-case a repo; the conf is the extension point.
- Never set `permissionDecision` or exit 2 in the advisory hooks; they are advisory by design.
  `block-git-ours-theirs` is the one deliberate deny: it needs no conf, and the only knob is
  `git-conflicts.conf` with `ENABLED=0` (repo, or `~/.claude/hooks/` for the machine). Do not
  write that file to get past a conflict — resolve the conflict by hand instead.
- Conf files are committed with the repo so every clone gets the same guardrails.
