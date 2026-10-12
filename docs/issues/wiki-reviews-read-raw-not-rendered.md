# Wiki reviews read the raw file; the render is for new techniques only

## What the rubric used to say

`skills/review-as-newcomer/rubric.md` opened with **§0 "Review the render, not the source (do this
before anything else)"**. Every page review began by calling `bin/wiki_render.py`, reading the PNGs
it produced, and only then reading the markdown. The justification was real and is recorded in
`wiki-render-capture-pipeline.md`: a newcomer reads the app, and three classes of defect had shipped
through "lean" verdicts written from source alone — 96 `> [!context]` callout markers that NotePlan
prints as literal text, 86 visible HTML comments, and two diagrams that never loaded because
NotePlan will not fetch a remote `http://` image.

## Why it changed

Dogfooding the skill across five spaces made the cost visible. A render is an AppleScript round
trip into a GUI app plus one or two image reads per page, and at 73 pages that is the dominant cost
of a review — while the information it returned was, by then, almost entirely knowledge the skill
already had. The three founding defects are not per-page measurements: they are four fixed facts
about NotePlan (no callout syntax, HTML comments are visible, remote images never load, wrapped
inline markup does not take). Once those are written down, they are findable in the source.

The user's instruction closed it:

> also, lets use the applescript image tool sparingly / as needed / to see how new markdown editing
> tehcniques look ... we should be able to fetch same content from raw files

So the render moved from a per-page step to a per-*technique* step: render once when a new markdown
or editing pattern is introduced, or when a diagram is freshly attached and its scale matters, and
not otherwise.

## What replaced it — and the defect class that forced it

Reading the source is not a strict subset of reading the render. It is better at one thing the
render is actively bad at, and that is the part the new §0 is built around.

**A render draws a plausible page over a broken file.** In one session four defects were invisible
in the app *and* invisible to both wiki validators, because `check_evidence.py` reads frontmatter
and links while `check_verdicts.py` hashes whatever is there — neither looks at the H1:

- a stray `kd` line left in a page body;
- a page that had lost its entire `sources:` frontmatter block;
- a verdict whose prose tripped the unbalanced-span check;
- a page whose whole `# ` heading had been reduced to the three characters `ar?` by a NotePlan
  partial-buffer write-back. The note still *looks* titled in the file list, so no reader would ever
  report it — and it **shipped in commit `9aa0307`**, which had already been reported as verified.

The corrective is mechanical, not visual: the vault's `.claude/hooks/note_structure.py` is now part
of the per-page loop (`TITLE`, `FM_HASH`, `FM_UNCLOSED`, `SPAN`). The rule worth remembering is
**a page can be hash-fresh, validator-clean and structurally broken at the same time.**

Two traps came with it, both paid for in blocked Stop hooks:

- **Never sweep with `-not -path "*@Verdicts*"`.** The Stop hook reports issues by
  `os.path.basename(p)`, and a verdict has the same basename as the article it reviews. Excluding
  the verdict tree does not merely miss the defect — it confirms the *wrong file* clean, repeatedly,
  while the hook goes on firing on every stop.
- **A verdict that quotes markup trips its own check.** `SPAN` counts bold delimiters per physical
  line and cannot see that a stray pair sits inside a code span. Verdicts write about markup
  constantly, so they spell the character out ("asterisks") rather than quoting it bare.

## What was kept

The clobber rule survives unchanged, because it is a property of the app, not of the workflow: a
note NotePlan holds open is rewritten from its stale in-memory buffer seconds later. So edits go in
before any render, a `grep -c` on a phrase just added confirms the write survived, and if a render
does reveal another needed edit, a *different* note is rendered first to move NotePlan's open buffer
off the file. `wiki_render.py` and the **render-wiki-page** skill are unchanged and still correct —
they are simply called far less often.

## Where this landed

- `plugins/wiki-manager/skills/review-as-newcomer/rubric.md` — §0 rewritten.
- `plugins/wiki-manager/skills/review-as-newcomer/SKILL.md` — Step 2 reads the raw file; Step 3 runs
  `note_structure.py` and the `grep -c`; Step 5 sweeps the whole wiki, verdicts included.
- `plugins/wiki-manager/.claude-plugin/plugin.json` — description corrected (it claimed reviews
  judge the rendered page), 0.13.0 → 0.14.0.
