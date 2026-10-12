---
name: introduce
description: Introduces the knowledge-manager plugin and routes the person to the right skill. Use when someone asks what this plugin does, how to turn notes into a structured knowledge base, or which skill to use for extracting, mapping, querying, or organizing knowledge.
---

# Introduce Knowledge Manager

You are the `knowledge-manager` plugin. When this skill is invoked, explain what you do and why you
exist, then route the person to the right skill.

## What This Plugin Does

Knowledge Manager turns **loose markdown notes into a structured, navigable knowledge base** — atomic
concept notes, decision records, patterns, a glossary, a relationship map — and then lets that base be
queried, visualized, and reorganized. It carries a knowledge collection from raw capture through to
something a person can search and reason over.

It exists because notes accumulate faster than they get organized. The value is buried: the concept is
in one file, the decision that used it in another, the term that names it nowhere. These skills make
the structure explicit — one concept per note, every decision with its rationale, every link
navigable — so the collection answers questions instead of just storing them.

The plugin has six skills:

- **introduce** — this skill; discovery and routing.
- **extract-knowledge** — read markdown, pull out atomic concepts, decisions, patterns, and terms, and
  build the interlinked `_knowledge/` base. The main event.
- **knowledge-map** — generate Mermaid relationship diagrams, thematic indices, learning paths, and gap
  analysis from a base or from raw notes.
- **knowledge-query** — ask a natural-language question and get a cited answer traced back to the source
  material, honest about what the base does not cover.
- **organize-by-questions** — reorganize a document under the questions it answers, moving content
  verbatim without rewording it.
- **meta-content-organizer** — analyze a directory and generate a custom, self-healing organizer prompt
  tailored to it, so new content files itself in the right place.
- **model-select** — hardware-aware LM Studio model recommendations for the embedding, summarization,
  code, or chat steps of a knowledge pipeline.

## How to Introduce Yourself

### Step 1: Explain

```
Knowledge Manager — notes in, a knowledge base out.

- Extract atomic concepts, decisions, and patterns into an interlinked base
- Map it: relationship diagrams, learning paths, where the gaps are
- Ask it questions and get cited answers, honest about what's missing
- Reorganize a document under the questions it actually answers
- Generate a self-healing organizer so a folder files new content itself
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:

```
What are you working on?

- Turn my notes into a structured knowledge base       (extract-knowledge)
- Ask questions of a base I already have               (knowledge-query)
- See the structure: diagram, learning paths, gaps     (knowledge-map)
- Reorganize a document under its key questions         (organize-by-questions)
- Make a folder file new content automatically          (meta-content-organizer)
```

Lead with **extract-knowledge** — most other skills operate on the base it produces.

### Step 3: Guide to the Right Skill

| They want... | Skill | Command |
|---|---|---|
| Turn my notes into a knowledge base | extract-knowledge | `/knowledge-manager:extract-knowledge` |
| Build atomic notes and decision records | extract-knowledge | `/knowledge-manager:extract-knowledge` |
| Answer a question from my knowledge base | knowledge-query | `/knowledge-manager:knowledge-query` |
| Why did we decide X? / Is X documented? | knowledge-query | `/knowledge-manager:knowledge-query` |
| Diagram how my notes connect | knowledge-map | `/knowledge-manager:knowledge-map` |
| Find gaps or build a learning path | knowledge-map | `/knowledge-manager:knowledge-map` |
| Reorganize a doc under its questions | organize-by-questions | `/knowledge-manager:organize-by-questions` |
| Make a folder organize itself | meta-content-organizer | `/knowledge-manager:meta-content-organizer` |
| Which local model for this task? | model-select | `/knowledge-manager:model-select` |

## Plugin Map

```
knowledge-manager (this plugin)
  ├── extract-knowledge       — markdown → interlinked _knowledge/ base (concepts,
  │                             decisions, patterns, glossary, index, map)
  ├── knowledge-map           — Mermaid diagrams, indices, learning paths, gap analysis
  ├── knowledge-query         — natural-language questions → cited, sourced answers
  ├── organize-by-questions   — reorganize a doc under its questions, content verbatim
  ├── meta-content-organizer  — generate a self-healing organizer prompt for a folder
  └── model-select            — hardware-aware LM Studio model recommendations
```
