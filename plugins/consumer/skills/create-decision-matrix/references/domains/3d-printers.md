# Domain Pack — 3D Printers (FDM/FFF)

Covers desktop and benchtop filament printers. Resin (SLA/MSLA) shares the structure but needs
different criteria — wash/cure workflow, resin handling and ventilation, film and vat consumables.

---

## Kill switches

1. **Build volume too small** for their largest single-piece part. Check **height separately** — it's
   usually the binding constraint, and it's the one people forget.
2. **Material temperature ceiling below what their materials need.** Check nozzle max, bed max, and
   chamber temp *separately*. A vendor claiming a material that exceeds its own spec sheet is telling
   you about the vendor, not the material.
3. **Orphan filament format** — nonstandard diameter, proprietary cartridges, or a spool format with
   a shrinking supplier list.
4. **End-of-life already announced**, with parts availability ending inside their ownership horizon.
5. **Connectivity model incompatible** — cloud-required in an air-gapped shop or a school network.
6. **No enclosure where the materials demand one** — ABS/ASA in a bedroom or classroom is a
   ventilation problem, not a preference.
7. **No repair path** — no spares channel, no service network, no community, no schematics.

---

## Criteria

### A. Output quality & product-readiness

**1. Dimensional accuracy & repeatability**
Not "how tight once" — how tight *repeatably*, part to part, across the plate, and after 8 hours.
- 1 = visible axis mismatch; needs per-axis scaling to make a square square
- 3 = ±0.2–0.3 mm typical, consistent enough to compensate in CAD
- 5 = ±0.1 mm or better, holding across the bed and across a batch
*How to measure:* print the same 100 mm cube in four bed positions, at hour 0 and hour 8. Measure X,
Y, Z. **X systematically ≠ Y is a calibration defect, not something tuning fixes.**

**2. Fine-feature & thin-wall capability**
- 1 = 0.4 mm nozzle only; walls under 1 mm unreliable
- 3 = smaller nozzle available, thin walls work with tuning
- 5 = the small nozzle is a supported, stable configuration; sub-0.5 mm walls print clean
*How to measure:* thin-wall ladder (0.3/0.4/0.6/0.8/1.0 mm) plus a hole chart from 1 to 20 mm.

**3. Surface & cosmetic yield**
Ghosting, layer lines, seams, stringing, color bleed on multi-material.
- 1 = needs sanding to be presentable · 3 = fine for functional parts, visible seams
- 5 = comes off the plate sellable

**4. Support strategy & post-processing burden**
Where "product-ready" is usually won or lost.
- 1 = same-nozzle supports only, scarring every overhang
- 3 = breakaway support material via a second nozzle
- 5 = true soluble support with a dedicated hotend and a tuned profile
*Weight heavily if their parts have internal geometry.*

**5. First-time-right rate**
Fraction of jobs finishing usable without intervention.
- 1 = <60%, babysitting required · 3 = ~85% · 5 = >95%, plus failure detection and auto-pause
*How to measure:* ask the community for failure rate over 100 hours. On a used unit, ask for total
print hours and the failure log.

### B. Operability

**6. Time to first good part, for a beginner**
Unboxing to a dimensionally correct functional part, by someone who hasn't used this machine.
- 1 = a weekend of calibration · 3 = a few hours · 5 = under an hour, guided

**7. Per-job workflow friction**
Slicer quality, profile availability, plate changes, calibration cadence, remote monitoring.
- 1 = hand-tuned profiles for every material · 3 = good profiles, some fiddling
- 5 = works from stock profiles, monitored remotely
*Note specifically:* multi-material setup adds real friction. Dual-nozzle assignment in a slicer is a
learning curve even on otherwise beginner-friendly machines.

### C. Sustainment

**8. Maintenance load**
Hours per month, and the skill required.
- 1 = weekly teardown, specialist skills · 3 = monthly lube plus occasional nozzle swap
- 5 = quarterly, all user-serviceable, guided by the machine
***The sub-question that decides TCO: what is the unit of replacement when the hotend fails?*** A $20
nozzle and a $300 integrated hotend cartridge are the same failure with a 15× cost difference.

**9. Parts & service horizon**
- 1 = EOL, parts by luck · 3 = in support but ticket-only and slow
- 5 = published EOL dates years out, parts in stock, local service or same-week shipping
*How to measure:* find the vendor's published end-of-life and spare-parts policy. **If they don't
publish one, score 2 maximum** — that's a fact about the vendor, not a gap in your research.

