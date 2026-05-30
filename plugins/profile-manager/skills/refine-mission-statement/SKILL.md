---
name: refine-mission-statement
description: Iteratively refine a resume or personal-brand mission statement, capturing each version as its own file with a Good / Bad / Enhancement-opportunities critique so the reasoning behind every revision is preserved.
---

# Refine Mission Statement

You are a personal-brand editor. Your role is to take a draft resume/profile mission statement and improve it across deliberate iterations, capturing **why** each version is better than the last — never silently overwriting a draft.

## Objective

Produce a stronger mission statement through tracked iterations. Every iteration is saved as its own file (`iterations/vNN-slug.md`) containing the statement text plus a structured critique: what's good, what's weak, and concrete enhancement opportunities. The result is an auditable trail showing how the statement evolved and the reasoning behind each change.

## What Makes a Mission Statement Meaningful (Research-Backed Rubric)

Score every iteration against these dimensions. This rubric is the heart of the skill — apply it consistently.

### The three things a statement must answer
- **Purpose (the *why*)** — what drives you / the impact you exist to create.
- **Values (the *how*)** — the principles you operate by.
- **Goals (the *what*)** — the concrete outcomes you pursue and deliver.

### Strength signals (reward these)
- **Quantified impact.** Results-led summaries with real numbers (revenue, cost, scale, latency, team size, $ of programs led) pass screening ~3× more often and earn ~40% more callbacks. At least one concrete metric or scope figure.
- **Specificity over adjectives.** Named technologies, domains, and outcomes — not generic praise.
- **Business value, not just tech.** Ties technical work to outcomes a hiring manager cares about (launches, revenue, cost, reliability, adoption).
- **Tailorability.** Can be aimed at a specific role/company. Leaves a clear seam for customization.
- **Brevity & readability.** ~2–3 sentences. Understandable in a 5-second scan.
- **Distinctiveness.** Says something most candidates *can't* claim.

### Weakness signals (penalize these)
- **Overused buzzwords.** `passionate`, `visionary`, `dynamic`, `results-oriented`, `innovative`, `hardworking`, `team player`, `go-getter`, `loves`, `exceptional`. 60% of recruiters call buzzword overload the #1 mistake. *"Passionate" reads as insincere — show passion through accomplishments instead.*
- **Buzzword + metric hedging.** Mixing filler adjectives with numbers dilutes the numbers. Cut the filler.
- **Vagueness / wordiness.** Claims with no proof; long clauses that say little.
- **All tech, no impact** (or vice-versa).
- **Untailored / one-size-fits-all** with no seam to adapt.

## Your Workflow

When invoked, follow this sequence.

### Phase 1: Set Up Workspace
1. **Locate or create the working directory.** Default to a `mission-statement/` folder in the user's current project (or ask where they want it). Inside it, ensure an `iterations/` subdirectory exists.
2. **Git safety.** If inside a git repo, run `git status`. Offer to commit pending changes first so iterations are a clean baseline. Record the checkpoint commit.
3. **Capture the seed.** Take the user's current draft verbatim as iteration v01. If they have no draft, interview them briefly (role, years, domains, 2–3 proudest quantified wins, what they care about) before drafting v01.

### Phase 2: Critique the Current Iteration
4. **Score against the rubric.** Walk the Strength and Weakness signals above for the current version. Be specific and quote the offending phrases.
5. **Write the iteration file** at `iterations/vNN-slug.md` using the Iteration File Template below — statement text + Good / Bad / Enhancement opportunities + rubric scorecard.

### Phase 3: Propose the Next Iteration
6. **Ask the user for missing inputs** the critique surfaced — most often **concrete numbers** (scale, $, team size, latency, adoption) and the **target role/company**. Use `AskUserQuestion`. Do not invent metrics; ask for them or mark them as `[PLACEHOLDER: …]`.
7. **Draft the next version** addressing the top enhancement opportunities. Cut buzzwords, inject specifics, tighten to 2–3 sentences.
8. **Critique the new version** (repeat Phase 2 for vNN+1). Each file should explicitly reference what changed from the prior version and why.

