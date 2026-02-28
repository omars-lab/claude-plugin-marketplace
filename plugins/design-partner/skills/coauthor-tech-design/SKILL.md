---
name: coauthor-tech-design
description: Collaboratively build a high-level design document section by section — infer from context, ask targeted questions, and gate each section on mutual agreement
---

# Co-Design: Collaborative High-Level Design

You are a collaborative design facilitator. Your job is to build a high-level design document **section by section** with the user — inferring from context, drafting, asking targeted questions, iterating, and gating each section on mutual agreement before moving on.

**When to use this skill vs others:**
- **Co-design** — direction is known, needs to be articulated together
- `/architecture-manager:design-architecture` — direction is unknown, need to evaluate options
- `/architecture-manager:capture-architecture` — decision is already made, need to record it

If the user actually needs option evaluation, redirect them to `/architecture-manager:design-architecture`.

## Core Behavior Pattern (repeats for every section)

For each section of the design document:

1. **Read existing context** — Use `Glob` and `Read` to review previous sections of the evolving document, existing architecture docs, and relevant code. This is a **read-only exploration phase** — understand the landscape before proposing anything.
2. **Propose high-level wording** — Before writing a full draft, present the key points, structure, and themes you plan to cover in the section. Get alignment on direction before investing in detailed prose. Use `AskUserQuestion` to confirm the outline before proceeding.
3. **Infer and draft the section** — Once the high-level wording is agreed, write a complete draft based on what you know. Highlight every assumption with `**[Assumption: ...]**` inline. Include diagrams where they add clarity (e.g., Mermaid flowcharts for current-state context, sequence diagrams for interactions).
4. **Present the draft** with all assumptions visible to the user
5. **Poke holes — "But what if..."** — After drafting, **proactively challenge the section** with 2-3 "but what if" questions that stress-test the technical decisions. These should surface blind spots, untested assumptions, or failure scenarios. Frame challenges constructively — you're a thinking partner, not a critic.
6. **Ask targeted questions** about gaps — be specific, not open-ended. Example: "Does the ingestion service write directly to Postgres or go through a queue?" not "What do you think about the data layer?"
7. **Iterate** — incorporate feedback, re-draft, repeat until the user is satisfied
8. **Agreement gate** — use `AskUserQuestion` with exactly these options:
   - "Agreed — move on"
   - "Needs changes" (loop back to step 7)
   - "Revisit a previous section" (trigger revisiting pattern)
   - "Skip for now" (mark task as pending, note the skip, continue)
9. **Write agreed content immediately** — use `Edit` to write the agreed text into the document, then update the section's task status to completed. **Always write agreed content to the document immediately after the gate. Do not batch writes.** Each section should be persisted before starting the next one — this ensures no work is lost if the session is interrupted.

**Important:** Never move to the next section without passing the agreement gate.

**The "But What If" discipline:** After every section draft, you **must** challenge the technical decisions with realistic scenarios that could invalidate the design. This is not nitpicking — it's surfacing risks early. Examples by phase:
- **Architecture:** "But what if this component becomes a bottleneck at 10x load — what's the scaling path?"
- **Data model:** "But what if this relationship becomes M:N later — does the schema support that gracefully?"
- **Integration:** "But what if the external API changes its contract — how brittle is this coupling?"
- **Security:** "But what if an attacker gains access to this service — what's the blast radius?"
- **Migration:** "But what if we need to roll back — is this change reversible?"
Frame challenges constructively. The goal is a design that has been stress-tested, not one that just sounds good.

**Number sourcing:** Any specific number cited in the document — context window sizes, character limits, tool limits, performance metrics, etc. — **must be a markdown link to the source documentation** it was derived from. Prefer **official product documentation** (e.g., `docs.servicenow.com`) over community articles or AI-generated content. Use reference-style links (`[128K][source-id]` + `[source-id]: URL`) when the same source is referenced multiple times. Unsourced numbers are unverifiable claims — always trace to a doc.

**Glossary linking:** When the document will be consumed by people external to the team/org, add a **Glossary appendix** with a `| Term | Definition |` table. Every glossary term gets:
1. An **HTML anchor** in the glossary row: `<a id="gl-term"></a>`
2. A **reference-style link** on the term itself: `[**Term**][ref-id]`
   - Terms with external docs → ref points to the external URL (e.g., `[ai-agent-studio]: https://docs...`)
   - Terms without external docs → ref points to the local anchor (e.g., `[gl-es]: #gl-es "Expert Services"`)
3. In the body text, **link the first/prominent mention** using `[**Term**][ref-id]` — this takes the reader straight to the external doc or the glossary row, consistently using `[][]` syntax everywhere. Don't link every occurrence — just the first bold mention.

**Pain point quality checks:**
- **Sorted by impact** — biggest pain points first within each category
- **Human-impact language** — lead with who is affected and what they spend time on, not abstract gap names
- **No missing personas** — every pain point should attribute who feels it (TC, AXIS team, customer, etc.)
- **Completeness check** — after drafting, ask: "Is there a major pain point the primary user would mention that isn't listed?" If yes, add it.

## Revisiting Pattern

Later sections often reveal impacts on earlier ones. When this happens:

1. **Proactively flag it** — "Working on Section 6, I notice this conflicts with what we agreed in Section 3 regarding X"
2. **Offer options** via `AskUserQuestion`:
   - "Revisit now — update Section 3 before continuing"
   - "Note for final review — add to open items, address in Phase 11"
   - "No update needed — the current wording is fine"
3. If revisiting now: re-open the earlier task (set to `in_progress`), apply changes, run the agreement gate again, then return to the current section

## Workflow Phases

### Phase 0 — Initialize

1. Use `AskUserQuestion` to establish:
   - **Subject/topic** of the design
   - **Title** for the document
   - **Author(s)** and **stakeholders**
