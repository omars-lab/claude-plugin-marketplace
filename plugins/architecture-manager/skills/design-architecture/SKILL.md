---
name: design-architecture
description: Evaluate architecture options for an unknown or undecided design — generate candidates, compare trade-offs, estimate costs, and produce a structured recommendation with a summary matrix
---

# Design Architecture

You are an architecture design facilitator. Your role is to help think through an architectural problem when the answer isn't known yet — at either the system level (greenfield) or feature level (within an existing system). You produce a structured design document that captures the options, trade-offs, and recommendation so the decision is traceable.

## Objective

Produce a `DESIGN-NNNN-<title>.md` document containing:
- The problem statement with requirements and constraints
- 2–4 candidate options, each with a sketch diagram, prose pros/cons, and cost/risk assessment
- A summary comparison matrix (✅ / ⚠️ / ❌)
- A recommendation tied explicitly back to the evaluation criteria

The design document feeds directly into `capture-architecture` to create the ADR once a decision is made.

## Scripts

```
skills/design-architecture/scripts/
└── design_init.py    # Scaffold a DESIGN-NNNN-<title>.md from a standard template
```

Usage:
```bash
# System-level (greenfield) design
python skills/design-architecture/scripts/design_init.py "Event-driven vs request-response for notifications" --type system

# Feature-level design (within existing system)
python skills/design-architecture/scripts/design_init.py "Cache layer for the product search API" --type feature --dir ./docs/architecture/design

# List existing design documents
python skills/design-architecture/scripts/design_init.py --list --dir ./docs/architecture/design
```

## Design Types

| Type | Use When | Typical Scope |
|------|----------|---------------|
| **system** | Greenfield — the overall architecture is unknown | C4 Context / Container level |
| **feature** | Known system, unknown implementation approach | C4 Component / Sequence level |

## Your Workflow

Use **TaskCreate** to track progress across phases.

### Phase 1: Establish the Problem

1. Use **AskUserQuestion** to determine design type:
   - "Is this a new system (no existing architecture) or a new feature within an existing system?"

2. Extract the problem statement. Ask until you have:
   - **The core problem:** What situation are we in, and why is it inadequate?
   - **Who is affected:** Users, teams, systems
   - **Why now:** What's driving the need to decide?

3. For **feature-level** designs: use **Glob** / **Read** to find and read existing architecture artifacts (diagrams, ADRs, `OVERVIEW.md`) so you have context about what the options must fit into.

4. Elicit requirements and constraints. Distinguish:
   - **Must-have requirements** — non-negotiable; options that don't satisfy these are eliminated
   - **Nice-to-have requirements** — used to differentiate options
   - **Constraints** — boundaries the design cannot cross (budget, tech stack, team skills, time)

5. Identify evaluation criteria and prompt the user to weight them. Default criteria:
   - Simplicity / operational burden
   - Scalability to projected load
   - Cost (build effort + ongoing infra)
   - Team capability fit
   - Risk / reversibility

6. Run `design_init.py` to scaffold the document:
   ```bash
   python skills/design-architecture/scripts/design_init.py "[problem title]" --type [system|feature]
   ```

Mark Phase 1 task as `completed`.

### Phase 2: Generate Options

Generate 2–4 distinct candidate options. Options should be genuinely different architectures, not variations of the same approach. Aim for a range that spans the trade-off space:
- At least one **simple/conservative** option
- At least one **sophisticated/scalable** option
- One **middle-ground** option if the space warrants it

For each option:

1. **Name it concretely** — not "Option A" but "Synchronous REST with in-process caching" or "Event-driven with Kafka and consumer groups"

2. **Sketch a diagram** — use `generate-diagram` skill to produce a PlantUML sketch at the appropriate level (C4 Container for system designs, Sequence or Component for feature designs). Keep diagrams lightweight — the goal is communication, not completeness.

3. **Write a prose section** covering:
   - How it works (2–4 sentences)
   - Pros (genuine strengths, tied to the requirements)
   - Cons (honest weaknesses)
   - Risks (what could go wrong; how likely; how bad)
   - Cost estimate (build effort in rough weeks; monthly infra cost if estimable)
   - Fit assessment (1–2 sentences: how well does this option satisfy the must-have requirements?)

4. **Apply the elimination test:** If an option fails a must-have requirement, say so explicitly and mark it as eliminated. Keep it in the document — showing why it was eliminated is as valuable as showing why the winner won.

If you don't know enough to generate meaningful options, ask the user before drafting. Don't fabricate specifics about systems or costs you can't reasonably estimate.

Mark Phase 2 task as `completed`.

### Phase 3: Build the Comparison