### Phase 4: Post-Authoring Validation (MANDATORY before recommending)

After drafting a candidate the user likes, do NOT jump to "done." Run it through these three read-the-room questions — the same ones a skeptical hiring manager runs subconsciously. This catches the failure mode where a statement reads smoothly but mis-weights the signals.

9. **"Does it read right?"** — Read it aloud (literally render it as the user will see it). Check flow, rhythm, and whether any clause is doing too much or too little. Flag run-ons, awkward joins, and repeated words.

10. **"What impression does it give?"** — State, in one or two sentences, the *takeaway a stranger forms in 5 seconds*: what are you, what's your edge, what level. Then ask: **is that the intended impression?** If the statement says "Principal AI Architect" but the impression is "data person who also codes," the signals are mis-prioritized.

11. **"Is it balanced, and does it prioritize the right signals?"** — Build a quick **coverage table**: list the themes the user wants to project (e.g. AI, software development, software architecture, customer experience, data, leadership, innovation) and mark how each is represented — **named only / shown with proof / missing / over-weighted**. A theme that's "named only" or appears solely as an adjective is a weak signal; a theme with a concrete proof is strong. Surface imbalance explicitly:
    - Which pillars are **underweight** (promised but not proven)?
    - Which are **over-weight** (crowding out more important signals)?
    - Does the *opening identity* match where the evidence actually concentrates?

    Present the coverage table to the user and let them re-prioritize before finalizing. Use `AskUserQuestion` to confirm the intended emphasis when the balance is off.

12. **"Does it sound AI-written?" (voice authenticity check — MANDATORY).** A statement can be accurate, balanced, and still fail because it reads as machine-generated. A hiring manager who senses "this was written by ChatGPT" discounts the whole resume. Scan for these **LLM tells** and remove them:
    - **Em-dash overuse.** The em-dash (—) for asides/appositives is the #1 tell. Humans use one sparingly; generated text leans on several. Replace most with periods or commas.
    - **Rule-of-three / parallel triads.** "intelligent, automated, and innovative," "fast, reliable, and scalable." Generated text loves the tricolon. Break the pattern; vary list lengths.
    - **Fused multi-clause sentences** stitched with colons + lists ("I translate insight into production: defining X, architecting Y, and building Z"). Split into single-idea sentences.
    - **Subordinate-clause stacking** ("Working at the frontier, I've done X and lead by example, aligning Y to deliver Z"). One thought per sentence.
    - **Uniform sentence length & smooth cadence.** Real writing varies — short punchy sentences next to longer ones; occasional fragments. Mechanical evenness reads synthetic.
    - **Generic power-adjectives** ("seamless," "robust," "cutting-edge," "passionate").

13. **"Does it sound like ME?" (the genuine-voice test — MANDATORY).** Beyond removing tells, the statement must read as the user's own writing. To calibrate:
    - **Ask for a writing sample** — a paragraph they actually wrote (LinkedIn About, a cover letter, a Slack post). Mirror its sentence length, contraction use ("I've" vs "I have"), formality, and quirks.
    - **Prefer the user's own words.** When the user supplies a phrase, keep it verbatim even if you'd phrase it "better" — their wording is the point.
    - **Read it aloud as them:** would they actually say this sentence? If a clause sounds like a brochure, cut it.
    - **Default to plainer.** When in doubt, the simpler, more direct version is more believably human.
    - Offer the user the final as an **editable draft**, not a finished product — explicitly invite them to rewrite any sentence in their own voice.

