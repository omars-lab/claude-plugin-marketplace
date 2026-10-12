---
name: simulate-conversation
description: Entry point for simulating an upcoming conversation; its main output is a Prep Sheet with two lists: the questions the other person is likely to ask (with answer shapes), and the questions the user should ask them (their concerns turned into questions). Interviews the user (who it's with, their role and relationship, what it's about, what each side wants, what each knows or suspects, length, depth), writes the Gameplan with private pre-briefs, picks the cheapest engine that fits (operator mode for 1–3 runs, workflow for larger matrices), runs it, and returns the recap. Use when the user says "simulate my conversation with…", "role-play my meeting with…", "how will my 1-1 with X go", or wants to rehearse any high-stakes conversation.
---

# Simulate Conversation

The front door for meeting simulations. You run the intake, then hand off to `simulation-manager`'s machinery: Gameplan format, `operator-protocol.md`, the workflow script, and `simctl`. Don't duplicate them; follow them.

## Step 1: Intake — Free Text

First extract everything the user already said, plus anything in the meeting note for this conversation, today's daily note, or a `vp-simulator` / `ic-simulator` brief. Then ask **one** plain-text message for the gaps only, grouped like this:

```
To set up the simulation:
1. Who — name, role, and how they relate to you (e.g. "Doug, VP, my skip-skip")
2. What it's about — what triggered it, and what's at stake
3. Your side — what you want out of it, what you're worried about, anything you'd rather not volunteer
4. Their side — what you think they want, what they know about you vs. what they probably only suspect
5. Context you both share — recent events, the state of the work
```

Don't invent answers. If the user skips something, write `(assumed)` against your best guess in the pre-brief and flag it in Step 3.

## Step 2: Intake — Choices

Use one `AskUserQuestion` call with these questions (drop any already answered):

| Header | Question | Options |
|---|---|---|
| Relationship | How are they positioned relative to you? | Above me: skip-level / VP · My manager · Peer / partner team · My report |
| Length | How long is the conversation? | 15 min · 30 min (Recommended) · 45 min · 60 min |
| Depth | How deep should the simulation go? | **Quick read**: 1 run × 3 exchanges (Recommended) · **Compare approaches**: 3 runs × 6 exchanges · **Full matrix**: 10 runs × 6 exchanges |
| Extras | Also produce… (multi-select) | Prep brief (`vp-simulator` / `ic-simulator`) · Ideal-scenario script · Top questions to prepare |

## Step 3: Build the Simulation

1. **Roles**: name the personas by role, never by person. The counterpart is `<their role> persona` (default **VP persona**); the user's side is **IC persona**, or `<user's role> persona` if they're not an IC. Real names appear only inside the instance files and the dialogue
2. **Folder**: `Notes/📽️ Simulations/📽️ YYMMDD <Name> <Meeting Type>/`
3. **Gameplan.md**: `## Shared Context`, `## Pre-brief: <Name>`, `## Pre-brief: IC`, `## Run Matrix`, `## Scoring`, `## Results`. The format and pre-brief rules are in `simulation-manager` Step 3. Suspicions go in the counterpart's brief; facts go in the user's brief as hidden cards
4. **Run matrix**, sized by Depth:
   - Quick read: 1 run, the strategy that best matches how the user actually plans to play it (ask if unclear)
   - Compare approaches: 3 runs: the user's planned approach, a strong alternative, and one negative control
   - Full matrix: 10 runs from the strategy pool in `simulation-manager`, including 2 controls
5. **Confirm**: show the pre-briefs (highlight every `(assumed)` line), the run matrix, the engine, and the cost estimate. Wait for a go

## Step 4: Pick the Engine and Run

| Depth | Engine | Why | Est. cost (price-weighted input) |
|---|---|---|---|
| 1–3 runs | **Operator mode**: follow [`../simulation-manager/operator-protocol.md`](../simulation-manager/operator-protocol.md). The main session relays between 2 persistent persona agents per run | ~3× cheaper per run; best quality; walls enforced by the operator | ~70k per 3-exchange run; ~140k per 6-exchange run |
| 4+ runs | **Workflow**: `simulation-manager` Step 4 (`simulate-conversations.workflow.js`, `model: sonnet`) | Parallel, unattended, resumable; operator relays would flood the main context | ~430k per 6-exchange run |

