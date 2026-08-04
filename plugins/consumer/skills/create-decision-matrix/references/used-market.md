# Used Market — The Last-Gen Flagship Play, and Buying One Safely

Read whenever a used item is in play, **and whenever the budget is tight relative to the
requirements** — because a generation-old flagship is often the best value on the board and most
buyers never consider it.

**Sources, URL patterns, the ceiling rule, the listing schema and listing red flags are in
`shared/references/used-market-sources.md`.** They are not repeated here. This file covers what's
specific to putting a used item into a decision matrix.

For actual price research — pulling sold prices and producing a distribution — hand off to the
`research-used-market` skill rather than doing it inline.

---

## Part 1 — The last-gen flagship strategy

The best value in most categories isn't the best new thing you can afford. It's the thing that *was*
the best, one generation ago, bought used.

**Why it works.** Flagships are built to a durability standard the budget line isn't. They depreciate
on a schedule set by marketing cycles rather than by wear. A three-year-old flagship has usually
consumed a small fraction of its service life while losing 60–75% of its price.

**Always price this option**, even unasked. Add it as a real candidate in Discovery mode. In Compare
mode, mention it once if a used flagship would clearly beat everything on their list at the same
money, then let them decline.

### When it wins

- The category's core capability hasn't changed much in a generation — the frame, the envelope, the
  rigidity, the optics, the motor.
- It's mechanically simple to service, with parts available.
- The seller is an owner who used it lightly, not a reseller flipping auction lots.
- The vendor publishes a spare-parts commitment with years left on it.
- The new-generation improvement is convenience or speed, not a capability they actually need.

### When it's a trap

- **The consumable format is proprietary and dying.** The single most common way a "great deal"
  becomes expensive. Check what the consumable costs and how many suppliers make it before anything
  else.
- **The common failure replaces a sealed, expensive assembly.** Where a routine failure means a
  $170–400 module instead of a $20 part, the cost curve has nothing to do with the purchase price.
- **End-of-service has passed**, or will inside their ownership window.
- **The new generation fixed a structural defect** rather than adding speed. Passive versus active
  thermal control isn't a spec bump.
- **The current entry-level model already beats it.** This is the check that ends most of these
  decisions — see the ceiling rule in `used-market-sources.md`. Work out the cheapest *new* thing
  meeting all the same requirements first; it's the anchor, and everything else is a discount off it.

---

## Part 2 — Score adjustments for used

Applied after scoring, before weighting. You are scoring **an unknown individual unit**, not the
model — these adjustments are what that difference costs.

| Criterion | Adjustment |
|---|---|
| Parts & service horizon | Cap at **3** unless the model is in active support with published spare-parts dates. Past end-of-service, cap at **1**. |
| First-time-right / reliability | **Subtract 1** unless the seller demonstrates a recent output. |
| TCO | Add an **unplanned-repair reserve of 15–20%** of purchase price. |
| Platform risk | No warranty. If the model is discontinued, set year-N resale near **zero** rather than optimistically. |

Note the adjustment in the row's `note` field so it stays visible. An adjusted score that looks like
a researched one is a small lie that compounds.

**A used unit and a new unit are not the same kind of candidate.** Say so in the output. The used one
carries variance the new one doesn't, and the matrix can show a central estimate but not that spread.

---

## Part 3 — Questions before you travel

1. **Exact revision and serial.** Revisions matter — vendors quietly swap subsystems mid-life and end
   support for the earlier revision years sooner.
2. **Total run hours**, and hours on each consumable module.
3. **What's been replaced, and when.**
4. **Why they're selling.**
5. **Modified? Which parts are original? Are the stock parts included?**
6. **Where has it lived** — climate, dust, abrasives, sunlight.
7. **A photo of it powered on showing the hours counter.** Not a stock photo.

A seller who can't answer 1, 2 and 5 either doesn't know the item or is a reseller. Price
accordingly.

---

## Part 4 — Inspection, in person

1. Verify revision and serial against what was stated.
2. Read the machine's own hours counter and compare it to the claim.
3. Run the calibration or self-test routine start to finish, **with any modified parts installed.**
4. Have it produce something real in front of you. "It powers on" is not a test.
5. Move every axis through full travel; listen for grinding or binding.
6. Inspect the work surface for damage and the business end for accumulated debris — that's evidence
   of past failures, which the seller may not mention.
7. Check consumable age and how they were stored.
8. Watch one full cold-start cycle.

Bring measuring tools and a test file. **Twenty minutes of measurement beats any amount of listing
text** — and it is the only way to earn a grade-A row on a used unit.
