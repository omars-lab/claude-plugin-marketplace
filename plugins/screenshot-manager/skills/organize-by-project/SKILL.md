---
name: organize-by-project
description: Sort Desktop screenshots and Desktop folders (Debugging/, Developing/, loose project folders) into one folder per project in the iCloud projects folder (CloudDesktop/projects), where every project is a git repo found under ~/Workspace/git* — grouped by company, with an image check for screenshots no project name shows on, a plan you approve before anything moves, and an undo
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
  "website":  ["acme storefront", "storefront"],
  "math-app": ["math cli"]
}
```

  - `_orgs`: words that mean "this company" when no project's name shows.
  - `_folders`: a Desktop folder (its name, or its path under the Desktop) mapped by hand.
    This beats every other rule. Add an entry when the user corrects a folder.
  - Any other key is a project name. Its list holds names a screen shows that the repo name
    doesn't: a product name, a site's title, a non-Latin title, an old folder name. Aliases
    count as strongly as the repo's own name.

## Tasks

Create these with `TaskCreate` at the start:

1. Find the projects
2. Read the Desktop screenshots (OCR) and match them by name
3. Match the Desktop folders
4. Check the unplaced screenshots by eye
5. Build the plan and get approval
6. Move, then report the undo command

## Step 1: Find the projects

```bash
python3 "$OP/scan_projects.py" --since-days 90 --out "$ROOT/.projects.json"
```

It finds every repo under `~/Workspace/git*` and folds worktrees and extra clones of the same
repo into one project. Show the user a short count (projects, active in 90 days, by company)
and the projects they may not expect. Don't make folders for projects; the move step makes
only the folders that get something.

## Step 2: OCR and match the screenshots

```bash
conda run -n screenshot-ocr python3 "$OCR/batch_ocr.py" --desktop > "$WORK/desktop_ocr.json"
python3 "$OP/match_projects.py" shots --projects "$ROOT/.projects.json" \
    --aliases "$ROOT/.aliases.json" --ocr "$WORK/desktop_ocr.json" --out "$WORK/shots.json"
```

- If the `screenshot-ocr` env is missing: `conda create -y -n screenshot-ocr python=3.11` then
  `conda run -n screenshot-ocr pip install pyobjc-framework-Vision`. OCR needs macOS.
- Redirect OCR to a file in the foreground. Run in the background, its JSON comes back mixed
  with other output.
- Each shot ends up `matched`, `unclear` or `none`. Only a **name** decides a match: a
  project's name, its repo name or an alias on screen. Commit-message words never decide;
  they are passed on as hints. See `docs/issues/organize-by-project-word-matching.md`.

## Step 3: Match the folders

```bash
python3 "$OP/match_projects.py" folders --projects "$ROOT/.projects.json" \
    --aliases "$ROOT/.aliases.json" --out "$WORK/folders.json"
```

It looks at the Desktop's folders and the ones inside `Debugging/` and `Developing/`. Show the
user every folder → project pair, with its file count and how many files are not images.

- **Folders full of non-images** (saved web pages, code) are usually a reconstruction or a
  scratch project. They still move whole, but call them out.
- **A folder with key or secret files** (client secrets, `.pem`, `.p12`, `.key`, `.env`,
  credentials) is never moved by the script. List it for the user to decide: move it whole,
  or move it with the key files sent to a keys folder first.
- **Life folders** (paperwork, receipts, family, trips) and folders with no matching repo are
  left alone. List the ones with no repo so the user can name one in `_folders`.

## Step 4: Check the unplaced screenshots by eye

```bash
python3 "$OP/move_to_projects.py" batch --root "$ROOT" --shots "$WORK/shots.json" \
    --size 40 --out-dir "$WORK"
