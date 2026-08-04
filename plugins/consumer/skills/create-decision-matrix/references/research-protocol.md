# Research Protocol

Read before Step 4. The goal is a score you can defend with a source, not a score that sounds right.

`research-candidates.md` covers how to fan this out to subagents. This file is what each of them
does.

---

## Evidence hierarchy

Ranked by how much a claim should move a score. The grade in `evidence.csv` follows from where the
claim sits here.

| # | Source | Grade it supports |
|---|---|---|
| 1 | **A test on the actual unit**, measured. Only available for a used item you can inspect. Beats everything. | A |
| 2 | **The manufacturer's own support forum**, last 6 months. Highest-signal source reachable from a browser, and the one most comparisons skip. | A or C |
| 3 | **Published end-of-life and spare-parts policies.** A vendor that publishes dates is telling you something real. One that doesn't caps that criterion at 2. | A |
| 4 | **Vendor spec sheet — hard ceilings only.** Maximum temperature, power, capacity, dimensions. Checkable, and vendors don't lie about them. Every *performance* claim on the same page is marketing. | A for ceilings, D for claims |
| 5 | **Retailer parts pages.** The fastest way to a real maintenance number: price the wear part, the consumable, the service kit. | A |
| 6 | **Independent reviews that measure things.** One review that runs a test and reports numbers beats ten that describe the unboxing. Weight recency heavily — a two-year-old review of something that's had firmware updates describes a different product. | A if measured, B if described |
| 7 | **Reddit, YouTube, forums outside the vendor's.** Useful for failure patterns and long-term ownership, unreliable for anything quantitative. | C |

**The forum is the move that gets skipped and shouldn't be.** Search the model name plus failure
words — `accuracy`, `fails`, `warranty`, `won't`, `broke`, `firmware`. Then read the *responses*: how
fast and how well the vendor replies **is** the support-quality score, observed rather than claimed.

---

## Searches to run, per candidate

All six. They're one round of searching and they are the difference between a matrix and a guess.

1. `<model> review <current year>` — reviews that measured something
2. `<model> problems OR issues OR failure` — the failure pattern, ideally on the vendor's forum
3. `<model> price` — current, not launch. Prices drop and models get discontinued into clearance
4. `<model> end of life OR discontinued OR spare parts` — the ownership horizon
5. `<model> <the common wear part> price` — the maintenance number that drives TCO
6. `<manufacturer> support response time` — once per brand, not per model

Also verify for every candidate: **is this still sold, and has a successor been announced?**
Something superseded three months ago is either the best value on the market or a trap with a
12-month parts clock, and which one depends entirely on the published policy.

**Search before you conclude, always.** Lineups turn over fast enough that recalled knowledge is
routinely a generation stale, and a recommendation built on it can reverse completely on one search.
If a recommendation changes mid-research, say it changed and why — that's the process working, and
watching it change is often more useful to the person than the conclusion.

---

## Red flags

**In a vendor's or seller's claims:**

- **A claimed capability that exceeds the hardware's own stated ceiling** — a material above its
  maximum temperature, a speed above its rated maximum, a capacity beyond its published spec. The
  highest-value tell available, and it generalizes to every category. One impossible claim means
  every other claim in the same listing is unverified.
- Specs quoted as "up to" with no test conditions — especially speed.
- "Originally retailed for $X" as the main price justification. Original retail is an anchor, not a
  value.
- Capacity quoted without saying whether it applies in every mode. Multi-tool and multi-head machines
  frequently lose working area when the second one engages.

**In your own research:**

- **All your sources trace back to the same press release.** Two "reviews" published within a day of
  launch with the same numbers are one source.
- **You can't find a single negative report.** Either it's under six months old, so nobody has found
  the problems yet — say so — or you haven't looked at the vendor forum.
- **The complaints are all from one firmware or hardware revision.** Check whether it's been fixed
  before scoring it.
- **Every candidate is scoring 4s and 5s.** That is a research failure, not a market full of
  excellence.

---

## Reporting research honestly

- Say when a finding is recent versus old, and where it came from.
- **When the forum contradicts the reviews, report both** and say which you weighted more and why.
  The forum usually wins: owners report what happened, reviewers report a loaner.
- **When you couldn't verify something, record a grade-D row with a note saying what you checked** —
  never a skipped row, never an unmarked guess. An unmarked guess inside a matrix is worse than an
  admitted gap, because the table makes it look like evidence.
- **Distinguish "no reports of problems" from "no problems."** For anything under six months old
  these are very different statements and only one of them is true.
- **Say when nobody publishes comparable data.** In most categories no two sources measure the same
  thing the same way. When that's true, it's a finding about the category and the person should hear
  it — it tells them how much to trust *any* comparison, including this one.