- **Operator mode with several runs**: interleave them. Spawn every pair's VP and IC personas up front and relay whichever reply arrives next. Keep relays terse and never echo JSON to the user mid-run
- Agent descriptions: `VP persona (sim · <Folder> · Run NN <Slug>)` / `IC persona (sim · <Folder> · Run NN <Slug>)`
- Render run files with `simctl.py render`; monitor workflows with `simctl.py status / cost`

## Step 5: Prep Sheet, Recap, and Report

**Prep Sheet.md** (`# Prep Sheet`) is the **primary deliverable**, with **two question lists**. First, `## Questions <Name> Will Ask You`: the counterpart's likely questions, merging paraphrases across all runs plus the questions in their prep. Rank by how many runs asked it × the impression swing. For each: `### N. "<question>"`, then **Asked** (X/N runs · swing), **They're testing** (from their private thoughts), **Answer shape** (the strongest pattern, with `[brackets]` for the user's real specifics), and **Avoid** (what cost points). Then **`## Questions to Ask <Name>`**: the user's concerns turned into questions. Sources: the user's pre-brief doubts, fears, and hidden cards; the IC side's prep worries; IC debrief objectives marked partly/no and `would_change`; and conditions or limits the counterpart revealed in the runs. For each: the question, **Concern** (what worry it covers), **When** (where in the meeting, usually after a related question of theirs), and **Sim signal** (the evidence from the runs). Rank by the user's biggest unmet objective first. Then `## Bring With You` (stories, the ask, a commitment, the top 2 questions to ask) and `## <Name>'s Tells` (recurring triggers from the private thoughts). Simulated stories are invented. Never present them as the user's facts; turn them into bracketed slots. Also append **two** condensed numbered lists to the meeting note's `## Archive` → `### <Name> Meeting Prep` section (fallback: today's daily note), and refresh the note's `## Exec Summary` from them, both linking [[Prep Sheet]]: `#### Prep: Questions <Name> Will Ask Me` (question → one-line answer shape) and `#### Prep: Questions to Ask <Name>` (question ← the concern it covers).


- **1 run**: skip the `sim-recap` agent. Write the Prep Sheet yourself from the run file + the counterpart's prep questions, then report: score, sponsor and flight-risk (or the equivalent outcome), the moments that moved the counterpart most and least, both sides' objectives scorecards, and any perception gap
- **2+ runs**: spawn the `sim-recap` agent on the folder (the workflow does this itself). It writes both Recap.md and Prep Sheet.md. Report the top strategy and the biggest positive and negative triggers
- **Extras** from Step 2: run `vp-simulator` / `ic-simulator` for the prep brief or ideal-scenario script, appended to the meeting note
- Fill Gameplan `## Results`; add a one-line pointer in the meeting note's prep section: `- 📽️ Simulation: [[<run file or Recap>]] — <one-line takeaway>`

**Output target: the meeting note.** Find the note for this conversation in the domain's meetings folder (e.g. `Notes/🏢 <Employer>/👤 Meetings/**/🏢 YYMMDD <Name>*.md`; match on date + name). Layout under its H1: **`## Exec Summary` first**, then **`## Archive`**, which holds all detailed prep (briefs, simulated conversations, full question lists) inside a `### <Name> Meeting Prep` section, with every heading demoted to fit and existing content never overwritten. The Exec Summary is the one screen the user reads before walking in, and it's rewritten (not appended) whenever new prep lands. It has: **Goal** (one line), **Headline** (one repeatable line), `### The Arc` (5–7 numbered beats of what the user will say, in order), `### Must-Ask` (the 3–4 questions to ask even if time runs short), `### Playbook: If <Name> ___ → Do ___` (a table, one row per likely move by them, with the user's response; built from the questions they'll ask + the simulations' triggers), `### Avoid` (one line), and `### Bring` (bracketed real-world items + links to [[Prep Sheet]] and the Archive). If no meeting note exists, ask once: create one (suggest a path that follows the CLAUDE.md naming conventions) or fall back to today's daily note (`Calendar/YYYYMMDD.md`).

## Guidelines

- **Ask once, then act**: one free-text round plus one choices round, at most
- **Cheapest engine that fits**: never use the workflow for 1–3 runs
- **Pronouns**: use those the user gives; otherwise they/them
- **Executive formatting** in every file: one-line bullets, quotes, no prose paragraphs
- Architecture, design options, and measured costs: `../simulation-manager/DESIGN.md`
