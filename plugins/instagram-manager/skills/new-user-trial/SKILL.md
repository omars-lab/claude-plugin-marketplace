---
name: new-user-trial
description: Try this plugin the way a newcomer would, in a sandbox. One agent plays someone with years of Instagram saves who has never seen the plugin, and goes from "how do I even get my saves out?" through export, import, collections, tagging, caching media and the hub map, writing a diary of every step and every snag. A second agent re-runs the steps that matter, keeps only what it can reproduce, adds what the first missed and ranks fixes by value. Use when someone asks how easy the plugin is for other people, wants a usability or onboarding review, wants gaps found in its skills, scripts or pages, or before telling anyone else to use it. Never touches the real data repo, Instagram, Google or OpenStreetMap.
---

# New-user trial

The plugin was built by one person for their own saves, so every rough edge they already know
is invisible to them. This skill finds those edges by watching a newcomer use it.

Two agents, one after the other, in a throwaway sandbox:

1. **The tester** (`agents/new-user-tester.md`) plays a person from `personas.md`: someone with a
   lot of saves and some collections, who has never seen this plugin or its data repo. It starts
   from nothing (no config, no Makefile, no data folder) and tries to get from "I have saves on
   Instagram" to "I can see them on a map, sorted". It writes a diary: each step, the exact command,
   what it expected, what happened, how long it took, where it looked for help.
2. **The reviewer** (`agents/trial-reviewer.md`) reads the diary, re-runs the steps that carry
   a finding in the same sandbox, and marks each finding confirmed, not reproduced, or not
   checkable. It adds the gaps the tester never reached, judges each against
   `review-rubric.md`, and ends with a table of fixes ranked by value for the effort.

The main session then turns each confirmed fix into a task.

## The sandbox

`scripts/make_sandbox.py` builds it in a new folder:

| Path | What |
|---|---|
| `downloads/instagram-example_wanderer-…zip` | An invented export in Instagram's HTML shape: 35 saved posts, one save only in a collection, 8 collections (two with the same name), and messages, likes and account files the importer must never open |
| `home/` | Empty. The newcomer's data folder (`INSTAGRAM_HOME`) |
| `media/` | Empty. The media folder (`INSTAGRAM_MEDIA_DIR`) |
| `shots/` | Screenshots of the sandbox hub |
| `run` | Runs one command inside the sandbox: sets the two folders, `INSTAGRAM_OFFLINE=1` and the map answers, then runs from `home/` |
| `.harness/geocode.json` | OpenStreetMap-shaped answers for the invented places, so pins land with no network |

Every name in it is invented: the state of Westmark and its towns, cafés, trails and creators.
The saves are awkward the way real ones are: a list naming five cafés, a place only in a hashtag,
a caption in Spanish, one with no caption, a giveaway, a recipe carrying a town's hashtag, a save
in two collections.

