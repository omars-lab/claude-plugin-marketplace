# Attribution belongs in frontmatter, not on the end of every sentence

**Date:** 2026-09-16 · **Shipped in:** wiki-manager 0.9.0

## What we had

The article template told the author to "cite inline as you go", with this shape:

```markdown
- A load-bearing fact. — [[raw-note-name]]  (base)
- A step that leans on another answer. — [[Another question]]  (derived)
```

Every article followed it. By the time the wiki reached 73 pages there were **272 such tails**
across 66 articles.

## What the evidence showed

Three things, all of which say the tail is costing the reader without paying anybody.

**It is the same link, over and over.** `What did we tell Lana's school about her fish allergy?`
carried the identical `— [[Lana Fish Allergy]]  (base)` on four consecutive bullets. A reader who
learns the provenance on bullet one is told it three more times.

**No tool reads it.** `check_evidence.py:196-280` builds its grounding haystack from **every note
a page links**, frontmatter or body, with no branch on where the link sits or on `kind`. The tail
was never load-bearing for validation — the frontmatter already carried it on most pages. Proof:
running `check_evidence.py --strict` before and after the migration gives an identical report —
`23` ungrounded literals, `0` on every hard gate.

**It reads worst exactly where it is most common.** Two thirds of the tails were on *paragraph*
lines, not bullets, and some were stranded mid-sentence before a list:

```markdown
The questions, grouped as raised: — [[questions-anthropic-asked]]  (base)
```

The first pass of the migration tool only handled bullets, on the theory that a tail on a
paragraph was more likely to be a real sentence. That was backwards, and a `--check` run said so:
86 of the 272 were paragraph tails, and the colon-stranded ones are worse than any bullet case.

## Why it changed

The governing tenets, set by the user the same day:

1. an answer reads **honestly and usefully**
2. it does not **bombard the reader on arrival**
3. concepts with shape get a **real diagram**

The tail is tenet-2 damage taken in the name of tenet 1. Omar's formulation: *"the sections of raw
pages a note is derived from should only be in front matter — readers shouldn't have to read it
too"*, and on what survives in the body, *"keep natural links in sentences that add value"*.

## What replaced it

`bin/migrate_attributions.py` (`--wiki`, `--raw`, `--check` / `--apply` / `--selftest`).

**Lift, then strip — in that order.** Grounding is computed from a page's links, so a raw note
cited *only* in the body stops grounding the page the moment the tail is deleted. The tool merges
those links into `sources:` first and strips second. Ten links needed lifting across the 66 pages;
without that step ten pages would have quietly lost their grounding.

**A tail is a narrow shape, deliberately.** `— [[link]]` plus an optional short parenthetical, with
**nothing between the dash and the link** and nothing after but another tail or the end of the
line. Anything else — `— the epipen itself comes from [[Z]]`, `(see [[Z]], which implements it)` —
is reported under AMBIGUOUS and left completely untouched, including the bare tail on the same
line. Deciding whether a sentence is *using* a link or just trailing it is intent, and intent is
the assistant's job, not a regex's (repo tenet). Four lines were deferred; three were genuine prose
cross-references and stayed, one was half-bare and got a hand edit.

**The parenthetical is noise whatever it says.** The tags were hand-written and had drifted —
`(base)`, `(derived)`, and three instances of `(base fact from source)`. Matching only the first
two would have left the third behind for no reason a reader would recognise.

**Space indexes are exempt** (`type: wiki-space-index`, so the tool only touches `wiki-faq`). An
early run stripped them too and had to be reverted: on an index, "which raw note is this leaf
grounded in" is the column the reader opened the page for, and an index has no `sources:` key for
the link to move into — the tool was inventing one.

**Fences and blockquotes are never touched.** They are verbatim source; rewriting them would break
the content-preservation invariant.

## Result

66 articles, 272 tails stripped, 10 links lifted into `sources:`, 4 lines deferred to a human.
`check_evidence.py --strict` identical before and after. Verified in the NotePlan render, not just
the diff.

## Also learned

NotePlan scrolls via **System Events** key codes:

```
osascript -e 'tell application "System Events" to key code 121'   # page down (116 = page up)
```

System Events is a different Apple-events target from NotePlan and *is* authorized, so this works
where `noteplan_ui` returns `-1743`. This matters because a note opens scrolled to its
References/Properties panels — the first `screencapture` of an article is almost always a header,
not the body under review. See `docs/issues/noteplan-renders-only-local-image-attachments.md` for
the other render limits.