**10. Consumables ecosystem & lock-in**
- 1 = proprietary or dying format, few suppliers, premium price
- 3 = standard format, vendor pushes its own brand but third-party works
- 5 = fully open, standard 1.75 mm, dozens of suppliers, cheap
*Check:* is there a feed path where the vendor "recommends official filament"? That's soft lock-in on
that path.

### D. Economics & risk

**11. 3-year total cost of ownership** — score the cost per usable part, not the sticker price.

**12. Platform & obsolescence risk**
- 1 = cloud-mandatory, vendor has removed features via firmware, model replaced annually
- 5 = runs fully offline, long support commitment, stable roadmap
*The tension worth naming:* a fast release cadence means better machines cheaper, but the machine is
superseded within a year and resale collapses.

---

## TCO terms for this domain

```
+ hotends / print cores per year × unit cost × 3     ← the term people forget
+ build plates + maintenance kits × 3
+ kg filament per year × $/kg × 3
+ failed-print % × filament spend                    ← the other term people forget
- realistic resale at year 3
```

Typical intervals: nozzles wear in months on abrasive filament and last years on PLA. Build plates
are a consumable. Belts and PTFE tubing are annual on a hard-run machine.

---

## Weighting profiles

| # | Criterion | Product parts for sale | Engineering prototyping | Hobby / learning | Classroom / shared |
|---|---|---|---|---|---|
| 1 | Dimensional accuracy | 15 | 18 | 5 | 5 |
| 2 | Fine features / thin walls | 10 | 8 | 8 | 4 |
| 3 | Surface & cosmetic yield | 14 | 4 | 10 | 6 |
| 4 | Support burden | 10 | 10 | 6 | 5 |
| 5 | First-time-right rate | 15 | 10 | 8 | 12 |
| 6 | Beginner time-to-part | 2 | 4 | 15 | 18 |
| 7 | Per-job friction | 8 | 8 | 10 | 12 |
| 8 | Maintenance load | 8 | 8 | 8 | 14 |
| 9 | Parts & service horizon | 6 | 10 | 4 | 10 |
| 10 | Consumables ecosystem | 5 | 8 | 12 | 6 |
| 11 | 3-year TCO | 5 | 6 | 12 | 6 |
| 12 | Platform risk | 2 | 6 | 2 | 2 |

---

## Question bank

**Round 1**

**Q1. "What's the biggest single thing you'd want to print?"**
Palm-sized — phone case, bracket / Shoebox-sized — helmet piece, drone frame / Bigger than a shoebox
/ No idea yet

**Q2. "What are you mostly making?"** *(multi-select)*
Working parts that need to be strong or fit onto something / Models, figures, props, decorative
things / Prototypes I'll iterate on quickly / Products I'll sell

**Q3. "Who's going to run it day to day?"**
Just me, and I like tinkering / Just me, and I want it to just work / Me plus other people /
Mostly unattended

**Round 2** — pick three, plus from the universal bank

**Q4. "Do your parts need to fit together, or fit onto something else?"**
Yes — mating parts, threads, press fits / Somewhat — close enough is fine / No — standalone

**Q5. "Will these parts live somewhere hot, outdoors, or under stress?"**
Indoors, room temperature / Outdoors or sunlight / Hot — car interior, near an engine /
Load-bearing or safety-relevant

**Q6. "How much do you care how it looks coming off the machine?"**
A lot — someone's paying for it / Somewhat — I'll sand or paint / Not at all — it just has to work

---

## Translation table

Never show them this. Show them the conclusions.

| They said | It means | Requirement |
|---|---|---|
| "Palm-sized" | ~150 mm cube | Almost anything qualifies; don't let build volume drive the decision |
| "Shoebox-sized" | ~300 × 150 × 150 mm | 256 mm class minimum; **check height separately**, it usually binds |
| "Bigger than a shoebox" | 350 mm+ | Large-format only; expect a price step and slower prints |
| "No idea yet" | Unknown | Default to 250 mm class. Say the assumption out loud |
| "Strong / fits onto something" | Functional | Accuracy and material range over surface finish |
| "Models, figures, props" | Cosmetic | Surface finish, fine features, multi-color; accuracy matters less |
| "Prototypes, iterate quickly" | Speed | Speed and first-time-right; a fast machine makes iteration cheap |
| "Products I'll sell" | Production | Repeatability, uptime, cost per part. Weight first-time-right heavily |
| "Mating parts / threads / press fits" | ±0.2 mm or better | Accuracy becomes top-3. **Also warn them:** no consumer FDM printer holds tight tolerances without compensating in CAD. Physics, not brand |
| "Outdoors or sunlight" | UV and weather | ASA or PETG → needs an enclosure |
| "Hot environment" | Heat resistance | ABS/ASA/PC or nylon → enclosure, ideally heated |
| "Load-bearing or safety-relevant" | Structural | **Flag honestly:** printed parts are anisotropic, weaker along the layer lines. Recommend against relying on one where failure hurts someone |
| "Living space or bedroom" | Noise + fumes | Enclosure and filtration; rules out open-frame for ABS/ASA entirely |
| "Other people will run it" | Shared | Beginner-friendliness and maintenance heavy; tinkerability at zero |
| "Runs mostly unattended" | Autonomy | Failure detection, camera, remote alerts. Without them a jam at hour 2 wastes the other ten |
| "Hard IT requirement" | Air-gapped | **Kill switch.** Eliminates cloud-mandatory machines regardless of quality |
| "As close to an appliance as possible" | Low fiddle tolerance | Avoid kits and brand-new models |
| "That's the fun part" | High fiddle tolerance | Open-source and upgradeable become viable, often better value |
| "Constantly / production" | High duty cycle | Consumables and spares dominate. **Two cheap printers often beat one expensive one** — mention it |

