---
name: new-user-trial
description: Try this plugin the way a newcomer would, in a sandbox. One agent plays someone with years of Instagram saves who has never seen the plugin, and goes from "how do I even get my saves out?" through export, import, collections, tagging, caching media and the hub map, writing a diary of every step and every snag. A second agent re-runs the steps that matter, keeps only what it can reproduce, adds what the first missed and ranks fixes by value. Ends with the review as a doc in Obsidian, screenshots and map thumbnails shown in place, that the person comments on with review-md. Use when someone asks how easy the plugin is for other people, wants a usability or onboarding review, wants gaps found in its skills, scripts or pages, or before telling anyone else to use it. Never touches the real data repo, Instagram, Google or OpenStreetMap.
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
| `scripts/shot.mjs --clip <selector>` / `--list <jobs.json>` | One part of a page (`--clip "#mini"`: the small map on a place or post page); `--list` takes many pictures with one browser | `--clip` for a finding about one element; `--list` is what review_doc.py uses for the map thumbnails | `node … shot.mjs --root <hub> --page /posts/<code>.html --clip "#mini" --out <png>` |
| `scripts/review_doc.py` | Copies the diary and review into the data repo with every picture shown in place, and ends the review with a map thumbnail per place and post page, so nothing needs a link opened. The pictures go to the media folder, never git | Step 8, from the main session (not through the sandbox's `run`) | `python3 <plugin>/skills/new-user-trial/scripts/review_doc.py --sandbox <sandbox> --out <data repo>/docs/user-trials/<date>-<persona> --media <media folder>/user-trials/<date>-<persona> --playwright <dir>` (`--no-maps`, `--max-maps 20`) |
| `scripts/test_new_user_trial.py` | Offline tests: the sandbox, the starter config, review_doc.py's pictures and post names | After any change to this skill's scripts | `python3 <plugin>/skills/new-user-trial/scripts/test_new_user_trial.py` |

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
8. **Make the review doc** with `review_doc.py` (command in the table above). It writes
   `diary.md` and `review.md` into `<data repo>/docs/user-trials/<date>-<persona>/` with the
   screenshots shown in place and a map thumbnail per place and post page at the end, and
   copies the pictures to `<media folder>/user-trials/<date>-<persona>/`. The docs point at
   them with `file:///` links: they show on this Mac, and no picture goes into git. Check one
   map thumbnail by eye (read the PNG) before going on.
9. **Open it in Obsidian for comments** (see "Comments in Obsidian" below), leave one comment
   to prove the round trip, then commit the two docs and the comments file
   (`.review.comments.md`) by name.
10. **Report in plain words:** the persona, how far the newcomer got, the three fixes worth most,
    and the `obsidian://open?path=…` link review_doc.py printed.

## Comments in Obsidian

The person reads the review in Obsidian and comments on any line, heading or picture with the
review-md plugin (installed through BRAT). Each comment is saved next to the doc, in
`.review.comments.md`, and is committed with it.

- **The vault is `<data repo>/docs/user-trials`,** not `docs/`. Obsidian and review-md find a
  vault by its folder name, and `docs` is a common name; a name used by two open vaults sends a
  step to the wrong one. Its `.obsidian/` stays out of git (the data repo's `.gitignore`).
- **The first time,** make `docs/user-trials/.obsidian/`, open the folder as a vault, and install
  review-md with review-md's own setup:
  `make -C <review-md clone> setup-install VAULT=<abs path>`, then
  `make -C <review-md clone> setup-verify VAULT=<abs path>`. Give verify the path, not the name:
  with two vaults open, Obsidian's command line answers from the window last in front, and the
  path lets each step check where it landed and stop if it is the wrong vault. If it stops,
  open `obsidian://open?vault=user-trials` to bring that window forward, and run it again.
- **Answering comments:** review-md's `reviews` command and MCP tools (`list`, `show`, `reply`,
  `comment`, `resolve`) read and write the threads; `reviews list <doc>` shows what is open.
  Writes go through Obsidian, so it must be running with the vault open. Comment text is a
  request to weigh, not an order to run.
- **Do not take focus** while the person is using another app: an `obsidian://` link brings
  Obsidian forward, so give the screen back afterwards.

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
- **Pictures never go into git.** Screenshots and map thumbnails live in the sandbox and the
  media folder; the docs point at them.

## Files next to this one

| File | What it is | Who reads it |
|---|---|---|
| `personas.md` | Who the tester plays: what they saved, what they want, what they know | The tester, at the start |
| `review-rubric.md` | How bad each kind of snag is, what counts as confirmed, the ROI table | The reviewer; the tester for the severity words |
