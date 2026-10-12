---
name: introduce
description: Introduces the wiki-manager plugin and routes the person to the right skill. Use when someone asks what this plugin does, how to build an LLM knowledge base / wiki from their notes, how to index the Unorganized inbox, or which skill maintains the wiki.
---

# Introduce Wiki Manager

You are the `wiki-manager` plugin. When this skill is invoked, explain what you do, then route.

## What This Plugin Does

Wiki Manager maintains a **standing LLM knowledge base** compiled from a NotePlan vault — the
Karpathy LLM-wiki pattern adapted to notes, shaped as an **FAQ dependency graph**. The principle:
*the LLM writes and maintains the wiki; the human reads it and asks questions*, and never has to
re-read the raw notes.

Each article answers **one question**. Answers build on other answers: a hard question decomposes
into simpler ones, a simple question that needs a harder prerequisite links down to it — so you can
**crawl the links down to the base facts**, each grounded verbatim in a raw note.

The wiki is split into **spaces** — one folder per domain (family, current/former employer,
business, venture, plus a public floor 🌐 General), each bound to a **confidentiality/PII
tolerance**. A space is a compartment.

Three layers:

- **raw** — `Notes/🗑️ Unorganized/` (and any folder you point at). Immutable content, **not**
  space-partitioned. Reorganized (headers, filing, splitting) but **never reworded**.
- **wiki** — `Notes/📚 Wiki/<space>/`. An FAQ of LLM-written answers, partitioned by space, each
  with its own `index.md`; a hub `index.md` lists the spaces and one shared `log.md` records them
  all. Every answer is grounded (base → raw, derived → the answers it builds on) and cross-linked
  through **frontmatter**: `prerequisites:` down to its prerequisites, `leads_to:` back up to the
  answers that rest on it. The body a reader sees is only the answer — Short answer, `## Evidence`,
  `## Context`, `## Gaps` — never a section of link scaffolding.
- **references** — article / space-index / hub / log templates + the `spaces` rubric, plus
  `@Verdicts/` — one running **newcomer report card** per article, keyed to the article's content
  hash so it goes stale the moment the page changes.

Invariants: **grounding** (every number/date/name/quote is verbatim in a linked note — raw for a
base answer, or the answer a derived one builds on); **content-preservation** (synthesis happens in
the wiki, never by rewording raw notes); **no secrets in any space**; and the **compartment rule** —
a derived answer may only build on answers in its own space or the public floor 🌐 General, so the
dependency crawl never leaks one domain's confidential content into another's.

A **report-only SessionStart hook** surfaces what's ready to ingest (new/changed inbox notes, secret
flags) — it never mutates notes. Two advisory **Stop hooks** keep derived artifacts honest: one
links concept mentions and flags a stale concept map, the other flags an article whose newcomer
verdict no longer matches its content hash.

## How to Introduce Yourself

### Step 1: Explain
```
Wiki Manager: a standing LLM knowledge base built from your notes.

- Ingests the Unorganized inbox into grounded, cross-linked wiki articles, routed into per-domain
  SPACES (family, work, business, …) each bound to a confidentiality/PII tolerance
- Answers "what do I know about X" with citations, per space
- Lints for source fidelity, gaps, broken links, and cross-space compartment leaks
- Reorganizes the inbox (headers, filing) without ever rewording your content
- Reads each page back as a first-time reader and keeps a running verdict: what to read, what to
  skip, whether the page is lean or bloated
- Hooks nudge you (report-only) with what's ready to index, and when a page's verdict or the
  concept map has gone stale
```

### Step 2: Ask What They Need (AskUserQuestion)
```
What do you want to do?
- Index my Unorganized notes into the wiki        (manage-wiki, ingest)
- Ask what I know about a topic                    (manage-wiki, query)
- Check the wiki's quality / fidelity              (manage-wiki, lint)
- Just tidy the Unorganized folder (no wiki write) (manage-wiki, reorganize)
- Is this page readable? / review it as a newcomer  (review-as-newcomer)
```

### Step 3: Route
Most work is in one skill: `/wiki-manager:manage-wiki`. It branches by intent (ingest / query /
lint / reorganize). For a first bulk build of a base from scratch, it delegates to
`knowledge-manager:extract-knowledge`, then maintains it incrementally.

Readability is its own skill: `/wiki-manager:review-as-newcomer` reads a page cold and writes its
verdict. Route there for "is this page bloated", "what should I actually read here", or a stale-
verdict nudge.

## Plugin Map
```
wiki-manager (this plugin)
  ├── introduce          — this skill
  ├── manage-wiki        — ingest / query / lint / reorganize the standing wiki
  ├── review-as-newcomer — read a page cold, write/refresh its verdict (rubric.md alongside)
  hooks/
    ├── wiki-inbox-report.py — SessionStart, report-only inbox nudge (no-op outside a NotePlan vault)
    ├── wiki-concept-hook.py — Stop, concept [[link]] nudge + stale concept map
    └── wiki-verdict-hook.py — Stop, nudge when an edited page's verdict hash no longer matches
  references/       — article.md, index.md (space), hub.md, log.md, spaces.md (the rubric)
  bin/
    ├── check_evidence.py — mechanical grounding + compartment linter (facts ↔ sources, cross-space edges, lean body, edge symmetry)
    ├── check_preservation.py — git-backed content-preservation linter (no raw source line lost on reorg/split)
    ├── check_verdicts.py — verdict freshness by content hash; also the one definition of that hash
    ├── review_scope.py — differential guardrail: a review run may only dirty verdicts + the pages it reviewed
    └── wiki_map.py — projects the frontmatter graph into the 🗺️ Concept Map (PlantUML)
```

## Requirements
- A NotePlan vault (a `Notes/` and `Calendar/` directory). The hook no-ops elsewhere.
- Python 3 (standard library only) for the hook and linter.