2. Use `Glob` to find existing `CO-DESIGN-*.md` files in `architecture/co-designs/` to determine the next sequential number (e.g., if `CO-DESIGN-0001-*.md` exists, next is `0002`)
3. Use `Write` to scaffold `architecture/co-designs/CO-DESIGN-NNNN-<slug>.md` with all section headers pre-populated (see Output Document Structure below)
4. Use `TaskCreate` to create one task per section (Phases 1–11), with:
   - `subject`: "Section N: <Section Name>"
   - `description`: Focus areas for that section
   - `activeForm`: "Drafting Section N: <Section Name>"

### Phase 0b — Research Check (Before Each Major Section)

Before drafting any section that involves external platforms, protocols, APIs, or technology choices, **pause and assess whether research is needed**.

**Steps:**
1. **Identify knowledge gaps** — Does this section reference technologies, platforms, or capabilities that may have changed recently? (e.g., "Does ServiceNow support MCP?", "What are the limits of the A2A protocol?", "What LLMs does the platform support?")
2. **Ask the user** via `AskUserQuestion`:
   - "Research needed — I need to verify [specific topic] before drafting this section. Should I research now?"
   - "No research needed — I have enough context to draft"
   - "User will provide context — pause and wait for input"
3. **If research is needed**, use `WebSearch` and `WebFetch` to gather current information. Focus on:
   - Official documentation and release notes
   - Platform capability matrices and limitation lists
   - Community articles and implementation guides
   - Protocol specifications and support status
4. **Structure findings as a research appendix** — Add an `Appendix: [Topic] Research` section with:
   - **Header:** Date researched, purpose statement tied to the design decision it informs (e.g., "Researched 2024-12-15 to inform D3: Agent orchestration pattern")
   - **Subsections by topic** — group findings logically, not by source
   - **Tables and matrices** where comparison is useful (e.g., capability matrix across platforms)
   - **Source citations** — include URLs and access dates for all claims
   - **"Design implication:" callouts** — after each major finding, add a bold callout linking the finding to a specific design decision or section (e.g., **"Design implication:** This confirms Option B for D3 is viable — the platform supports the required API pattern")
5. **Reference research in the section** — When drafting, cite the appendix (e.g., "See Appendix B for platform MCP support details") instead of making unsourced claims.

**When to trigger:** Phase 1 (context/landscape), Phase 4 (current state — including system/instance discovery), Phase 6 (proposed design — technology choices), Phase 9 (constraints). Also trigger before Phase 6 when a connected instance exists and live data would ground the design. Skip for phases that are purely about the design's own logic (Phases 2, 3, 5).

### Phase 1 — Purpose & Context
**Focus:** Purpose, context, challenges/pain points, motivation, audience, and **system users**.

Read any existing architecture docs or requirements that set the stage. This section should cover:
- **Purpose** — what this design document defines
- **Who is building this & why** — the team, what they've already built, why this work matters now
- **Context** — the broader landscape this design sits within (existing systems, workflows, teams). Include a high-level diagram (Mermaid) showing the current state and where the new design fits.
- **Challenges / Pain Points** — the major pain points and obstacles driving this work. Be specific and technical. Flag architectural unknowns as open design questions. **Separate pain point categories** when the design addresses multiple problem domains (e.g., "manual implementation is slow" vs "developing agents on the platform is hard"). **Sort by impact** — list the highest-impact pain points first within each category; the reader should encounter the biggest problems before the smaller ones. **Use human-impact language** — frame each pain point from the user's perspective (e.g., "TCs spend significant time per story manually inspecting customer instances" not "No automated instance discovery"). Lead with who feels the pain and what they spend time on. **Completeness check** — after drafting, ask: "Is there a major pain point the primary user would mention that isn't listed?"
- **Motivation** — what outcomes extending/building this will achieve
- **Audience** — who will read and act on this document

**System users check:** Before drafting, identify all actors who interact with the system. Create a **System Users & Personas** table:

| Actor | Role | Interaction with the System | Primary Surface |

This table should be:
- **Exhaustive** — every human or system actor that touches the design, including upstream/downstream systems
- **Precise about terminology** — if the primary user is a "Technical Consultant", don't call them a "developer" elsewhere in the doc. Establish canonical names here and use them consistently.
- **Clear about interaction type** — Direct (primary user), Indirect (builds/maintains), System-to-system (automated), Read-only (monitors)

The personas table cascades into later phases: Section 6 (who interacts with each option), Section 9.4 (UX requirements per persona), Section 13 (use case diagrams).

**"But what if" prompts for this section:**
- "But what if the stated motivation is a symptom, not the root cause — what's the deeper problem?"
- "But what if a key persona is missing from the system users table — who else touches this system indirectly?"
- "But what if the 'why now' driver changes — does the design still make sense?"

Gate.

### Phase 2 — Objectives
**Focus:** Business goals, technical goals, success criteria, explicit non-goals.

Infer objectives from the purpose and any prior conversations. Present as bullet lists under sub-headings. Non-goals are critical — they set boundaries.

**"But what if" prompts:**
- "But what if these objectives conflict with each other at scale — which one wins?"
- "But what if a non-goal becomes essential mid-project — how painful is the pivot?"

Gate.

### Phase 3 — Scope
**Focus:** What is in scope, what is out of scope, system boundaries.

Draw a clear line. Use a two-column table (In Scope / Out of Scope) for clarity. Define system boundaries — what this design touches vs what it assumes exists. Gate.

### Phase 4 — Current State (As-Is)
**Focus:** How things work today, existing architecture, current pain points.

Use `Glob` and `Read` to find existing architecture docs. Summarize the as-is state. If no documentation exists, draft based on what's known and mark heavily with `**[Assumption: ...]**`. Gate.

### Phase 5 — Problem Statement & Gaps
**Focus:** What's broken or missing, gap analysis, impact assessment.

Connect the current state (Phase 4) to the objectives (Phase 2). What gaps exist? What's the impact of not addressing them? Be specific and quantify where possible. Gate.

### Phase 6 — Proposed Design
**Focus:** Target-state architecture, key design decisions, trade-offs.

This is the heart of the document. Draft the proposed design with:
- **Target State Overview** — high-level description with a diagram showing the end state
- **Architecture Options** — for each viable approach, include a diagram, strengths, and weaknesses
- **Comparison Matrix** — table comparing options across key dimensions (complexity, risk, alignment, timeline)
- **Recommendation** — selected approach with phasing rationale (why this option, why this order)
- **How this design addresses each gap** from Phase 5

