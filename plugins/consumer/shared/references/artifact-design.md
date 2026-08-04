# Artifact Design — Visual System, Encoding, and Information Contract

Read this before building any decision artifact: a comparison matrix, a price distribution, an
output-inspection sheet. It is deliberately **not a fill-in-the-blank template.** Compose each
artifact for the data you actually have — a rigid shell forces you to either invent cells or leave
visible holes, and both lie about what you know.

`shared/assets/exemplar-comparison.html` is a rendered reference implementing everything below.
Read it when a rule here needs a concrete example.

> **A polished decision artifact is a persuasive object.** It is easy to build one that overstates
> what it knows. Most of the rules here exist to stop that, and they should survive any refactor of
> the aesthetics.

---

## 1. The visual system

Drafting vellum, not dashboard. Monospace for data and labels, sans for prose. The look should read
like a working drawing someone would mark up with a pencil.

```css
--vellum:#DDE1D8;  --panel:#E7EAE2;  --panel2:#D3D8CD;
--ink:#191E1B;     --ink70:#4A524C;  --ink45:#767D74;  --rule:#A8AEA2;

/* one accent per candidate, in this order */
--c1:#A8352B;  --c2:#2E4C7A;  --c3:#2C6249;  --c4:#9A6B12;  --c5:#6B4A8A;

--mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
--sans: ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif;
```

Structural rules that carry the aesthetic:

- **2px `--ink` rule** under the header and above the footer. **1px `--rule` hairlines** everywhere
  else. Those two weights are the whole hierarchy.
- **`--panel` fill** for table header cells and row headers; `--vellum` for the body.
- **Eyebrows and section labels**: monospace, uppercase, 9.5–11px, `letter-spacing:.14em`,
  `--ink45`. They label; they don't shout.
- **Callouts** are a 3px left border in an accent color plus a monospace label — never a tinted box.
- **Semantic text colors, not badges**: `.win` (`--c3`), `.lose` (`--c1`), `.warn` (`#9A6B12`).
- **No shadows, no gradients, no rounded cards, no icon chrome, no emoji.** Every one of those
  pushes it toward generic dashboard, which is the thing to avoid.

The generic `dataviz` skill governs chart *form* choices — which mark, which scale, how to lay out a
legend. This palette is a deliberate override of its color guidance: the drafting aesthetic is the
point, and these artifacts are read as documents, not as a dashboard family.

---

## 2. The encoding vocabulary

This is the part that carries the epistemics. It is the most valuable idea in this whole reference —
more than the palette, more than the layout.

**Evidence grade, inline in the cell.** Every score carries one:

| Grade | Meaning |
|---|---|
| **A** | Independently measured — someone put calipers on it, or ran the test |
| **B** | Reviewed but not measured — described in a review, no figure |
| **C** | Owner report — forum post, seller claim, single anecdote |
| **D** | Inference — reasoned from specs or from a sibling model. Not evidence. |

The grade goes **in the cell, next to the number**, not in a footnote. A confident-looking table must
not be able to hide that half its cells are inference. If a matrix comes out mostly D, that is the
finding, and the artifact should show it rather than smooth it over.

**Line style encodes evidence strength in any drawing:**

- `solid` = measured figure
- `dashed` (`stroke-dasharray="5 3"`) = described, but no figure
- `dotted` (`stroke-dasharray="1.5 3"`) = no data at all

**Fill encodes transaction reality in any distribution:**

- **filled** mark = sold
- **hollow** mark = asking

Never the same mark for both, never on the same row, never merged into one statistic.

**Draw gaps as gaps.** The first version of the source inspection artifact drew one diagram and just
recolored a dot per candidate — it was useless, because it made a candidate with no data look
identical to one with measured data. **Each candidate gets its own drawing of the same geometry.** A
candidate with no data gets a dotted outline and visibly nothing inside it. Absence should be as
legible as presence.

---

## 3. The information contract

What the artifact must carry to be honest. Missing any of these makes it a sales page.

