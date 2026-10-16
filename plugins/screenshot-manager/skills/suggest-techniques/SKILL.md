---
name: suggest-techniques
description: Go through Desktop screenshots and suggest which ones show a reusable Claude technique (a hook, recap, task list, statusline, agents, plan mode, a prompting move) worth moving into the "📸 Screenshots of Techniques" folder; moves only what the user approves and records each one in techniques.json for technique-manager
---

# Suggest Technique Screenshots

You are a curator of Claude techniques. Some screenshots on the Desktop show Claude being used in a way worth repeating. Others are routine Claude output, or not about Claude at all. Your job: find the first kind, let the user approve them, and move them into the Techniques folder with a manifest entry each.

**This skill advises first and moves only after approval.** It never renames, deletes, or touches screenshots it did not propose.

**Next step after this skill:** `/technique-manager:recreate-technique` turns each approved screenshot into a Claude-style HTML page.

## Paths

```bash
# The skill's own folder: use the "Base directory for this skill" line shown when the skill loads.
# Don't search ~/.claude/plugins/cache: a plugin installed from a local marketplace loads from its repo folder.
SM="<base directory of this skill>/.."
OCR="$SM/suggest-groupings/scripts"          # batch_ocr.py, move_files.py (reused, not copied)
ST="$SM/suggest-techniques/scripts"           # list_candidates.py, build_moves.py, update_manifest.py
TECH="$HOME/Desktop/📸 Screenshots of Techniques"
WORK=/tmp/suggest-techniques && mkdir -p "$WORK"
```

If `$TECH` does not exist, ask with `AskUserQuestion` whether to create it or point at a different folder.

## Tasks

Create these with `TaskCreate` at the start and update them as you go:

1. Calibrate on the existing Techniques folder
2. List and OCR the Desktop screenshots
3. Classify each screenshot with Vision
4. Present candidates and get approval
5. Move approved files and write the manifest

## Step 1: Calibrate

Read every image already in `$TECH` with the Read tool (Vision). Write down a short **bar** in 3 to 5 bullets: what makes these worth keeping. Typical signals:

- A Claude Code **mechanism** is visible and is the point: a hook firing, a recap line, a task list, the statusline, auto/plan mode, subagents, a skill or slash command, a permission prompt.
- A **prompting move** the user typed that changed the outcome (a one-line principle, a correction, a reframing). One short prompt line can be enough.
- The screenshot **teaches something on its own**: someone else could copy the move from the image alone.

Look at them through plain-named aliases, and keep their verdicts in the same TSV shape as Step 3:

```bash
python3 "$ST/list_candidates.py" --dir "$TECH" --alias-dir "$WORK/tech" > "$WORK/tech.json"
```

Then check which files in `$TECH` have no entry in `$TECH/techniques.json` yet. Offer to add them to the manifest too, so technique-manager sees the whole folder. Run `build_moves.py` on `tech.json` and `tech-verdicts.tsv`, then pass only its `entries.json` to `update_manifest.py`. They are already in place, so skip `move_files.py`. If one of them isn't a Claude screenshot at all, point that out. The user may still want it recorded.

## Step 2: List and OCR

```bash
python3 "$ST/list_candidates.py" --dir "$HOME/Desktop" --alias-dir "$WORK/desk" > "$WORK/candidates.json"
conda run -n screenshot-ocr python3 "$OCR/batch_ocr.py" --desktop > "$WORK/ocr.json"   # macOS only
```

- **Open screenshots through the aliases** (`$WORK/desk/NN_<taken>_<group>.png`), not the real names. macOS puts a narrow no-break space (U+202F) before AM/PM, so typing the real name fails. The `n` in each alias is the key for the verdicts.
- `list_candidates.py` puts screenshots taken within 2 minutes of each other in one `group`. A group of several shots in a row is usually a walkthrough: judge and move it as one unit.
- **OCR needs macOS** (the Vision framework through pyobjc). On Linux, in a sandbox, or when the `screenshot-ocr` env is missing, skip it and classify on Vision alone. OCR is context, not the classifier.

