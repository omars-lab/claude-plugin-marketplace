# wiki-manager

A standing **LLM knowledge base** compiled from a NotePlan vault, shaped as an **FAQ
dependency graph**. The LLM writes and maintains the wiki; you read it and ask questions —
you never have to re-read the raw notes.

Run `/wiki-manager:introduce` for the full capability list and routing. That skill is the
authoritative reference.

## The idea

Each article answers **one question** (its title *is* the question). Answers come in two kinds:

- **base** — grounded **directly in raw notes**. The leaves of the graph.
- **derived** — built on **other answers**. A hard question decomposes into simpler ones; a
  simple question that needs a harder prerequisite links **down** to it.

Because every derived answer lists the questions it rests on (`prerequisites:` ↓) and every
prerequisite lists its dependants back (`leads_to:` ↑), you can **crawl the links down to the
base facts** — the whole chain of reasoning is walkable *through the wiki*, and always terminates
at raw-grounded leaves. Both edge lists live in **frontmatter**, not in the page body, so the
graph is machine-checkable and the reader never scrolls past scaffolding (see *The page a
newcomer reads*).

## The page a newcomer reads

An article's body is only the answer, in this order and nothing else:

| Part | What it carries |
|---|---|
| **Short answer** | One paragraph that answers the title question on its own. If a reader stops here they leave correct. |
| `## Evidence` | How we know — the facts themselves, stated plainly. Where they came from is frontmatter, not a tail on each line. Skippable by design. |
| `## Context` | Framing a newcomer needs but did not ask for. Optional. |
| `## Gaps` | What the sources do not settle. Optional. |

`## Context` and `## Gaps` are the author's own synthesis, so they are exempt from the grounding
check and written as **plain paragraphs**. Only a genuine quotation uses `>` — a blockquote means
"someone else's words", and NotePlan renders it as such, so quoting your own prose misattributes
it. A `>` under `## Evidence` is a real quotation and is grounded like any other claim.

Everything else is **frontmatter**: `prerequisites:` (what a reader must understand first),
`leads_to:` (back-links, kept symmetric with `prerequisites`), `sources:`, `aliases:`, `space`, `kind`. There is no
`## Builds on` / `## Leads to` body section — those were a wall of scaffolding between the
reader and the answer, and a hand-maintained duplicate of an edge list the tools already read.
*Why* an edge matters is stated inline where it is used ("Because [[X]] establishes…"), not as a
gloss on a link. `bin/check_evidence.py` fails the build on a leftover body section or an
asymmetric edge.

