# The page body is Short answer → Evidence, and nothing the reader did not ask for

**Status:** resolved — shipped in wiki-manager 0.7.0, completed in 0.8.0 (see *Only a quotation
looks like a quotation*, below)
**Affects:** `plugins/wiki-manager/bin/migrate_body_shape.py` (new), `bin/check_evidence.py`,
`bin/wiki_map.py`, `references/article.md`, `skills/manage-wiki/SKILL.md`,
`skills/review-as-newcomer/rubric.md`, `README.md`

## Symptom

"The wiki pages are overwhelming." The frontmatter-link migration (0.6.0) had already deleted the
`## Builds on` / `## Leads to` walls, and the pages were still heavy. Three separate things were
landing on the reader's screen that nobody had decided to put there:

1. **The answer, twice.** `**Short answer.**` gave the answer in two sentences, then `## Answer`
   gave it again at length. A reader who had already got it kept reading, because the heading
   promised the thing they had just been given.
2. **96 `> [!context]` / `> [!gap]` marker lines.** Obsidian callout syntax. NotePlan has no
   callouts, so it renders the marker as a literal italic `[!context]` — directly underneath a
   heading that already says "Context".
3. **86 lines of HTML comment.** `<!-- … -->` is *not* hidden in NotePlan; it renders as ordinary
   body text. Author-facing scaffolding — "keep each paragraph on one physical line", "the fences
   below are the source of truth" — was being read by readers.

All three were invisible when reading the markdown. The user found them by looking at the app.

## Cause

Each has its own, and they are worth separating:

- **The double answer** is a design drift. The template called the section `## Answer`, so authors
  wrote an answer in it, and the bold line above became a summary *of the page* rather than the
  answer itself. Two copies of a claim then drift: one page ended up attributing a headline
  false-positive-rate figure to the wrong cause because the number was maintained in both places.
- **The callout markers** came from Obsidian habit. They were also believed to be load-bearing —
  `## Context` and `## Gaps` are exempt from the grounding check, and the assumption was that the
  `[!context]` marker is what marked them. It is not: `check_evidence.py`'s `EXEMPT_PREFIXES` is
  `(">", "<!--")`. The exemption keys on the **blockquote**, so the marker could be deleted with
  no effect on validation. Confirming that before migrating was the step that made this safe.
- **The HTML comments** came from the opposite of a bug: `docs/issues/noteplan-renders-only-local-image-attachments.md`
  had just established that NotePlan renders a `#`-prefixed line inside frontmatter as an H1, so
  the frontmatter guide was moved into an HTML comment to hide it. It does not hide it.

## What we did

`bin/migrate_body_shape.py` — one tool, three mechanical transforms, `--check` / `--apply` /
`--selftest`:

| Transform | Rule |
|---|---|
| Rename | `## Answer` → `## Evidence`, exact-heading match only |
| Drop markers | `> [!context]` → removed; `> [!context] text` → `> text`. **The `>` always survives.** |
| Strip comments | whole `<!-- … -->` blocks including multi-line, collapsing the blank line left behind |

This is regex on structurally-identified lines — a mechanical transform, not intent detection, so
it is inside the repo's no-regex-for-intent tenet.

The new body shape, and the reason it is in this order:

```
# <the question>
**Short answer.**   ← this IS the answer; a reader who stops here has it
## Evidence         ← the receipts: how we know, with — [[source]] attributions. Skippable.
## Context          ← plain > blockquote: synthesis, caveats, what this connects to
## Gaps             ← plain > blockquote: what the sources do not settle
```

Renaming the section is the whole fix for problem 1. `## Evidence` cannot be restated in longer
words, because it is a different kind of thing from the answer — it is the attribution list. The
name does the work the instruction could not.

**`@References/` keeps its comments**, because there the reader *is* the author. That exception is
a `--templates DIR` parameter, not a hardcoded filename, and a tempdir selftest proves both halves:
the template is restructured but keeps its comment; the article loses both.

## Result

82 wiki files rewritten — 74 headings, 93 markers, 10 comment blocks. Two raw inbox notes had a
stray marker each. `wiki_map.py` was emitting two comments of its own into the generated map, so it
was fixed too (the text became real prose under the fence) and the map regenerated; `--check` over
the regenerated tree reports zero, so regeneration can never reintroduce them.

Validators after: `check_evidence.py` 0 leaks, 0 legacy sections, 0 asymmetry.
`check_verdicts.py` 73 stale — correct by construction, every `page_hash` changed.

## The real finding

The newcomer-review skill had already reviewed pages carrying all three defects and called them
`lean`. It missed them because it read the page **source** with the Read tool and reasoned about how
it would look. That is the same mistake as the remote-image bug, in a skill written partly to catch
it.

`skills/review-as-newcomer/rubric.md` now opens with **section 0: review the render, not the
source** — open the page in NotePlan, look at it, write the verdict from what you saw, and if you
could not look, *say so in the verdict* rather than implying you did. An unrendered review is a
source review and should be labelled one.

## Only a quotation looks like a quotation (0.8.0)

Stripping the `[!context]` marker and keeping the `>` was half a fix. Looking at the result, the
user's verdict was immediate: **"only quotes should use quotes."** They were right. `## Context` and
`## Gaps` are the author's own synthesis, and a blockquote is markdown for *someone else's words* —
NotePlan renders it as grey ground, italic, left rule. The page was misattributing its own prose,
loudly, on a section meant to read light.

The `>` had survived because the grounding exemption keyed on it. But that was always a proxy: what
the exemption means is *this section is synthesis*. So the key moved to the section —

```python
SYNTHESIS_SECTIONS = ("## Context", "## Gaps")
EXEMPT_PREFIXES = ("<!--",)
```

— and `>` got its real job back. A `>` under `## Evidence` is a genuine quotation, and is now
grounded like any other claim, which is *stricter*: appearing verbatim in a linked source is the
entire point of quoting something. Re-running the validator surfaced no new findings, so every
existing quotation was already honest.

### The bug the render caught, again

The obvious transform — strip the leading `>` from each line — is wrong, and only looking shows why.
A blockquote wraps its paragraph over several physical lines, each carrying its own `>`, and the
renderer flows them back together. Plain prose in NotePlan gets no such courtesy: a hard newline
**is** a line break. So unquoting a four-line wrapped paragraph without rejoining it produces four
stubs, and any `**bold**` or `[[link]]` spanning a break renders as literal markup — the vault's
oldest render rule, walked into from a new direction.

`unquote_synthesis()` therefore joins consecutive quoted lines into one physical line, ends a
paragraph on a bare `>`, and leaves anything block-level once unquoted (a bullet, a sub-heading, a
table row) on its own line. 74 files, 105 lines.

This was caught before it shipped only because the counts looked odd — three pages reporting six
unquoted lines each — and opening one showed a wrapped paragraph rather than six separate ones.

## Takeaway

A rule ("don't restate the answer") loses to a heading that invites the restatement. Rename the
container and the behaviour follows. And a review skill that never looks at the artifact its reader
looks at is auditing a different document.

Second takeaway, from the 0.8.0 round: when a check keys on a *marker* rather than on the thing it
means, the marker becomes load-bearing for reasons that have nothing to do with the reader, and the
page pays for it in how it looks. Key the check on the structure — here, the section — and the
formatting is free to be whatever serves the reader.
