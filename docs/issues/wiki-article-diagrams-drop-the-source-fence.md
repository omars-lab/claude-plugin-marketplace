# Article diagrams keep the PlantUML source out of the body

## The situation

Tenet 3 of the wiki work — "make meaningful visual diagrams to explain concepts and add to
notes" — needs a way to attach a diagram to an *ordinary article*. The machinery already
existed, but only inside `bin/wiki_map.py`, welded to the one generated `🗺️ Concept Map` note.
It was lifted into `bin/wiki_diagram.py`, which takes `--page` and `--puml`.

The lift was mechanical except for one decision, which went the other way from the map.

## What the map does, and why it is wrong here

`wiki_map.py` writes each image followed by a ```plantuml fence holding its source. The stated
reason is a fallback: if the render fetch fails, the note still says something.

The first article diagram (the `fol_star` vocabulary mindmap on
*What primitives does the Flower of Life Star pattern DSL define?*) was written that way, then
looked at in NotePlan. The render showed the problem immediately: under the picture sat twenty
lines of raw mindmap syntax — `** blueprint\n<i>builds construction geometry</i>` and so on —
between the diagram and `## Context`, in a code block the reader has to scroll the whole way
past. That is exactly the "do not bombard the reader with info that would inhibit reading"
tenet, violated by the very edit meant to serve tenet 3.

The fallback argument also does not survive contact with the article case: the PNG is a
**downloaded local attachment** committed next to the note, not a remote URL. There is no fetch
at read time to fail. The map's reasoning was about the note it was written for.

## What replaced it

`wiki_diagram.py` writes, by default:

- `<page>_attachments/<key>.png` — the image, linked from the note.
- `@References/@Diagrams/<page path>/<key>.puml` — the source, out of the reader's way.

The note body gains exactly one line: the `![image](…)` link. The diagram stays re-renderable
(edit the `.puml`, re-run the tool) without costing a reader anything. `--fence` restores the
old behaviour for a page that genuinely wants its source visible.

## Where the source cannot go: `_attachments/`

The first fix put the `.puml` beside the PNG, which is the obvious place. It did not survive,
and the reason is worth writing down: **NotePlan garbage-collects any file in a note's
`_attachments/` folder that the note does not reference, a few seconds after the note is
saved.** So the `.puml` was deleted by the very note-write that attached its image — silently,
with the tool reporting success.

Measured directly rather than guessed:

| Action | `_attachments/` a few seconds later |
|---|---|
| write `probe.puml`, touch nothing for 30s | `probe.puml`, `vocabulary.png` — both there |
| write `probe2.puml`, then re-save the note | `vocabulary.png` only |

A no-op save (`page.write_text(page.read_text())`) is enough to trigger it. The folder is for
files the note points at, and NotePlan enforces that.

`@References/@Diagrams/` mirrors where verdicts already live, and `@`-folders are already
excluded from the concept map, the alias registry and the evidence checks, so nothing else
needed changing. `--selftest` now asserts the path and asserts `_attachments` is *not* in it,
because this failure mode is invisible at run time.

A re-run with the same `--key` replaces the whole block, and dropping `--fence` on a re-run
removes a previously written fence — otherwise a note would keep a stale copy of source that no
longer matches its picture. Both are asserted in `--selftest`.

## Consequence for the rubric

`skills/review-as-newcomer/rubric.md` §6 said to keep the source in a fence under the diagram.
That line was written from the map's pipeline and has been corrected: the source goes to the
attachments folder. The tenets outrank the mechanical instructions, and this is a case where
following the instruction literally would have broken one.
