# Domain Pack — CNC Cutters (Routers, Mills, Laser Cutters)

Covers subtractive cutting machines: **CNC routers and benchtop mills**, and **laser cutters**
(CO2, diode, fiber). They're one pack because they share the axes that actually decide the purchase —
rigidity and accuracy under load, extraction and safety, the CAM chain, and a consumable cost per
hour that dominates TCO. Where a criterion differs between them, both anchors are given.

Plasma and waterjet share the structure but need their own consumable and safety anchors.

---

## Kill switches

1. **Work envelope too small** for the largest single-piece part they named — in any orientation,
   **allowing for workholding.** A part that fits the table exactly does not fit, because clamps,
   tabs, or a jig need room. On a router, check **Z clearance and cutting depth separately** from
   table size; it's the constraint people miss.
2. **Material class the machine physically cannot cut.** A diode laser will not cut clear acrylic or
   any metal. A CO2 laser will not cut metal without a fiber source. A router without rigidity and
   flood or mist cooling will not do steel. **Check the claim against the vendor's own stated
   maximums** — a listing claiming a material beyond its own spec sheet tells you about the seller,
   not the machine.
3. **No viable extraction path in their space.** Ducting to outside, or a filter unit sized to the
   machine. Laser cutting acrylic, plastics, rubber, and coated stock releases VOCs that a particulate
   filter does not remove — that needs activated carbon. This is a hard requirement, not a nice-to-have,
   and it's the one most often discovered after delivery.
4. **Electrical service unavailable.** 240 V, a dedicated circuit, or three-phase they don't have and
   can't get. Include the cost of adding it or it's a kill switch.
5. **No enclosure where the material or the beam class demands one.** An open-frame laser above Class 1
   in a shared or domestic space isn't a preference question.
6. **Closed CAM with no post-processor for their toolchain** — cloud-mandatory control, or a
   controller their software can't drive. Verify against the actual controller (Ruida, GRBL,
   Smoothieboard, TopWisdom, EZCad2 and similar are broadly supported), not the brand name.
7. **End-of-life announced** with parts ending inside their ownership horizon, or **no repair path** —
   no spares channel, no service network, no schematics.

---

## Criteria

### A. Capability

**1. Work envelope & Z clearance**
- 1 = smaller than their stated largest part · 3 = fits with careful workholding, no margin
- 5 = comfortable margin, and Z clearance for the tallest stock plus the tool
*How to measure:* vendor drawing, minus workholding. Ask what the envelope is **with the accessory
they'll use** — rotary axes, pass-through, and second heads all take envelope back.

**2. Material class & cut capacity**
- 1 = only the softest class (foam, thin ply, paper) · 3 = wood, plastics, and thin non-ferrous
- 5 = the full class they named, at production depth, without babying it
*How to measure:* the vendor's own maximum thickness **per material**, then look for owner-reported
figures — vendors quote a single-pass maximum under ideal conditions that the machine will not hold
in production.

**3. Accuracy & repeatability under load**
The criterion people most often confuse with resolution. Stepper microstepping resolution is not
accuracy, and a spec sheet quoting 0.01 mm "resolution" is quoting a number that means nothing about
the finished part.
- 1 = ±0.5 mm / ±0.020 in — fine for signs, impossible for fitted joinery or precision aluminum
- 3 = ±0.25 mm / ±0.010 in — most hobby benchtop work
- 5 = ±0.05 mm / ±0.002 in repeatably, across a batch and under cutting load
*How to measure:* cut the same test part four times across the table and measure. **Open-loop
steppers lose steps under load and never report it**; closed-loop servos hold accuracy under the same
cut. Ask which it is — this single question separates two price classes.

**4. Frame rigidity & drive system**
Rigidity is what converts a good spec into a good part. It is also the thing you cannot upgrade
later.
- 1 = extruded aluminum gantry, V-wheels, belt drive on all axes
- 3 = heavier extrusion or steel, linear rails, ball screws on the important axes
- 5 = welded steel frame, oversized linear rails, ball screws or racks, servo drive
*How to measure:* look for deflection tests under real cutting load, not photos of finished work.
Frame material and rail type in the spec are a good proxy when nobody has measured it.

**5. Cut / edge quality & finishing burden**
- 1 = every edge needs sanding, or every laser cut needs the char removed by hand
- 3 = clean enough for shop work, some finishing on visible faces
- 5 = comes off the bed sellable
*Laser note:* edge quality is mostly beam quality plus air assist. **Ask whether air assist is
included or an accessory** — it usually isn't included, and it is not optional.

