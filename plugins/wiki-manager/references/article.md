---
title: <The question, phrased as a question?>
type: wiki-faq
space: <🌐 General | 🏢 Work | 📦 Past Work | 🏡 Personal | ☕️ NaqshCoffee | 👥 EarlBear>
status: living
kind: base
asked_by:
  - as a <role, doing something specific>, I need this to <task the answer unblocks>
  - as a <a second role who arrives at this question a different way>, I need this to <their task>
matters_because: <what goes wrong if this answer is absent or wrong — one line>
updated: YYYY-MM-DD
sources:
  - "[[raw-note-name]]"
prerequisites:
  - "[[Another question this answer needs]]"
leads_to:
  - "[[A question that depends on this one]]"
aliases:
  - <short surface term this concept is called in prose, e.g. RAG>
---

# <The question, phrased as a question?>

<!--
Frontmatter guide (NotePlan renders `#`-comment lines inside the --- block as H1 headings, so
this guidance lives here as a hidden HTML comment, and the block above stays pure key: value):
  status  — living | stable | stale
  kind    — base | derived. WHERE THE FACTS CAME FROM, and nothing else. base = read off raw
            notes: fill `sources`. derived = taken from other answers: fill `prerequisites`.
  asked_by — WHO NEEDS THIS ANSWER AND WHAT FOR. Required, flat list, at least one entry, each
             written as a user story: "as a <role doing something specific>, I need this to <task>".
             A bare job title ("an engineer") FAILS: it names an audience without naming what the
             answer is for, and the "I need this to…" half is the part that makes the page's
             existence arguable — and therefore reviewable. A question often has more than one use
             case; list each one, because they are how the review skill judges whether the page is
             aimed at anybody real. If you cannot write a single honest entry, that is the finding:
             the page may not deserve to exist.
  matters_because — WHAT GOES WRONG when this answer is missing or wrong. Required, ONE line, and
             a different thing from `asked_by`: the entries say what someone is trying to do, this
             says what is at stake across all of them. It must not restate the title ("matters
             because latency matters") and must not be a synonym of the short answer. Keep it to a
             line — this block is metadata a reader scans before the answer starts, and the whole
             point of moving cross-links into frontmatter was to stop that block becoming a wall.
  sources    — for a BASE answer: the raw notes it is grounded in.
  prerequisites — WHAT A READER MUST ALREADY UNDERSTAND to follow this answer. A DIFFERENT
               question from `kind`, so the two do not constrain each other: a `base` page whose
               facts came off a raw note can still require another answer first, and 31 pages do.
               (This key used to be called `depends_on`, which sounded like a claim about
               grounding and made those pages look broken. Renamed, no edge changed.)
               Cross-linking is FRONTMATTER-DRIVEN — the edges live here, not in a body section.
               State *why* each edge matters inline in `## Evidence` ("Because [[X]] establishes…"),
               not as a gloss. Keep it a flat list of "[[question]]" links.
  leads_to   — the back-links: questions that name THIS answer as a prerequisite. Flat
               "[[question]]" list, kept symmetric (every edge wired both ways); `[]` if none.
  aliases    — OPTIONAL. Short surface terms this concept is called by in prose (acronyms, proper
               nouns: RAG, Andon Cord, Bedrock Guardrails). The wiki-concept Stop hook exact-matches
               these against notes you write and nudges you to add a [[link]] where the mention
               really is this concept. Add only unambiguous terms — a generic word (e.g. "system")
               over-matches. Omit the block entirely when nothing fits.
  COMPARTMENT RULE (see [[spaces]]): every prerequisite must live in THIS answer's own space
  or in 🌐 General — never in a different private space.
Body rule: keep each paragraph on ONE physical line — NotePlan treats a hard newline as a line
break, so inline **bold**/*italic*/[[links]] that span a wrapped line render as literal markup.
Quoting rule: ONLY a quotation uses `>`. A blockquote is markdown for "someone else's words", and
NotePlan renders it that way (grey ground, italic, left rule), so quoting your own prose
misattributes it. `## Context` and `## Gaps` are YOUR synthesis — write them as plain paragraphs.
They are exempt from the grounding check because of the section they are in, not because of any
prefix. And never add an Obsidian `> [!context]` / `> [!gap]` marker: NotePlan has no callout
syntax and renders the marker as a literal italic line under a heading that already says the word.
-->

**Short answer.** One or two sentences a reader can stop at. This IS the answer — a reader who
stops here has it. Everything below is the receipts.

## Evidence

How we know. Two grounding rules, by `kind`:

- **base** — every number, date, name, quote, decision here appears **verbatim in a linked raw note** (`sources`). These are the leaves of the knowledge graph.
- **derived** — this answer builds on other answers (listed in `prerequisites:`). State each borrowed fact and link the question it comes from inline, so a reader can **crawl down** to the base facts:
  - Because [[Another question this answer needs]] establishes X, it follows that …

- A load-bearing fact, stated and then left alone.
- A step that leans on another answer — because [[Another question this answer needs]] settles Y.

<!-- ATTRIBUTION IS FRONTMATTER, NOT A TAIL. Do NOT end a line with "— [[note]]  (base)". Where a
     fact came from is recorded once, in `sources:` / `prerequisites:`, which is where every tool
     reads it from; repeating it per-sentence tells the reader nothing new and makes them step over
     punctuation to reach the next fact. Four bullets in a row once carried the identical
     "— [[Lana Fish Allergy]]  (base)". A link only stays in the body when the SENTENCE uses it —
     "Because [[X]] establishes Y…", "see [[Z]], which implements it" — because then it is prose
     carrying information, not metadata. Check `sources:`/`prerequisites:` actually names the note
     BEFORE you leave it out of the body: grounding is computed from a page's links, so a note
     cited nowhere else stops grounding the page.
     Cross-links are frontmatter-driven for the same reason: prerequisites go in `prerequisites:`,
     back-links in `leads_to:`, and there is NO "Builds on" / "Leads to" body section. A reader
     gets only the answer; the graph is walkable through the frontmatter and the concept map. -->

## Context

Your synthesis — how this fits the bigger picture. Your words, exempt from grounding. Plain prose, one paragraph per physical line, no `>`.

## Gaps

What's unverified, missing, or contradictory.

"None." is almost always wrong, and writing it is a sign the page has not been read against its
source rather than a sign the source was complete. In one sweep of eight pages, six said "None."
and all six had real gaps sitting in plain view: a self-reported figure presented as a measurement,
a load-bearing premise nobody showed their work on, a count that contradicted itself two paragraphs
later in the same source. Before you write "None.", ask the three questions that keep finding
things: who wrote the source and what were they trying to achieve by writing it; which single claim
is the page's whole argument resting on, and how would a reader check it; and does any number here
measure the thing it is being used to prove. Delete the section only when you have asked those and
genuinely have nothing — which is rare enough to be worth a second look.