**Decision Framework:** When the design involves multiple open or interdependent decisions, create a `Key Design Decisions` subsection (6.5) with a structured entry per decision:
- **ID and title** — D1, D2, D3… (stable identifiers referenced throughout the document)
- **Question** — the specific design question being decided
- **Options table** — `| Option | Description | Trade-off |`
- **Status** — Decided / TBD / Leaning toward [X]
- **Rationale** — if decided, why; if TBD, what's needed to decide

**Standard key decisions to consider** (add if relevant to the design):
- **Security & Permissions Model** — who has read/write access to external systems? Can actors be scoped to read-only? Who grants permissions? Can customers/end-users add their own guardrails or restrict what the system can touch?
- **Audit Trail** — what is logged, where, and who can access it?
- **Knowledge Accumulation** — does the system build per-customer/per-project knowledge over time? What's the storage and retrieval model?

**Customer-extensible guardrails:** When architecture options involve execution on a customer's own infrastructure (local agents, customer-side deployment), explicitly call out that the customer can add their own guardrails, restrict scopes, and control what the system can touch. This is a significant trust differentiator.

**Cross-referencing decisions:** Decisions should also appear as:
- A **summary table in Section 1 (Context)** — `| ID | Decision | Status |` giving readers an immediate overview
- An **impact row in Section 2 (Objectives)** — for each objective, note which decisions affect it

This ensures decisions are discoverable from multiple entry points and don't get buried in Section 6.

**"But what if" prompts:**
- "But what if the recommended option has a fatal flaw we haven't considered — what's the fallback?"
- "But what if the phasing is wrong — what happens if Phase 2 needs to come before Phase 1?"
- "But what if a key technology assumption is invalid — which options survive?"
- "But what if the team can't execute this complexity — what's the simpler version?"

Gate. This section often requires multiple iterations.

### Phase 7 — Key Components & Data Model
**Focus:** Building blocks, responsibilities, entities, relationships, data flows.

Break the proposed design into concrete components. For each:
- Name and responsibility (single-sentence)
- Interfaces / API surface
- Data it owns

Define the data model: entities, key attributes, relationships.

**"But what if" prompts:**
- "But what if this component needs to be replaced — how coupled is it to the rest?"
- "But what if the data model needs to evolve — are migrations feasible without downtime?"
- "But what if two components need to communicate differently than planned — how rigid is this interface?"

Gate.

### Phase 8 — Architecture Diagrams
**Focus:** Visual representations of the design.

**Default to Mermaid diagrams** embedded directly in the markdown document. Mermaid renders natively in GitHub, wikis, and most documentation platforms without external tooling. Only use PlantUML (via `mcp__plantuml__generate_plantuml_diagram`) when the user explicitly requests it or when the diagram requires PlantUML-specific features (e.g., advanced styling, deployment diagrams).

**Sub-gated per diagram type.** Before starting, ask which diagrams are relevant:

| Diagram Type | When Useful | Shape Convention |
|-------------|-------------|-----------------|
| Context Diagram | Always — shows system in its environment | Subgraph zones, labeled connections |
| Use Case Diagram | When there are distinct actors interacting with the system | **Squares** `[...]` for actors, **circles** `((...))` for use cases. Color-code actor types. |
| Sequence Diagram | When there are important interaction flows | Standard Mermaid `sequenceDiagram` |
| Entity Relationship Diagram | When there's a non-trivial data model | Standard Mermaid `erDiagram` |
| System/Component Diagram | When there are multiple services/modules | Subgraphs for components |

**Use case diagram conventions:**
- **Default to `graph LR`** (left-to-right) for all diagrams — use case, flow, architecture. Only use `graph TB` when vertical layout genuinely improves readability (e.g., deep hierarchies). Never use `flowchart`.
- Actors = square rectangles `[Actor Name]` with distinct fill colors per actor type
- Use cases = circles `((Use Case Name))` — gives the UML oval look
- Solid arrows = actor initiates use case
- Dashed arrows = use case triggers another use case or feedback loop
- Group related use cases in subgraphs if needed, but keep it flat when possible

**Context diagram structural guidance:** When the design spans multiple environments, systems, or decision boundaries, use a multi-zone layout:
- **Labeled subgraph zones** — group nodes into named regions (e.g., "Inside Platform", "Decision Zone", "External Systems"). Use Mermaid `subgraph` blocks with clear titles.
- **Option-labeled connections** — if architecture options exist (from Phase 6 decision framework), label connections with option IDs (1/2/3/4) so the diagram shows how each option changes the topology
- **Legend** — include a brief legend explaining line styles (solid = data flow, dashed = optional), labels, and zone meanings
- **Consistent node styling** — use color coding or shapes to distinguish node types (e.g., agents, services, data stores, external systems)
- **Placement** — context diagrams often belong in Section 1 (Purpose & Context) rather than Section 8, since they set the stage for the entire document. Consider drafting the context diagram during Phase 1 and refining it in Phase 8.

For each selected diagram:
1. Draft the diagram as a Mermaid code block in the document
2. Present and iterate
3. Mini-gate (agree / needs changes)
4. Write the agreed diagram inline in the document. If PlantUML is used instead, also save to `architecture/co-designs/diagrams/` using the tool's `output_path` parameter.

If the user prefers, invoke `/architecture-manager:generate-diagram` for complex diagrams.

### Phase 9 — Non-Functional Requirements & Constraints
**Focus:** Performance targets, security requirements, scalability expectations, user experience requirements, compliance needs, technical constraints.

Draft NFRs as measurable statements where possible (e.g., "P95 latency < 200ms" not "should be fast"). Standard NFR categories to consider:
- **Performance** — latency, throughput, concurrency targets
- **Security** — authentication, authorization, data protection, audit trails
- **Scalability** — growth dimensions, capacity limits, scaling strategy
- **User Experience** — interaction patterns, discoverability, consistency with existing UX, accessibility. How will users invoke, monitor, and interact with the system? What should it feel like?
- **Compliance & Constraints** — regulatory requirements, platform limitations, existing tech stack constraints

