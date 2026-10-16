---
name: research-backstory
description: Fetch the pre-context behind one technique in the technique hub — the session turns that led up to the screenshot, what came of it afterwards, the files it touched, the user's own commits around it, and related techniques — then write context/<slug>.md and suggest a focus and back story for the user to confirm by page comment. Use when a hub comment asks to "fetch what led here", "get the PR", "find the back story", or when a technique has no context yet.
---

# Research a Technique's Back Story

A screenshot shows the moment. What led to it lives in the session, and what came of it lives in git. You fetch both, write them up for the user, and **suggest**, never decide, what the post is about.

Works in a technique hub (`technique-manager:build-hub`). The context file is internal: it can hold real names, and it is never rendered into the post view, zipped or synced.

## Paths

```bash
# The skill's own folder: use the "Base directory for this skill" line shown when the skill loads.
RB="<base directory of this skill>"
# Run from the hub repo (or pass --root).
```

## Tasks

Create with `TaskCreate`: `Fetch excerpts`, `Write context`, `Suggest focus and back story`, `Re-render and reply`.

## Step 1: Fetch

```bash
python3 "$RB/scripts/fetch_context.py" --spec <slug>                       # all sources
python3 "$RB/scripts/fetch_context.py" --spec <slug> --sources git         # only what the comment asked for
```

| Source | What you get |
|---|---|
| `session-before` | Up to 40 user prompts and Claude replies leading to the screenshot's message, stopping at the previous compaction |
| `session-after` | What happened in the next 60 minutes (`--after-minutes`) |
| `files` | Files that Edit, Write or NotebookEdit touched in that window |
| `git` | The user's own commits in the session's folder, from 1 hour before to 2 hours after. CI and bot commits are left out unless there are no others (`"authors": "all authors"`) |
| `related` | Other techniques with the same mechanism |

**What it reads:**
- **Session:** the hub's archived copy first (`source.session.archived`), then the original, then the copy another Mac backed up (hub.json `"backup"`, `<dest>/archive/sessions/`). That last one is fetched into `$TMPDIR/technique-sessions/backup/`, never into the hub, and reused while it's there. Delete that folder when the research is done.
- **Excerpts:** every one is cut to 600 characters (`--max-chars`), so the whole output stays readable in one pass. Passwords, keys and tokens are hidden first (`recreate-technique/scripts/hide_secrets.py`), so a value pasted into the session shows as `[hidden <kind>]` and never reaches `context/<slug>.md`.
- **Notes:** a missing session or folder becomes a line in `notes`, not an error.
- **Session on another Mac:** when `notes` says the session is missing here (or the spec has no session), search the studio's transcripts with `/technique-manager:search-transcripts` (`make transcripts GREP="…"` in the hub) using words from the spec's prompt blocks, and write Step 2 from its snippets.

## Step 2: Write `context/<slug>.md`

Write five sections. Use what the excerpts show, and nothing they don't:

```markdown
# <technique title>: context

## What led here
<the problem, in 2–4 sentences, with the turns that show it>

## What happened after
<what the move produced: the hook added, the rule kept, the fix shipped>

## Changes
- <sha> <subject> (<stat>)   ← from git; link the PR if the remote is GitHub

## Touched files
- <path>

## Related
- <slug>: <why>
```

Real names are fine here, because the file is internal.

## Step 3: Suggest a focus and a back story

- **The focus:** one line saying what a reader should leave with. Make it about the *move*, not the project.
- **The back story:** 1–3 sentences of how it came up, written as it would read in the post.

**More than one plausible focus:** a screenshot often shows two moves. When the run came from the terminal rather than a page comment, use `AskUserQuestion` with the 2–3 candidates (the best first, marked Recommended). When it came from a comment, list them in the reply and suggest the first. Only one focus gets suggested.

Record both:

```bash
python3 "$RB/scripts/fetch_context.py" --spec <slug> --mark \
  --suggested-focus "<line>" --suggested-backstory "<text>"
```

`--mark` saves `context.file`, `fetched` and `sources`, plus the suggestions. Each suggestion is checked the way it would appear in the post, with the spec's replacements applied. **It refuses one the privacy scan flags.** When that happens, reword it or add a replacement (`recreate-technique` Step 3); never work around the scan. The scan can't recognize names of people, companies or products, so read your suggestion for those yourself.

A suggestion is never confirmed by you. The Post plan panel shows it as "Suggested, not confirmed". The user replies "yes" on it, and the hub's routing table then copies it into `focus.line` or `backstory`.

## Step 4: Re-render and reply

```bash
make hub SLUG=<slug>
```

When a page comment asked for this, reply on it in one line: what was found (for example "2 commits and the 12 turns before it; suggested a focus, see the Post plan"). Then resolve the thread.

## Output

```
<slug>: context/<slug>.md (before 20 · after 40 · files 8 · commits 2 · related 2)
Suggested focus: "<line>"   back story: "<text>"   (waiting for the user's yes)
```
