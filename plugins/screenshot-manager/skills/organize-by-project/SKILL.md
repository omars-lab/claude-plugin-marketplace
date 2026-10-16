---
name: organize-by-project
description: Sort Desktop screenshots and Desktop folders (Debugging/, Developing/, any folder of folders, loose project folders) into one folder per project in the iCloud projects folder (CloudDesktop/projects), where every project is a git repo found under ~/Workspace/git* — grouped by company. Looks inside folders no name places, keeps a fingerprint.md in every screenshot folder (its sites, paths, words, and the user's guidance) to file new screenshots by, asks the user about the unclear ones (a few in chat, many at once in an Obsidian review doc with the pictures and tick boxes, using the review-md plugin) and writes the answer into the fingerprint. An image check for screenshots no project name shows on, a plan you approve before anything moves, and an undo
---

# Organize Desktop Screenshots by Project

You file the Desktop by **project**, and a project is a git repo. Every repo under
`~/Workspace/git*` gets a folder in the iCloud projects folder. Desktop screenshots and
Desktop folders about that repo move into it.

**This skill plans first and moves only after the user approves the plan table.** Every
apply writes an undo list before the first move. It never deletes, renames inside a folder,
or touches a file that is not in the approved plan.

How it differs from the other screenshot skills:

| Skill | Sorts by | Into |
|---|---|---|
| `organize-by-plan` | NotePlan plans | `~/Desktop/Screenshots/` |
| `suggest-groupings` | events and sessions | the OneDrive Screenshots folder |
| `suggest-techniques` | "shows a Claude technique" | `~/Desktop/📸 Screenshots of Techniques/` |
| **`organize-by-project`** | git repos | `~/Library/Mobile Documents/com~apple~CloudDocs/CloudDesktop/projects/` |

It also files a screenshot that is **not** project work into the Desktop folder it belongs in
(a receipt into `Receipts - Orders/`), when that folder's fingerprint has a site the screenshot
shows and no other folder has. Those moves show in the plan table as `Desktop: <folder>`, so
the user can say no.

## Paths

```bash
# The skill's own folder: use the "Base directory for this skill" line shown when the skill loads.
OP="<base directory of this skill>/scripts"
OCR="<base directory of this skill>/../suggest-groupings/scripts"   # batch_ocr.py (reused, not copied)
ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs/CloudDesktop/projects"
WORK="<scratchpad>/organize-by-project"                            # or /tmp/organize-by-project
```

If `$ROOT` does not exist, ask with `AskUserQuestion` whether to create it or use another folder.

## Layout (decided 2026-10-16: grouped by company)

```
$ROOT/<org>/<project>/screenshots/<loose Desktop screenshot>
$ROOT/<org>/<project>/<Desktop folder>/          moved whole, name kept
$ROOT/<org>/screenshots/  and  $ROOT/<org>/<Desktop folder>/   work on the company as a whole
```

`org` is `personal` for `~/Workspace/git`, and the folder suffix for `~/Workspace/git-<org>`.
**Why:** the user works across a few companies and personal projects. Grouping by company
keeps each company's material in one place to share or archive, and gives company-wide
material (a brand folder, a business's debugging shots) a home that is not a fake project.
Desktop folders keep their names so nothing the user remembers by name disappears.

## Private files (never commit them)

Both live in `$ROOT`, not in this repo. This marketplace is public.

- `.projects.json`: the project list from `scan_projects.py`. Rebuild it each run.
- `.aliases.json`: hand-written. Shape:

```json
{
  "_orgs":    {"acme": ["acme", "acme co"]},
  "_folders": {"debugging-site": "website", "Debugging/old-name": "new-repo"},
  "_skip":    ["2026-01 Course", "Initiatives/Budgeting"],
  "website":  ["acme storefront", "storefront"],
  "math-app": ["math cli"]
}
```

  - `_orgs`: words that mean "this company" when no project's name shows.
  - `_folders`: a Desktop folder (its name, or its path under the Desktop) mapped by hand.
    This beats every other rule. Add an entry when the user corrects a folder.
  - `_skip`: Desktop folders (path under the Desktop) never looked inside: life folders whose
    names the built-in word list misses. Add one when the image check says a folder is not
    project work, so the next run doesn't spend a look on it.
  - Any other key is a project name. Its list holds names a screen shows that the repo name
    doesn't: a product name, a site's title, a non-Latin title, an old folder name. Aliases
    count as strongly as the repo's own name.

`fingerprint.md` files live inside the user's own folders (Desktop and `$ROOT`). They hold
what is on the user's screenshots, so they are private too: never copy one into this repo.

## Tasks

Create these with `TaskCreate` at the start:

1. Find the projects
2. Fingerprint the screenshot folders (and read their Guidance)
3. Read the Desktop screenshots (OCR) and match them by name and fingerprint
4. Match the Desktop folders, then look inside the ones no name placed
5. Check the unplaced screenshots by eye
6. Ask the user about what is still unclear (in chat, or in a review doc for many groups),
   and write the answers into the fingerprints
7. Build the plan and get approval
8. Move, report the undo command, refresh the fingerprints

## Step 1: Find the projects

```bash
python3 "$OP/scan_projects.py" --since-days 90 --out "$ROOT/.projects.json"
```

It finds every repo under `~/Workspace/git*` and folds worktrees and extra clones of the same
repo into one project. Show the user a short count (projects, active in 90 days, by company)
and the projects they may not expect. Don't make folders for projects; the move step makes
only the folders that get something.

## Step 2: Fingerprint the screenshot folders

Every folder with 3 or more screenshots of its own gets a `fingerprint.md`: the web addresses
and Mac folder paths that show on its screenshots, the words common there and rare elsewhere,
the date range, the project it belongs to, and a **Guidance** section. Guidance is the user's
word on what belongs in that folder. A rebuild rewrites everything above Guidance and never
touches Guidance itself.

```bash
python3 "$OP/fingerprint.py" to-read --under ~/Desktop --under "$ROOT" --out "$WORK/fp_list.txt"
conda run -n screenshot-ocr python3 "$OCR/batch_ocr.py" --list "$WORK/fp_list.txt" --out "$WORK/fp_ocr.json"
python3 "$OP/fingerprint.py" build --under ~/Desktop --under "$ROOT" --ocr "$WORK/fp_ocr.json" \
    --root "$ROOT" [--folders "$WORK/folders.json" --inside "$WORK/inside.json"]
python3 "$OP/fingerprint.py" index --under ~/Desktop --under "$ROOT" --out "$WORK/fingerprints.json"
```

- Only real screenshots count: files named like one, or PNGs. Phone photos are skipped, and so
  are saved web pages (`<page>_files/`), code folders and the folders other skills own.
- It looks 3 folders deep. `--depth` changes that.
- On a first run, `--folders`/`--inside` don't exist yet. Build without them, then build again
  after Step 4 so Desktop folders carry their project. The rebuild is cheap; pass the same OCR.
- **Read the Guidance of every folder you will file into before you start.** It is the user's
  earlier answers. Don't ask a question it already answers.

## Step 3: OCR and match the screenshots

```bash
conda run -n screenshot-ocr python3 "$OCR/batch_ocr.py" --desktop --out "$WORK/desktop_ocr.json"
python3 "$OP/match_projects.py" shots --projects "$ROOT/.projects.json" \
    --aliases "$ROOT/.aliases.json" --ocr "$WORK/desktop_ocr.json" \
    --fingerprints "$WORK/fingerprints.json" --out "$WORK/shots.json"
```

- If the `screenshot-ocr` env is missing: `conda create -y -n screenshot-ocr python=3.11` then
  `conda run -n screenshot-ocr pip install pyobjc-framework-Vision`. OCR needs macOS.
- Use `--out`. If OCR runs in the background, JSON sent to the screen comes back mixed with
  other output. It logs `ev=ocr_progress done= of=` every 25 files.
- Each shot ends up `matched`, `unclear` or `none`. Only a **name** decides a match: a
  project's name, its repo name or an alias on screen. Commit-message words never decide;
  they are passed on as hints. See `docs/issues/organize-by-project-word-matching.md`.
- **Screen furniture never matches.** A part of a project's name ("career" from a repo named
  `workspace-career`) that shows on more than 10% of all the screenshots is a bookmarks bar
  or a tab title, on screen whatever the user was doing, so that word alone no longer matches.
  The project's full name still does. `--furniture 0.10` sets the share; the run logs the
  words it dropped as `ev=furniture_words`.
- **Fingerprints add hints, never decisions.** A site or path that only one project's folders
  have puts that project first in the shot's candidates for the image check. A site only one
  non-project folder has (a shop's order page in `Receipts - Orders/`) is kept as a suggestion,
  used only if the image check says the shot is not project work. Sites many folders share
  (github.com, localhost) count for nothing.

## Step 4: Match the folders, then look inside

```bash
python3 "$OP/match_projects.py" folders --projects "$ROOT/.projects.json" \
    --aliases "$ROOT/.aliases.json" --out "$WORK/folders.json"
python3 "$OP/match_projects.py" to-read --projects "$ROOT/.projects.json" \
    --folders "$WORK/folders.json" --out "$WORK/inside_list.txt"
conda run -n screenshot-ocr python3 "$OCR/batch_ocr.py" --list "$WORK/inside_list.txt" --out "$WORK/inside_ocr.json"
python3 "$OP/match_projects.py" inside --projects "$ROOT/.projects.json" \
    --aliases "$ROOT/.aliases.json" --folders "$WORK/folders.json" \
    --ocr "$WORK/inside_ocr.json" --out "$WORK/inside.json"
```

The first command matches every Desktop folder by its name. A **folder of folders** that no
name placed is opened, and its subfolders are matched one by one. That covers `Debugging/`,
`Developing/`, and any folder with 3 or more subfolders and fewer loose images than
subfolders (`Learning/`, `Unorganized - Archive/`). Show the user every folder → project pair,
with its file count and how many files are not images.

The look inside (`to-read`, then `inside`) reads the screenshots of every folder no name
placed, except life folders. It reads at most 80 per folder, evenly spread. Each folder gets:

| Verdict | When | What the plan does |
|---|---|---|
| `whole` | names show on 2 or more and at least 40% of the shots read, and one project has 70% of those | moves the folder whole to that project |
| `split` | names show on 2 or more shots, but not like that (or the loose shots of a folder of folders, from 1) | moves only those shots, under the folder's name |
| `undecided` | no names (or just one stray one) | 5 sample shots go to the image check, which decides |
| `none` | the loose shots of a folder of folders, with no names | they stay |

- **Life folders** are never looked inside: a word in the folder's name such as receipt,
  paperwork, family, trip, health, school, visa, career (the full list is `LIFE` in
  `match_projects.py`). Add a folder the list misses to `_skip`.
- **Folders full of non-images** (saved web pages, code) are usually a reconstruction or a
  scratch project. They still move whole, but call them out.
- **A folder with key or secret files** (client secrets, `.pem`, `.p12`, `.key`, `.env`,
  credentials), or a name that says it holds keys (`api-keys`), is never moved by the script.
  List it for the user to decide: move it whole, or move it with the key files sent to a keys
  folder first.
- One stray name match does not move a shot out of a folder. In one run, a job-onboarding
  folder had one shot where a one-word project name showed as an ordinary word.

## Step 5: Check the unplaced screenshots by eye

```bash
python3 "$OP/move_to_projects.py" batch --root "$ROOT" --shots "$WORK/shots.json" \
    --inside "$WORK/inside.json" --fingerprints "$WORK/fingerprints.json" \
    --size 40 --out-dir "$WORK"
```

This puts every `unclear` **and** every `none` shot into batch files, with the sample shots of
the undecided folders. Check `none` too: on one Desktop, about half the `none` shots checked
turned out to be project work with no name on screen. Each batch also carries the
fingerprints that have a project or Guidance. Start one agent per batch (`general-purpose`,
model `sonnet`, in the background, all in one message) with this prompt, filling in the paths:

> You are sorting Desktop screenshots by which software project (git repo) they show. Read
> `<batch file>`. It has "projects" (name, company, README title, active), "folders" (what
> each folder's fingerprint says: its project, its top sites, and the user's guidance about
> what belongs there) and "shots" (an image path plus up to 3 "candidates" a word match
> guessed; the guesses are often wrong). A shot with a "folder" is a sample from a Desktop
> folder, and your answers decide where the whole folder goes.
> **Open EVERY image with the Read tool and look at it. Never answer from a folder's name or
> from other shots in the same folder.** If an image can't be opened, answer "unsure" and say
> so. Decide:
> - a project name from the list, when the screen clearly shows work on that project (its repo
>   or folder name in a terminal path or prompt, a page of that site, its app, its plan or PR,
>   or what a folder's guidance says belongs to it). Use a company's name for work on that
>   company that fits no single repo.
> - "none" when it is not project work: shopping, school, family, health, bills, travel,
>   social media browsing, news, general reading, a job's onboarding, a course.
> - "unsure" when it is software or Claude work but you can't tell which project.
> Prefer "unsure" over a guess. Don't judge by a candidate alone.
> Write JSON to `<work dir>/vision_answers_<n>.json`:
> `{"<file path exactly as given>": {"project": "<name|none|unsure>", "reason": "<what you saw>"}}`.
> Every shot needs an entry. Do not move, rename or edit any image. Reply with the counts and
> how many images you opened.

When they finish:
- **Check the opened count.** On the first run, checkers opened about a third of the images
  and answered the rest from the folder's name. Re-run a batch whose checker skipped images
  if any of its skipped answers would move something (a project answer). Skipped answers that
  only keep things on the Desktop are safe to leave.
- **Spot-check 3 images** from any batch whose calls rest on look alone ("in the style of the
  app", no repo name on screen). Open them yourself. If the calls don't hold up, change them to
  `unsure` before planning.

## Step 6: Ask about what is still unclear, and remember the answer

The unsure shots, undecided folders and folders held for key files are where the user's word
is worth most. Build a first plan (Step 7) so you know what is left, then group what's left
by what it shows (the same app, the same site, the same task), not only by time.

- **Before asking,** read the Guidance in the fingerprints of the candidate folders. If it
  already answers the question, follow it and don't ask.
- **1–4 groups: ask in chat** with `AskUserQuestion`, one question per group. Show the image
  paths. Each option names a destination and says what moves: "File these 6 screenshots of
  the lesson editor in personal/<project>", "Leave them on the Desktop", "A new folder: …".
  Recommend one, with what each choice buys and costs.
- **More than 4 groups: write a review doc** (below) and let the user answer it in Obsidian,
  in their own time. Tell them where it is and what to do; don't wait in the session.

### The review doc (many groups at once)

One Obsidian doc, one section per group: the pictures side by side, what the image check saw
under each, and a tick box per choice. The user ticks one box per group and, when a box isn't
enough, leaves a comment with the review-md plugin. It lives in its own small vault,
`$ROOT/_review`, so Obsidian never indexes the code folders that moved into `$ROOT`; every
scan skips `_review`.

```bash
python3 "$OP/review_doc.py" draft --plan "$WORK/plan.json" --shots "$WORK/shots.json" --out "$WORK/groups.json"
# edit $WORK/groups.json by hand (see below), then:
python3 "$OP/review_doc.py" write --groups "$WORK/groups.json" --vault "$ROOT/_review"
```

1. **Draft, then edit the groups by hand.** `draft` groups unsure shots taken within 30
   minutes of each other on the same day (`--gap`), and gives each undecided folder and each
   key-file folder a group of its own. On a real Desktop that made 40 groups, most of one
   screenshot. Merge them by topic (every shot of one site's sign-up form, every crop of a
   button) into 10–20 groups. For each, write a plain title and question, pick 2–3 likely
   projects as choices from the candidates and the captions, and set `recommend` only when
   you would bet on it. Choices that say "none" are labelled "Not project work: leave on the
   Desktop". Every shot of the draft must end up in one group; count them.
2. **Write.** `write` makes 1200-pixel copies of the pictures in `_review/images/<date>/`, the
   doc `_review/<date> Screenshots to file.md`, and the groups beside it as
   `.<doc name>.groups.json`. It adds "Not sure yet" and "Somewhere else (leave a comment)" to
   every group, a "show me the rest next time" box and a final "I'm done" box. It refuses to
   overwrite a doc that already has ticks; `read` it first.
3. **Set up the vault, the first time only.**
   - Plugins: copy `.obsidian/plugins/review-md/` and `.obsidian/plugins/obsidian42-brat/`
     from a vault that has them, and list both in `.obsidian/community-plugins.json`. Or
     install BRAT in Obsidian and add `omars-lab/review-md`.
   - Register the vault in `~/Library/Application Support/obsidian/obsidian.json` (an entry
     under `vaults` with `path`, `ts` and `open: true`). **Quit Obsidian first:** it rewrites
     that file when it quits, and an entry added while it runs is lost.
   - Open it with `open "obsidian://open?vault=_review"`. On first open Obsidian asks whether
     to trust the vault's plugins; the user clicks "Trust author and enable plugins" (or you
     do, screenshot before and after).
   - Check the render: a Reading-view screenshot should show the pictures, the captions and
     the tick boxes, with no `%%value%%` text showing.
4. **Tell the user** where the doc is and how to answer: tick one box per group (in Reading
   view a click ticks it); to say more, press `c`, click the picture or heading, write and
   press Comment; tick "I'm done" and say "read my screenshot answers". A group with no tick
   stays on the Desktop.
5. **Read the answers** when they say so:

```bash
python3 "$OP/review_doc.py" read --doc "$ROOT/_review/<date> Screenshots to file.md" \
    --answers "$WORK/vision_answers_user.json" --aliases "$ROOT/.aliases.json"
reviews list "$ROOT/_review" --open --waiting claude --json
```

   - `read` merges each answered group into the answers file, adds folder answers to
     `_folders` / `_skip` in the aliases file, and prints the `--keys-to/--keys-from` flags for
     Step 7. It lists the groups with more than one tick (ask again) and the ones that point
     at a comment.
   - Read each comment with `reviews show`, act on it, and answer it in the doc with the
     review-md `reply` tool (Obsidian has to be running), then `resolve` it.
   - Then do the "write it down" steps below for each group, using the "filed" list `read`
     prints.

### After every answer

- **Write it down in three places:**
  1. In the destination folder's fingerprint, in plain words, so the next run and the next
     image check read it:
     `python3 "$OP/fingerprint.py" note --folder "<destination folder>" --text "<what belongs here>" --project <name>`
     For a project with no folder in `$ROOT` yet, give its future folder
     (`$ROOT/<org>/<project>`): `note` makes the folder, and `--project` goes into the new
     file's header so the index knows whose it is.
     For "not here" answers, note it on the folder the shots looked like they belonged to:
     "Admin screens of the shop's theme editor are NOT this project; they are the shop's".
  2. In `.aliases.json` when the answer is a name: an alias for a screenshot name the screen
     shows, `_folders` for a folder, `_skip` for a life folder the word list missed.
  3. In `$WORK/vision_answers_user.json`, the same shape as the image-check answers
     (`{"<file>": {"project": "<name>", "reason": "the user: …"}}`), for the shots asked
     about. Pass it last to `plan`: a later answers file wins over an earlier one.
- Rebuild the index, re-run `shots` (new aliases may place more shots by name) and rebuild the
  plan (Step 7) so the moves follow the answers. An alias can take a shot from another
  project; read the text of any shot that changed project before trusting it. A browser
  screenshot shows the names of its other tabs too.

## Step 7: Plan and approve

```bash
python3 "$OP/move_to_projects.py" plan --root "$ROOT" --shots "$WORK/shots.json" \
    --folders "$WORK/folders.json" --inside "$WORK/inside.json" \
    --vision "$WORK/vision_answers_0.json" [--vision "$WORK/vision_answers_1.json" ...] \
    [--vision "$WORK/vision_answers_user.json"] \
    --out "$WORK/plan.json"
```

- The image check wins over the name match.
- `none` and `unsure` stay on the Desktop, except:
  - an `unsure` shot taken within 120 seconds of a placed one borrows its project (a run of
    shots is usually one task);
  - a `none` shot with a fingerprint suggestion goes into that Desktop folder.
- An undecided folder moves whole when at least 3 of its sampled shots (or all of them, if
  fewer) are called for one project and none for another. All `none`: it stays and counts as
  "folder: not project work". Anything else: "folder: undecided".
- A name already taken in the destination gets ` (2)`.
- **Folders with key files** stay unless the user said "move the key files first". Then add
  `--keys-to ~/Desktop/api-keys --keys-from "<that folder>"` (one `--keys-from` per folder):
  the plan moves each key file to the keys folder as its own `key` row, then the folder.
- Save the plan where it survives the session too: `$ROOT/.moves/plan-<date>.json`.

Show the user the printed table (destination, shots, folders, files) plus what stays behind,
counted by reason. Ask with `AskUserQuestion`: move all, move folders only, or change something
first. Corrections go into `.aliases.json` and the fingerprints (Step 6) and the plan is
rebuilt, so the fix lasts.

## Step 8: Move, report the undo, refresh the fingerprints

Move folders and screenshots as two separate batches. That gives two undo lists, so a bad
screenshot batch can be undone without touching the folder moves.

```bash
python3 "$OP/move_to_projects.py" apply --plan "$WORK/plan.json" --only folders
python3 "$OP/move_to_projects.py" apply --plan "$WORK/plan.json" --only shots
```

- It writes `$ROOT/.moves/<UTC time>.json` before the first move and prints the undo
  command. Give the user both undo commands with full paths.
- It skips a file that is gone, an iCloud placeholder (not downloaded to this Mac), and a
  destination that already exists. It reports the skips.
- Undo is per batch (`undo --log <file>`). To put back one wrong item, just move it back by
  hand.
- If the session's safety check won't let you run `apply`, give the user the two commands to
  run themselves with `!`. Don't look for a way around it.

Then refresh the fingerprints, so the folders that just got screenshots describe them, and add
the notes from Step 6 for projects that had no folder before:

```bash
python3 "$OP/fingerprint.py" to-read --under "$ROOT" --out "$WORK/fp_list.txt"
conda run -n screenshot-ocr python3 "$OCR/batch_ocr.py" --list "$WORK/fp_list.txt" --out "$WORK/fp_ocr2.json"
python3 "$OP/fingerprint.py" build --under "$ROOT" --root "$ROOT" --ocr "$WORK/fp_ocr.json" --ocr "$WORK/fp_ocr2.json"
```

Every run of this skill starts by reading the fingerprints (Step 2) and ends by refreshing
them, so each one gets a little better at saying what belongs where.

**Run it again whenever the Desktop fills up.** The second run is much smaller than the
first: only new screenshots, the folders already moved are gone, and the fingerprints and
aliases now answer most of what was asked last time. Groups the user marked "Not sure yet"
come back in the next review doc; the ones they left blank do too.

## Scripts — when to use each

| Script | What it does | When | Command |
|---|---|---|---|
| `scan_projects.py` | Lists every repo under `~/Workspace/git*` as a project (folds worktrees and clones) | Step 1, every run | `python3 "$OP/scan_projects.py" --out "$ROOT/.projects.json"` |
| `fingerprint.py to-read` | Lists the screenshots to read in every screenshot folder (80 per folder at most) | Steps 2 and 8 | `python3 "$OP/fingerprint.py" to-read --under ~/Desktop --under "$ROOT" --out …` |
| `fingerprint.py build` | Writes or refreshes `fingerprint.md` in each folder; keeps Guidance | Steps 2 and 8 | `python3 "$OP/fingerprint.py" build --under … --ocr … --root "$ROOT"` |
| `fingerprint.py note` | Adds a dated line to a folder's Guidance | Step 6, after each answer | `python3 "$OP/fingerprint.py" note --folder … --text "…" [--project …]` |
| `fingerprint.py index` | Gathers every fingerprint into one JSON for matching and batches | Step 2 | `python3 "$OP/fingerprint.py" index --under ~/Desktop --under "$ROOT" --out …` |
| `match_projects.py shots` | Matches each screenshot's OCR text to a project by name; fingerprints add hints | Step 3 | `python3 "$OP/match_projects.py" shots --projects … --aliases … --ocr … --fingerprints … --out …` |
| `match_projects.py folders` | Matches Desktop folders (and the subfolders of folders of folders) by name; flags key files | Step 4 | `python3 "$OP/match_projects.py" folders --projects … --aliases … --out …` |
| `match_projects.py to-read` | Lists the screenshots inside the folders no name placed | Step 4 | `python3 "$OP/match_projects.py" to-read --projects … --folders … --out …` |
| `match_projects.py inside` | Judges each of those folders by the names on its screenshots | Step 4 | `python3 "$OP/match_projects.py" inside --projects … --folders … --ocr … --out …` |
| `move_to_projects.py batch` | Splits the unplaced screenshots and undecided folders' samples into image-check batch files | Step 5 | `python3 "$OP/move_to_projects.py" batch --root … --shots … --inside … --fingerprints … --out-dir …` |
| `review_doc.py draft` | Groups what the plan left unclear (unsure shots, undecided folders, key-file folders) into a groups JSON to edit | Step 6, more than 4 groups | `python3 "$OP/review_doc.py" draft --plan … --shots … --out "$WORK/groups.json"` |
| `review_doc.py write` | Writes the Obsidian review doc with the pictures and tick boxes; won't overwrite one with ticks | Step 6, after editing the groups | `python3 "$OP/review_doc.py" write --groups … --vault "$ROOT/_review"` |
| `review_doc.py read` | Turns the ticks into an answers file, alias rules and key-file plan flags | Step 6, when the user says they're done | `python3 "$OP/review_doc.py" read --doc … --answers "$WORK/vision_answers_user.json" --aliases "$ROOT/.aliases.json"` |
| `move_to_projects.py plan` | Builds every destination and prints the table. Moves nothing | Step 7 | `python3 "$OP/move_to_projects.py" plan --root … --shots … --folders … --inside … --vision … [--keys-to … --keys-from …] --out …` |
| `move_to_projects.py apply` | Writes the undo list, then moves | Step 8, after approval | `python3 "$OP/move_to_projects.py" apply --plan … --only folders` |
| `move_to_projects.py undo` | Moves one batch back, newest first | When the user wants it undone | `python3 "$OP/move_to_projects.py" undo --log "$ROOT/.moves/<time>.json"` |
| `../suggest-groupings/scripts/batch_ocr.py` | OCRs images (macOS Vision): the Desktop, or a list of paths | Steps 2–4, 8 | `conda run -n screenshot-ocr python3 "$OCR/batch_ocr.py" --list … --out …` |

## Lessons from the first run

- **Narrow spaces in file names.** macOS puts a narrow no-break space (U+202F) before AM/PM.
  Agents often write a plain space back. The move script compares names with that space
  evened out; don't "fix" file names by hand.
- **"No project words" is not "not project work."** Check those shots by eye too.
- **Look-alike calls are weaker.** A checker that calls a run of shots for one app "by its
  style" may be right (it was, the first time) but spot-check before moving.
- **`Developing/` folders can hold code**, not only screenshots, and some Desktop folders are
  small projects with no repo. Move them whole by name, and say so in the report.
- **Key files stay put** until the user decides where they go.
- **Many shots need the image check.** On one Desktop of about 270 screenshots, only a quarter
  showed a project's name. That's expected: a wrong move is silent, a look is cheap.
- **Name-only folder matching misses most folders.** On the first run it left about half the
  screenshots in Desktop folders unexamined, in folders it never opened. The look inside
  (Step 4) fixed that. See `docs/issues/organize-by-project-folder-contents.md`.
- **Most unplaced folders are life admin.** Dated folders (`2026-02-04 <a school event>`) and
  folders of forms and trips were all "not project work" on the first run. Grow the `LIFE`
  word list or `_skip` instead of checking them again each run.
- **Image checkers skip images.** Asked to look at 40, they opened about 15 and answered the
  rest from the folder name. The prompt now says to open every one and report how many it
  opened. Re-run a batch when its skipped answers would move something.
- **Everyday sites are not hints.** Search, mail, code hosting, shopping and CDN sites show on
  screenshots from every folder. `fingerprint.py` keeps a `COMMON_SITES` list: they stay
  listed in fingerprint.md but never point a shot anywhere. A site or path that holds a
  project's own name (its blog's site, its folder) belongs to that project, even when one
  life folder happens to have it too.
- **OCR misreads fold together.** "tacebook.com" next to "facebook.com" is one site; sites and
  paths that differ by a letter or two are merged before counting.
- **A new alias moves shots between projects.** On the first run, adding an app's on-screen
  phrase as an alias moved a shot from one project to another. The shot did show the app; the
  old project's name was only a browser tab. Read the text of every shot that changed project
  after an alias is added.
- **A bookmarks bar is not a match.** On one Desktop, one word of a project's name sat in
  the browser's bookmarks bar and "matched" a large share of all screenshots. The furniture
  rule (Step 3) drops a name word that shows on that many.
- **Time alone makes bad question groups.** Grouping the unsure shots by time gave 40 groups,
  most of one shot, and the same site's screens months apart in different groups. Merging
  them by topic by hand gave 15 groups, each a question worth asking. See
  `docs/issues/organize-by-project-asking-many.md`.

## Lessons from the review doc

- **Pictures side by side, boxes in view.** Full-width pictures pushed the tick boxes off the
  screen. `write` puts a group's pictures on one line (300 pixels wide, 560 for a lone one) so
  Obsidian wraps them like a gallery, and the captions and boxes follow right after.
- **No title line.** Obsidian already shows the file name as the title; a `# title` showed it
  twice.
- **Choice values are hidden**, as `%%value%%` at the end of each tick line. Obsidian hides
  them in Reading view, and review-md may add ` ^id` after them; `read` allows for both.
- **Obsidian rewrites its vault list when it quits.** Edit `obsidian.json` only while it is
  closed, or the new vault is gone the next time it opens.
- **Don't script Obsidian with AppleScript** (`tell application "Obsidian" …`). It hangs and
  sets off a macOS "wants to control" prompt. Open things with `obsidian://` links, and press
  its buttons by screen position, screenshot before and after.
- **To scroll Reading view with keys,** click into the page first; page-down does nothing
  until the page has focus.
