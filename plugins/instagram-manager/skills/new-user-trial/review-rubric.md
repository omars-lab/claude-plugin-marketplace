# Review rubric

Both agents use these words. The reviewer judges every finding against them.

## How bad a snag is

| Severity | Means | Example |
|---|---|---|
| **blocker** | A newcomer cannot go on without reading source code or asking someone | A step needs a config file that no doc says how to write |
| **major** | They can go on, but only after a long detour, a guess, or a wrong turn that costs data or trust | An error names a file that does not exist; a command silently does nothing |
| **minor** | It works, but is confusing, slow, or reads in insider words | A message says "the share overlay" or a ledger id with no explanation |
| **polish** | Small, nice to fix | A heading that could be clearer, a missing example |
| **good** | Worth keeping as is; say so, so it survives the next rewrite | A dry run that showed exactly what would change |

## What to look at

Group findings under these. A finding can sit under two; pick the one where the fix would go.

1. **Getting the export.** Does anything say how to request the download from Instagram, which
   format to pick (HTML or JSON), how long it takes, and what to do with the zip?
2. **Setting up.** Where does the data live, what files must exist first (topics, collections,
   a Makefile), and does anything make them? Can a newcomer start with no folder at all?
3. **Importing.** Does the import say what it found, and does it stay out of messages and likes?
4. **Organizing.** Collections to topics and places: is it clear what to write, with an example?
5. **Tagging and splitting.** Is it clear that Claude Code starts agents for this, how many, how
   long, what it costs, and how to resume after stopping?
6. **Caching media.** Thumbnails and videos: is it clear it fetches logged out, slowly, with
   pauses, and why? Does offline mode say what it skipped?
7. **The map and pages.** Does the hub open, do pins land, are the pages clear to someone who did
   not build them? Look at the screenshots.
8. **Docs and skills.** Does each skill's description say when to use it? Do the README and
   the introduce skill match what exists? Are there stale lines ("coming", old names)?
9. **Trust and safety.** Does anything say plainly what is never touched (login, messages, posting)?
   A newcomer worried about their account should find that in the first page they read.

## Confirmed or not

- **confirmed:** you re-ran the step (same command, same sandbox) or opened the same file and saw
  the same thing. Quote the output or the line.
- **not reproduced:** you ran it and it worked. Say what you ran. The tester may have mistyped;
  if the docs led them to mistype, that is a finding of its own.
- **couldn't check:** it needs the network, a real account, or time the trial does not have.
  Say what it would take.

A finding resting only on the tester's word, with no command or file to show, is never confirmed.

## The ROI table

End the review with every confirmed fix in one table, highest value per effort first:

| # | Fix (what to change, in plain words) | Where (file) | Severity | Effort (S / M / L) | Why it is worth it |
|---|---|---|---|---|---|

- **S** is under an hour (a doc line, a message, a flag). **M** is half a day (a new script mode,
  a new doc page). **L** is more (a new skill, a setup wizard).
- A blocker beats everything below it at the same effort. A fix that clears several findings at
  once (one setup command that writes every missing file) ranks above the separate fixes.
- When the same kind of snag keeps coming back (every error message says the wrong thing), name
  the one fix that clears the kind, not each case.