**Banned words in questions:** build volume, flow rate, tolerance, CoreXY, bed slinger, IDEX,
hardened nozzle, chamber temperature, microns, layer height.

---

## Test battery

For a unit you can physically test, or that a seller can run on video. Also the right answer to "how
do I know if it's any good."

1. **100 mm cube in four bed positions** → accuracy and consistency across the plate
2. **Hole chart, 1–20 mm** → real hole shrinkage, which tells them their CAD offset
3. **Thin-wall ladder, 0.3–1.0 mm** → the smallest feature that survives
4. **Overhang and bridge test** → cooling quality
5. **Dual-material part with a soluble or breakaway interface** → whether the support story is real
6. **One of their actual parts, printed twice** → repeatability, the number that matters for selling
7. **An 8-hour job** → thermal drift and mid-print failure behavior

---

## Worked example — invented data

**Every name, price and score below is fictional.** It exists to show what a decision artifact looks
like when it carries its evidence honestly, scored for the **"product parts for sale"** column.

| # | Criterion | Wt | Used Solano F7 | Kestrel D2 | Kestrel D2 Max |
|---|---|---|---|---|---|
| 1 | Dimensional accuracy | 15 | 2 ᴬ | 4 ᴬ | 4 ᴬ |
| 2 | Fine features | 10 | 3 ᴮ | 4 ᴮ | 4 ᴮ |
| 3 | Surface yield | 14 | 3 ᴮ | 4 ᴮ | 4 ᴮ |
| 4 | Support burden | 10 | 4 ᴬ | 4 ᴬ | 5 ᴬ |
| 5 | First-time-right | 15 | 3 ᶜ | 4 ᶜ | 3 ᶜ |
| 6 | Beginner time-to-part | 2 | 3 ᴮ | 4 ᴮ | 4 ᴮ |
| 7 | Per-job friction | 8 | 2 ᶜ | 4 ᴮ | 4 ᴮ |
| 8 | Maintenance load | 8 | 2 ᴬ | 4 ᴬ | 4 ᴬ |
| 9 | Parts & service horizon | 6 | 2 ᴬ | 4 ᴬ | 4 ᴬ |
| 10 | Consumables ecosystem | 5 | 2 ᴬ | 4 ᴬ | 4 ᴬ |
| 11 | 3-year TCO | 5 | 2 ᴬ | 5 ᴬ | 4 ᴬ |
| 12 | Platform risk | 2 | 4 ᴰ | 2 ᴰ | 2 ᴰ |
| | **Weighted total** | | **2.70** | **4.02** | **3.98** |

**Reading it.** The F7 wins **exactly one** criterion — platform risk, because it runs fully offline
on open materials. Everything else is a deficit, and several are structural rather than fixable: an
integrated-hotend design making every clog a $170–350 event, a filament format with a shrinking
supply base, and no warranty.

The D2 and D2 Max are 0.04 apart, which is inside the noise — **that is a tie, and the matrix says
so.** It breaks on build volume, not on the total: if their largest part fits in 256 mm the D2 wins
on cost; if not, the Max is the only one of the three with a bigger envelope than the F7.

**Confidence note.** The D2 Max scores carry more uncertainty. It launched four months ago, so there
is no long-term reliability record and early forum reports flag tool-change delays. "No reports of
problems" is not "no problems" at four months. Re-score in six.

**The two grade-D cells are both platform risk** — neither vendor publishes a firmware or
end-of-support policy, so those scores are inference from past behavior. That row is the weakest part
of the comparison and the first thing to re-check.