### B. Operability & environment

**6. Extraction, enclosure & safety**
Score the machine **as it will actually be installed**, including whatever they have to add.
- 1 = no enclosure, no extraction port, interlocks absent or defeatable
- 3 = enclosed with an extraction port, filter or ducting bought separately
- 5 = enclosed, interlocked, extraction included and sized, filtration rated for their materials
*How to measure:* an enclosed desktop laser wants a few hundred CFM; a 12 × 24 in bed wants roughly
**500 CFM at about 6 in of water static pressure**; a large open bed can want 1,500 CFM or more. For
a router, size dust collection to the port and expect chips, not dust. Price ducting **or** a filter
unit and put it in TCO — filtered units avoid building work but carry a recurring filter cost, and
carbon stages are the expensive ones.

**7. CAM chain & post-processor openness**
Where lock-in actually bites, and it's invisible on the spec sheet.
- 1 = cloud-mandatory or vendor software only; no post-processor for standard toolchains
- 3 = vendor software is the happy path, third-party works with effort
- 5 = standard controller and G-code, works with mainstream CAM and control software offline
*How to measure:* **identify the controller, not the brand.** Then confirm the software they already
use has a post-processor for it. A subscription or a cloud dependency is a recurring cost and a
platform risk — put it in both places.

**8. Per-job workflow friction**
Workholding, tramming, probing, focus and Z-zero, material changes, job setup time.
- 1 = manual everything; tram and re-zero for every job
- 3 = a touch probe or auto-focus, decent fixturing
- 5 = automatic probing, repeatable fixturing, camera alignment or a good jig system
*Ask specifically about workholding.* On a router it is most of the real learning curve, and it is
never in the review.

### C. Sustainment

**9. Cutting-source life & replacement cost**
The single largest sustainment term, and the one that decides most used purchases.

*Laser:* a **glass CO2 tube** typically runs **2,000–4,500 hours** and costs roughly **$400–1,500**
to replace. An **RF metal tube** runs **10,000+ hours** but costs **several thousand and up** to
replace or recharge — the longer life does not automatically mean lower cost per hour, and you should
compute it rather than assume it. Diode modules are cheap and short-lived.
- 1 = source near end of life, replacement is a large fraction of machine value
- 3 = mid-life, replacement is a planned, affordable event
- 5 = long-life source, published hours, replacement cheap relative to the machine

*Router:* score the **spindle**. A trim router is a consumable that lasts a few hundred hours; a VFD
spindle with real bearings lasts thousands. Runout is the number: **professional spindles hold well
under 0.01 mm; entry-level can be several times that**, and runout shows up as tool wear and chatter
long before it shows up as a dimension.

**10. Consumable cost per hour**
Bits and end mills, lenses and mirrors, nozzles, collets, filters, lubricants, bed slats.
- 1 = proprietary or single-source, priced accordingly · 3 = standard sizes, ordinary prices
- 5 = fully standard, many suppliers, cheap
*How to measure:* price the **three** things they'll replace most, then multiply by their duty cycle.
On a laser, don't forget the **filter cartridges** — on a filtered install they can rival the tube.

**11. Parts & service horizon**
- 1 = EOL, parts by luck · 3 = in support but ticket-only and slow
- 5 = published spare-parts commitment years out, parts in stock, service reachable
*How to measure:* find the published policy. **If they don't publish one, score 2 maximum** — that is
a fact about the vendor, not a gap in your research.

### D. Economics & risk

**12. 3-year total cost of ownership** — score cost per usable part, not sticker price.

**13. Platform & obsolescence risk**
- 1 = cloud-mandatory, subscription software, vendor has removed features by update, annual model churn
- 5 = runs offline on a standard controller, stable roadmap, healthy used market
*Machines with a standard controller hold resale far better*, because the next owner isn't buying
into a dependency.

---

## TCO terms for this domain

```
+ cutting source replacement (tube or spindle) × expected replacements over 3 years
+ consumables/hr × hours per year × 3            ← bits, lenses, nozzles, collets
+ extraction filters or duct maintenance × 3     ← the term nobody budgets
+ software subscription × 3                      ← if the CAM chain isn't owned
+ electrical work / bench / chiller, one time    ← the other term nobody budgets
+ scrap rate × material spend
- realistic resale at year 3                     ← near zero for closed-ecosystem machines
```