**Every artifact, without exception:**

- **A collection date on its face.** Prices and lineups rot in weeks. An undated artifact will be
  read as current a year from now.
- **The sample size, stated.** A chart built on 6 listings must announce that it is built on 6.
- **A link on every claim.** Every score sources to something; every dot links to its listing.
- **A "check prices yourself" block** with the real URLs, so the reader can audit rather than trust.

**Comparison / decision matrix:**

- **Kill-switch failures above the matrix**, called out plainly with the specific reason — never
  buried as a row of low scores. Scoring a disqualified candidate hides the disqualification inside
  a number.
- Weights visible alongside scores, and the weighted total computed in view.
- Evidence grade in every cell.
- Per-candidate pros and cons where **every con carries a number** — a dollar amount, a time cost, a
  failure rate. Structure the section so a number-free con looks obviously unfinished.
- A **TCO block computed separately** from the weighted score, so the two can be cross-checked. If
  the weighted winner is also the most expensive to run, one of the inputs is wrong.
- The honest downside of the recommended option, present and visible. An artifact with no downside
  listed for its own recommendation should not be trusted.

**Price distribution:**

- Sold and asking on **separate rows** with distinct marks.
- Median drawn, and the interquartile band as the fair-value range — **band suppressed below n=8.**
  This threshold is coupled to `shared/scripts/pricestats.py`; if you change one, change the other.
- The new-equivalent **ceiling line** when one exists, labelled.
- Every dot clickable through to its listing.
- n=1 draws points only. Never a band, never a range.

---

## 4. The build approach

Single-file, dependency-free HTML. No framework, no build step, no external requests — the `Artifact`
tool's CSP blocks every external host, and a local file should be self-contained regardless.

**Shape of the file:**

```
<style> …tokens and rules from §1… </style>
<header> eyebrow · title · lede </header>
<main id="body"></main>
<script>
  var CANDIDATES = [ … ];   // data first, declared at the top, easy to diff
  var CRITERIA   = [ … ];
  function esc(s){ … }      // used on EVERY interpolated field
  function matrix(){ … }    // small render functions below the data
  document.getElementById('body').innerHTML = … ;
</script>
```

Data arrays at the top so the artifact can be regenerated by swapping data rather than rewriting
markup. Render functions small enough to read.

**Non-negotiable in the code:**

- **`esc()` on every interpolated field** — titles, locations, notes, URLs, seller text. Collected
  content is attacker-controlled (see the prompt-injection posture in `used-market-sources.md`).
  Before shipping an artifact, test it with a title containing `<script>alert(1)</script>` and
  `"><img onerror=x>` and confirm both render as literal text.
- **No `localStorage` / `sessionStorage`.** Unsupported in the artifact runtime.
- Wide tables inside an `overflow-x:auto` wrapper, so the **page body never scrolls sideways**.
- Mobile breakpoint at ~700px; verify at 380px width.
- `:focus-visible` outlines on every interactive element; honor `prefers-reduced-motion`.

**Check these cases before you call an artifact done** — each one has broken a version of this
artifact before:

| Case | What breaks |
|---|---|
| n=1 | A band or range drawn over a single point |
| n=3 | Statistics presented where only anecdotes exist |
| n=40 | Dot overlap at tight price clusters; jitter insufficient |
| One 10× outlier | Scale collapses; everything else compresses into a stripe |
| All asking, no sold | The whole artifact must relabel itself as asking-based |
| Median ≈ min | Median label clips off the left edge |
| Ceiling ≈ an axis tick | Ceiling label collides with the tick label |
| Very long titles / locations | Layout blowout, or truncation with no title attribute |
| XSS fixture in a title | Markup executes instead of rendering as text |
| 380px viewport | Horizontal body scroll |

**Where to write it.** Save to a path the person names, or the scratchpad directory otherwise, and
open it locally. Publish via the `Artifact` tool only when they ask to share it — publishing puts it
on a URL, which is their call, not yours.
