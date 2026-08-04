# Discovery Questions — Method and the Universal Bank

Read before Step 2. The **domain pack** carries that domain's specific questions and its translation
table; this file carries the method and the questions that are the same everywhere.

The person knows what they want to do. They don't know what specs that implies. Your job is to ask
about the first and derive the second.

**If a question can only be answered by someone who already owns one of these, it's the wrong
question.**

| Bad | Good |
|---|---|
| "What capacity do you need?" | "What's the biggest single thing you'd want to handle?" |
| "What tolerance do your parts require?" | "Do the parts need to fit together or fit onto something else?" |
| "What duty cycle are you looking at?" | "Roughly how much will it run?" |

Ask with `AskUserQuestion` and tappable options every time. **At most 3 questions per round, 2–3
rounds total.** Interview fatigue produces careless answers, and careless answers produce a confident
matrix built on sand.

---

## The two rounds

**Round 1 — the three that change the answer most.** In every domain these are:

1. **Capability envelope** — the biggest / hardest / most demanding thing they need it to handle.
   This is almost always the binding constraint and the source of the first kill switch.
2. **What they're making or doing with it** — the use case, which sets the weighting profile.
3. **Who operates it** — which decides how much beginner-friendliness and maintenance load matter.

The domain pack phrases these three in that domain's language, with its own options.

**Round 2 — pick three from the universal bank below plus the pack's domain questions,** chosen by
what Round 1 left open. Skip anything already answered.

---

## The universal bank

These generalize across every durable good. The domain pack adds to them; it doesn't replace them.

**"What's your all-in budget?"**
Under $500 / $500–1,000 / $1,000–2,500 / $2,500+ — adjust the bands to the category.
*All-in.* Ask it that way, because consumables, tooling, and the thing nobody budgets for
(extraction, a circuit, a stand, software) routinely add 20–40%.

**"Where will it live?"**
Living space or bedroom — noise and smell matter / Garage, workshop, or basement / Office or
classroom / Dedicated space
→ Often a kill switch in disguise. Noise, fumes, heat, vibration, and floor space disqualify more
candidates than price does.

**"Who's going to run it day to day?"**
Just me, and I like tinkering / Just me, and I want it to just work / Me plus other people /
It needs to run mostly unattended
→ "Other people" weights beginner-friendliness and maintenance heavily and tinkerability at zero.
"Unattended" requires failure detection and remote alerts — without them a jam at hour 2 wastes the
other ten.

**"How much fiddling are you willing to do?"**
I want to tune and upgrade it, that's the fun part / Some setup is fine, then leave me alone / As
close to an appliance as possible
→ High tolerance makes open and upgradeable options viable, and they're often better value. Low
tolerance rules out kits and brand-new models.

**"Roughly how much will it run?"**
A few times a month / Weekly / Most days / Constantly — this is production
→ At high duty cycle, consumable cost and spare-parts availability dominate everything else. Two
cheap units often beat one expensive one; mention it.

**"Any rules about it connecting to the internet?"**
No rules, cloud features are fine / Prefer local, not a dealbreaker / Hard requirement — work or
school IT won't allow it / Not sure
→ A hard requirement is a kill switch, regardless of how good the cloud-only option is.

**"How long do you expect to keep it?"**
A couple of years / Five-ish / As long as it lasts / Until it stops paying for itself
→ Sets the ownership horizon that parts availability and end-of-life dates get measured against, and
the horizon for the TCO calculation.

---

## The translation table

Each domain pack carries one: *they said* → *it means* → *requirement*. **Never show them the table;
show them the conclusions.** The table is how you avoid asking them to do your job.

Two entries belong in every pack because they are honesty obligations, not preferences:

- **Anything safety-relevant or load-bearing** — say plainly what the material or mechanism can and
  cannot be trusted with, and recommend against relying on it where failure hurts someone.
- **Any tolerance or precision claim** — state whether consumer-grade equipment in this category can
  actually hold it, and that this is physics rather than brand.

---

## Handling "I don't know"

Common and fine. Take the default, then say so out loud:

> "I've assumed [default] — that covers most of what people end up doing. If you later need
> something bigger, the answer changes to [X], so it's worth knowing now that it's a real fork in
> the road."

Never let an unknown stall the process. A stated assumption they can correct beats a question they
can't answer.

---

## Things not to ask

- **Jargon.** Any term they'd have to look up. The pack lists that domain's banned words.
- **Which brand they prefer.** Brand preference is an output, not an input, and asking invites them
  to anchor on marketing.
- **More than 3 questions in a call, or more than ~3 rounds total.**
- **Anything the conversation already answered.** Re-asking reads as not listening, and it burns a
  slot you needed.