**Two costs specific to this domain that people miss entirely:** the extraction system, and the
electrical work to feed the machine. Either can be $600–1,500 and neither appears on the product
page. Ask early enough that they aren't a surprise.

---

## Weighting profiles

| # | Criterion | Production / parts for sale | Prototyping & one-offs | Hobby / weekend shop | Classroom / makerspace |
|---|---|---|---|---|---|
| 1 | Work envelope & Z clearance | 10 | 10 | 10 | 8 |
| 2 | Material class & cut capacity | 10 | 14 | 10 | 8 |
| 3 | Accuracy & repeatability | 15 | 12 | 5 | 4 |
| 4 | Frame rigidity & drive | 12 | 10 | 6 | 6 |
| 5 | Cut quality & finishing | 10 | 5 | 8 | 5 |
| 6 | Extraction, enclosure & safety | 6 | 6 | 10 | 18 |
| 7 | CAM chain openness | 6 | 12 | 10 | 8 |
| 8 | Per-job friction | 6 | 8 | 10 | 12 |
| 9 | Source life & replacement cost | 8 | 6 | 8 | 8 |
| 10 | Consumable cost per hour | 7 | 5 | 9 | 6 |
| 11 | Parts & service horizon | 5 | 6 | 4 | 9 |
| 12 | 3-year TCO | 3 | 4 | 8 | 5 |
| 13 | Platform risk | 2 | 2 | 2 | 3 |

Safety and extraction carry **18** in a classroom and **6** in a production shop — not because it
matters less in production, but because a production shop already has extraction and a classroom is
deciding whether it can have the machine at all.

---

## Question bank

**Round 1**

**Q1. "What's the biggest single piece you'd want to cut?"**
Small — coasters, brackets, panels under a foot / Cabinet-door sized / Full sheet — 4 × 8 ft or
close / Not sure yet

**Q2. "What are you cutting, mostly?"** *(multi-select)*
Wood, plywood, MDF / Acrylic, plastics, foam / Aluminum or other soft metals / Steel or hard metals /
Paper, leather, fabric, thin stock

**Q3. "Where would it live, and who's around it?"**
My own garage or shop / A shared shop or makerspace / A classroom or office / A commercial space with
extraction already

**Round 2** — pick three, plus from the universal bank

**Q4. "Do the pieces need to fit together — joinery, press fits, mating parts?"**
Yes, precisely / Roughly — I can sand to fit / No — signs, engraving, decorative

**Q5. "How are the fumes or chips getting out of that room?"**
There's a window or a duct run / Nothing yet, I'd need to solve it / Extraction already installed /
I hadn't thought about it

**Q6. "What software do you already use for design or machining?"**
A specific CAM package I want to keep / Whatever comes with it is fine / I haven't picked one /
I need it to work offline

**Q7. "What power is available where it'd go?"**
Normal wall outlets only / I have or can add a 240 V circuit / Three-phase / I don't know

**Q8. "How much of a run is a typical job?"**
One-offs / A handful at a time / Dozens of the same part / Continuous production

---

## Translation table

Never show them this. Show them the conclusions.