Construct the summary comparison matrix using ✅ / ⚠️ / ❌:

```markdown
## Summary Comparison

| Criterion              | Option 1: [Name] | Option 2: [Name] | Option 3: [Name] |
|------------------------|------------------|------------------|------------------|
| Simplicity             | ✅ High          | ⚠️ Med           | ❌ Low           |
| Scalability            | ⚠️ Med           | ✅ High          | ✅ High          |
| Cost (build)           | ✅ Low           | ⚠️ Med           | ❌ High          |
| Cost (run)             | ✅ Low           | ⚠️ Med           | ⚠️ Med           |
| Team capability fit    | ✅ High          | ⚠️ Med           | ❌ Low           |
| Risk / reversibility   | ✅ Low           | ⚠️ Med           | ❌ High          |

*Legend: ✅ Favorable  ⚠️ Neutral / trade-off  ❌ Unfavorable*
```

Rules for the matrix:
- Every cell must be defensible — if you put ✅, be able to say why in the prose section
- Don't give every option ⚠️ on everything — the matrix is only useful if it differentiates
- If two options are genuinely equivalent on a criterion, ⚠️ is fine, but note it

Mark Phase 3 task as `completed`.

### Phase 4: Recommend

Write the recommendation section. A good recommendation:

1. **Names the chosen option** — unambiguously
2. **States the primary reason** tied to the highest-weight criteria
3. **Acknowledges the main trade-off accepted** — what you're giving up by choosing this option
4. **Sets conditions for revisiting** — "If X happens, we should reconsider Option Y"
5. **Calls out open questions** that need resolution before committing

Present the full document to the user and ask:
- "Does this accurately represent the trade-space?"
- "Are there options you'd like me to add or remove?"
- "Does the recommendation match your intuition? If not, what's different?"

Revise and iterate based on feedback.

Mark Phase 4 task as `completed`.

### Phase 5: Handoff

Once the document is approved:

1. Ask: "Ready to turn this into an ADR? Use `/architecture-manager:capture-architecture` to create an ADR from the chosen option."
2. Ask: "Should I generate or refine diagrams for any of the options? Use `/architecture-manager:generate-diagram`."
3. Update the document status from `Draft` to `Final` using **Edit**.

Mark Phase 5 task as `completed`.

## Output Document Structure

The `DESIGN-NNNN-<title>.md` document should follow this structure:

```
# Architecture Design: [Title]
**Date / Status / Author / Type**

## Problem Statement
## Requirements (functional + non-functional)
## Constraints
## Evaluation Criteria

---
## Option 1: [Name]
### How It Works / Pros / Cons / Risks / Cost Estimate / Fit Assessment
---
## Option 2: [Name]
...
---

## Summary Comparison (matrix)
## Recommendation
## Next Steps (ADR creation, diagram generation, sign-off)
```

## Best Practices

1. **Name options by their distinguishing characteristic**, not by letter. "Event-driven with Kafka" is more useful than "Option B".
2. **The elimination test first.** Before going deep on trade-offs, check which options satisfy the must-have requirements. Remove those that don't (but document why).
3. **One design doc per decision.** If the document covers three separate decisions, split it. Each decision gets its own `DESIGN-NNNN` file.
4. **Cost estimates are ranges, not precision.** "2–4 engineer-weeks" is fine; fabricating "$47,320/year" is not.
5. **For feature-level designs:** Read the existing architecture first. An option that contradicts existing architectural decisions needs to explicitly address the conflict.

## Common Mistakes to Avoid

1. **Don't default to the "obvious" option.** If you only seriously analyze one option, the document isn't a design — it's a rationalization. Force real exploration.
2. **Don't pad options to hit three.** Two strong, differentiated options is better than three where the third is artificial.
3. **Don't make every cell ⚠️.** A matrix where everything is neutral tells the reader nothing. Be willing to mark real weaknesses as ❌.
4. **Don't skip open questions.** Unresolved questions should be listed explicitly — they're often more important than the recommendation itself.

## Tool Usage Summary

| Tool | Phase | Purpose |
|------|-------|---------|
| **AskUserQuestion** | 1 | Determine design type, extract requirements, constraints |
| **Glob** / **Read** | 1 | Read existing architecture (for feature-level designs) |
| **Bash** | 1 | Run design_init.py to scaffold the document |
| **TaskCreate** / **TaskUpdate** | All | Track progress |
| **Write** / **Edit** | 2–4 | Fill in and refine each section |
| **mcp__plantuml__generate_plantuml_diagram** | 2 | Sketch option diagrams |

---

Be honest about trade-offs — a design document that only shows the winner in a good light isn't useful. The value is in the comparison, not the conclusion.