Attribution is frontmatter too. A line does **not** end with `— [[raw-note]]  (base)`: where a
fact came from is recorded once, in `sources:` / `prerequisites:`, which is where every tool reads
it from. Grounding is computed from a page's links wherever they sit, so the tail never earned
its keep — it just made the reader step over punctuation to reach the next fact. A link stays in
the body only when the **sentence uses it** ("Because [[X]] establishes Y…", "see [[Z]], which
implements it"). The one exception is a space index, where the raw-note column is the page.
`bin/migrate_attributions.py --check` finds the tails; it lifts a body-only link into `sources:`
before stripping, so no page loses its grounding.

## Newcomer verdicts (report cards)

Every article has a running **verdict** — a review written by reading the page cold, as someone
who does not already know the answer — at
`Notes/📚 Wiki/@References/@Verdicts/<space>/<topic>/<question>.md`. It records what to **read**,
what to **skip**, what a newcomer got **stuck on**, and any **fixes** applied, plus a one-word
`verdict: lean | ok | bloated`.

Freshness is a **content hash**, not a timestamp. The verdict stores the `page_hash` of the
article it reviewed, so editing the page makes its verdict stale by construction and re-reviewing
makes it fresh again — no clocks, no touch-ordering, no re-firing nudge.

```
python3 bin/check_verdicts.py --wiki "Notes/📚 Wiki"           # which pages need a review
python3 bin/check_verdicts.py --hash "<path to article.md>"    # the one definition of the hash
python3 bin/check_verdicts.py --wiki "Notes/📚 Wiki" --strict   # non-zero if any page is stale
```

Run `/wiki-manager:review-as-newcomer` to do the review and write the verdict.

### The review reads the render, not the markdown

NotePlan is an **editor, not a preview**: it prints `**` and backtick markers in grey while also
applying the formatting, shows HTML comments, gives `>` a grey ground and italics, has no callout
syntax, never loads a remote image, and turns inline markup that spans a wrapped line into literal
text. None of that is visible in the source, so judging readability from the file is guessing.

`bin/wiki_render.py` opens an article in the app and screenshots what a reader sees:

```
python3 bin/wiki_render.py --page "<article>.md" --section Evidence --screens 2 --out <dir>
python3 bin/wiki_render.py --selftest
```

The `--section` flag is the part that matters. NotePlan's `highlightStart` counts from the start
of the **file**, frontmatter included, so offset 0 lands on the properties panel rather than the
body; the tool computes the real character offset of the heading and scrolls straight there. The
capture is cropped to the editor column, because the right-hand Timeline panel stays open and no
x-callback closes it. See `/wiki-manager:render-wiki-page` and
`docs/issues/wiki-render-capture-pipeline.md`.

## Spaces (domain partitions)

The wiki is split into **spaces** — one folder per domain under `Notes/📚 Wiki/`, each bound to a
**confidentiality/PII tolerance**: `🌐 General` (public floor — no PII), `🏢 Work` (current
employer), `📦 Past Work` (former employer), `🏡 Personal` (self + family), `☕️ NaqshCoffee` (business),
`👥 EarlBear` (venture). A space is a *compartment*: content of one sensitivity never leaks into
another through the dependency crawl. The rubric lives in `references/spaces.md`.

## Three layers

| Layer | Location | Rule |
|---|---|---|
| **raw** | `Notes/🗑️ Unorganized/` | Immutable content, **not** space-partitioned. Reorganized (headers, filing, splitting) but **never reworded**. |
| **wiki** | `Notes/📚 Wiki/<space>/` | The FAQ, partitioned by space: LLM-written answers + per-space `index.md`, a hub `index.md`, and one shared append-only `log.md`. |
| **references** | `Notes/📚 Wiki/@References/` | Article / space-index / hub / log templates + the `spaces` rubric (copied from this plugin's `references/`). |
| **verdicts** | `Notes/📚 Wiki/@References/@Verdicts/` | One running newcomer report card per article, mirroring the wiki path. Not articles — `@`-folders are excluded from the map, the alias registry and the evidence checks. |

### Invariants

- **Grounding** — every number, date, name, quote, decision is verbatim in a linked note:
  raw for a base answer, or the answer a derived one builds on.
- **Content-preservation** — synthesis happens in the wiki, never by rewording raw notes.
- **No secrets, ever** — a credential/token/password never enters *any* space (hard gate).
- **Compartment rule** — a derived answer may only build on answers in its **own space** or the
  public floor **`🌐 General`**, never in a different private space. A shared, safe-to-state fact is
  promoted to a base answer in `🌐 General`; an unsafe one is re-derived in-space. This keeps the
  dependency crawl from leaking one domain's confidential content into another.

## Skills

- `/wiki-manager:manage-wiki` — ingest / query / lint / reorganize. Branches by intent.
- `/wiki-manager:review-as-newcomer` — read a page cold and write/refresh its verdict.
- `/wiki-manager:render-wiki-page` — open a page in NotePlan and screenshot the reader's view.
- `/wiki-manager:introduce` — what this plugin does + routing.

## Hooks

A **report-only** SessionStart hook (`hooks/wiki-inbox-report.py`) surfaces what's ready to
ingest (new/changed inbox notes, possible-secret flags) and nudges toward
`/wiki-manager:manage-wiki`. It **never mutates a note**, no-ops silently outside a NotePlan
vault, is rate-limited, and always exits 0. Opt out per repo with
`.claude/hooks/wiki-inbox.conf` (`ENABLED=0`).

An **advisory** Stop hook (`hooks/wiki-concept-hook.py`) links concepts to articles and keeps the
map fresh. It (1) exact-matches each article's declared `aliases:` (plus its title) against the
notes written that turn and nudges to `[[link]]` any verbatim mention that isn't linked yet —
Claude judges whether the mention is really that concept (no regex for intent detection), and
(2) reminds you to regenerate the concept map when a wiki article changed. It never mutates a note,
is deduped so an unchanged nudge won't re-fire, and opts out via `CONCEPT_LINKS=0` in the same conf.

A second **advisory** Stop hook (`hooks/wiki-verdict-hook.py`) nudges when an article you edited
this turn no longer matches its verdict's stored `page_hash` (or has no verdict yet). Because the
freshness test is the hash and not a timestamp, rewriting the verdict silences it by
construction. It never mutates a note and opts out via `VERDICT_NUDGE=0` in the same conf.

## Concept map

**`bin/wiki_map.py`** projects the wiki into a hybrid **PlantUML** note (`🗺️ Concept Map.md`): a
`@startmindmap` of the space → topic → article hierarchy, plus a `@startuml` graph of the
`prerequisites` edges (the true interconnection). Purely mechanical — it reads only frontmatter
(`type`/`space`/`kind`/`prerequisites`/`title`) and folder layout. Regenerate after any ingest:

```
python3 bin/wiki_map.py --wiki "Notes/📚 Wiki" --out "Notes/📚 Wiki/🗺️ Concept Map.md"
python3 bin/wiki_map.py --wiki "Notes/📚 Wiki" --stdout        # preview
python3 bin/wiki_map.py --selftest
```

**Rendering as an image.** NotePlan shows a `plantuml` fence as source code, not a picture. To
render the diagrams inline as `![](…)` PNGs, point the tool at a PlantUML server **you control**
— via `--render-server URL` or `$WIKI_PLANTUML_SERVER` (e.g. set in the vault's
`.claude/settings.json` `env`). Use a private host on your own Tailscale/LAN, **never** a public
server: the image URL carries the diagram content (article titles across every space), so a public
server would leak compartmented content off your infrastructure.

**The images are downloaded, not linked.** With `--out`, the tool fetches each PNG from the server
and writes it into a sibling `🗺️ Concept Map_attachments/` folder, then links it by relative path
— NotePlan's own attachment convention. This is not a preference: **NotePlan will not display a
remote `http://` image at all.** macOS App Transport Security blocks the cleartext load, so a note
carrying a perfectly valid server URL renders as a silent empty gap (`curl` on the same URL returns
the PNG happily, which is what makes it so confusing to diagnose). Downloading also means the map
keeps rendering when the render host is off the network. `--remote-images` restores the old
link-only behaviour for publishing the note somewhere that is not NotePlan. Either way the
`plantuml` source stays under a `## Source` heading, so the map still reads as text if a fetch
fails.

## Linters

Mechanical nets — none of them is a judge.

**`bin/check_evidence.py`** — grounding + compartment (wiki → raw). It flags:

1. unresolved `[[links]]`,
2. numbers/dates/quotes in an article not found verbatim in its linked notes (base → raw,
   derived → the answers it builds on — the crawl-through-the-wiki check),
3. **cross-space dependency edges** — a private space building on another private space (a
   compartment leak; no false positives),
4. **space frontmatter ≠ folder**,
5. raw notes referenced by no article,
6. **legacy body sections** — a leftover `## Builds on` / `## Leads to` (edges belong in
   frontmatter),
7. **asymmetric edges** — a prerequisite with no matching `leads_to` back-link on the target, or
   the reverse.

Expect false positives on the grounding (2) and orphan (5) checks — they are candidates for review.
Checks 3, 4, 6 and 7 are mechanical with no false positives. `--strict` exits non-zero on
unresolved links, cross-space edges, space mismatches, legacy body sections, and asymmetric edges.

**`bin/check_verdicts.py`** — newcomer-verdict freshness (article → verdict). For each article it
locates the verdict in the `@Verdicts` tree and reports it **stale** (missing, or the stored
`page_hash` no longer matches the article's content) or **orphan** (a verdict whose article is
gone). It is also the *single definition* of the page hash — `--hash <file>` is what the skill,
the validator and the Stop hook all call, so they cannot drift apart. `--strict` exits non-zero on
any stale page; `--json` for scripting.

**`bin/review_scope.py`** — the review-run guardrail. A NotePlan vault is never clean (the app
touches dozens of daily notes on its own), so the check is **differential**: `--snapshot` records
what was already dirty before the run, and `--verify --page <path>…` fails only on paths that
became dirty *during* it and are neither a verdict nor one of the articles the run reviewed. That
keeps "only verdict + wiki-fix diffs" enforceable without blocking on churn the run did not cause.

**`bin/check_preservation.py`** — content-preservation (raw → raw, git-backed). Every original body
line in the inbox at a baseline commit must still exist verbatim somewhere in the raw layer today, so
reorganizing (moving, adding headers, **splitting** a multi-topic dump) never silently loses or
rewords a source line. Splits pass (lines redistributed across files); a dropped/reworded line is
flagged with **no expected false positives**, and it exits non-zero on any loss. `--since <ref>` sets
the baseline (default `HEAD`); `--also <dir>` counts content intentionally moved out of the inbox.

```
python3 bin/check_evidence.py --wiki "Notes/📚 Wiki" --raw "Notes/🗑️ Unorganized"
python3 bin/check_preservation.py --raw "Notes/🗑️ Unorganized" --since HEAD
python3 bin/check_verdicts.py --wiki "Notes/📚 Wiki"
python3 bin/check_evidence.py --selftest
python3 bin/check_preservation.py --selftest
python3 bin/check_verdicts.py --selftest
python3 bin/review_scope.py --selftest
python3 hooks/wiki-inbox-report.py --selftest
python3 hooks/wiki-concept-hook.py --selftest
python3 hooks/wiki-verdict-hook.py --selftest
```

## Requirements

A NotePlan vault (`Notes/` + `Calendar/`) and Python 3 (standard library only).
