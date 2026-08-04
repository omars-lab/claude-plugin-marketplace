---
name: create-decision-matrix
description: Builds a researched, weighted, evidence-graded decision matrix for buying a durable good — 3D printers, CNC routers and laser cutters, cameras, bikes, machine tools, instruments, appliances, vehicles. Use this whenever someone is choosing between products, evaluating a used listing, asking "which one should I buy", asking whether a specific item is worth the price, or comparing brands — even if they name only one item, even if they phrase it casually ("is this a good deal?", "found one on marketplace"), and even if they never say "compare" or "matrix". Also use it to extend or re-run a previous comparison with new candidates. It delegates used-market pricing to research-used-market; if the person only wants to know what something sells for and is not choosing between options, use research-used-market directly instead.
---

# Decision Matrix

Buying decisions go wrong in a predictable way: the buyer compares spec sheets, spec sheets are
marketing, and the things that actually decide whether they get what they wanted — replacement part
cost, failure rate, how long spares will exist — appear on no spec sheet at all. This skill forces
the comparison onto the axes that matter and says plainly what each choice costs.

Two jobs, in order: **understand what they actually need**, then **research candidates against that
need.** Never skip to recommending. A recommendation made before you know the largest part they need
to make is a guess wearing a lab coat.

Track the run with `TaskCreate` / `TaskUpdate` — one task per phase, plus one per candidate during
research. The research phase fans out to subagents and takes real time; without tasks, the person
watches a blank screen and you lose track of which candidate came back.

---

## Step 1: Route

Open with `AskUserQuestion`. One question, always this one:

> "Do you have specific ones in mind already?"
> Options: "Yes, I have a shortlist" / "I have one I'm considering" / "No — help me find candidates" / "I have a used listing to evaluate"

| Answer | Go to |
|---|---|
| Shortlist, or one item | Step 2, then Step 3 as **Compare mode** |
| No candidates | Step 2, then Step 3 as **Discovery mode** |
| Used listing | Step 2, then Compare mode, **plus** `references/used-market.md` |

Everyone goes through Step 2. Someone with a shortlist still needs their requirements pinned down,
because the requirements are what the weights are built from.

**Load the domain pack now.** Look in `references/domains/` for the category. If there's no pack,
read `references/domains/_TEMPLATE.md` and build the criteria from first principles — then offer at
the end to save what you built as a new pack.

---

## Step 2: Needs interview — in plain language

Read `references/discovery-questions.md` for the method, and the domain pack for that domain's
question bank and translation table.

**The rule that makes this work: ask about the person's world, not the product's specs.** They know
what they want to do. They do not know what capacity, tolerance, or throughput that implies, and
asking them is asking them to do your job.

Ask in rounds of **at most 3 questions**, with options every time, **2–3 rounds total.** Skip
anything the conversation already answered. On "I don't know", take the safe default from the
translation table, say what you assumed, and move on.

After the last round, restate what you heard in one short paragraph before any research. This catches
misunderstandings while they are still cheap.

---

## Step 3a: Discovery mode

They don't have candidates. Produce them — and **deliberately reach past what they already know to
name**, which is the whole value of this step.

1. **Search for what's current.** Lineups change fast enough that recalled knowledge is unreliable.
   Verify each candidate still exists and check for an end-of-life announcement.
2. **Reach up one tier.** Look at the professional or industrial tier above their band, not just the
   consumer line. Sometimes the tier above is barely more money used and solves the requirement
   outright.
3. **Reach back one generation, and price it used.** Do this every time, not only when asked. The
   best value in most categories is the item that *was* the flagship, bought used at 25–40% of launch
   price — flagships are built to a durability standard the budget line isn't, and they depreciate on
   marketing cycles rather than wear. `references/used-market.md` covers when this wins and when it's
   a trap. Include it as a real candidate with a real price, or say explicitly why it fails.
4. **Check the vendor refurb program.** Consistently overlooked, sometimes barely above private-party
   price, and it carries a warranty.
5. **Shortlist 3–5 spanning the tradeoff space** — not five variations of one thing. A good shortlist
   has a safe boring option, a value option, a capability option, and if their requirements allow it,
   a wildcard that wins if one of their assumptions turns out wrong.
6. **Name the tradeoff each represents in one line** before scoring. "The cheap reliable one." "The
   one that handles the hard materials but you'll fiddle with it." This is how a non-expert holds
   five options in their head.
7. **Confirm before deep research** with `AskUserQuestion` — let them drop any or add their own.
   Researching five candidates properly is real work; don't spend it on something they'd never buy.

## Step 3b: Compare mode

They named the candidates. Add one of your own only for a genuine gap — something that dominates one
of theirs on every axis at the same price, or something cheaper that meets every stated requirement.
Say why in one sentence and let them reject it.

Steps 2 and 3 above are still worth a pass even here: if a used last-gen flagship would clearly beat
everything on their list at the same money, mention it once, then let them decline.

---

## Step 4: Research — fan out

Read `references/research-protocol.md` for the evidence hierarchy and the searches, and
`references/research-candidates.md` for how to brief the subagents and what they must return.

