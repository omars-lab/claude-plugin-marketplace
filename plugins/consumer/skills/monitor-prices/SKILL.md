---
name: monitor-prices
description: Watches a used market over time — saves each price research run as a dated snapshot, re-runs it later, and reports what moved or which listing beat a threshold. Use when someone wants to track prices, watch for a deal, be told if something drops, or see how a market has moved since last time. Triggers on "track prices for X", "let me know if it drops below $Y", "watch for a deal on X", "has this gotten cheaper", "I'm not in a rush". It builds on research-used-market, which does the actual collection — use that skill directly for a one-time "what's this worth" question.
---

# Monitor Prices

There is no live crawler here, and pretending otherwise would set the wrong expectation. What works
instead is honest and nearly as useful: **save each research run as a dated snapshot, and re-run it
on a schedule.** Each run compares itself to the last and reports what moved.

Say this plainly to the person. It is a repeatable research run whose results accumulate — a good fit
for a market that moves over weeks, a poor one for a market that moves in minutes.

Two levels, and only the first is always worth doing.

Track a monitor setup with `TaskCreate` / `TaskUpdate` — writing the snapshot, drafting the
unattended prompt, and registering the job are separate steps, and a half-registered job that never
fires is worse than none.

---

## Level 1 — Snapshot (always do this)

A snapshot is **the dated listings file plus a small context sidecar.** Keep the rows, not just the
statistics: recomputing later with different filters is usually the point, and a stats blob can't be
re-cut.

```
research/pricewatch-<slug>-<YYYY-MM-DD>.csv     the listings.csv from this run, untouched
research/pricewatch-<slug>-<YYYY-MM-DD>.json    run context — see references/monitor.md
```

The sidecar holds only what isn't per-listing: the exact model and variant, the collection date,
location and radius, which sources were used *and which were skipped*, the new-equivalent ceiling,
and the alert threshold as a dollar figure.

Statistics are **not** stored. They are recomputed from the CSV on every comparison:

```bash
python3 shared/scripts/pricestats.py research/pricewatch-<slug>-<YYYY-MM-DD>.csv
```

That way a threshold change — the n≥8 quartile rule, say — applies retroactively to old snapshots
instead of leaving stale numbers behind that disagree with the current ones.

Tell the person where the files are, and that handing them back on a later run gives them a trend
instead of a fresh guess.

---

## Level 2 — Recurring run

**Offer this once**, and only when they're watching a market rather than buying today. Signals: "let
me know if it drops", "I'm not in a rush", "track this for me". Don't offer it to someone with a
listing open who needs an answer now. If they decline, don't raise it again.

Use `AskUserQuestion` to settle the three things an unattended run can't ask about later:

> **"What should wake you up?"** — a dollar threshold / any movement in the median / only a listing in
> your area
> **"How often?"** — weekly / every two weeks / monthly
> **"How long before we stop?"** — a month / three months / until I say

Then read `references/monitor.md` and register the job. Registration follows this marketplace's
background-job conventions — `cron-manager` owns that pattern, and `monitor-prices` supplies the
prompt rather than inventing its own scheduling.

An unattended run **cannot ask questions and cannot receive a paste.** So it works from what fetches
cleanly, and it must **name the sources it skipped** in its report — otherwise a shrinking sample
reads as a falling market.

---

## What a scheduled run reports

Lead with the answer to *"should I act?"*, never with a data dump.

- **Nothing moved** — one line. Median, n, "no change worth acting on." Resist padding it out.
- **The market moved** — the new median, the delta, and the likely cause if identifiable. A step
  change usually means a successor launched; check for a product announcement before speculating.
- **A listing beat the threshold** — lead with it. Price, condition, location, link, and how it
  compares to the median. This is the entire reason the monitor exists.

**Two snapshots is a comparison. Three or more is a trend.** Only at three should a run estimate a
monthly rate or advise on waiting.

---

## Winding down

Tell them how to stop it, and stop when they say so.

If a monitor has run several times with nothing to report, **say that plainly and offer to widen the
radius, loosen the threshold, or end it.** A monitor that reports nothing forever should be retired,
not left running — an unread recurring notification is worse than no monitor, because it trains the
person to ignore the one that eventually matters.

---

## Reference files

- `references/monitor.md` — the sidecar schema, the unattended prompt, drift reporting, cadence, and
  how to register the job. Read before Level 2.
- `shared/references/record-format.md` — the `listings.csv` a snapshot is made of.
- `shared/references/artifact-design.md` — before drawing drift into a chart.
- `shared/scripts/pricestats.py` — recompute stats from any snapshot.

Collection itself belongs to `research-used-market`; this skill schedules and diffs it rather than
reimplementing it.
