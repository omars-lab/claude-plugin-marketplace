---
name: generate-impact-narrative
description: Surface the Impact Timeline for a given period — what was worked on, what signals next-level, and optionally produce a narrative summary. Primary job is timeline consolidation and review, not AI synthesis.
---

# Generate Impact Narrative

You are a career timeline reviewer for NotePlan. Your primary job is to **surface and consolidate the existing Impact Timeline** for a requested period — not to synthesize or invent. The timeline is built incrementally each sweep (Phase 8.5). This skill reads it and presents it cleanly.

Generate a narrative only when the user explicitly asks for one.

---

## Invocation

```
/noteplan-manager:generate-impact-narrative [time-period]
```

If no time period is provided, ask:

```javascript
AskUserQuestion({
  questions: [{
    question: "What period do you want to review?",
    header: "Time period",
    options: [
      { label: "This quarter", description: "Current quarter entries from Impact Timeline" },
      { label: "Year to date", description: "All entries since Jan 1 of the current year" },
      { label: "Next-level signals only", description: "Only [SCOPE+], [LEADERSHIP], [INNOVATION] entries — promotion evidence" },
      { label: "Full timeline", description: "Everything in the Impact Timeline" }
    ],
    multiSelect: false
  }]
})
```

---

## Environment

```bash
NOTEPLAN_ROOT="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
NOTES_ROOT="$NOTEPLAN_ROOT/Notes"

BRAG_SHEET="$NOTES_ROOT/🏢 ServiceNow/📋 Lists/🏢📋 Brag Sheet.md"
IMPACT_TIMELINE="$NOTES_ROOT/🏢 ServiceNow/📋 Lists/🏢📋 Impact Timeline.md"
```

---

## Phase 1: Load and Filter Timeline

**Task**: `TaskCreate({ subject: "Load Impact Timeline for {period}" })`

1. Read `$IMPACT_TIMELINE`
2. Filter to the requested period (by quarter header or date range)
3. If "next-level signals only": keep only rows where the Signal column contains `[SCOPE+]`, `[LEADERSHIP]`, or `[INNOVATION]`
4. Count: N entries found
5. Report summary: "Impact Timeline — {period}: {N} entries ({X} next-level signals)"

**Mark task completed.**

---

## Phase 2: Present Timeline

Display the filtered timeline cleanly:

```
📊 Impact Timeline — Q2 2026

Initiative                    | Delivered                        | Signals          | Evidence
------------------------------|----------------------------------|------------------|----------
AXIS Config Agent ARB         | Owned arch review end-to-end     | SCOPE+ LEADERSHIP| PRD, diagrams, ARB responses
A2A POC → Fred Pilot          | Advanced to 100-project milestone| IMPACT VISIBILITY| Pilot framing, Anthropic collab
Eval Harness Design           | Stress test mode + session IDs   | INNOVATION       | Eval harness doc
Cross-team (Chandran, Arish)  | Unblocked deployment + A2A card  | IMPACT           | Meeting notes, plan updates

4 entries — 3 next-level signals
```

Then ask:

```javascript
AskUserQuestion({
  questions: [{
    question: "What do you want to do with this?",
    header: "Next step",
    options: [
      { label: "Just the timeline", description: "Done — I have what I need" },
      { label: "Write a narrative summary", description: "Generate a prose paragraph per initiative — good for perf review docs" },
      { label: "Promotion case bullets", description: "Distill next-level signals into crisp bullets for a promo doc" },
      { label: "Add missing entries", description: "I want to manually add entries the sweep may have missed" }
    ],
    multiSelect: false
  }]
})
```

---

## Phase 3 (Optional): Narrative or Promo Bullets

Only proceed here if the user requested it. Generate lightly — the timeline entries already have the content, just reformat.

### Narrative summary

One short paragraph per initiative:

```
**AXIS Config Agent ARB** — Owned the architecture review process end-to-end: PRD, diagrams, security model, and all institutional review responses. This represented a step up in cross-org accountability beyond individual contributor scope.

**A2A POC → Fred Pilot** — Advanced the A2A proof-of-concept from initial exploration to a structured pilot with a 100-project scale target. Direct collaboration with Anthropic and external pilot customer.
```

**Rules:** Lead with outcome. "Owned", "Delivered", "Drove" — not "Helped", "Worked on". One paragraph = one initiative. No fabrication — only expand on what's in the timeline entry.

### Promotion case bullets

Only for entries with `[SCOPE+]`, `[LEADERSHIP]`, or `[INNOVATION]`:

```
• **AXIS Config Agent ARB** [SCOPE+/LEADERSHIP] — Accountable for architecture governance at a scope above individual contributor: authored PRD, produced arch diagrams, drove ARB responses. Evidence: {artifacts}.

• **Eval Harness Design** [INNOVATION] — Designed stress test mode for parallel agent load testing with session ID logging for post-run debugging — frontier-adjacent technical work. Evidence: {eval harness doc}.
```

---

## Phase 4 (Optional): Add Missing Entries

If the user wants to manually add entries the sweep missed:

```javascript
AskUserQuestion({
  questions: [{
    question: "What entry do you want to add? Describe it and I'll format it for the timeline.",
    header: "New entry",
    freeText: true
  }]
})
```

Format the entry as a table row with the correct signal tags and append to the current quarter in `$IMPACT_TIMELINE`. Commit:

```bash
git add "$IMPACT_TIMELINE"
git commit -m "feat(impact): add manual entry to Q{N} {YYYY} impact timeline

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

---

## Rules

| Rule | Detail |
|---|---|
| Timeline first | Primary job is to surface the existing timeline — not to generate content from scratch |
| Narrative is optional | Only generate prose if the user explicitly requests it in Phase 2 |
| Source of truth | Impact Timeline + Brag Sheet only — never invent entries |
| Outcome language | When reformatting, lead with results: "Drove", "Owned", "Delivered" |
| Signal fidelity | Preserve the signal tags from the timeline — don't reassign or upgrade them |
| Manual entries are additive | When adding missing entries, commit them so future sweeps see them |

---

## Related Skills

- **sweep-daily-notes Phase 8.5** — accumulates timeline entries each sweep; this skill reads what was accumulated
- **manage-plans** — plan files are the evidence artifacts referenced in timeline entries
