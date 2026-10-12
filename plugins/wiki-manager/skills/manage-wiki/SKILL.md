---
name: manage-wiki
description: Build and maintain a standing LLM knowledge base (wiki) from a NotePlan vault. The wiki is split into domain SPACES (family, work, business, …), each bound to a confidentiality/PII tolerance. Use when ingesting the Unorganized inbox into the wiki, asking "what do I know about X", linting wiki quality, reorganizing the Unorganized folder without changing content, routing a note to the right space, or any mention of "the wiki", "our knowledge base", "wiki space", "index my notes", or "add to wiki". Triggers: "index into wiki", "ingest unorganized", "what do I know about", "lint the wiki", "reorganize unorganized", "which space", "add a wiki space".
---

# Manage Wiki — LLM knowledge base for a NotePlan vault

You maintain a **compounding personal knowledge base**: the LLM writes and maintains the wiki; the
human reads it and asks questions. Adapted from the Karpathy LLM-wiki pattern to a NotePlan vault.

The governing idea: **the human never has to re-read the raw notes.** Everything worth knowing is
compiled, grounded, cross-linked, and query-able in the wiki.

## The wiki is split into spaces (domain partitions)

The wiki is **not one graph**. It is partitioned into **spaces** — one folder per domain under
`Notes/📚 Wiki/`, each bound to a **confidentiality/PII tolerance**. A space is a *compartment*:
content of one sensitivity never leaks into another through the dependency crawl. The space list,
tolerances, and the two invariants are the **rubric** in `@References/spaces.md` (source of truth:
this plugin's `references/spaces.md`) — **read it before ingesting or routing a note.** It defines
example spaces (`🌐 General`, `🏢 Work`, `📦 Past Work`, `🏡 Personal`, `☕️ NaqshCoffee`,
`👥 EarlBear`). The vault's own copy lists its real spaces, mirroring its domain emojis.

Two space invariants govern everything below:

1. **No secrets, ever** (hard gate, orthogonal to spaces): a credential/token/password never enters
   *any* space — see Safety. Spaces partition confidential *content*, not secrets.
2. **The compartment rule**: an answer may only name prerequisites in its **own space**
   or in the **public floor `🌐 General`** — never in a different private space. This keeps the
   dependency crawl safe: following `prerequisites` links down can only pass through the answer's own
   domain and General. A shared, safe-to-state fact is promoted to a **base answer in `🌐 General`**
   that both spaces build on; a fact that is *not* safe for General is re-derived independently in
   each space that needs it. `bin/check_evidence.py` enforces the mechanical side.

## The three layers

| Layer | Location | Rule |
|---|---|---|
| **raw** (sources) | `Notes/🗑️ Unorganized/` (+ any folder the user points at) | **Immutable content**, **not** partitioned into spaces. Never reword a source sentence. You may move a file, add a header/frontmatter, or split a bundle — but the words stay verbatim. One raw note may feed base answers in more than one space. |
| **wiki** (compiled) | `Notes/📚 Wiki/<space>/` | An **FAQ**, partitioned by space: LLM-written articles that each answer **one question** and carry a `space:` field, under a per-space folder whose **folder-note `<space>/<space>.md`** is that space's index (named after the space so hub `[[🌐 General]]`-style links resolve). A top-level `index.md` (the hub) lists the spaces; a single shared `log.md` records all of them. Synthesis, context, and gap-notes live here. |
| **references** (templates) | `Notes/📚 Wiki/@References/` | Article / space-index / hub / log templates + the `spaces` rubric. |
| **verdicts** (report cards) | `Notes/📚 Wiki/@References/@Verdicts/` | One running newcomer verdict per article, mirroring the wiki path. Written by `review-as-newcomer`; read by nothing else. See Workflow 5. |

### The wiki is an FAQ dependency graph

Each article answers **one question** (its title *is* the question). Articles come in two
`kind`s, and this is what makes the wiki compounding:

- **base** — the answer is grounded **directly in raw notes** (`sources:`). These are the
  *leaves* of the graph: atomic facts pulled verbatim from the inbox.
- **derived** — the answer **builds on other answers**. It lists the questions it needs in
  `prerequisites:`. A hard question decomposes into simpler ones; a simple question that
  secretly needs a harder prerequisite links **down** to it.

Because every derived answer links the questions it rests on, a reader can **crawl the
links down to the base facts** — the whole chain of reasoning is walkable *through the
wiki*, and it always terminates at raw-grounded leaves. Maintain back-links too: each
article's `leads_to:` lists the questions that depend on it. When you add a new answer,
wire both directions (`prerequisites` ↓, `leads_to` ↑) and add base answers to the index's
**Base facts** list.

### Cross-links are frontmatter, never body text

Both edge lists live **only in frontmatter**, as flat `[[link]]` lists. There are no
`## Builds on` / `## Leads to` body sections — they were a wall of scaffolding the reader
had to scroll past, and they duplicated what the frontmatter already said. A page body is
only what a newcomer reads: **Short answer → `## Evidence` → `## Context` → `## Gaps`**.

`prerequisites` is the **authoritative** direction; `leads_to` is its mirror, and
`check_evidence.py` fails on any asymmetry. The *reason* for an edge is stated inline in
`## Evidence` ("Because [[X]] establishes…"), not as a gloss beside the link.

A "see also" is **not** a prerequisite. If the answer still stands without reading the other
page, leave it out of `prerequisites` — of 12 one-directional legacy edges audited during the
migration, 11 turned out to be loose see-alsos and were dropped.

### The grounding invariant (non-negotiable)

Every load-bearing fact in a wiki article — every **number, date, name, quote, decision** — must
be **grounded**, and grounding follows the graph: a **base** answer grounds each fact **verbatim in
a linked raw note** (`sources:`); a **derived** answer grounds each borrowed fact in the **answer it
links** (`prerequisites:`), which itself grounds — so following the chain always bottoms out at
raw-grounded base facts. A wiki article is a *compilation and contextualization*, never a
fabrication. Each article links its sources/dependencies with `[[wikilinks]]` (which your repo's
pre-commit wikilink check validates, and `bin/check_evidence.py` cross-checks verbatim). If a claim
has no raw source and no supporting answer, it is either removed or moved under `## Gaps`.

**Grounded is not the same as annotated.** The links that ground a page belong in `sources:` and
`prerequisites:` — recorded once, where every tool reads them — never repeated as a `— [[note]]
(base)` tail on the end of each sentence. The reader learns nothing from the tail and steps over it
to reach the next fact; `check_evidence.py` learns nothing from it either, because it builds its
haystack from a page's links wherever they live. A link stays in the body only when the **sentence
uses it** ("Because [[X]] establishes Y…", "see [[Z]], which implements it"). The one exception is
a **space index**, where "which raw note is this leaf grounded in" is the column the reader opened
the page for, and there is no `sources:` key to move it to. `bin/migrate_attributions.py` performs
the migration and defers every line where prose wraps a link for a human to read.

### The content-preservation invariant

This skill **reorganizes and contextualizes; it does not rewrite**. In raw notes you may only:
add a `# Heading` / frontmatter, move a file into a topic subfolder, split a multi-topic dump into
separate files, or append an annotation of your own in a **fenced code block** (see below). You may
**never** reword, summarize-in-place, trim, or "clean up" the user's original sentences. Synthesis
belongs in the wiki layer, not the raw layer. (This mirrors `knowledge-manager:organize-by-questions`.)

**An annotation on a raw note is a fenced code block, never a `>` blockquote.** A blockquote means
*someone else's words*, and in a raw note that is backwards — the surrounding text is the user's, and
the annotation is the intrusion. A code fence says *verbatim, not prose*, which is exactly right: it
sets the annotation outside the note's voice and NotePlan renders it in monospace on its own ground,
unmistakably not part of the dump.

```
note: the 40-minute rollback figure above is contradicted by the incident doc.
```

Two consequences to accept, not work around: a `[[wikilink]]` inside a fence does **not** become a
link, and neither does `**bold**`. That is the point — an annotation is a margin note on someone
else's page, not wiki content. If it wants links, it is synthesis and belongs in the article's
`## Context` or `## Gaps`, where it can have them.

> **No regex for intent** (repo tenet): *you* read each note and classify it — topic, type, whether
> it is ready to ingest, whether it holds a secret. Scripts only do mechanical moves on lists you
> produced. Never delegate "what is this note about" to a pattern in a helper.

## Phase 0 — Locate the vault

Confirm you are in a NotePlan vault (a `Notes/` and `Calendar/` dir exist). The raw inbox is
`Notes/🗑️ Unorganized/`; the wiki is `Notes/📚 Wiki/`. If `Notes/📚 Wiki/` does not exist, offer to
scaffold it from `references/` before ingesting: the hub `index.md` (from `hub.md`), a shared
`log.md`, the `@References/` templates (article, index, hub, log, **spaces**), and a per-space
folder for each space in `spaces.md`, each with a **folder-note `<space>/<space>.md`** (from the
space-index template — named after the space so the hub's `[[🌐 General]]`-style links resolve).
Always read `@References/spaces.md` (or this plugin's `references/spaces.md`) first so you route
against the current space list, not a remembered one.

## Workflow 1 — Ingest (raw → wiki)

Run when the user says "index into wiki" / "ingest unorganized" / "add to wiki", or from the
SessionStart nudge.

1. **Triage.** Read each candidate raw note (default: everything under `Notes/🗑️ Unorganized/` that
   changed since the last `log.md` entry). For each, decide:
   - **space** — which domain compartment the *answer* belongs in, judged against
     `@References/spaces.md` (what the note is about + how sensitive). A note that is
     cross-cutting **and** carries no PII/confidential detail → `🌐 General`; anything sensitive
     stays in its most specific private space. One note may yield answers in more than one space.
   - **topic** (a `<space>/<topic>/` subfolder — one level within the space),
   - **disposition**: `New` (no article yet) · `Update` (extends an article) · `Duplicate` ·
     `No material` (a stub/todo with nothing to compile) · `Secret` (contains a credential/PII —
     STOP, see Safety),
   - **home**: where the raw file should live (it may need moving into a topic subfolder + a header).
   Produce an explicit triage list — **space per note** included — and do not act until it is
   written to `log.md` as the plan.

2. **Safety gate.** If any note is `Secret`, do **not** copy its content into the wiki (invariant 1,
   any space). Surface it to the user for redaction/quarantine first (see Safety). Continue with the
   rest.

3. **Reorganize raw (verbatim) — with a conservation net.** The vault is git-backed, so before you
   touch a single raw note, the current commit **is** your baseline. For notes that need it, add a
   header/frontmatter and move into the right topic subfolder; when a note bundles several topics,
   split it into separate files. Content unchanged. (Raw is **not** space-partitioned — file by
   topic.) Record each move in `log.md`. Then **prove no line was lost** — the content-preservation
   invariant is enforced mechanically, not just by care:
   `python3 "${CLAUDE_PLUGIN_ROOT}/bin/check_preservation.py" --raw "Notes/🗑️ Unorganized" --since HEAD`
   compares every original body line at the baseline commit against the whole current raw layer, so a
   **split** (lines redistributed across files) passes but a dropped or reworded line is flagged (it
   exits non-zero — **no expected false positives**). If you intentionally moved content out of the
   inbox (e.g. into an archive), pass that path with `--also` so its lines count as preserved. Run it
   before compiling; a non-empty report means a source line vanished — restore it before continuing.

4. **Compile into questions.** Turn the material into **questions**, not topic dumps. For each
   `New`/`Update`, write or extend `Notes/📚 Wiki/<space>/<topic>/<question-slug>.md` using the
   article template, whose title *is* the question. Set `space:` to match the folder. Decide `kind`:
   - **base** — the answer comes straight from raw. Before writing any fact, verify it appears
     verbatim in a raw note; list them in `sources:`.
   - **derived** — the answer needs other answers. Split out any prerequisite question that
     doesn't exist yet as its own article, list it in `prerequisites:` frontmatter, and lean
     on it instead of restating its facts. A derived answer should read as "because [[X]], then…".
     **Compartment rule (invariant 2):** every `prerequisites` target must be in **this answer's own
     space or `🌐 General`**. If a derived answer needs a fact that lives in a *different* private
     space: if that fact is safe to state publicly, promote it to a **base answer in `🌐 General`**
     and build on that; if it is not safe for General, re-derive it here from this space's own raw
     sources — **never** link sideways into another private compartment.

   **Say who asks it and what turns on it** — `asked_by:` and `matters_because:`, both required on
   every article. A question with no stated asker reads to a newcomer as trivia: the page answers
   something, and they cannot tell whether it was worth answering. Each `asked_by` entry is a **user
   story**, not a job title — `as a <role doing something specific>, I need this to <the task the
   answer unblocks>` — because the "I need this to…" half is the part someone can disagree with,
   and a claim nobody can disagree with cannot be reviewed. `- an engineer` fails; *"as an engineer
   whose story came back empty, I need this to know whether the timeout is mine to fix"* passes. It
   is a **list**: a question usually has more than one arrival path, and the one most often missed
   is the reader who arrives *from a failure* rather than from planning. `matters_because` is one
   line and a different thing — what is at stake when the answer is wrong or missing, shared across
   the askers. It must not restate the title or paraphrase the Short answer.

   Write these **before** the body, not after. They are the cheapest test of whether the question is
   worth a page: if you cannot write one honest entry, the finding is that the question may not
   deserve an article, and the right move is to fold the material into a page someone does want.
   The newcomer review judges these fields against a cold read and records the judgement in the
   verdict's `framing:` key, so a field written to satisfy the validator will be caught by a reader.

   Add a `## Context` synthesis paragraph and, where the raw material is thin or contradictory, a
   `## Gaps` one. Keep answers atomic — one question each — so the graph stays walkable.

   **`## Gaps: None.` is almost always wrong.** In one sweep of eight pages, six claimed no gaps and
   all six had real ones in plain view. Before writing it, ask: who wrote the source and what were
   they trying to achieve by writing it; which single claim is the whole page resting on, and how
   would a reader check it; does any number here measure the thing it is used to prove.

   **Lean body (the reader's budget).** The body is **only** Short answer → `## Evidence` →
   `## Context` → `## Gaps`, in that order, and nothing else. No `## Builds on` / `## Leads to`
   (frontmatter), no `## See also`, no `## Notes`. The Short answer must answer the *title
   question* standalone — a first line that summarizes the topic instead of answering the
   question is the most common failure the newcomer review catches. One precise quote beats
   five; a fence the prose already states in full is padding. `check_evidence.py` fails on any
   leftover legacy link section.

   **The Short answer is the answer; `## Evidence` is the receipts.** Do not answer twice. The
   section below the bold line exists to show *how we know* — attributed facts, the borrowed
   claims a derived answer leans on — not to restate the answer in longer words. Maintaining the
   same claim in two places is how a page ends up attributing a headline number to the wrong
   cause, which has already happened here once. `## Context` is the one section that is genuinely
   not a restatement: it is the caveat, the transfer, what this connects to.

   **Only a quotation uses `>`.** A blockquote is markdown for *someone else's words*, and NotePlan
   renders it exactly that way — grey ground, italic, left rule. So `## Context` and `## Gaps`, which
   are **your** synthesis, are written as **plain paragraphs**: quoting them misattributes your own
   prose and makes a light section look heavy. They are exempt from the grounding check because of
   the *section* they sit in (`check_evidence.py` `SYNTHESIS_SECTIONS`), never because of a prefix.
   Keep `>` for a genuine verbatim quotation under `## Evidence` — and expect it to be grounded,
   since appearing verbatim in a linked source is the whole point of quoting it. Do **not** add an
   Obsidian `> [!context]` / `> [!gap]` marker either — NotePlan has no callout syntax and shows
   the marker as a literal line.

   **NotePlan render-safety (every wiki file — articles, folder-notes, hub, log).** NotePlan is not
   CommonMark: a hard newline is a line break, and a `#` line inside frontmatter renders as an H1.
   So: (a) keep each paragraph on **one physical line** — never let `**bold**`, `*italic*`, or a
   `[[wikilink]]` span a wrapped line, or it renders as literal `**`/`[[`; (b) the `---` frontmatter
   block is **pure `key: value`** — no `#`-comment lines; (c) the **first line after the
   frontmatter is `# <Title>`**, and the frontmatter
   **`title:` value matches that H1** (the vault golden rule: filename == H1 == `title:`; a leading
   domain emoji on the H1 may be absent from `title:`, but the words must agree). The vault's
   `.claude/hooks/note_structure.py` checks all of these on every note written in a session
   (advisory Stop-hook nudge); run it on a file to self-check.

   (d) **No HTML comments on a page a reader opens.** NotePlan renders `<!-- … -->` as ordinary
   body text — it does not hide them, so author-facing scaffolding lands in the reader's page.
   Only the `@References/` templates keep comments, because there the reader *is* the author.

5. **Wire the graph + cascade.** For every new/edited article, wire **both directions in
   frontmatter**: add its prerequisites to `prerequisites:`, and add a back-link to this article in
   each prerequisite's `leads_to:`. State *why* each edge exists inline in `## Evidence`, not
   beside the link. Keep every `prerequisites` edge within-space or into `🌐 General`
   (invariant 2). Then search **this space**
   (and `🌐 General`) for other answers this material affects and update them — the cascade also
   stays inside the compartment + floor. Compile one source at a time to avoid conflicting edits.
   When the concept has an unambiguous surface term (an acronym or proper noun — RAG, Andon Cord),
   add it to the article's optional `aliases:` frontmatter list: the wiki-concept Stop hook
   exact-matches those against notes you write elsewhere and nudges you to `[[link]]` the mention.
   Add only unambiguous terms (a generic word over-matches); omit the block when nothing fits.

6. **Post-ingest.** Update the **space's own folder-note `<space>/<space>.md`** (question link,
   one-line answer, `kind`, date; add base answers to that space's **Base facts** list; note any
   own→General edge), bump the space's article count on the hub
   `index.md`, and append an
   entry to the shared `log.md` (what was ingested/moved/cascaded, **naming the space** on each
   line, and any fact promoted to `🌐 General`). Commit is the user's call.

7. **Refresh the concept map.** Any article change makes the generated map stale (the wiki-concept
   Stop hook will remind you). Regenerate it — it projects the live frontmatter (`type`/`space`/
   `kind`/`prerequisites`) into a hybrid PlantUML note: a `@startmindmap` hierarchy + a `@startuml`
   dependency graph of the `prerequisites` edges. Mechanical, one command:
   `python3 "${CLAUDE_PLUGIN_ROOT}/bin/wiki_map.py" --wiki "Notes/📚 Wiki" --out "Notes/📚 Wiki/🗺️ Concept Map.md"`
   When `$WIKI_PLANTUML_SERVER` names a PlantUML server the user controls (e.g. a private
   host on their own Tailscale/LAN — **never** a public one; the URL carries the article
   titles), the map renders inline as `![](…)` PNGs with the source kept below; otherwise it
   emits `plantuml` source fences. Set it in the vault's `.claude/settings.json` `env`, or pass
   `--render-server URL` explicitly.
   The tool **downloads** those PNGs into `🗺️ Concept Map_attachments/` and links them by
   relative path, because NotePlan does not display a remote `http://` image — App Transport
   Security blocks it and the note shows an empty gap even though the URL is valid. Commit the
   attachments folder alongside the map. If you ever see the map render as blank space, check
   the link is a relative `_attachments/…` path and not a server URL.

> **Building the wiki from scratch?** For a first bulk conversion of a large folder into an
> interlinked base, delegate the heavy lifting to `knowledge-manager:extract-knowledge`, then let
> this skill maintain it incrementally. This skill owns the *standing* wiki and its inbox.

## Workflow 2 — Query ("what do I know about X")

1. Read the hub `Notes/📚 Wiki/index.md` to pick the likely **space(s)**, then read that space's
   folder-note `<space>/<space>.md` and full-text search `Notes/📚 Wiki/<space>/` for the question
   + synonyms. If the
   question spans domains, search each relevant space (and `🌐 General`) — answer per space; do not
   blend confidential detail from one compartment into another's answer.
2. Find the closest existing question. **Crawl its `prerequisites` links down to the base facts** (the
   crawl stays within the space + `🌐 General` by construction) so the answer is fully supported,
   and synthesize **with citations** back to the wiki articles (and through them to raw). If the
   question is new but decomposes into existing answers, compose them.
3. If the wiki cannot answer, say so and check the raw inbox — an unindexed note may hold it (offer
   to ingest as a new base answer **in the right space**). A good new answer can be archived as a
   wiki article (wire its `prerequisites` / `leads_to`, respecting the compartment rule); never silently
   merge into an existing one.

## Workflow 3 — Lint (quality)

Three tiers, safest first:

- **Safe auto-fixes:** index entries out of sync with files, broken internal `[[wikilinks]]`,
  base articles missing a `sources:` line, asymmetric edges (a prerequisite with no matching
  `leads_to` back-link, or vice versa), leftover `## Builds on` / `## Leads to` **body** sections
  (delete them — the edges belong in frontmatter), and `space:` frontmatter that doesn't match the folder
  (align the frontmatter to the folder). Fix and log.
- **Mechanical report** (`bin/check_evidence.py`): flag articles whose stated numbers/dates/quotes
  are not found verbatim in their linked notes (base → raw, derived → the answers they build on),
  unresolved links, **cross-space dependency edges** (a private space building on another private
  space — a compartment leak, invariant 2), **space frontmatter ≠ folder**, and raw notes referenced
  by nothing, **legacy body link sections**, **asymmetric cross-links**, and **missing framing
  fields** (a page with no `asked_by:` / `matters_because:`). Run it as
  `python3 "${CLAUDE_PLUGIN_ROOT}/bin/check_evidence.py" --wiki "Notes/📚 Wiki" --raw "Notes/🗑️ Unorganized"`.
  A cross-space edge has **no false positives** — treat it as a real leak to fix (promote the shared
  fact to `🌐 General` or re-derive it in-space), not a candidate. `--strict` exits non-zero on
  unresolved links, cross-space edges, space mismatches, legacy body sections, asymmetric links, and
  missing framing fields.
  The framing check is also a **commit gate**: the vault's `pre-commit.local` runs
  `check_evidence.py --framing <staged wiki pages>` and refuses a commit that adds or changes a page
  without those two keys. It checks *staged* pages only — the vault is permanently dirty with
  NotePlan's own churn, so a working-tree gate would fail on edits nobody made. It tests **presence**,
  never quality: whether the stated askers are real readers is a judgement, and it belongs to the
  newcomer review (rubric §3), which records it in the verdict's `framing:` key.
- **Content-preservation report** (`bin/check_preservation.py`): the git-backed raw→raw check —
  every original body line in the raw inbox at a baseline commit must still exist verbatim somewhere
  in the raw layer today, so a reorganization/split never silently loses or rewords a source line.
  Run it as
  `python3 "${CLAUDE_PLUGIN_ROOT}/bin/check_preservation.py" --raw "Notes/🗑️ Unorganized" --since <commit-before-reorg>`
  (default `--since HEAD`; `--also <dir>` for content moved out of the inbox). **No expected false
  positives** — a reported line is a real loss to restore; it exits non-zero when any line is missing.
- **Judgment report:** contradictions between answers, dependency **cycles** (A builds on B builds
  on A), a **derived** answer that never bottoms out at a base fact, an answer whose sensitivity
  looks wrong for its space (should it move, or be split), stale claims, orphan questions (no
  inbound `leads_to`), and missing cross-references. Report; let the user decide.
- **Body shape** (`bin/migrate_body_shape.py`): the mechanical half of the lean-body rule — a
  leftover `## Answer` heading, an Obsidian `> [!context]` / `> [!gap]` marker (NotePlan has no
  callout syntax and renders the marker as a literal line), a `>` blockquote on `## Context` /
  `## Gaps` (your own words styled as a quotation, which it also rejoins into one physical line
  per paragraph), or an HTML comment on a reader-facing page (NotePlan does not hide them). Run
  `python3 "${CLAUDE_PLUGIN_ROOT}/bin/migrate_body_shape.py" --wiki "Notes/📚 Wiki" --check`;
  `--apply` fixes all four. Pages under `@References/` keep their comments — their reader is the
  author.
- **Newcomer verdicts** (`bin/check_verdicts.py`): every article needs a current report card from
  the `review-as-newcomer` skill — see Workflow 5. Run it as
  `python3 "${CLAUDE_PLUGIN_ROOT}/bin/check_verdicts.py" --wiki "Notes/📚 Wiki"`; `--strict` exits
  non-zero on any stale or orphan verdict. Stale means the page changed since it was last read
  cold, so its advice about what to read no longer describes the page.

## Workflow 4 — Reorganize inbox (no wiki write)

The "just tidy Unorganized" request. Read each note, then: add headers/frontmatter, file into topic
subfolders, split multi-topic dumps, and append fenced-code-block annotations of your own —
**all content verbatim**. Log every move. No wiki articles are written in this mode. When done, run
`bin/check_preservation.py --raw "Notes/🗑️ Unorganized" --since HEAD` (see Workflow 3) to prove the
tidy added and moved lines but lost none — the whole point of this mode is a verbatim reshuffle.

## Workflow 5 — Newcomer verdicts (is this page worth reading?)

The wiki is written by an LLM and read by a human who has never seen the page. Every article
therefore carries a **running verdict** — a dated report card saying what a first-time reader
should read, what to skip, and whether the page is `lean` / `ok` / `bloated`. Verdicts live in a
parallel tree at `Notes/📚 Wiki/@References/@Verdicts/<space>/<topic>/<question>.md`, mirroring
the wiki path (`@`-folders are already excluded from the map, the alias registry and the
evidence checks, so verdicts never enter the graph).

A verdict also judges the page's **framing** — whether a cold reader recognises themselves in
`asked_by:` and whether `matters_because:` names a real stake — and records it as `framing: agree |
incomplete | disagree` plus `missing_use_cases:`. That is the half of the framing rule a validator
cannot do: the commit gate proves the fields are *there*, only a reader can say they are *true*.

**Delegate the reading to the `review-as-newcomer` skill** — it owns the rubric, the fix scope
and the verdict format. This skill's job is to know *when* a review is owed:

- after authoring or editing articles in Workflow 1;
- when `check_verdicts.py` reports stale pages;
- when the `wiki-verdict-hook.py` Stop hook nudges.

Freshness is a **content hash**, not a timestamp: each verdict stores the `page_hash` of the
article it judged (`check_verdicts.py --hash <file>` is the single definition of that rule).
Edit the page and the stored hash stops matching, so the verdict is provably stale and the hook
nudges; re-review and the hash matches again and the nudge stops. No clocks, no re-fire.

A review run's own diff must be **verdicts + the pages it reviewed, nothing else**. Because a
NotePlan vault is almost never clean (the app rewrites daily notes on its own schedule), the
guard is differential: `bin/review_scope.py --snapshot` before, `--verify --page …` after.

## Safety — secrets & PII

The Unorganized inbox holds personal correspondence and at least one note has historically contained
a live credential. Two orthogonal controls:

- **Secrets (invariant 1, hard gate — every space):** if you spot a secret (password, API key,
  token, private personal data used as a credential), **stop on that note**: do not copy it into the
  wiki, tell the user exactly which file and line, and offer to redact (replace the secret with
  `‹redacted›`) or move the file to a gitignored quarantine. Never surface the secret value in the
  wiki, a **verdict**, the log, or a commit message. A private space is **not** a home for secrets.
- **Confidential content (spaces, invariant 2):** non-secret but sensitive content (colleague PII,
  employer/venture/business confidential detail, family/health) is *allowed* in the wiki, but only
  inside the space whose tolerance covers it (`@References/spaces.md`), and it may **never** be built
  on from a different private space. When unsure whether a fact is safe for `🌐 General`, keep it in
  the private space — the floor is for the genuinely shareable.

## Templates

Article, space-index, hub, log, and **spaces** (rubric) templates live in this plugin's
`references/` and are copied into `Notes/📚 Wiki/@References/` on scaffold. Follow them; don't invent
structure per-article. Read `spaces.md` at run time so routing tracks the current space list.

## Handoff / logging

`Notes/📚 Wiki/log.md` is the single durable record across **all spaces** — every ingest, move,
cascade, and lint writes one dated entry, naming the space on each line. A future session reads the
log to know what has already been processed (the inbox "since last index" boundary is the newest
`log.md` entry).
