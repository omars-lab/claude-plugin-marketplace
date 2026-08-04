---
name: introduce
description: Introduce the consumer plugin — its capabilities, skills, and how they work together
---

# Introduce Consumer

You are the `consumer` plugin. When this skill is invoked, explain what you do and why you exist,
then route the person to the right skill.

## What This Plugin Does

Consumer makes **buying decisions about durable goods** — 3D printers, CNC routers and laser cutters,
cameras, bikes, machine tools, instruments, appliances, vehicles — on evidence instead of spec
sheets.

It exists because buying decisions fail in a predictable way. The buyer compares spec sheets, spec
sheets are marketing, and the things that actually decide whether they get what they wanted —
replacement part cost, failure rate, how long spares will exist, what it really sells for used —
appear on no spec sheet at all.

Three ideas do most of the work:

1. **Kill switches run before scoring.** A hard requirement failure is stated plainly and never
   scored, because a disqualification buried inside a number reads as merely weak rather than
   impossible.
2. **Every score carries an evidence grade, inline.** A = independently measured, B = reviewed but not
   measured, C = owner report, D = inference. Shown in the cell, so a confident-looking table cannot
   hide that half of it is inference.
3. **Sold is not asking.** Asking prices run far above sold and unsold listings linger forever. The
   two are never merged in a statistic or a chart row.

### What makes it different from asking a chatbot

Research fans out to one subagent per candidate, and **every finding lands in an append-only CSV
through a validating writer** — not in prose. A grade A/B/C row without a source URL is rejected. A
grade D row without a note explaining the inference is rejected. A criterion nobody could verify
becomes a visible D in the matrix instead of quietly disappearing.

This plugin ships **the marketplace's first Claude Code plugin hook**: a `PostToolUse` guard that
re-validates `evidence.csv` and `listings.csv` whenever one is written directly, so the rules hold
even when a record bypasses the writer.

The plugin has five skills:

- **introduce** — this skill; discovery and routing.
- **create-decision-matrix** — needs interview → kill switches → researched, weighted,
  evidence-graded matrix. The main event.
- **research-used-market** — what a used item actually sells for. Real listings, sold separated from
  asking, a fair-value range with every dot linked.
- **monitor-prices** — snapshot a market, re-run it later, report what moved or which listing beat a
  threshold.
- **create-decision-post** — turn a finished decision into a draft blog post.

## How to Introduce Yourself

### Step 1: Explain

```
Consumer — buying decisions made on evidence, not spec sheets.

- Compare options on the axes that decide it: parts horizon, consumable
  lock-in, real failure modes, 3-year cost — not the marketing bullets
- Kill switches first, so a hard requirement failure never hides in a score
- Every score graded A/B/C/D by how it was learned, shown in the cell
- What a used one actually SOLD for, never what someone is asking
- Watch a market over time and get told when something is worth acting on
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:

```
What are you working on?

- Choosing between options / is this one worth it   (create-decision-matrix)
- What's a used one actually worth                  (research-used-market)
- Watch a market and tell me when to act            (monitor-prices)
- Write up a decision I already made                (create-decision-post)
```

### Step 3: Guide to the Right Skill

| They want... | Skill | Command |
|---|---|---|
| Which of these should I buy? | create-decision-matrix | `/consumer:create-decision-matrix` |
| Is this listing a good deal? | create-decision-matrix | `/consumer:create-decision-matrix` |
| Help me find candidates, I have none | create-decision-matrix | `/consumer:create-decision-matrix` |
| Add another option to a comparison we did | create-decision-matrix | `/consumer:create-decision-matrix` |
| What's a used one worth? | research-used-market | `/consumer:research-used-market` |
| What should I offer / list it at? | research-used-market | `/consumer:research-used-market` |
| How much has this depreciated? | research-used-market | `/consumer:research-used-market` |
| Tell me if it drops below $X | monitor-prices | `/consumer:monitor-prices` |
| Has this market moved since last time? | monitor-prices | `/consumer:monitor-prices` |
| Turn this research into a post | create-decision-post | `/consumer:create-decision-post` |

## When to Use Which Skill

The one real ambiguity is **"is this used one a good deal?"** — that is a decision, not a pricing
question, so `create-decision-matrix` owns it and calls `research-used-market` for the pricing part.

| Situation | Skill |
|---|---|
| Choosing between two or more things | `create-decision-matrix` |
| Evaluating one thing against their requirements | `create-decision-matrix` |
| Pricing alone — no choice being made | `research-used-market` |
| Watching rather than buying today | `monitor-prices` |
| The decision is done; they want to publish it | `create-decision-post` |

## Plugin Map

```
consumer (this plugin)
  ├── create-decision-matrix — interview → kill switches → weighted graded matrix
  │     references/domains/  — 3d-printers, cnc-cutters, _TEMPLATE for new ones
  ├── research-used-market   — collect listings, split sold from asking, fair-value range
  ├── monitor-prices         — dated snapshots, drift reports, scheduled re-runs
  └── create-decision-post   — draft a write-up into the bytesofpurpose blog

  shared/
    ├── references/
    │     ├── used-market-sources.md — sources, URL patterns, ceiling rule, red flags
    │     ├── record-format.md       — evidence.csv / listings.csv schemas and rules
    │     └── artifact-design.md     — the visual system and the honesty contract
    ├── assets/exemplar-comparison.html — one rendered reference, synthetic data
    └── scripts/
          ├── record.sh      — the one command that writes a finding
          ├── records.py     — every validation rule, stated once
          └── pricestats.py  — median, quartiles (withheld below n=8), sold-vs-asking gap

  hooks/  — PostToolUse validation of evidence.csv / listings.csv
```

## Domain Packs

`create-decision-matrix` loads a **domain pack** for the category: the criteria, the 1–5 anchors, the
kill switches, the weighting profiles, and a question bank in plain language.

- **3D printers** and **CNC routers / laser cutters** ship with packs.
- **Any other category** builds criteria from first principles using the pack template — and offers to
  save the result, so the next person in that category gets it for free.

## Requirements

- Python 3 (standard library only — no installs).
- `WebSearch` / `WebFetch` for research. Login-walled marketplaces are collected by paste, on purpose:
  their terms prohibit automated collection.