```

This puts every `unclear` **and** every `none` shot into batch files. Check `none` too: on
one Desktop, about half the `none` shots checked turned out to be project work with no name on
screen. Start one agent per batch (`general-purpose`, model `sonnet`, in the background, all
in one message) with this prompt, filling in the paths:

> You are sorting Desktop screenshots by which software project (git repo) they show. Read
> `<batch file>`. It has "projects" (name, company, README title, active) and "shots" (an image
> path plus up to 3 "candidates" a word match guessed; the guesses are often wrong).
> For EACH shot, open the image with the Read tool and look at it. Decide:
> - a project name from the list, when the screen clearly shows work on that project (its repo
>   or folder name in a terminal path or prompt, a page of that site, its app, its plan or PR).
>   Use a company's name for work on that company that fits no single repo.
> - "none" when it is not project work: shopping, school, family, health, bills, travel,
>   social media browsing, news, general reading.
> - "unsure" when it is software or Claude work but you can't tell which project.
> Prefer "unsure" over a guess. Don't judge by a candidate alone.
> Write JSON to `<work dir>/vision_answers_<n>.json`:
> `{"<file path exactly as given>": {"project": "<name|none|unsure>", "reason": "<what you saw>"}}`.
> Every shot needs an entry. Do not move, rename or edit any image. Reply with only the counts.

When they finish, **spot-check 3 images** from any batch whose calls rest on look alone
("in the style of the app", no repo name on screen). Open them yourself. If the calls don't
hold up, change them to `unsure` before planning.

## Step 5: Plan and approve

```bash
python3 "$OP/move_to_projects.py" plan --root "$ROOT" --shots "$WORK/shots.json" \
    --folders "$WORK/folders.json" --vision "$WORK/vision_answers_0.json" \
    [--vision "$WORK/vision_answers_1.json" ...] --out "$WORK/plan.json"
```

- The image check wins over the name match.
- `none` and `unsure` stay on the Desktop, except that an `unsure` shot taken within 120
  seconds of a placed one borrows its project (a run of shots is usually one task).
- A name already taken in the destination gets ` (2)`.

Show the user the printed table (destination, shots, folders, files) plus what stays behind:
the unsure and not-project counts, the folders held for keys, and the folders with no repo.
Ask with `AskUserQuestion`: move all, move folders only, or change something first.
Corrections go into `.aliases.json` (`_folders` for a folder, an alias for a screenshot
name) and the plan is rebuilt, so the fix lasts.

## Step 6: Move, then report the undo

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

## Scripts — when to use each

| Script | What it does | When | Command |
|---|---|---|---|
| `scan_projects.py` | Lists every repo under `~/Workspace/git*` as a project (folds worktrees and clones) | Step 1, every run | `python3 "$OP/scan_projects.py" --out "$ROOT/.projects.json"` |
| `match_projects.py shots` | Matches each screenshot's OCR text to a project by name | Step 2 | `python3 "$OP/match_projects.py" shots --projects … --aliases … --ocr … --out …` |
| `match_projects.py folders` | Matches Desktop, `Debugging/`, `Developing/` folders to a project by name; flags key files | Step 3 | `python3 "$OP/match_projects.py" folders --projects … --aliases … --out …` |
| `move_to_projects.py batch` | Splits the unplaced screenshots into image-check batch files | Step 4 | `python3 "$OP/move_to_projects.py" batch --root … --shots … --out-dir …` |
| `move_to_projects.py plan` | Builds every destination and prints the table. Moves nothing | Step 5 | `python3 "$OP/move_to_projects.py" plan --root … --shots … --folders … --vision … --out …` |
| `move_to_projects.py apply` | Writes the undo list, then moves | Step 6, after approval | `python3 "$OP/move_to_projects.py" apply --plan … --only folders` |
| `move_to_projects.py undo` | Moves one batch back, newest first | When the user wants it undone | `python3 "$OP/move_to_projects.py" undo --log "$ROOT/.moves/<time>.json"` |
| `../suggest-groupings/scripts/batch_ocr.py` | OCRs every Desktop image (macOS Vision) | Step 2 | `conda run -n screenshot-ocr python3 "$OCR/batch_ocr.py" --desktop > …` |

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
