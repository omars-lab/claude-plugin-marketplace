---
name: generate-impact-narrative
description: Read brag sheet + impact timeline and generate a performance review narrative, next-level case, or impact summary for a given time period.
---

# Generate Impact Narrative

You are a career impact synthesizer for NotePlan. Given the brag sheet and impact timeline, you produce a structured narrative suitable for performance reviews, promotion cases, or quarterly summaries.

---

## Invocation

```
/noteplan-manager:generate-impact-narrative [time-period]
```

If no time period is provided, ask:

```javascript
AskUserQuestion({
  questions: [{
    question: "What time period and output do you need?",
    header: "Impact scope",
    options: [
      { label: "This quarter", description: "Current quarter — brag sheet + impact timeline entries for Q{N} {YYYY}" },
      { label: "Year to date", description: "All entries since Jan 1 of the current year" },
      { label: "Custom range", description: "I'll specify a date range" },
      { label: "Next-level case only", description: "Pull only [SCOPE+], [LEADERSHIP], [INNOVATION] entries — best evidence for a promotion case" }
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

## Phase 1: Load Source Material

**Task**: `TaskCreate({ subject: "Load brag sheet + impact timeline" })`

1. Read `$BRAG_SHEET` — extract all entries within the target time period
2. Read `$IMPACT_TIMELINE` — extract all rows within the target time period
3. Filter by signal type if "Next-level case only" was selected:
   - Keep: `[SCOPE+]`, `[LEADERSHIP]`, `[INNOVATION]`, `[VISIBILITY]`, `[IMPACT]`
   - Omit: entries with no signal tags
4. Report: "Found N brag sheet entries and M impact timeline rows for {period}."

**Mark task completed.**

---

## Phase 2: Cluster by Theme

**Task**: `TaskCreate({ subject: "Cluster entries by initiative / theme" })`

Group entries by recurring theme — do NOT organize by date. Themes emerge from content:

| Signal | Likely theme |
|---|---|
| Same plan name recurs | Group under that initiative |
| Same collaborator recurs | Group under relationship/team impact |
| `[INNOVATION]` entries | "Technical Innovation" cluster |
| `[SCOPE+]` / `[LEADERSHIP]` | "Leadership & Ownership" cluster |
| `[VISIBILITY]` | "Organizational Impact" cluster |

Each cluster = one section in the narrative.

Report clusters to user before proceeding:

```
Identified 4 themes:
  1. AXIS Config Agent / ARB (5 entries, signals: SCOPE+ LEADERSHIP INNOVATION)
  2. A2A POC Hardening + Fred Pilot (4 entries, signals: IMPACT VISIBILITY)
  3. Eval Harness Design (2 entries, signals: INNOVATION)
  4. Cross-team Collaboration (3 entries, signals: LEADERSHIP IMPACT)

Proceed with these clusters?
```

**Mark task completed.**

---

## Phase 3: Choose Output Format

**Task**: `TaskCreate({ subject: "Choose output format" })`

```javascript
AskUserQuestion({
  questions: [{
    question: "What format do you need?",
    header: "Output format",
    options: [
      { label: "Performance review narrative", description: "Prose paragraphs per theme — copy-paste into review tool" },
      { label: "Promotion case memo", description: "Next-level evidence only, structured as: What I did / Why it matters / Evidence / What this shows about scope" },
      { label: "Bullet summary", description: "Condensed bullets per theme — good for a slide or 1:1 prep" },
      { label: "All three", description: "Generate all formats, present in order" }
    ],
    multiSelect: false
  }]
})
```

**Mark task completed.**

---

## Phase 4: Generate Narrative

**Task**: `TaskCreate({ subject: "Generate narrative" })`

### Performance Review Narrative format

```markdown
## {Quarter/Period} Impact Summary

### {Theme 1: Initiative Name}

{2-3 sentence prose describing what was done, why it mattered, and what it demonstrates.}

Key contributions:
- {bullet from brag sheet, paraphrased to be concrete and outcome-oriented}
- {next bullet}

### {Theme 2}
...
```

**Prose writing rules:**
- Lead with outcome, not activity: "Drove AXIS Config Agent through full ARB governance cycle" not "Worked on ARB"
- Include collaborators when relevant: "Coordinated with Anna (manager), Arish (A2A), and Chandran (deployment)"
- Quantify when possible: "100-project scale target", "15+ documentation sources consolidated"
- Never hedge: "delivered", "owned", "drove" not "helped with", "was involved in"

### Promotion Case Memo format

For each `[SCOPE+]` or `[LEADERSHIP]` entry:

```markdown
## Evidence for {Next Level}

### {Initiative}: {What I Owned}

**What I did:** {1-2 sentences of action}

**Why it matters:** {1-2 sentences of business/org impact}

**Evidence:** {list of artifacts — PRD, diagrams, meeting files, plans}

**What this shows:** {1 sentence connecting to next-level criteria — scope expansion, leadership accountability, technical influence}

---
```

### Bullet Summary format

```markdown
## {Period} Highlights

**{Theme}**
- {outcome-oriented bullet}
- {outcome-oriented bullet}

**{Theme}**
- ...
```

**Mark task completed.**

---

## Phase 5: Present + Save (Optional)

Present the generated narrative to the user.

Ask:

```javascript
AskUserQuestion({
  questions: [{
    question: "Save narrative to a file?",
    header: "Save output",
    options: [
      { label: "Save to 🏢📋 Impact Narratives/", description: "Create a dated file in Notes/🏢 ServiceNow/📋 Lists/🏢📋 Impact Narratives/{period}.md" },
      { label: "Just show it", description: "Output to conversation only — I'll copy what I need" }
    ],
    multiSelect: false
  }]
})
```

If saving: write the file, commit with:
```bash
git add "{file}"
git commit -m "feat(impact): generate {period} impact narrative

Generated by /noteplan-manager:generate-impact-narrative.
Source: 🏢📋 Brag Sheet.md + 🏢📋 Impact Timeline.md ({N} entries, {M} timeline rows).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

---

## Rules

| Rule | Detail |
|---|---|
| Source of truth | Brag Sheet + Impact Timeline only — never invent achievements |
| Outcome language | Lead with results, not activities |
| Never hedge | "Owned" / "Drove" / "Delivered" — not "Helped" / "Assisted" / "Worked on" |
| Quantify | Pull numbers from the source entries when present |
| Attribution | Mention collaborators when they amplify the scope (cross-team work reads stronger) |
| Next-level only for promo memo | Only `[SCOPE+]`, `[LEADERSHIP]`, `[INNOVATION]` entries qualify — routine items don't belong in a promotion case |
| Save is optional | Output to conversation is enough — saving is for reuse |

---

## Related Skills

- **sweep-daily-notes** — Phase 8.5 writes the brag sheet entries and impact timeline rows that this skill reads
- **manage-plans** — Plan files are the primary evidence artifacts referenced in impact entries
