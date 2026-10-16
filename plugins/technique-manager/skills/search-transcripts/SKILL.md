---
name: search-transcripts
description: Search the Claude Code transcripts on another Mac (the studio, by default) over SSH for words a technique mentions, copy the matching sessions into a temporary folder here, and cut short snippets around each match for analysis. Covers that Mac's ~/.claude/projects and the hub's backed-up session archive. Use when a technique's session isn't on this Mac, when a hub comment asks to "find the transcript", "search the studio for …", "what else did I say about …", or before research-backstory when the linked session is missing here.
---

# Search Transcripts on Another Mac

The sessions behind a technique often live on a different Mac from the one you're working on. You search them where they are, copy only the matches here, and read bounded snippets, never whole transcripts.

The copies are whole sessions and can hold anything (names, paths, secrets), so they stay in a **temporary folder**. Never put them in the hub repo, a spec, a context file or a post. What you learn from them goes into `context/<slug>.md` in your own words, the way `research-backstory` writes it.

## Paths

```bash
# The skill's own folder: use the "Base directory for this skill" line shown when the skill loads.
ST="<base directory of this skill>"
# Run from the hub (or pass --root) so it also searches the hub's backed-up sessions.
```

## Scripts: when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `remote_sessions.py search` | Lists the transcripts on the other Mac that hold every `--grep` text (one SSH call; nothing copied) | First, to see how many sessions match and how big they are | `python3 "$ST/scripts/remote_sessions.py" search --grep "<words>"` |
| `remote_sessions.py fetch` | The same search, then copies the matches here, newest first, up to `--max-mb` (200 by default) | Once the search looks right | `python3 "$ST/scripts/remote_sessions.py" fetch --grep "<words>"` |
| `remote_sessions.py snippets` | Cuts a window around each match (typed prompts, Claude's replies, tool calls and results) from copied files | To read what was said, without loading whole sessions | `python3 "$ST/scripts/remote_sessions.py" snippets --grep "<words>" <out folder>` |

In a hub, `make transcripts GREP="<words>"` runs `fetch` and then `snippets`.

## Where it searches

Paths are relative to the home folder on the other Mac:

- `.claude/projects`: every session Claude Code still keeps there. It deletes sessions after 30 days by default.
- `<backup dest>/archive/sessions`: the hub's backed-up copies (`hub.json` → `backup.dest`), when run in a hub. They outlive the deletion.

The Mac is `--host`, else `hub.json` → `transcripts.host`, else `backup.host`, else `host` in `~/.config/technique-manager/studio.json`. To search other folders, set `"transcripts": {"host": "...", "dirs": [...]}` in `hub.json`, or pass `--dir` (repeatable).

## Tasks

Create with `TaskCreate`: `Pick the words`, `Search`, `Fetch`, `Read snippets`, `Write it up`.

## Step 1: Pick the words

Use **distinctive** text: a phrase from the technique's `user_prompt` blocks, a file name, an error message, a command. Each `--grep` is fixed text, matched without regard to case, and a file must hold **all** of them (`--any` for one of them).

- **Typos:** specs fix the user's typos, but the transcript has the original. Prefer a short run of words that's likely to be spelled right ("over engineering infrastructure", not the whole sentence).
- **Narrowing:** add `--since YYYY-MM-DD` (files changed on or after that date) when a phrase is common. The spec's `source.taken` gives the date.

## Step 2: Search, then fetch

```bash
python3 "$ST/scripts/remote_sessions.py" search --grep "over engineering infrastructure"
python3 "$ST/scripts/remote_sessions.py" fetch  --grep "over engineering infrastructure"
```

- **No match:** that's often expected. A session older than 30 days that was never archived is gone. Say so, and fall back to what the spec and the screenshot show.
- **Many matches:** narrow with another `--grep` or `--since` before fetching. Sessions can be tens of MB each; `fetch` skips any past `--max-mb` and lists them under `skipped`.
- **Can't reach the host:** this sandbox may have no SSH keys. Ask the user to run the same command with `! python3 …`.
- **`fetch` output:** prints `out`, the temporary folder. Files keep their folders from the other Mac's home folder, so the `.claude/projects/<project>/` name tells you which repo a session ran in.

## Step 3: Read snippets

```bash
python3 "$ST/scripts/remote_sessions.py" snippets --grep "over engineering infrastructure" <out> [--chars 300] [--max 40]
```

Each snippet gives the session id, the line number, the time (UTC), who said it (`user`, `claude` or `tool`), the folder it ran in, and up to `--chars` either side of the match.

- **More context:** search again with words from a nearby snippet, or open the file at that line (`sed -n '<line>,+20p' <file>`), and still read in pieces.
- **Matching the screenshot:** a snippet's time converted to local time should be close to the spec's `source.taken`. That's how you know it's the right moment.

## Step 4: Use what you found

- **Back story:** write `context/<slug>.md` and suggest a focus through `research-backstory`, Steps 2–4. Quote at most a line or two, and apply the spec's replacements in your head: anything that will reach the post goes through the privacy scan there.
- **A comment asked:** reply in one line with what was found ("3 sessions match; the one at 12:44 on Oct 10 is the moment in the screenshot"), then resolve it.
- **Afterwards:** delete the temporary folder when the analysis is done (`rm -r <out>`).

## Output

```
Searched <host>: .claude/projects, git/technique-hub-files/archive/sessions
N sessions match "<words>" (fetched M, S MB, into <out>; skipped K over the limit)
<time> <role>: "<snippet>"   ← the 2–3 that matter
```