**`INSTAGRAM_OFFLINE=1`** (`shared/scripts/home.py` `offline()`) is what keeps the trial off the
network: map lookups answer from the fixture file only, and fetch-media and find-google-ids refuse
to start. Every plugin command the tester runs goes through `<sandbox>/run`; without it, scripts
fall back to the default data folder (`~/Workspace/git/instagram`) and would write there.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/make_sandbox.py` | Makes a sandbox folder: the invented export, empty home and media folders, the `run` wrapper and the offline map answers | Before each trial; one new folder per trial, so no earlier trial is overwritten | `python3 <plugin>/skills/new-user-trial/scripts/make_sandbox.py --out <sandbox>` (`--saves 15` for a short trial) |
| `scripts/shot.mjs` | Serves a folder on 127.0.0.1 on a port it picks, screenshots one page, stops | When the tester or reviewer wants to see a hub page the sandbox built; `--fill <selector> --text <words>` types into a filter or search box first, to see it at work | `node <plugin>/skills/new-user-trial/scripts/shot.mjs --root <sandbox>/home/.cache/hub --page / --out <sandbox>/shots/map.png --playwright <playwright-core dir>` (add `--full` for the whole page, `--fill "#tq" --text pasta` on a topic page) |

`shot.mjs` needs `playwright-core` (pass `--playwright <dir>` or set `PLAYWRIGHT_CORE`) and Chrome.
With no network the map tiles stay grey; pins, lists and links still show.

## Steps

1. **Pick the persona.** Read `personas.md` and pick one (the trip planner unless asked otherwise).
   Note today's date. The agents write their reports inside the sandbox (`diary.md`,
   `review.md`), so neither ever touches the data repo; step 8 copies them in.
2. **Note the real data repo's state.** Run `git -C <data repo> status --short` and keep the
   output. The trial must leave it exactly the same.
3. **Make the sandbox.** Run `make_sandbox.py --out <scratch>/trial-<date>-<persona>`. Use the
   session's scratch folder, never the data repo.
4. **Start the tester.** One agent, `instagram-manager:new-user-tester` (if that type is not listed
   yet because the plugin was not reloaded, start a `general-purpose` agent with model sonnet and
   the prompt "Follow `<plugin>/agents/new-user-tester.md` exactly", then the details below).
   Give it: the plugin folder, the sandbox folder, the persona's name, the diary's path
   (`<sandbox>/diary.md`) and the playwright-core folder.
   Do not give it the data repo's own docs, Makefile or CLAUDE.md; a newcomer has none of them.
5. **Start the reviewer** when the tester is done. One agent, `instagram-manager:trial-reviewer`
   (or `general-purpose`, model opus, "Follow `<plugin>/agents/trial-reviewer.md` exactly").
   Give it the same plugin and sandbox folders, the diary's path, and the review's path
   (`<sandbox>/review.md`). It works in the same sandbox, so do not delete it in between.
6. **Check nothing leaked.** Run `git -C <data repo> status --short` again; it must match step 2
   (another session's running job may have changed its own files; check any difference is theirs).
   Look at `<sandbox>/home/` to see what the trial made.
7. **Read both reports yourself,** then open one task per confirmed fix, in the review's ROI order,
   each naming the finding and the file to change. Leave "not reproduced" findings as they are.
8. **Copy the two reports** to `<data repo>/docs/user-trials/<date>-<persona>/` and commit them
   by name. Screenshots stay in the sandbox; they never go into git.
9. **Report in plain words:** the persona, how far the newcomer got, the three fixes worth most,
   and where the diary and review are.

## Rules

- **The sandbox only.** The tester and reviewer read the plugin folder and the sandbox. They never
  read the real data repo (its config, data, docs, `.cache` or Makefile), never the real export
  in `~/Downloads`, and pass the sandbox zip by path (`--from-zip`), because `make import` picks
  the newest real export.
- **No network for the plugin.** Every plugin command goes through `<sandbox>/run`. Fetching from
  Instagram, Google lookups and OpenStreetMap lookups are written in the diary as "not tried, and
  why", never run. Viewing a hub page loads Leaflet and map tiles from the internet in the browser;
  that is fine.
- **No model calls from scripts.** Where a step needs a model (tagging, splitting, finding spots),
  the tester follows that agent's file itself on one batch, since a subagent cannot start agents.
  It notes that a newcomer would need Claude Code to start those agents.
- **No servers on the shared ports.** `shot.mjs` picks its own port. Never start anything on 8765
  to 8769 or 8780.
- **Invented names only** in the plugin. The reports live in the private data repo and may name
  plugin files, never real saves.

## Files next to this one

| File | What it is | Who reads it |
|---|---|---|
| `personas.md` | Who the tester plays: what they saved, what they want, what they know | The tester, at the start |
| `review-rubric.md` | How bad each kind of snag is, what counts as confirmed, the ROI table | The reviewer; the tester for the severity words |
