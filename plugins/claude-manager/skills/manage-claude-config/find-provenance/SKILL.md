---
name: find-provenance
description: Pin a claim, number, decision, or technique to the Claude Code transcript line that proves it, and cite it by session id, line, and timestamp. Use when someone asks "where did this come from", "which session decided this", "cite the transcript", "who wrote this number", "find the turn where I asked for X", or needs a verifiable citation into ~/.claude/projects instead of a paraphrase from memory.
---

# Find Provenance

Locate the transcript line that proves a claim and hand back coordinates, not a paraphrase.
`git blame` gives the commit; the transcript gives the conversation in which the thing was
decided, which is usually where a wrong number or an unsourced rule was born.

## When to use

- A test, doc, plan, or comment asserts something nobody can source, and the question is
  whether it was ever true.
- A technique, preference, or decision is being written up and needs a first-party citation
  rather than "I remember asking for this".
- A claim may have been drafted by a subagent and accepted without a check.
- A ledger or review log records "reviewed on <date>" and you need the turn that shows it.

Do not use it to reconstruct what changed: `git log` is faster and authoritative. Transcripts
answer why and who, not what.

## What the transcripts are

Every session for a working directory is appended to `~/.claude/projects/<slug>/<session>.jsonl`,
where the slug is the absolute path with every non-alphanumeric character replaced by `-`.
Subagent transcripts of a session sit under `<slug>/<session>/subagents/`. Timestamps are UTC.

The label on a hit decides what it proves:

| Label | Meaning |
|---|---|
| `human` | the person's own words: an ask, a correction, an approval |
| `assistant:tool_use:<Tool>` | that turn wrote the text (authorship) |
| `assistant:text` / `assistant:thinking` | Claude said or considered it |
| `user:tool_result` | a read-back: the text already existed on disk |
| `*:raw` | the text sits in an entry with no content blocks (queue operations, notifications) |

A read-back is not authorship. If nothing in the session wrote the text, a subagent probably
did: search the session with `--session`, which includes its subagents.

## Script

`scripts/transcript_grep.py` (python3, stdlib only). Run its selftest once after install:

```bash
python3 "<skill dir>/scripts/transcript_grep.py" --selftest
```

Search one session (main transcript plus subagents), only the person's turns:

```bash
python3 "<skill dir>/scripts/transcript_grep.py" --session <uuid> --find "exact substring" --human-only
```

Search every transcript of a repo, newest first:

```bash
python3 "<skill dir>/scripts/transcript_grep.py" --repo /path/to/repo --find "exact substring"
```

Each hit prints `file:line`, timestamp, label, and a short excerpt. `--limit` caps hits per
file, `--context` widens the excerpt. The HTML-escaped twin of the substring is searched too,
because plan text quoted back into a user turn arrives with `<` as `&lt;`.

## Workflow

Track with `TaskCreate` (one task: locate the proving line; a second: record the citation).

1. **Pick the substring.** Short, distinctive, no quotes or angle brackets. The person's own
   phrasing beats a paraphrase: "as a CEO, would you interview" finds the ask; "executive
   review" finds nothing.
2. **Search the narrowest scope first.** A known session with `--session`; otherwise the repo.
   Add `--human-only` when the claim is about what the person asked for or approved.
3. **Read the label.** Authorship, a read-back, or the person's words. If the answer is a
   read-back only, widen to the session's subagents or an earlier session.
4. **Confirm the line.** Open it with `sed -n '<line>p' <file> | cut -c1-400` and check the
   timestamp matches the one printed. Line numbers are stable for finished sessions; a live
   session only appends.
5. **Record coordinates, never text.** A citation is `session id + line + timestamp` (plus the
   repo). Transcripts hold whatever the session held, including pasted secrets and other
   people's names, so committed files carry the pointer and re-fetch the text on demand.

When several substrings all miss, use `AskUserQuestion` before guessing: offer the two or
three closest hits found and ask which turn the person means, or whether the claim came from
somewhere other than a session (a design chat, a document, a conversation off-record).

## Rules

- Never paste transcript text into a committed file; cite coordinates and re-fetch.
- A citation that cannot be re-found is a gap, not evidence. Say so in the record.
- Transcript timestamps are UTC; `git log` prints local time. Compare in one zone.
- Never edit, move, or delete a transcript from this skill. Moving belongs to `move-sessions`.