**One subagent per candidate, spawned together.** Each researches its candidate against the loaded
criteria and appends its findings to a shared `evidence.csv` with
`shared/scripts/record.sh`. Initialize that file once, on the main thread, *before* spawning —
writers refuse to create it, so parallel agents can never race on the header.

The single highest-value move, and the one that gets skipped: **search the manufacturer's own
support forum for the model name plus failure words** — "accuracy", "fails", "warranty", "won't",
"broke". Filter to recent posts. Marketing tells you the thing is accurate; the forum tells you which
axis is off and how long the vendor took to answer the ticket. Report what you find there even when
it contradicts the reviews, and say how recent it is.

**Every score needs a source, and every gap needs to stay visible.** A criterion nobody could verify
becomes a **grade-D row with a note saying what was checked** — never a skipped row, and never a
quiet guess. The record format enforces this: grade A/B/C without a source URL is rejected, and
grade D without a note is rejected. A recorded gap shows up as a visible D in the matrix; a skipped
one silently narrows the comparison to whatever was easy to find.

When the subagents come back, read `evidence.csv` — not their prose summaries — and check it:

```bash
shared/scripts/record.sh check research/evidence.csv
```

If a candidate came back mostly D, **that is the finding.** Say so rather than smoothing it over.

---

## Step 5: Kill switches, then score

Read `references/criteria.md` for the scoring machinery, and the domain pack for that domain's kill
switches and criteria.

**Kill switches run first.** Anything that fails a hard requirement is out, stated plainly, and **not
scored.** Scoring a disqualified candidate buries the disqualification inside a number, where it
reads as merely weak rather than impossible.

Then score the survivors 1–5 against the pack's anchors, apply the weighting profile matching their
use case, and compute weighted totals. **Compute TCO separately and cross-check:** if the weighted
winner is also the most expensive to run, one of your inputs is wrong.

Anything within 0.3 points is a tie. Say it's a tie and break it on something real.

---

## Step 6: Output

```
## The call
[One paragraph: the recommendation, the price, the single most important reason.
If it's close, say it's close and give the tiebreaker.]

## What I assumed about your needs
[Bullets restating the requirements the matrix is built on, so they can spot a wrong one.]

## Ruled out immediately
[Kill-switch failures with the specific reason. Skip if empty.]

## The matrix
[Criteria as rows, candidates as columns, scores 1–5 with the evidence grade beside each,
weights and weighted totals visible.]

## Each one in plain terms
[Per candidate: 2–3 pros and 2–3 cons. This is where the person actually decides,
so it gets the most care.]

## What it costs you over 3 years
[TCO. Purchase + consumables + replacement parts + waste − resale.]

## What would change this answer
[2–3 specific conditions. "If you ever need X, the answer becomes Y."]
```

Offer an HTML artifact of the matrix when there are 3+ candidates or the comparison is close — read
`shared/references/artifact-design.md` first, and look at
`shared/assets/exemplar-comparison.html` for what it should come out like.

### Pros and cons: the rules that make them useful

A pro or con that could be copied onto any product's page is noise. Every one must be **concrete,
consequential, and grounded in an example from their world.**

**Every con carries a number** — a dollar amount, a time cost, or a failure rate. Structure the
section so a number-free con looks obviously unfinished.

**Weak:** "Proprietary consumables can be expensive."
**Strong:** "The wear part isn't separate — it's inside a sealed assembly, so a routine failure means
replacing the whole $180 unit instead of a $30 part. For the abrasive material you mentioned, budget
two a year."

Also required here:

- **Name the failure mode, not the feature.** "Fast" is a spec. "Fast enough that a failed job costs
  you 40 minutes instead of 9 hours, so iterating is cheap" is a decision input.
- **Give the honest downside of the one you're recommending.** Everything has one. A recommendation
  with no downside listed reads like a sales page and should not be trusted.
- **Flag new-product risk explicitly.** Something released in the last six months has no long-term
  reliability record. Say the release date and say that plainly. "No reports of problems" and "no
  problems" are different statements, and only one of them is true.
- **Translate every piece of jargon on first use,** in the same sentence, in a clause.

### Extending it later

Close by telling them the matrix is extensible: name another candidate and it gets scored on the same
criteria with the same weights, which is the entire reason for scoring rather than vibing. Re-run the
kill switches on anything new first.

---

## Reference files

- `references/discovery-questions.md` — the interview method and the universal question bank. Step 2.
- `references/domains/` — per-domain criteria, anchors, weights, kill switches, question bank.
- `references/criteria.md` — scoring machinery, weighting mechanics, the TCO formula. Step 5.
- `references/research-protocol.md` — evidence hierarchy, searches, red flags. Step 4.
- `references/research-candidates.md` — the subagent brief and its return contract. Step 4.
- `references/used-market.md` — last-gen flagship strategy, used scoring adjustments, seller
  questions, inspection checklist. Whenever a used item is in play **or** the budget is tight
  relative to the requirements.
- `shared/references/record-format.md` — `evidence.csv`, and why gaps have to be recorded.
- `shared/references/used-market-sources.md` — marketplace sources, the ceiling rule, red flags.
- `shared/references/artifact-design.md` — before building any artifact.

For the pricing sub-problem — what a specific used item actually sells for — hand off to
`research-used-market` rather than reproducing its method here.