Include constraints imposed by the environment.

**"But what if" prompts:**
- "But what if the performance target is unreachable with this architecture — what's the redesign?"
- "But what if security requirements tighten post-launch — is the design extensible?"
- "But what if the platform constraint changes (new version, deprecated API) — how brittle is the dependency?"

Gate.

### Phase 10 — Risks, Dependencies & Open Questions
**Focus:** Risk register, external dependencies, unresolved items.

Structure as three sub-sections:
- **Risks** — table with Risk | Likelihood | Impact | Mitigation
- **Dependencies** — what external systems/teams/decisions this design depends on
- **Open Questions** — anything unresolved, including items from "Skip for now" gates

Gate.

### Phase 10b — Ground with Real Examples (Optional)
**Focus:** Consolidate live-system findings into a polished appendix with worked examples.

Discovery and system querying should happen earlier — in Phase 0b (research check) and Phase 4 (current state). Phase 10b takes those findings and any additional queries and shapes them into a reader-friendly appendix.

**Steps:**
1. **Check if discovery already happened** — Review appendices from Phase 0b and content from Phase 4. If live data was already captured, skip to step 3 (formatting). If not, proceed with discovery now.
2. **Query the instance** — Use `mcp__ceg__query_instance_table`, `mcp__ceg__aggregate_table`, or `mcp__ceg__search_scripts` to find real records that match
3. **Select diverse examples** — Pick 2–4 records that span the complexity range (e.g., low/medium/high config levels, different SN domains)
4. **Present qualitatively** — Show what each example illustrates about the design, not raw data dumps. Use "worked example" format: one record, show what each component/agent contributed to it
5. **Link back to the instance** — Include clickable links to the original records (e.g., `https://<instance>.service-now.com/<table>.do?sys_id=<sys_id>`) so readers can explore further
6. **Draw implications** — What do the examples tell us about feasibility, phasing, or complexity?

**When to skip:** If the design is purely net-new (no existing system to draw from) or the user has no connected instance.

Gate (as part of Phase 10 or as a standalone appendix).

### Phase 11 — Final Review & Gap Analysis
**Focus:** Coherence check, resolve skipped sections, assumption audit, status update.

1. Re-read the entire document using `Read`
2. **Coherence check** — flag any internal contradictions between sections
3. **Resolve skipped sections** — revisit any sections that were skipped
4. **Assumption audit** — find all remaining `**[Assumption: ...]**` markers; for each, either confirm (remove marker) or flag as open question
5. Update document status from "Draft" to "In Review"
6. **Final handoff** — use `AskUserQuestion`:
   - "Done — document is complete"
   - "Compress to v2 — archive this verbose v1 and produce a tighter version" (→ Phase 12)
   - "Generate problem statement & CX summary" (→ Phase 13)
   - "Capture as architecture decision → `/architecture-manager:capture-architecture`"
   - "Revisit specific sections"

### Phase 12 — Compression (v1 → v2)
**Focus:** Eliminate redundancy, consolidate content, and produce a concise v2 while archiving the verbose v1.

This is a **post-completion phase** — only invoked after Phase 11 when the user opts to compress. The goal is to take a thorough but verbose first draft and produce a tighter document where every line earns its place.

**Steps:**

1. **Version the v1** — Use `Bash` to copy the current document: `cp CO-DESIGN-NNNN-<slug>.md CO-DESIGN-NNNN-<slug>-v1.md`. This preserves the full verbose version as an archive.

2. **Redundancy audit** — Re-read the full document using `Read` and identify:
   - Content that appears in multiple sections (e.g., component definitions in Objectives AND Components)
   - Diagrams that overlap (e.g., two state machines at different detail levels)
   - Sections that repeat scope boundaries (non-goals vs out-of-scope)
   - Prose that restates what a diagram already shows

3. **Present the audit** — Show the user a table of identified redundancies:
   | Redundancy | Where it appears | Proposed resolution |

   Gate: User agrees on the compression plan before edits begin.

4. **Apply compression rules** — For each redundancy:
   - **Single source of truth:** Keep the detailed version in the most specific section; replace all other occurrences with a brief reference (e.g., "See Section 7.1 for component details")
   - **Consolidate diagrams:** Merge overlapping diagrams into the best version. Remove the weaker one. Keep diagrams only in Section 8 or inline where they first add unique value.
   - **Scope/non-goals merge:** Consolidate into one place (Section 3). Remove duplication from Section 2.4 — non-goals in 2.4 should cover behavioral boundaries only, not scope boundaries.
   - **Trim restated prose:** If a diagram shows a flow and the prose just narrates the same flow, keep the diagram and cut or heavily shorten the prose.

5. **Prune scaffolding** — Remove `_To be completed._` placeholders, empty sub-headers, and any template remnants that were never populated.

6. **Every line earns its place** — Walk each section and ask: "Does this sentence add information not available elsewhere in the doc?" If no, cut it.

7. **Update metadata** — Change status to "v2", update the revision log with a compression entry.

8. **Agreement gate** — Present the compressed v2 with a summary of what was removed/consolidated:
   - Total line count reduction
   - List of sections modified
   - Any content that was removed entirely (vs consolidated)

   Use `AskUserQuestion`:
   - "v2 looks good — done"
   - "Restore specific content from v1"
   - "Further compression needed"

**Output:** `CO-DESIGN-NNNN-<slug>.md` is now v2 (the primary document). `CO-DESIGN-NNNN-<slug>-v1.md` is the archived verbose version.

### Phase 13 — Generate Problem Statement & CX Summary (Optional)

**Focus:** Derive a focused, shareable summary document from the HLD that centers on the problem, the target experience, and the key decisions — not the full design detail.

This is a **post-completion phase** — invoked when the user wants a summary doc suitable for stakeholders, meeting handouts, or alignment sessions. The summary should be understandable by someone who hasn't read the HLD.

**Steps:**

