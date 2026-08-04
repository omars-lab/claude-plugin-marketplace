# Domain Pack Template

Copy this to `<domain>.md` when building criteria for a category with no pack yet. Everything
domain-specific lives in a pack; the machinery in `../criteria.md` never changes.

**Build the pack live, with the person, while you research.** Don't present an empty template and ask
them to fill it in — that's asking them to do the job they came to you for.

When you finish a comparison in a new domain, **offer to save the pack.** The next person in that
category gets the researched criteria for free, and that's most of the work.

---

## Choosing criteria

**8–14 criteria.** Below 8 and the comparison is coarse enough that everything ties. Above 14 and the
weights get so thin that no single criterion can move the result, which is the same as not scoring.

Group them so a reader can navigate the table. These four groups fit almost every durable good:

| Group | Asks |
|---|---|
| **A. Output / capability** | Does it do the thing, well enough, repeatably? |
| **B. Operability** | What is it like to actually use, for the person who'll use it? |
| **C. Sustainment** | What does keeping it running cost in money, time, and skill? |
| **D. Economics & risk** | What does owning it cost over the horizon, and what could strand it? |

Include a criterion only if it **discriminates** between real candidates in this category and
**maps to something the person said in Step 2.** A criterion where everything scores 4 is decoration.

Two that belong in nearly every pack, because they're where used and new decisions are actually won
or lost:

- **Parts & service horizon** — how long can this be kept alive, and does the vendor publish that?
- **Consumables ecosystem & lock-in** — open format with many suppliers, or one source that can
  reprice at will?

---

## Writing anchors

Anchor **1, 3 and 5** at minimum. Describe observable outcomes, not adjectives, and say how to check.

```
**N. <Criterion name>**
<One line on what this actually measures — and what it is commonly confused with.>
- 1 = <the failure case someone would return it over>
- 3 = <ordinary; what a competent mid-market option does>
- 5 = <genuinely excellent, and reachable by something on the market today>
*How to measure:* <a check someone could actually run, or a source that publishes it>
```

The three ways anchors go wrong:

1. **Aspirational 5.** If nothing on the market reaches it, every score compresses into 2–3 and the
   comparison dies.
2. **Anchors that restate the score.** "5 = excellent accuracy" says nothing. `±0.1 mm held across a
   batch` says something.
3. **Unmeasurable anchors.** If nobody publishes it and nobody can test it, every cell comes back
   grade D. Either find the measurable proxy or drop the criterion — and if you drop it, say why.

**Write the anchors so they mean the same thing across candidates and across years.** Anchoring to
"as good as the current market leader" rots the moment the leader changes.

---

## Kill switches

**4–7 of them**, each a hard requirement failure rather than a low score. Derive them from the six
shapes in `../criteria.md`: capacity below requirement, physical ceiling below need, orphan consumable
format, announced end-of-life, environment incompatible, no repair path.

Write each as a **checkable question with a specific threshold**, not a principle:

> **Work envelope too small** — the largest single-piece part they named does not fit, in any
> orientation, allowing for workholding.

Not: *"insufficient capacity."*

At least one kill switch should come from the **environment** — power service, ventilation, noise,
floor loading, connectivity policy. It's the category buyers most often discover after delivery, and
it disqualifies more candidates than price does.

---

## Weighting profiles

**3–4 profiles, one per realistic use case, each column summing to exactly 100.** Name them after the
person, not the product: "product parts for sale", "classroom", "weekend hobby", "production shop".

The profiles should **disagree with each other sharply.** If two columns are within a few points on
every row, they're the same profile and one should go. A profile that changes nothing isn't a
profile.

Sanity-check by scoring two very different candidates and confirming the ranking actually flips
between profiles. If it never flips, the weights aren't doing any work.

---

## The question bank

Round 1's three questions, phrased in this domain's language — capability envelope, use case,
operator — plus 4–8 Round 2 questions specific to the domain. `../discovery-questions.md` carries the
universal ones; don't repeat them.

Then the **translation table**: *they said* → *it means* → *requirement*. This is the most valuable
part of a pack, because it's what lets a non-expert be interviewed usefully.

Include a **banned words list** — this domain's jargon that must never appear in a question.

---

## The rest of the pack

- **Domain-specific TCO terms.** The general formula is in `../criteria.md`; the pack names *this*
  category's wear parts, consumables, and typical replacement intervals and costs.
- **The test battery** — what to run on a unit you can physically inspect, in order. This is how a
  used candidate earns grade-A rows instead of grade-C ones.
- **A worked example, with invented data.** See the warning below.

---

## Worked examples must be synthetic

**This marketplace is public.** A worked example with real dated products rots within months and
reads as a live recommendation long after it stops being one.

Invent the candidates and the numbers. Keep the *teaching shape* — three candidates, one that wins
exactly one criterion, a tie broken on a concrete requirement, a confidence note on something
recently released, a few honest grade-D cells. Change the specifics.

`shared/assets/exemplar-comparison.html` is a rendered example built this way.

**The domain criteria themselves stay real** — that's product-domain knowledge, and it's the reason
the pack is worth having. Only the *scored example* is fictionalized.
