---
name: create-decision-post
description: Turns a finished purchase decision into a draft blog post for the bytesofpurpose blog — the method, the evidence, and what the research actually changed. Use after a decision matrix or a used-market price study, when someone wants to write up how they decided, publish their research, or turn a comparison into a post. Triggers on "write this up", "turn this into a post", "blog this", "I want to share how I decided". Writes a draft file for review and never commits or pushes.
---

# Write Up a Decision

A purchase decision is worth writing up when the **method** generalizes past the purchase. Nobody
needs another "I bought X and I like it." What people can use is the check that killed a candidate,
the source that beat every review, the moment the recommendation reversed.

So the post is about **how the decision was made**, and the product is the worked example. If the
method didn't generalize, say so and don't write the post — a thin write-up costs the blog more than
it earns.

Track it with `TaskCreate` / `TaskUpdate`: gather, choose the angle, draft, then hand back for review.
The last step is a handoff, not a publish.

---

## Step 1: Gather what's already there

A finished decision has the material lying around. Pull it before writing anything:

- `evidence.csv` — the grades tell you where the research was thin, and the thin places are usually
  the interesting part
- `listings.csv` and the `pricestats.py` output — the sold-versus-asking gap is a fact worth a
  paragraph on its own
- The matrix, the kill switches, the TCO block
- **What changed mid-research.** If the recommendation moved, that's the post's spine

If the decision happened in this conversation, it's all in context. If not, ask for the paths.

## Step 2: Choose the angle

Use `AskUserQuestion` — the same research supports very different posts, and the choice changes
everything downstream.

> **"What's the post actually about?"**
> - **The method** — how to decide well in this category (`kind: framework`)
> - **What the research found** — the surprising facts, the market read (`kind: research`)
> - **The decision itself** — what they bought and why (`kind: reflection`)

Also ask **who it's for**: someone buying the same thing, or someone who'll never buy one but wants
the reasoning. The second audience is larger and needs the product details compressed hard.

## Step 3: Draft

Write to
`/Users/omareid/Workspace/git/projects/omars-lab.github.io/bytesofpurpose-blog/blog/YYYY-MM-DD-<slug>.md`.

Use `.md`. Only use `.mdx` if the post actually imports a JSX component — the extension is a
capability, not a default.

### Frontmatter

```yaml
---
slug: how-i-decided-what-to-buy
title: "How I Decided What to Buy"
kind: framework
sidebar_label: "Deciding What to Buy"
description: "One sentence that says what the reader gets. Shows up in listings and search."
authors: [oeid]
tags: [decision-making, research]
date: 2026-08-04T10:00
draft: true
---
```

- `slug` matches the filename after the date, and is what the URL becomes — **don't change it after
  publishing.**
- `kind` comes from the existing vocabulary. `framework` for a method, `research` for findings,
  `project` for a build, `reflection` for a retrospective. Check what's already in use rather than
  inventing one.
- `date` includes a time (`T10:00`) so same-day posts order deterministically.
- **`draft: true` on every new post.** The author flips it, not you.

### Shape

```
[Opening hook — 2–4 sentences. The concrete moment, not a thesis statement.
 "The listing said it could print a material its own nozzle couldn't reach."]

<!-- truncate -->

## The problem with how this normally goes
[Why spec-sheet comparison fails in this category.]

## What I actually did
[The method. Steps a reader can copy — this is the part with reuse value.]

## What the research turned up
[2–4 findings. Each with its number and where it came from.]

## What changed my mind
[The reversal. The most valuable section and the one people leave out,
 because it reads as having been wrong. It reads as having checked.]

## What I'd tell someone starting from scratch
[The compressed version. Three or four bullets.]
```

`<!-- truncate -->` goes after the hook — everything above it is the listing preview, so it has to
stand alone.

### Rules that carry over

- **Every claim keeps its number and its source.** The evidence grades exist for exactly this; a post
  that drops them is less honest than the research behind it was.
- **Say what wasn't verified.** A post that reports only the confident findings misrepresents the
  process, and the gaps are usually the more useful half.
- **Date-stamp the market read.** Prices rot in weeks. A sold-price range without "as of August 2026"
  will be quoted back wrong a year later.
- **Say the sample size** wherever a distribution appears.
- Show a real listing quote if it's the point, but **strip anything identifying** — seller name,
  exact location, a URL that resolves to a person.

Real product names and real findings are appropriate here. **This is the author's own blog, not the
public skill library** — the abstraction rule in the marketplace's CLAUDE.md governs skill examples,
not this post.

### Diagrams

The blog renders Mermaid in fenced ```mermaid blocks. A decision flow or a criteria tree often earns
one. A screenshot of a table doesn't — write the table in Markdown so it's searchable and readable on
a phone.

## Step 4: Hand it back

**Never commit and never push.** Report the path, quote the frontmatter, and say what's left to
decide — usually the `kind`, the tags, whether a social image is needed, and flipping `draft`.

Offer the local preview: `yarn start` in the blog repo, then open the post.

---

## Reference files

- `shared/references/artifact-design.md` — if the post ships an interactive chart rather than a
  Markdown table.
- `shared/references/record-format.md` — what the evidence grades in `evidence.csv` mean, so the post
  reports them correctly.
