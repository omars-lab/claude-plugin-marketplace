# Scoring Machinery — Kill Switches, Anchors, Weights, TCO

Read before Step 5. This file is the **domain-independent machinery**. The criteria themselves, their
anchors, and the weighting profiles live in `domains/<domain>.md`. If you find a specific product
criterion written here, it's in the wrong file.

---

## Kill switches run first

A kill switch is a **hard requirement failure**, not a low score. Anything that fails one is out,
named plainly with the specific reason, and **not scored.**

This ordering is the single most important structural rule in the skill. Scoring a disqualified
candidate buries the disqualification inside a number, where a 1 on one criterion gets averaged
against 5s elsewhere and the thing that made it impossible turns into a mild weakness. A table that
does that is worse than no table, because it launders the disqualification into arithmetic.

Every domain's kill switches come from the same six shapes:

1. **Capacity below the requirement** — it physically cannot handle the largest / hardest thing they
   named.
2. **A physical ceiling below what they need** — temperature, power, speed, precision, load. Check
   the vendor's own stated maximums. A vendor claiming something that exceeds its own spec sheet is
   telling you about the vendor, not the capability.
3. **Orphan consumable or media format** — a shrinking supplier list, or proprietary with one source.
4. **End-of-life already announced**, with parts availability ending inside their ownership horizon.
5. **Environment incompatible** — power service, ventilation, noise, floor loading, or a
   connectivity model their site won't allow.
6. **No repair path** — no spares channel, no service network, no community, no schematics.

If a candidate fails one, say which and why in one sentence. If it fails on a requirement the person
might be flexible about, say that too — sometimes the requirement is softer than it sounded, and
that's their call to make, not yours to make silently.

---

## Anchors: what makes a score mean something

Score **1–5**. Every criterion needs written anchors so a 4 means the same thing across candidates,
across domains, and six months from now.

Anchor rules:

- **Anchor 1, 3 and 5 at minimum.** 1 = the failure case someone would return it over. 3 = ordinary,
  what a competent mid-market option does. 5 = genuinely excellent, not merely "good".
- **Anchors describe observable outcomes, not adjectives.** "±0.1 mm held across a batch" is an
  anchor. "Excellent precision" is a vibe with a number attached.
- **Say how to measure it.** An anchor nobody can check is decoration.
- **Never let 5 be aspirational.** If nothing on the market reaches the 5, the anchor is wrong and
  every score compresses into 2–3, which destroys the comparison.

A criterion where every candidate scores the same is doing no work. Either the anchors are too coarse
or the criterion doesn't discriminate in this category — drop it and say you did.

---

## Evidence grades travel with scores

Every score carries a grade — **A** measured, **B** reviewed, **C** owner-reported, **D** inferred —
recorded in `evidence.csv` and shown **inline in the matrix cell**, never in a footnote.

A confident-looking table must not be able to hide that half its cells are inference. If a comparison
comes out mostly D, that is the finding, and the output should show it rather than smooth it over.
See `shared/references/record-format.md` for the rules the writer enforces.

---

## Weighting profiles

Weights come from the **use case**, established in Step 2 — not from the person's stated priorities,
which are usually a restatement of whatever they read last.

Each domain pack carries 3–4 profiles as columns, **each summing to 100.**

```
Weighted score = Σ (criterion score × weight) ÷ 100     Max 5.0
```

Mechanics that matter:

- **Pick one profile, don't blend.** Blending produces a flat weight vector, and a flat vector is the
  same as not weighting at all.
- **Show the weights next to the scores.** A weighted total the person can't reconstruct is a number
  they have to take on faith, and the whole point is that they don't have to.
- **If they disagree with a weight, change it and re-run.** That's the feature. A matrix that can't
  be re-run under different weights is a conclusion wearing a table's clothes.
- **Sensitivity check the close ones.** If the ranking flips under a small weight change, the honest
  answer is "these two are equivalent, pick on something else" — not a winner by 0.04.

---

## TCO, computed separately

```
TCO over N years =
      Purchase price
    + (wear parts per year × unit cost × N)
    + (consumables per year × unit price × N)
    + (maintenance kits + service × N)
    + (estimated downtime hours × their hourly cost)
    + (waste / scrap rate × material spend)
    - (realistic resale at year N)

Cost per usable output = TCO ÷ (output per year × first-time-right rate × N)
```

Two terms people always forget, and they are usually the two that decide it:

- **The unit of replacement when the common failure happens.** A $30 part and a $300 sealed assembly
  are the same failure with a 10× cost difference. Find out which one it is before concluding
  anything.
- **First-time-right rate.** Something $1,000 cheaper that scraps 25% of its output is not cheaper.

**Compute TCO separately from the weighted score and cross-check them.** They are built from
different inputs, so agreement is a real signal and disagreement means one of the inputs is wrong.
If the weighted winner is also the most expensive to run, go find out why before you recommend it.

---

## Reading the finished matrix

1. **Kill switches first** — is anything disqualified hiding in the scores? It shouldn't be here at
   all.
2. **Look at the grade column before the score column.** A 5 with a D beside it is a hope.
3. **Anything within 0.3 points is a tie.** Say so. Break it on the criterion the person cares most
   about, on TCO, or on which vendor they'd rather call at 9pm when it fails.
4. **A one-criterion winner is a real pattern** — a candidate that wins exactly one axis and loses
   everywhere else. Name what that one axis is and let them decide whether it's the one that matters.
5. **Check the loser you expected to win.** If a candidate scored far below expectation, confirm it's
   a real deficit and not a research gap wearing a low score.

---

## Adding a candidate later

1. Run the kill switches. Most candidates die here — that's the point.
2. Score against the same anchors, recording each row with its grade and source.
3. Recompute weighted totals under the same profile.
4. Recompute TCO and cross-check.
5. Re-read the ties.

Same criteria, same weights, same anchors. That consistency is the entire reason for scoring rather
than vibing, and it's what makes the matrix worth keeping.
