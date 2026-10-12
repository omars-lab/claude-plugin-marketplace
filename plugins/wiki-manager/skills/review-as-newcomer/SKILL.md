---
name: review-as-newcomer
description: Read a wiki article the way a first-time reader would and write a running verdict (report card) for it, saying what is worth reading, what to skip, and whether the page is lean or bloated. Applies the fixes it finds. Use when a wiki page feels overwhelming or too long, when asking what on a page is actually worth reading, after authoring or editing wiki articles, when the Stop hook reports stale verdicts, or to review the whole wiki in one pass. Triggers "review as newcomer", "read this as a new reader", "is this page bloated", "what should I read on this page", "verdict", "stale verdicts", "check_verdicts", "review the wiki pages".
---

# Review as newcomer — running verdicts for wiki articles

A wiki article is written by an LLM and read by a human who has never seen it. This skill closes
that loop: you read the page **cold**, decide what a newcomer actually needs from it, fix what
gets in their way, and leave a **running verdict** — a dated report card that accumulates over
the page's life so the next review sees what the last one said.

The verdict is not a summary of the page. It is advice about **reading** the page.

## Where things live

| Thing | Path |
|---|---|
| Article | `Notes/📚 Wiki/<space>/<topic>/<question>.md` |
| Its verdict | `Notes/📚 Wiki/@References/@Verdicts/<space>/<topic>/<question>.md` |
| The rubric | `${CLAUDE_PLUGIN_ROOT}/skills/review-as-newcomer/rubric.md` |
| Freshness validator | `${CLAUDE_PLUGIN_ROOT}/bin/check_verdicts.py` |
| Scope guard | `${CLAUDE_PLUGIN_ROOT}/bin/review_scope.py` |

The verdict tree mirrors the wiki tree exactly. `@`-folders are excluded from the concept map,
the alias registry and the evidence checks, so verdicts never pollute the graph.

## Step 0 — Preconditions

A review run's own diff must be **only** verdict files plus fixes to the wiki pages it reviewed.

**Be on latest.** `git branch --show-current`, then `git fetch` and check the branch is not
behind its upstream; pull if it is. A verdict records a `page_hash` of the page *as it is now* —
reviewing a stale checkout writes a hash for content that is already superseded. Stop and ask if
the pull would conflict.

**Snapshot the pre-existing dirt.** The vault is almost never clean: NotePlan rewrites daily
notes, table separators and image alt-text on its own schedule. That churn is not the review's
doing, so the guard is differential rather than a clean-tree demand — record what was already
dirty, and Step 5 checks only what changed *during* the run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/review_scope.py" --snapshot "<scratchpad>/review-scope.json"
```

## Step 1 — Pick the pages

| Ask | Do |
|---|---|
| a named page | just that one |
| "the pages I just changed" | the articles written this turn |
| "stale verdicts" / no target given | `python3 "${CLAUDE_PLUGIN_ROOT}/bin/check_verdicts.py" --wiki "Notes/📚 Wiki"` and take the stale list |
| "the whole wiki" | every article — batch it, and **commit every 10 pages** so a long run is never lost |

A page whose verdict is already fresh (hash matches) does not need re-reading. Say so and skip it.

## Step 2 — Read it cold, from the raw file

Read `rubric.md` (path above). Then **Read the article file** — the whole thing, top to bottom,
once, without jumping ahead to the frontmatter for context. That first uninformed pass *is* the
measurement; you cannot recover it by re-reading. Note as you go: where you stopped needing to
read, where you got stuck, what you had to look up.

Read the raw markdown, not a screenshot of it. Rubric §0 says why and what it costs: NotePlan's
render limits are knowledge you already carry, and a render per page buys almost nothing the source
does not show. Renders are for checking a **new** markdown technique or a freshly attached diagram,
not for every page.

Then apply the rubric's six questions and its structural checks.

**Only now read `asked_by:` and `matters_because:`** — the two frontmatter keys that claim who this
page is for. They are deliberately the last thing you look at, because knowing who the author
thought you were is exactly the knowledge a cold read is measuring the absence of. Judge them
against the read you just had: rubric §3 has the three questions and the failure shapes.

## Step 3 — Fix what's worth fixing

Apply fixes directly to the article (scope limits are in the rubric, §6). Typical ones:

- Rewrite a Short answer that summarizes the topic instead of answering the title question.
- Define an acronym or project name inline on first use.
- Delete padding: a quote or fence the prose already states in full.
- Remove a leftover `## Builds on` / `## Leads to` body section, after confirming every link it
  held lives in `prerequisites:` / `leads_to:` frontmatter.
- Wire a genuine missing prerequisite into `prerequisites:` **and** the reciprocal `leads_to:` on
  the other page.
- Rewrite an `asked_by` entry that is a bare role or a restatement of the title, or add the arrival
  path the fields missed. Fixing it does not excuse you from reporting it — see rubric §3.

Things you **report but do not fix**: a `kind: base` page sourcing a wiki article, a page in the
wrong space, a compartment-rule violation. Those are routing/schema decisions — raise them.