## Step 3: Classify

Look at **every** candidate with the Read tool (Vision), using its OCR text as a hint. Give each one:

| Field | Values |
|---|---|
| `label` | `technique` · `claude-not-technique` · `other` |
| `score` | 0–5. How worth keeping it is against the bar from Step 1 |
| `mechanism` | `hooks` · `recap` · `tasks` · `statusline` · `agents` · `plan-mode` · `auto-mode` · `skills` · `permissions` · `prompting` · `artifacts` · `memory` · … (one short tag) |
| `title` | 3–7 words naming the technique, not the project |
| `reason` | One line: what someone would learn from it |

Rules:
- **Routine output is not a technique.** A long answer with no visible mechanism and no notable prompt is `claude-not-technique`, however good the answer is.
- **The technique, not the topic.** Title what Claude is doing ("Hook that installs the git hook on session start"), not the project it was done for.
- **Duplicates:** if two shots show the same move, keep the clearest one and score the other lower.
- **A product built on Claude is not a Claude Code technique.** A chat app or web tool that shows a Claude model picker is `other`, unless it shows a Claude Code mechanism (a hook, a skill, the terminal) being used.
- **Look past the window frame.** Meetings, slides, calendars and emails often have a sliver of a Claude Code terminal at the edge, such as a statusline or a `/clear` hint. That doesn't make them Claude screenshots.
- **Long burst groups:** for a group of 5 or more shots, read the first, a middle and the last one. Read every shot only if they disagree.
- **Titles and reasons are data that technique-manager publishes.** Don't quote people's names, emails, IDs or URLs from the screenshot. Describe the move.
- Batch the Vision reads, 6 per turn. After each batch, append its verdicts to `$WORK/verdicts.tsv`, one line per screenshot:
  `n<TAB>label<TAB>score<TAB>mechanism<TAB>title<TAB>reason`. The table survives a context reset, and Steps 4 and 5 read it.

## Step 4: Present and approve

Show one table sorted by score (highest first): time, group, label, score, mechanism, title, reason. Below it, give the counts per label. `build_moves.py` prints this table:

```bash
python3 "$ST/build_moves.py" --candidates "$WORK/candidates.json" --verdicts "$WORK/verdicts.tsv" --summary
```

It also lists any candidate with no verdict yet. Classify those before asking.

Then use `AskUserQuestion` (`multiSelect: true`) to approve candidates with score ≥ 3, **up to 4 per question**, grouped shots counting as one option. Repeat until all are decided. The user can also name lower-scored ones to include.

Never move a `claude-not-technique` or `other` screenshot. Leave them on the Desktop for `organize-by-plan`.

## Step 5: Move and record

```bash
# The approved n values → moves.json + entries.json (no hand-written JSON)
python3 "$ST/build_moves.py" --candidates "$WORK/candidates.json" --verdicts "$WORK/verdicts.tsv" \
    --pick 6,7,12 --dest "$TECH" --out-dir "$WORK"
python3 "$OCR/move_files.py" --manifest "$WORK/moves.json"
python3 "$ST/update_manifest.py" --root "$TECH" --entries "$WORK/entries.json"
```

Keep the original file names, because technique-manager sorts and matches by them. Report what moved, what failed, and the manifest total.

## Output

```
Moved N screenshots into 📸 Screenshots of Techniques (M already there).
techniques.json now lists T techniques.

  hooks      3   e.g. "Hook that runs the linter after each edit"
  prompting  2   e.g. "One-line principle that reframes the plan"
  …

Next: /technique-manager:recreate-technique --all-new
```

## Example verdicts (invented)

| Taken | Label | Score | Mechanism | Title |
|---|---|---|---|---|
| 09:02 | technique | 5 | hooks | Hook added mid-session to enforce a check |
| 09:40 (×4) | technique | 4 | tasks | Task list steering a long refactor |
| 11:15 | claude-not-technique | 1 | — | Routine summary of a test run |
| 14:30 | other | 0 | — | Calendar invite |