| They said | It means | Requirement |
|---|---|---|
| "Coasters, small brackets" | ~300 mm envelope | Desktop class; don't let envelope drive the decision |
| "Cabinet-door sized" | ~600–900 mm | Mid-size; check **Z clearance** separately |
| "Full sheet" | 1220 × 2440 mm | Full-sheet gantry; a large price and floor-space step. Ask about **doorway and floor loading** |
| "Wood, plywood, MDF" | Softest class | Almost anything qualifies. Dust collection, not fume extraction |
| "Acrylic, plastics" | VOC-producing | **Carbon filtration or ducting is mandatory.** A particulate filter is not enough |
| "Aluminum or soft metals" | Rigidity + cooling | Rules out light gantries and diode lasers entirely. Needs mist or flood, and chip evacuation |
| "Steel or hard metals" | Serious machine | Router class is out; this is a mill or a fiber/plasma question. Say so plainly |
| "Paper, leather, fabric" | Low power, high speed | Laser, not router. Watch for materials that **must never** be cut — PVC and vinyl release chlorine gas that destroys the machine and harms the operator |
| "Yes, precisely" (joinery) | ±0.1 mm or better | Accuracy and rigidity become top-3. **Warn them:** hobby benchtop machines land around ±0.25 mm; that gap is frame and drive, not tuning |
| "Nothing yet, I'd need to solve it" | No extraction | Price a filter unit **or** a duct run and put it in TCO before comparing anything |
| "I hadn't thought about it" | No extraction | Same, plus tell them now — it changes the budget by hundreds and sometimes the location |
| "A specific CAM package" | Toolchain constraint | Verify a post-processor exists **for the controller**. Cloud-only is a kill switch here |
| "I need it to work offline" | Air-gapped | **Kill switch** for cloud-mandatory machines |
| "Normal wall outlets only" | 120 V / 15 A | Caps laser wattage and spindle size. Say what that costs them in capacity |
| "I don't know" (power) | Unknown | Default to standard outlets and **flag the 240 V question early** — adding a circuit is $600–1,500 |
| "Dozens of the same part" | Production | Repeatability, workholding, and consumable cost dominate. Fixturing matters more than peak speed |
| "A shared shop or makerspace" | Multiple operators | Safety, interlocks, and maintenance load heavy; tinkerability at zero |

**Banned words in questions:** kerf, runout, tram, backlash, ball screw, closed-loop, collet, CFM,
static pressure, post-processor, G-code, duty cycle, Class 1/Class 4.

---

## Test battery

For a unit you can inspect, or that a seller can run on video. This is how a used candidate earns
grade-A rows.

1. **Cut a 150 mm square and measure both diagonals** → squareness and gantry tram. Diagonals
   differing is a geometry problem, not a tuning problem.
2. **The same part cut four times across the bed** → repeatability, and whether accuracy falls off
   away from the origin.
3. **A full-depth cut in their hardest material** → real capacity under load, not the brochure number.
4. **Listen and watch during a heavy cut** → chatter, deflection, the gantry visibly flexing.
5. **Move every axis through full travel by hand, power off** → binding, notchy bearings, backlash.
6. **Laser: a focus ramp test and a cut through their thickest stock** → true focus and real power.
   A tube down on power cuts noticeably slower, which is how you catch an aging tube the seller
   didn't mention.
7. **Router: measure spindle runout with an indicator** → the number that predicts tool life.
8. **Run one job start to finish, from their own file, on their own toolchain** → proves the CAM
   chain, which is the failure nobody tests before buying.
9. **Ask to see the machine cold-start** → a controller or chiller fault often only shows on startup.

For a laser, also ask for the **hours meter and the tube's install date**. A tube is a consumable with
a known life; buying one at 3,500 hours is buying a machine plus an imminent bill.

---

## Worked example

`shared/assets/exemplar-comparison.html` is a rendered comparison in this domain, built entirely on
**invented candidates and invented numbers**. It shows a kill switch called out above the matrix, an
evidence grade inline in every cell, four honest grade-D cells, a TCO block computed separately, and
a price distribution with sold and asking kept apart and the confidence band suppressed at n=5.

Read it for the shape. Do not reuse any of its numbers — they describe machines that do not exist.

---

## Sources for the anchors in this pack

The capability figures above were researched rather than recalled. Re-verify before quoting them to
someone; consumable pricing in particular moves.

- Tube life and replacement cost: [Thunder Laser USA](https://www.thunderlaserusa.com/blog/glass-vs-metal-co2-laser-tubes/),
  [EMP Laser](https://shop.emplaser.com/a/docs/laser-101/co2-laser-tubes-rf-or-glass),
  [Epilog](https://www.epiloglaser.com/laser-machines/laser-features/metal-ceramic-rf-co2-laser-tubes-manufactured-by-epilog-laser/)
- Accuracy classes, runout, open- vs closed-loop: [CNCCookbook](https://www.cnccookbook.com/understanding-cnc-precision-and-accurate-cnc-repeatability/),
  [AccTek](https://www.acctekgroup.com/how-to-choose-the-right-cnc-router-spindle/)
- Extraction CFM and filtration stages: [Baison](https://baisonlaser.com/blog/laser-cutter-exhaust-systems/),
  [Donaldson](https://www.donaldson.com/en/resources/technical-articles/thermal-cutting-dust-collection-balancing-variables/)
- Controller compatibility and CAM lock-in: [LightBurn machine compatibility](https://lightburnsoftware.com/blogs/machine-compatibility)