Then confirm the edit survived — a note NotePlan holds open is written back from its stale buffer
seconds later, and the loss is silent:

```bash
grep -c "<a phrase you just added>" "Notes/📚 Wiki/<space>/<topic>/<question>.md"
```

Then re-run the mechanical checks, because a fix can break one:

```bash
python3 .claude/hooks/note_structure.py "Notes/📚 Wiki/<space>/<topic>/<question>.md"
python3 "${CLAUDE_PLUGIN_ROOT}/bin/check_evidence.py" --wiki "Notes/📚 Wiki" --raw "Notes"
```

`note_structure.py` is the one that catches a destroyed `# ` heading or an unbalanced span — neither
validator looks at either, so a page can be hash-fresh, validator-clean and broken at once. Run it
on the **verdict** too once Step 4 has written it (rubric §0).

## Step 4 — Write the verdict

**Compute the hash last**, after every fix to the page is saved — a verdict that stores the
pre-fix hash is born stale. **Attaching a diagram counts as a fix**: `wiki_diagram.py` splices an
image line into `## Evidence`, so a hash taken before it ran is already wrong (rubric §7):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/check_verdicts.py" --hash "Notes/📚 Wiki/<space>/<topic>/<question>.md"
```

Never compute the digest by hand or with your own `sha256` call; that flag is the single
definition of the rule the validator and the Stop hook enforce.

Create the verdict at the mirrored path (creating folders as needed), or **prepend** a new dated
entry to the existing one. Frontmatter is replaced; the body log is append-on-top, older entries
kept verbatim:

```markdown
---
of_page: "[[<the question, exactly as the article title>]]"
page_hash: <the value printed by --hash>
reviewed: <YYYY-MM-DD>
verdict: <lean | ok | bloated>
framing: <agree | incomplete | disagree>
missing_use_cases:
  - <an arrival path the page serves but `asked_by` still does not list — omit the key entirely when none>
---

# Newcomer read — <the question>

## <YYYY-MM-DD> — <verdict>

**Read:** <the parts a newcomer needs, and in what order>
**Skip:** <what they can pass over, and why it's there at all>
**Stuck on:** <what a cold reader could not parse — or "nothing">
**Framing:** <whether you, as this page's cold reader, recognise yourself in `asked_by`; which use case is missing if one is; whether `matters_because` names a real stake or paraphrases the answer. Say it even when you fixed the fields this run.>
**Fixes:** <what you changed this run — or "none needed">

## <earlier date> — <earlier verdict>

…kept verbatim…
```

Render-safety rules apply as everywhere in this vault: pure `key: value` frontmatter, one
physical line per paragraph, `of_page` matching the article title exactly.

## Step 5 — Verify and commit

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/check_verdicts.py" --wiki "Notes/📚 Wiki"
```

The pages you reviewed must now be **fresh**. If one is still stale you wrote the hash before
the last edit — recompute and rewrite.

Then confirm the run stayed in its lane — pass every page you reviewed:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/review_scope.py" --verify "<scratchpad>/review-scope.json" --page "Notes/📚 Wiki/<space>/<topic>/<question>.md"
```

If it reports out-of-scope paths, revert those **by name** before committing — they are edits
this run made that it had no business making.

Sweep the structure checker over the **whole** wiki, verdicts included — never with
`-not -path "*@Verdicts*"`, because the Stop hook reports by basename and a verdict shares its
article's basename, so excluding the tree confirms the wrong file clean (rubric §0):

```bash
find "Notes/📚 Wiki" -name "*.md" -print0 | xargs -0 python3 .claude/hooks/note_structure.py
```

Stage the verdict files and the reviewed articles **by name** (never `git add -A`; another
session's files are not yours), and commit. Report to the user: which pages were reviewed, the
verdict for each, the fixes applied, and anything you raised but did not fix.

**When a space is finished, close it out.** Two things drift across a space-sized run and are
invisible from any single page:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/wiki_map.py" --wiki "Notes/📚 Wiki" --out "Notes/📚 Wiki/🗺️ Concept Map.md"
```

Any change to `prerequisites:` moves the edge count, so the map is stale by the end of a space and
the Stop hook will nag for it. And check the **space index**: its per-page `(… updated YYYY-MM-DD)`
suffixes are hand-maintained and do not follow the pages — one index carried ten dates two days
behind the articles it listed. `grep -H "^updated:"` on the space's pages is the ground truth.

## Why the hash

The Stop hook `wiki-verdict-hook.py` compares each changed article against its verdict's stored
`page_hash`. Matching hash ⇒ silence. So the loop closes by construction: edit a page and the
nudge returns, review it and the nudge stops — no timers, no mtime ordering, no re-fire.

## Never

- Let a credential, token, password or signed URL into a page or a verdict (hard gate).
- Rewrite a `— [[source]]` quotation. Raw sources are immutable and quoted verbatim.
- Write a verdict for a page you did not actually read this run.
- Judge the page as it was *before* your fixes. The verdict describes what a newcomer will meet.
