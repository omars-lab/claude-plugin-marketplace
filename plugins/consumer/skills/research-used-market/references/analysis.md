# Analysis — Normalization, Statistics, Localization

Read before Step 2. **The ceiling rule and sold≠asking are stated in
`shared/references/used-market-sources.md`** and not repeated here; they govern what you say, this
file governs what you compute.

---

## Normalize before you compute

Raw listings aren't comparable. Six adjustments, in order:

1. **Split sold from asking.** Never compute one statistic across both. Report them as two
   distributions. With only asking prices, say so and note that the whole analysis reads high.
2. **Subtract or tag bundles.** A machine sold with $600 of accessories is not a comparable data
   point. Either subtract a conservative accessory value and mark the row adjusted in `notes`, or tag
   it and exclude it from the headline number. **Be conservative** — used accessories are worth far
   less than retail, often 30–40%.
3. **Separate variants.** Different generations, trims, and capacities are different products. With
   enough of each, chart them as separate series. Without, keep the one they're actually asking about
   and **say what you dropped**.
4. **Tag condition.** Condition is the second-largest price driver after variant. A "fair" unit and a
   "like new" one in the same cloud makes signal look like noise.
5. **Flag local versus shipped.** Local pickup typically runs 15–30% below shipped — smaller buyer
   pool, and shipping bulky things is painful. Genuinely different markets.
6. **Drop the junk.** Parts-only units, wrong-model matches, listings with no real price ("$1
   auction", "message me"). Keep parts units as a separate floor tier if there are several.

---

## Statistics

Run `pricestats.py` rather than computing by hand — the thresholds below are encoded in it, and a
hand-computed quartile is exactly where they get quietly ignored.

```bash
python3 shared/scripts/pricestats.py research/listings.csv
python3 shared/scripts/pricestats.py research/listings.csv --local "Austin"
```

**Use median.** Small samples plus occasional collector or desperation pricing means the mean lies.
Report:

- **Median** — the headline number
- **Interquartile range (25th–75th)** — the fair-value band, and the thing you actually recommend
  against
- **Min and max** — with a note on what they are. Extremes are usually explicable rather than random
- **n** — always, in the chart and in the prose

**A buyer's target is the 25th percentile; a seller's is the 60th.** Both are achievable, neither is
the median. Say which you're recommending and why.

### Sample-size thresholds

| n | What you can honestly say |
|---|---|
| 1–3 | Nothing statistical. These are anecdotes — report them individually |
| 4–7 | A rough midpoint with a wide caveat. **No quartiles** |
| 8–14 | Median plus a range, flagged provisional |
| 15–30 | A real distribution. Quartiles are meaningful |
| 30+ | Confident. You can start reading condition and regional effects |

Don't compute a percentile on 5 points and present it as a market. **State the thinness in the same
sentence as the number**, not in a footnote below it — a caveat that arrives after the number has
already been read isn't a caveat.

The **n≥8 quartile threshold is coupled** to `pricestats.py` and to the chart spec in
`shared/references/artifact-design.md`. If one changes, all three change.

**Outliers: flag, don't silently delete.** A price at 3× the median usually has a reason — a rare
variant, a bundle you missed, a listing that never sold. Investigate first, then say what you did.

---

## Localization

Location moves used prices more than most buyers expect. Three effects:

1. **Market density.** Major metros have more supply and more competition; prices run lower and
   turnover is faster. Thin markets have fewer units and stickier prices.
2. **Shipping feasibility.** Heavy or fragile items barely travel, so local supply dominates and
   regional variation is large. Small light items are effectively one national market.
3. **Regional demand.** Some categories cluster near universities, industry hubs, or hobby scenes. A
   local glut or drought is real and worth naming.

**How to handle it:**

- Collect a local set and a national set separately when the item is bulky.
- Report both: *"nationally $900–1,200 shipped; locally in your metro, two listings at $750 and
  $825."*
- If local supply is thin, name the travel radius that would open it up. A three-hour drive is often
  worth several hundred dollars, and nobody computes that for themselves.
- For heavy items, add the real cost of shipping or freight into any non-local comparison. A
  "cheaper" unit two states away frequently isn't.

---

## Depreciation and timing

With dated sold data spanning several months, look at the trend:

- **Steady decline** — normal. Estimate the monthly rate and tell them what waiting costs or saves.
- **A cliff** — usually a successor launched. Check for a recent product announcement before
  speculating; that is by far the most common cause of a step change.
- **Firming or rising** — supply has dried up, or the model has a following. Worth naming, because it
  inverts the usual "wait for a better price" advice.

Seasonality is real in some categories. Mention it if you see it in the data; don't invent it from
intuition.

**Two dated snapshots is a comparison. Three is a trend.** Only at three should you estimate a
monthly rate or advise on waiting — see `monitor-prices` for accumulating them.