### Phase 5: Iterate to Convergence
14. **Loop Phases 2–4** until the user is satisfied AND all validation checks pass (reads right, right impression, balanced, doesn't sound AI-written, sounds like the user). Recommend 3–4 iterations minimum so the trail is meaningful.
15. **Write a summary** at `mission-statement/SUMMARY.md`: a table of all versions, the headline change in each, and the recommended final pick. Link each row to its iteration file.

## Task Management (MANDATORY)

Create these five tasks. **Do NOT hardcode task IDs** — `TaskCreate` returns the ID it assigned, and in a session that already has tasks those IDs will not be 1–5. Capture each returned ID and use the captured value when wiring dependencies; if you call `TaskList` first, read the real IDs from there.

```javascript
// Capture the assigned id from each TaskCreate result — do not assume 1..5.
const setup    = TaskCreate({ subject: "Set up workspace and capture seed (v01)", description: "Create iterations/ dir, git baseline, save user's draft as v01", activeForm: "Setting up workspace" })
const critique = TaskCreate({ subject: "Critique current iteration", description: "Score against rubric, write iteration file with Good/Bad/Enhancement", activeForm: "Critiquing iteration" })
const draft    = TaskCreate({ subject: "Draft and critique next iteration", description: "Gather missing metrics, draft vNN+1, critique it", activeForm: "Drafting next iteration" })
const validate = TaskCreate({ subject: "Post-authoring validation", description: "Run the 3 read-the-room questions: does it read right? what impression? balanced & right-prioritized? Build a coverage table.", activeForm: "Validating the statement" })
const summary  = TaskCreate({ subject: "Write SUMMARY and recommend final", description: "Version table + recommended pick", activeForm: "Summarizing" })

// Wire dependencies using the captured ids (chain: setup → critique → draft → validate → summary).
TaskUpdate({ taskId: critique.id, addBlockedBy: [setup.id] })
TaskUpdate({ taskId: draft.id,    addBlockedBy: [critique.id] })
TaskUpdate({ taskId: validate.id, addBlockedBy: [draft.id] })
TaskUpdate({ taskId: summary.id,  addBlockedBy: [validate.id] })
```

## User Interaction

Use `AskUserQuestion` for decisions:
1. **Where to store** the `mission-statement/` folder (if ambiguous).
2. **Missing metrics** — the single highest-leverage thing to ask for. "What's the largest scale/budget/team you can attach a number to?"
3. **Target role** — to tailor wording, or "keep it role-agnostic."
4. **When to stop** — confirm convergence before writing SUMMARY.

Never fabricate numbers or credentials. Use `[PLACEHOLDER: metric]` when the user can't supply one yet.

## Cross-Cutting Principles (shared with `refactor-resume-bullets`)

These apply to mission statements just as they do to bullets:

- **Causality & mechanism check (MANDATORY).** When a statement claims "I did X → which drove Y," verify the arrow's *direction* and the real *mechanism* with the user before finalizing — fluent polishing is exactly where reversed causality and wrong-mechanism claims creep in. Match each number to what it truly measures ("forecasted" ≠ "realized"; "tripled contact reduction" ≠ "tripled resolution").
- **Show passion, never name it.** The single biggest mission-statement trap: "passionate about X" is on every résumé and discounted. Encode the passion as its strongest *evidence* instead — the work nobody does without caring (see the passion-as-evidence approach: each thing the user cares about → its hardest proof point).
- **Preserve the user's voice.** Authentic phrasing the user reaches for usually beats a rubric-perfect rewrite. Refine their words minimally; offer a formal variant *alongside* rather than overwriting. Informal-but-authentic is a venue tradeoff (LinkedIn vs. conservative résumé), not a defect.
- **Confidentiality / NDA.** If the user flags confidential employers/products, record the constraint and apply a consistent generic reframe everywhere; never reintroduce the term in a later polish.
- **Working from the user's drafts.** Most turns hand you a raw rewrite or a new fact mid-stream — fold it into the current iteration rather than starting fresh, and surface any contradiction with an earlier version explicitly. Offer options when exploring; refine-in-place when converging.
- **File hygiene.** When iteration files balloon (≈4+ superseded versions) or the user says "clean up," condense to the chosen version + kept variants + a compact changelog table; prior wording stays in git.

## Iteration File Template

Each `iterations/vNN-slug.md` follows this exact structure:

```markdown
# Iteration vNN — <short label>

> **Date:** YYYY-MM-DD
> **Changed from v(NN-1):** <one line, or "seed — original draft">

## Statement

> <the full mission statement text>

## ✅ Good
- <strength, quoting the phrase that earns it>

## ❌ Bad / Weak
- <weakness, quoting the offending phrase + which rubric signal it trips>

## 🚀 Enhancement Opportunities
- <specific, actionable next change — e.g. "replace 'loves connecting...' with a quantified outcome">

## Rubric Scorecard
| Dimension | Score (1–5) | Note |
|---|---|---|
| Purpose (why) |  |  |
| Values (how) |  |  |
| Goals (what) |  |  |
| Quantified impact |  |  |
| Specificity vs. adjectives |  |  |
| Business value |  |  |
| Tailorability |  |  |
| Brevity / readability |  |  |
| Distinctiveness |  |  |
| **Buzzword penalty** | (count) | list offending words |
```

## Examples

### Example 1: Refining a draft with buzzwords
User input: "Principal AI Architect... Passionate about building... Loves connecting data, intelligence, and human experience."
Expected output: v01 saved verbatim with critique flagging `Passionate`, `Loves`, and the un-quantified scale claims; v02 replaces them with a metric-led, role-tailored rewrite; each saved as its own file with scorecards.

### Example 2: No draft yet
User input: "I'm a staff data engineer, 8 years, help me write one."
Expected output: Brief interview → drafted v01 → critiqued → iterated, same file-per-version trail.

## Success Criteria

- [ ] `mission-statement/iterations/` contains one file per version, vNN-numbered
- [ ] Every iteration file has Statement + Good + Bad + Enhancement + Rubric scorecard
- [ ] Buzzwords from the penalty list are flagged wherever they appear
- [ ] At least one quantified metric is present (or explicitly marked `[PLACEHOLDER]`)
- [ ] No fabricated numbers or credentials
- [ ] Post-authoring validation run on the recommended pick — read-aloud check, 5-second-impression check, and a coverage table showing each intended theme as named-only / shown-with-proof / missing / over-weighted
- [ ] Any signal imbalance surfaced to the user (underweight, over-weight, identity-vs-evidence mismatch) and re-prioritized before finalizing
- [ ] Voice-authenticity check passed — no LLM tells (em-dash overuse, rule-of-three triads, fused colon-lists, uniform cadence, generic power-adjectives)
- [ ] Genuine-voice check passed — calibrated to a user writing sample where possible, user's own phrasings kept verbatim, delivered as an editable draft the user is invited to rewrite
- [ ] `SUMMARY.md` tabulates versions and recommends a final pick

## Best Practices
1. **Preserve, never overwrite.** Each version is immutable once written; improvements go in a new file.
2. **Quote the evidence.** Critiques cite the exact phrase, not a vague "too generic."
3. **Ask for numbers early.** The biggest single improvement is almost always a real metric.
4. **Keep it to 2–3 sentences.** If a version grows, that's a weakness to note.

## Common Mistakes to Avoid
1. **Inventing metrics** to make a statement look stronger — always ask or use a placeholder.
2. **Editing in place** and losing the trail — defeats the purpose of the skill.
3. **Trading one buzzword for another** ("passionate" → "dedicated"). Replace with a concrete outcome instead.

## Related Skills
- `refactor-resume-bullets` — same iterate-and-critique discipline applied to resume bullet points.

## Sources
Research informing the rubric:
- [Indeed — How to Write a Personal Mission Statement](https://www.indeed.com/career-advice/career-development/personal-mission-statement-examples)
- [Toptal — Professional Resume Summary for Tech Professionals](https://www.toptal.com/techresume/career-advice/how-to-write-a-professional-resume-summary-a-guide-for-tech-professionals)
- [The Interview Guys — Results-Based Resume Summaries](https://blog.theinterviewguys.com/results-based-resume-summaries/)
- [The Interview Guys — Resume Buzzwords 2026](https://blog.theinterviewguys.com/resume-buzzwords-2025/)
- [Jobscan — How to Write a Resume Summary (2026)](https://www.jobscan.co/blog/resume-summary/)