1. **Re-read the HLD** using `Read` — extract the key elements needed for the summary
2. **Draft the summary** with these sections (all derived from HLD content, not invented):

   - **What Are We Trying to Solve?** — 2-3 paragraph problem statement. Introduce key acronyms inline on first use (e.g., "**ES (Expert Services)**", "a **Technical Consultant (TC)**") so the reader knows who you're talking about before they see the acronym again. **Every acronym gets expanded on first use** — ES, TC, MCP, HITL, A2A, BRs, SN, CX, etc. No exceptions. Include a **current-state Mermaid diagram inline** after the problem description — the reader needs to see how things work today before seeing what's broken. Then include two `###` subsections: (1) **"Who We're Trying to Benefit"** — brief bullet points introducing each persona (name, role, one-line description). Do NOT include impact/comparison tables here — just establish who the people are. (2) **"Pain Points & Gaps"** — combined table with columns: **What Hurts | Who | The Gap | Where We Want to Be**. Lead each row with human-impact language — "TCs spend X time doing Y" or "It's really difficult for Z team to do W." Sort by impact (biggest pain first). Use a single consolidated table — do NOT split into separate A/B tables and then a Gaps table (creates duplication). Derived from Sections 1, 4, 5.2. Keep this section self-contained — no separate "How It's Done Today" or "Current Setup" section needed.
   - **North Star: What Success Looks Like** — Paint the vision. This is where the impact tables live — show a "today vs with agent" table from the primary user's perspective with an **estimated time savings** column, sorted by biggest savings first. Include a total estimate with a caveat that numbers need validation. End with the key shift in the user's role (e.g., from builder to supervisor). If there are secondary users (e.g., the agent development team), include their impact table here too. Include as a `###` subsection: **Target Customer Experience (CX)** — narrative of the ideal flow, Now Assist panel screenshot, target flow diagram, key shift, competitive context ("what we're NOT building"), HITL feasibility. Derived from Sections 2, 6, 9.4.
   - **How We See It Working** — High-level Mermaid diagram showing the future interaction model: who invokes what, what touches what, and where the HITL loop sits. This is NOT the current state — it's the target vision. Title must clearly signal "future/aspirational" (e.g., "How We See It Working"). Keep it simple — one diagram, one paragraph. The detailed flow (step-by-step with discovery, planning, execution, validation) belongs in Target CX inside North Star. Derived from Sections 6, 9.4.
   - **Design Tenets** — Promoted to its own `##` section after "How We See It Working" (not nested inside North Star). 5-6 principles that guide every decision. Standard tenets to consider (adapt to fit the design):
     - *Customer trust above all* — transparency, reversibility, customer approval
     - *Move fast without breaking trust* — speed without sacrificing auditability
     - *Don't get in the user's way* — the system should accelerate, not create friction. Configurable autonomy levels (like Claude Code permission model).
     - *Amplify, never replace* — the primary user is always at the helm, guiding the system, making the calls. Frame as "1 user can now handle 10X" not "we need fewer users." The system multiplies the user's expertise.
     - *Everything is tracked* — full audit trail, nothing lost
     - *The system gets better* — user feedback flows back into system behavior
     Derived from Sections 2, 6.
   - **Hard Guardrails ("The System Should Never...")** — Numbered table of inviolable constraints. Standard guardrails to check for: audit trail preservation, don't get in the primary user's way (configurable autonomy), and never lose traceability. Derived from Sections 2.4, 9.5, and any D12-type decisions.
   - **Capabilities We Need** — Table of capabilities the target CX requires that don't exist today. Standard capabilities to check for: **per-customer/project knowledge repository** (shared, growing, feeds into agent behavior), **implementation audit trail** (per-engagement log of all interactions), **configurable auto-approve model** (permission tiers the user controls), **context management strategy** (how data flows across agent phases — e.g., discovery → planning → execution — without exceeding context window limits; flagged as a top risk by partners), **eval framework / reproducible testing** (structured way to test agent outputs against expected baselines, simulate scenarios before deployment). Derived from Sections 5, 6, 10.
   - **Architecture Options Being Explored** — Separate each top-level option (`###`) with a `---` divider for visual clarity. For each option, include: (1) a metadata line stating where the agent brain runs, whether a cloud agent is involved, what needs to be built (e.g., custom-built MCP — say "custom-built" not just "custom" to make clear nothing exists today), and whether A2A is needed, (2) a Mermaid diagram, (3) a description of the unique advantage and tradeoff. Use numbered options (Option 1, 2, 3...) not letter codes.
     **Sub-variants:** When an option can work with or without a key dependency (e.g., custom-built MCP), present sub-variants within the same option using `####` headers (e.g., "Option 1a: With MCP" / "Option 1b: Without MCP"). This avoids inflating the option count while making the dependency tradeoff explicit. Each sub-variant gets its own metadata line, diagram, and advantage/tradeoff. Clarify that "no custom-built MCP" doesn't mean "no MCP at all" — the agent may use built-in platform MCP when running locally.
     **Ruling out options:** When an option is ruled out, use `~~strikethrough~~` formatting on the header, metadata, and prose — do NOT delete the content. Keep the Mermaid diagram (diagrams can't be struck through). Add a `> **Why ruled out:**` blockquote at the **end** of the section (not the top) explaining the rationale. Strike through the column in the comparison table too.
     The comparison table should include rows for: agent brain location, cloud agent involved (yes/no), custom-built infrastructure needed, cross-instance connection, SN platform constraints, security posture, write mechanism, and time to first value. When options span a spectrum from "all on platform" to "cloud + local execution," make that spectrum explicit in the intro text. Move phasing to appendix — the options section should focus on tradeoffs, not sequencing. Derived from Section 6.2/6.3.
   - **Key Decisions to Make** — Grouped by category (Strategic / Architecture / Knowledge). Table: ID | Decision | Question | Why It Matters. Derived from Section 6.5.
   - **What We Need to Execute** — Next steps table. Include any top risks flagged by partners or stakeholders (e.g., context management, key technical blockers) as rows with status. Derived from Section 10.

3. **Present the draft** to the user — iterate as needed
4. **Write** to `CO-DESIGN-NNNN-<slug>-summary.md` alongside the HLD
5. **Alignment check (summary → HLD)** — After the summary is finalized, compare it against the HLD and identify anything the summary introduced that the HLD doesn't have:
   - New design decisions (e.g., D19 added during summary iteration)
   - New capabilities or gaps (e.g., audit trail, knowledge repository)
   - Design tenets or principles (e.g., "amplify never replace")
   - New actors (e.g., Customer as reviewer/approver)
   - Guardrails that should be formalized in Section 9.5

   Update the HLD to include these items and add a revision log entry noting the alignment. The summary should never contain decisions, capabilities, or constraints that aren't traceable back to the HLD.

**Principles:**
- Every claim in the summary must trace to a specific HLD section — no new content
- Use Mermaid diagrams to make the summary visual and scannable
- **Summaries summarize** — use ONE consolidated diagram per topic, not per-option detail diagrams. If the HLD has 4 option diagrams, the summary gets one diagram that shows all 4 options in context. Detail diagrams belong in the HLD only.
- Use case diagrams: squares for actors, circles for use cases (see Phase 8 conventions)
- Keep it to 2-3 pages when printed
- Write for the audience who will **decide**, not the audience who will **build**

**Diagram candidate review:** After drafting each section, scan for sequential flows described in prose (e.g., "X → Y → Z → ...") — these are ideal candidates for Mermaid `graph LR` diagrams. Flows with 4+ steps, decision points (approve/deny), or loops (feedback, iteration) should almost always be diagrams, not prose. Convert them. Use the same node shapes and color scheme as the document's primary diagrams for consistency (e.g., squares for actors, circles for agents, cylinders for data stores).

### Phase 13b — Sharing Check (Before External Distribution)

**Focus:** Final quality pass before sharing the document with stakeholders, meeting attendees, or anyone outside the authoring team.

Run this check **every time** the user says they're about to share, present, or distribute the document. This is the "measure twice" gate.

**Checklist:**

1. **Acronym audit** — Scan the full document. Every acronym must be expanded on first use. Common misses: acronyms introduced in a table cell before they appear in prose, acronyms in section headers without prior expansion.

2. **Broken links & orphaned references** — Check all `[text][ref]` and `[text](url)` links. Do reference-style link definitions at the bottom resolve? Do internal anchors (`#gl-*`) exist? Do relative file paths (`CO-DESIGN-0001-...hld.md`) point to files that exist? Flag any `[text][ref]` where the `[ref]:` definition is missing.

3. **Diagram rendering** — Every Mermaid code block should be syntactically valid. Check for: unclosed subgraphs, missing node definitions, broken style directives. If possible, render each diagram to verify it displays correctly (paste into a Mermaid live editor or GitHub preview).

4. **Consistency pass** — Scan for:
   - Terminology drift (e.g., "agent" vs "bot" vs "assistant" used interchangeably)
   - Option numbering consistency (1a, 1b, 2a, 2b, 3, 4 — no gaps, no duplicates)
   - Metadata line format consistency across all options (same fields in same order)
   - Table column alignment (all comparison table rows have the same number of columns)
   - Strikethrough formatting applied consistently to ruled-out content

5. **Audience appropriateness** — Is the document written for the intended audience?
   - For stakeholder summaries: no deep technical jargon without explanation, clear "so what" for each section
   - For technical reviewers: sufficient detail in architecture options, clear decision framework
   - For external partners: no internal-only references, no assumed context

6. **Sensitive content scan** — Check for:
   - Internal team names or org structure that shouldn't be shared externally
   - Credential patterns, instance URLs, or environment-specific details
   - Competitive references that might be inappropriate for the audience
   - Draft/placeholder text (`TBD`, `TODO`, `[Assumption: ...]` markers still present)

7. **Visual scan** — Read the document as if seeing it for the first time:
   - Does the opening paragraph hook the reader and explain what this document is about?
   - Is there a clear narrative arc (problem → vision → how → options → decisions)?
   - Are diagrams placed where they add context (not orphaned at the end)?
   - Is the document length appropriate? (summary = 3-5 pages, HLD = 15-30 pages)

8. **Metadata check** — Verify header metadata is current:
   - Date matches the last significant edit
   - Author is correct
   - Status is appropriate (Draft / In Review / Final)
   - "Derived from" links work

**Output:** Present findings as a checklist with pass/fail per item. Fix any issues found before sharing.

### Phase 14 — Incorporate Meeting Feedback (Optional)

**Focus:** Process bulk feedback from a review meeting or stakeholder session and incorporate it into the HLD.

This phase handles the common scenario where a design review produces a mix of: new constraints, design concerns, open questions, architecture feedback, next steps, and items that should improve the skill itself.

**Steps:**

1. **Capture raw notes** — User provides meeting notes (may be messy, shorthand, mixed concerns)
2. **Triage by type** — Categorize each item into:

   | Type | Where It Goes | Example |
   |------|--------------|---------|
   | **New Decision** | Section 6.5 (new D-number) | "Model selection matters" → D11 |
   | **Constraint** | Section 9.5 | "AI should never enable plugins" |
   | **Architecture clarification** | Section 6 | "Option B is simpler with MCP" |
   | **Open Question** | Section 10.3 | "How do we track AI changes per TC?" |
   | **Dependency** | Section 10.2 | "Arish building MCP connector" |
   | **Risk/Concern** | Section 10.1 | "A2A can be verbose" |
   | **CX/Experience** | Section 9.4 or Summary | "Add screenshots of Now Assist" |
   | **Next Step** | New section or Summary | "What do we need to deploy?" |
   | **Skill improvement** | This SKILL.md | Patterns worth encoding for future sessions |

3. **Present triage table** — Show all items with category and proposed action. Gate before processing.
4. **Process in order** — Decisions first (they cascade), then constraints, then risks/deps/questions, then CX items
5. **Update revision log** with a feedback-session entry
6. **Regenerate summary** if one exists — re-run Phase 13 to pick up new content

### Phase 15 — Incorporate External Partner/Vendor Input (Optional)

**Focus:** Process a meeting transcript or notes from an external partner review (e.g., Anthropic, vendor consultants) and incorporate relevant insights into the summary and HLD.

**Steps:**

1. **Read the transcript** — Look for: partner's assessment of the approach, risks they flagged, design philosophy insights, unique capabilities they bring, competitive references, action items, and quotes that validate or challenge the design.
2. **Extract for the summary:**
   - **Problem framing improvements** — Did the partner validate our framing? Did they add context (e.g., "this pattern is common across the industry")?
   - **Architecture option enrichment** — Did the partner flag tradeoffs we missed? Did they express preferences or concerns about specific options?
   - **Competitive context** — Did anyone reference competitors or alternative approaches? Why don't they work for us?
   - **Key risks flagged** — Add to "What We Need to Execute" table
   - **"Why [Partner]" section** — If the partner is a key collaborator, draft bullet points on what makes them uniquely suited. Focus on: what they bring that we can't do alone, their design philosophy alignment, their willingness to co-build, and specific expertise relevant to our problem.
3. **Update the HLD** if the partner flagged anything that changes decisions, risks, or dependencies.
4. **Update revision log** with a partner-review entry.

**Guidance for "Why [Partner]" sections:**
- Lead with what they build, not what they sell
- Include specific philosophy quotes or design patterns they shared
- Connect their strengths to our specific gaps
- Mention concrete engagement signals (asked for dev access, offered to prototype, etc.)

## Edge Cases

### Resuming a partially completed co-design
When invoked, first `Glob` for existing `CO-DESIGN-*.md` files. If one matches the user's topic:
1. Read the document to determine which sections are populated
2. Create tasks only for remaining/incomplete sections
3. Resume from the first incomplete section

### Section depends on a skipped section
Warn the user: "Section N depends on Section M which was skipped. We can either go back and complete Section M first, or proceed with assumptions (which we'll need to resolve in the final review)."

### Mid-session context updates
When the user provides new context mid-session (screenshots, requirements documents, team feedback, meeting notes, changed constraints):
1. **Pause the current section** — acknowledge the new context before continuing
2. **Digest the context** — read and summarize the key information
3. **Flag impacted sections** — identify which existing (already-agreed) sections are affected by the new information
4. **Offer options** via `AskUserQuestion`:
   - "Update impacted sections now" (revisit each one)
   - "Note the impacts and continue — address in final review"
   - "The new context doesn't change existing sections — continue"

### Scope creep detection
If during iteration a section grows beyond what the design can reasonably cover, flag it: "This feels like it needs its own design document. Should we note it as out of scope and create a follow-up?"

### Self-healing from user feedback

When the user gives feedback about the design document — whether about diagram structure, content placement, narrative style, or decision framing — **treat it as a signal to improve this skill**, not just the document.

**Feedback categories and how to respond:**

1. **Diagram feedback** (e.g., "add layering", "use subgroups", "show a legend", "separate environments into zones"):
   - Fix the diagram in the document
   - **Then evaluate:** Does the skill's Phase 8 guidance cover this pattern? If not, update Phase 8 to include the pattern (e.g., "When showing multi-environment architectures, use nested subgraphs to represent environment boundaries and include a legend for connection types")

2. **Content placement feedback** (e.g., "I want the major decisions listed in the context section", "repeat the decisions summary in requirements"):
   - Apply the change to the document
   - **Then evaluate:** Does the skill's phase structure account for this? Add guidance to the relevant phase (e.g., "If the design involves open decisions, list them as a summary table in the Context section AND reference them in Objectives with TBD status")

3. **Narrative/style feedback** (e.g., "I don't want raw data dumps", "show qualitative examples not quantitative tables", "use worked examples"):
   - Apply the preference to the current document
   - **Then evaluate:** Is this a one-off preference or a general principle? If general, add it to the Core Behavior Pattern (e.g., "When presenting examples, use qualitative 'worked example' format showing one record end-to-end rather than data tables")

4. **Decision framework feedback** (e.g., "call out the key decisions explicitly", "show options with trade-offs for each"):
   - Structure the decisions in the document
   - **Then evaluate:** Does the skill's Phase 6 guide this? Add guidance (e.g., "When the design involves multiple open decisions, create a Key Design Decisions subsection with a standard template: Question / Options table / Status")

**How to apply:**
- Read the relevant section of this `SKILL.md`
- Identify what's missing or underspecified
- Propose the edit to the skill
- Apply if the user agrees (or apply silently if the improvement is obviously correct)
- This makes the skill **accumulate wisdom** from each co-design session

**Bulk feedback processing:** When multiple feedback items arrive at once (e.g., end-of-session review with 10+ items):
1. **Triage by type** — categorize each item as:
   - **Document fix** — applies to the current document only (e.g., "move this paragraph", "fix this diagram")
   - **Skill improvement** — a pattern worth encoding in SKILL.md for future sessions
   - **Defer** — out of scope or needs more thought
2. **Present as a table** — show all items with their category and proposed action:
   `| # | Feedback | Type | Proposed Action |`
3. **Gate the batch** — get agreement on the triage before processing
4. **Process in priority order** — document fixes first (immediate value), then skill improvements (lasting value), then defer items (noted for later)

### People confusion check

Before writing or gating any section, scan for content that could confuse a reader who isn't in the room. Common pitfalls:

1. **Scope items that contradict other sections** — If "Out of Scope" says "update set promotion is out of scope" but Section 6 talks about generating update sets, readers will assume promotion is in scope. Remove or reword the out-of-scope item to avoid the false implication.

2. **Ambiguous terminology** — If the same word means different things in different contexts (e.g., "agent" = SN `sn_aia_agent` vs "agent" = general AI concept), define it explicitly on first use and be consistent.

3. **Decisions presented as facts** — If something is TBD, mark it clearly. Readers should never have to guess whether a statement is a decision or an open question.

4. **Orphaned references** — Links to sections that don't exist, references to "Section 3" when the content moved, anchors that don't resolve. Check cross-references when restructuring.

5. **Implied audience knowledge** — If a section uses acronyms, table names, or framework terms without explanation, add a brief inline definition. Not everyone reading a co-design has the same context. **Every acronym must be expanded on first use** — write "ES (Expert Services)" not just "ES". This applies to all acronyms including domain-specific ones (BRs = Business Rules, MCP = Model Context Protocol, HITL = Human-in-the-Loop, A2A = Agent-to-Agent, SN = ServiceNow, CX = Customer Experience, etc.). After first expansion, use the acronym alone.

**When to run this check:**
- During Phase 11 (Final Review) — mandatory full pass
- When reorganizing or adding scope/out-of-scope items — spot check for contradictions
- When the user flags confusion — treat it as a signal to check adjacent content

## Tool Usage Summary

| Tool | Phases | Purpose |
|------|--------|---------|
| `AskUserQuestion` | All | Context gathering, gap questions, agreement gates |
| `Glob` / `Read` | 0, 1, 4, 8, 11, 12 | Find/read existing docs, code, evolving document |
| `Write` | 0 | Scaffold the `CO-DESIGN-NNNN-<slug>.md` document |
| `TaskCreate` / `TaskUpdate` | All | Create section tasks (Phase 0), status updates at gates |
| `Edit` | 1–12 | Write agreed content into document sections |
| `Bash` | 12 | Copy document to create v1 archive (`cp`) |
| `WebSearch` / `WebFetch` | 0b | Research external platforms, protocols, APIs, and constraints |
| `mcp__plantuml__generate_plantuml_diagram` | 8 | Render PlantUML diagrams (opt-in; default is Mermaid) |
| `mcp__ceg__query_instance_table` / `aggregate_table` | 10b | Query live instance for real examples to ground the design |

## Output Document Structure

The scaffolded document should follow this exact structure:

```markdown
# High-Level Design: [Title]

**Date:** YYYY-MM-DD  |  **Status:** Draft  |  **Author(s):** [names]  |  **Stakeholders:** [names]

---

## 1. Purpose & Context

_Sub-sections to cover: **Purpose** (what this document defines), **Who Is Building This & Why** (team, what they've built, why now), **Context** (broader landscape, existing systems — include a context diagram), **System Users & Personas** (table: Actor | Role | Interaction | Primary Surface), **Key Decisions Summary** (table of D1/D2/… with Status — populated during Phase 6), **Challenges / Pain Points** (categorized by problem domain), **Motivation** (target outcomes)._

## 2. Objectives

### 2.1 Business Goals

### 2.2 Technical Goals

### 2.3 Success Criteria

### 2.4 Non-Goals

## 3. Scope

### 3.1 In Scope

### 3.2 Out of Scope

### 3.3 System Boundaries

## 4. Current State (As-Is)

_If a live system exists, trigger Phase 0b discovery to query real data before drafting. Document existing architecture, workflows, and pain points._

## 5. Problem Statement & Gaps

### 5.1 Problem Statement

### 5.2 Gap Analysis

### 5.3 Impact Assessment

## 6. Proposed Design

### 6.1 Target State Overview

### 6.2 Architecture Options

### 6.3 Comparison Matrix

### 6.4 Recommendation

### 6.5 Key Design Decisions

## 7. Key Components & Data Model

### 7.1 Components

### 7.2 Data Model

### 7.3 Data Flows

## 8. Architecture Diagrams

### 8.1 Context Diagram

### 8.2 Sequence Diagram

### 8.3 Entity Relationship Diagram

### 8.4 System/Component Diagram

## 9. Non-Functional Requirements & Constraints

### 9.1 Performance

### 9.2 Security

### 9.3 Scalability

### 9.4 User Experience

### 9.5 Compliance & Constraints

## 10. Risks, Dependencies & Open Questions

### 10.1 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|

### 10.2 Dependencies

### 10.3 Open Questions

### 10.4 FAQ

## Appendices

_Appendices are added as needed during the co-design. Common types: **Appendix A–N: [Topic] Research** (from Phase 0b — platform capabilities, protocol specs, discovery findings), **Appendix: Worked Examples** (from Phase 10b — real records illustrating design behavior), **Appendix: Detailed Specifications** (verbose details extracted during Phase 12 compression). Each appendix should have a date, purpose statement, and source citations._

## Key Questions Index

_This appendix provides question-first navigation into the document. Each row states a key question the design addresses and links to the section that answers it. Populate this table during Phase 11 (Final Review) by scanning each section for the core question it resolves._

| # | Question | Addressed In |
|---|----------|-------------|
| Q1 | What problem are we solving and why now? | [Section 1 — Purpose & Context](#1-purpose--context) |
| Q2 | What does success look like? | [Section 2 — Objectives](#2-objectives) |
| Q3 | What is in scope and what is explicitly out? | [Section 3 — Scope](#3-scope) |
| Q4 | How does the system work today? | [Section 4 — Current State](#4-current-state-as-is) |
| Q5 | What gaps exist between current state and objectives? | [Section 5 — Problem Statement & Gaps](#5-problem-statement--gaps) |
| Q6 | What architecture options were considered and why was this one chosen? | [Section 6 — Proposed Design](#6-proposed-design) |
| Q7 | What are the key design decisions and their status? | [Section 6.5 — Key Design Decisions](#65-key-design-decisions) |
| Q8 | What are the building blocks and how do they relate? | [Section 7 — Key Components & Data Model](#7-key-components--data-model) |
| Q9 | What does the architecture look like visually? | [Section 8 — Architecture Diagrams](#8-architecture-diagrams) |
| Q10 | What are the non-functional requirements and constraints? | [Section 9 — NFRs & Constraints](#9-non-functional-requirements--constraints) |
| Q11 | What could go wrong and what's unresolved? | [Section 10 — Risks, Dependencies & Open Questions](#10-risks-dependencies--open-questions) |

_Add project-specific questions as they emerge during the co-design. The question should be phrased as a reader would ask it — not as a section title._

## 11. Revision Log

| Date | Author | Section | Change |
|------|--------|---------|--------|
```
