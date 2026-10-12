---
name: simulation-manager
description: Run N simulated leader ↔ IC conversations (e.g. 10 runs of a skip-level 1-1). Each side walks in with a private pre-brief and does its own prep; the IC plays a different strategy per run; the leader records private thoughts + impression shifts per turn; both debrief against their objectives — then recap which moments impressed vs hurt and where runs diverged. Writes a Gameplan.md, one back-and-forth file per run, and a Recap.md into a NotePlan simulations subfolder. Use when the user wants to stress-test a meeting, compare approaches, or "simulate the conversation N times". Builds on vp-simulator / ic-simulator.
---

# Simulation Manager

> Most users should start with `simulate-conversation`, which runs the intake and picks the engine. This skill is the engine room it hands off to.

You orchestrate multi-run meeting simulations. Separate agents play the leader and the IC turn by turn — the leader only hears spoken words, never the IC's strategy or thoughts — so the leader's private reactions are real signals, not scripted ones. A recap compares all runs.

Architecture, information walls, per-run focus design, and trade-offs: see [DESIGN.md](DESIGN.md).

## Output Layout

```
Notes/📽️ Simulations/
  📽️ YYMMDD <Title>/          e.g. 📽️ 261001 Doug Skip-Level
    Gameplan.md               shared context, private pre-briefs, run matrix, scoring — the input
    Prep <Leader>.md          the leader's own prep notes (written once by the leader agent, shared by all runs)
    Run 01 <Slug>.md          one file per run: IC prep → conversation (💭 thoughts, impression deltas, agenda) → both debriefs
    Run 02 <Slug>.md
    …
    Prep Sheet.md             ★ PRIMARY OUTPUT: questions they'll ask you (ranked, with answer shapes) + questions to ask them (your concerns turned into questions)
    Recap.md                  leaderboard, objectives scorecard, impressed / hurt, divergence, perception gaps, top 5 questions, composite script
```

Root: `~/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/📽️ Simulations/`. Filename (minus `.md`) = H1 heading in every file.

## Modes

| Mode | When | Steps |
|---|---|---|
| **New simulation** | Default | 1 → 3, then the engine: **operator mode for 1–3 runs (default)**, Step 4 workflow for 4+ runs, then 5 |
| **Re-run** | Gameplan exists, user edited strategies or wants more runs | 4 → 5 (new run IDs continue numbering; old runs are kept) |
| **Recap only** | Run files exist, user wants a fresh analysis | Spawn the `sim-recap` agent on the folder |
| **Operator mode** | Default for 1–3 runs; ~3× cheaper per run | 1 → 3, then [operator-protocol.md](operator-protocol.md) instead of Step 4, then Step 5 |

**Choosing an engine** — Workflow (Step 4): wide unattended matrices (10+ runs), parallel and resumable. Operator mode: the main session relays between 2 persistent persona agents per run (16 → 2 agents, ~3× cheaper by price), serial ping-pong, best for a few runs. See DESIGN.md → Design Options and PoC Findings.

**Naming** — the skill is generic: the **VP persona** and the **IC persona**. The real name ("Doug") belongs only to the instance (Gameplan, pre-briefs, dialogue). Agent descriptions, agent names, and workflow labels always use the role, e.g. `VP persona (sim · 261001 Doug Skip-Level · Run 03 Ambition-First)`.

## Step 1: Gather the Scenario

Reuse whatever exists — a `vp-simulator` / `ic-simulator` brief in the meeting note (or today's daily note), plans. Read them. Ask (one `AskUserQuestion` round max) only for material gaps:
- Leader name, level, distance, stance toward the IC
- Meeting length (default 30 min)
- IC role, impact, ambitions, doubts, options
- Trigger for the meeting and the core tension
- **What each person walks in with**: what they just came out of (e.g. the workshop) and their takeaway from it, what they know vs only suspect about the other, objectives (must-get / nice-to-have), cards they won't volunteer, what they can and can't offer, mood
- Number of runs (default 10; offer 5 as the cheaper option) and turns per run (default 6)

## Step 2: Create the Folder

`📽️ YYMMDD <Leader> <Meeting Type>` under the root. If it exists, switch to **Re-run** mode.

## Step 3: Write Gameplan.md

```markdown
# Gameplan

## Shared Context
- Facts BOTH people know: who they are to each other, the trigger event, the public state of the work. Nothing private here

## Pre-brief: <Leader>
- **Role**: level / distance, accountabilities
- **Coming in from**: what they just left, and their private takeaway from it
- **Knows**: …   **Suspects (unconfirmed)**: …
- **Objectives**: must-get / nice-to-have
- **Fears**: …
- **Can offer / constraints**: what's really on the table, and what isn't
- **Hidden cards**: things they won't volunteer unless asked
- **Mood / stance toward the IC**: …

## Pre-brief: IC
- Same fields from the IC's side: role, impact, style, ambitions, doubts, options, hidden cards (e.g. a conversation with the other team), objectives, mood

## Run Matrix
| Run | Slug | Strategy |
|---|---|---|
| 01 | Scope-First | Opens with a proposed scope split between teams; org-level framing |
| … | … | … |

## Scoring
- **Prep**: the leader writes their own prep once (agenda, must-learn, questions, hypotheses about the IC), shared by all runs; the IC writes prep per strategy (objectives, key messages, the ask, evidence, anticipated questions, cards to hold)
- **Per turn**: the leader records a private impression delta (-2..+2) reacting to each IC line, with the trigger, inner monologue, and remaining agenda
- **Leader close**: would sponsor (y/n), flight risk, verdict, best / worst moment, objectives met, hypotheses confirmed / refuted
- **IC debrief**: objectives met, read of the leader, intent (stay … leave), what they'd change

## Results
- (filled after the run: link to [[Recap]] and the leaderboard top 3)
```

**Pre-brief rules** — write them as two people walking into the same room with different information. Things the leader only *suspects* (e.g. "might be talking to product") go in the leader's pre-brief as suspicions; the facts (e.g. "product's director pinged me") go in the IC's pre-brief as a hidden card. Never put the IC's doubts or options in the leader's brief as facts.

**Run matrix design** — vary one thing per run so divergence is attributable. Include 1–2 **negative controls** (e.g. transactional, anxious) to calibrate what "hurts" looks like. Typical strategy pool: scope-first, loyalty-first, ambition-first, candid-about-other-offer, team-credit/multiplier, data-driven, listener/asks-questions, cautious/guarded, transactional (control), anxious (control). Tailor to the scenario.

Show the run matrix to the user and confirm before Step 4 — this is the cost gate.

## Step 4: Run the Workflow (4+ runs)

Invoking this skill is the user's opt-in to multi-agent orchestration. Call the `Workflow` tool with:

- `scriptPath`: `<this skill's base directory>/simulate-conversations.workflow.js`
- `args`:
  ```json
  {
    "folder": "<absolute path of the simulation subfolder>",
    "shared": "<Gameplan ## Shared Context section>",
    "leaderBrief": "<Gameplan ## Pre-brief: <Leader> section>",
    "icBrief": "<Gameplan ## Pre-brief: IC section>",
    "leader": "<Leader name>",
    "ic": "<IC name, or \"IC\">",
    "maxTurns": 6,
    "durationMin": 30,
    "model": "sonnet",
    "runs": [{ "id": "01", "slug": "Scope-First", "strategy": "<strategy text from the run matrix>" }]
  }
  ```

Cost: 1 leader prep + `runs × (2 × maxTurns + 4)` agents (IC prep, turns, close, IC debrief, writer) + 1 recap (10 runs × 6 turns ≈ 162). Tell the user the estimate when confirming the matrix.

Pass `"model": "sonnet"` by default. Opus conversation agents have been blocked by the `reasoning_extraction` safeguard on the IC turns.

The workflow writes `Prep <Leader>.md`, every `Run NN <Slug>.md`, and `Recap.md` itself. The script enforces the walls: the leader's prompts only ever contain `shared` + `leaderBrief` + their own prep and thoughts.

Monitor and recover with `scripts/simctl.py` (no agents spent):
- `simctl.py status latest`: per-run progress and why failures failed
- `simctl.py cost latest`: token usage by run and role
- `simctl.py extract latest -o runs.json` then `simctl.py render runs.json <folder>`: rebuild run files, including partial runs

## Step 5: Close Out

**Prep Sheet.md** (`# Prep Sheet`) is the **primary deliverable**, with **two question lists**. First, `## Questions <Name> Will Ask You`: the counterpart's likely questions, merging paraphrases across all runs plus the questions in their prep. Rank by how many runs asked it × the impression swing. For each: `### N. "<question>"`, then **Asked** (X/N runs · swing), **They're testing** (from their private thoughts), **Answer shape** (the strongest pattern, with `[brackets]` for the user's real specifics), and **Avoid** (what cost points). Then **`## Questions to Ask <Name>`**: the user's concerns turned into questions. Sources: the user's pre-brief doubts, fears, and hidden cards; the IC side's prep worries; IC debrief objectives marked partly/no and `would_change`; and conditions or limits the counterpart revealed in the runs. For each: the question, **Concern** (what worry it covers), **When** (where in the meeting, usually after a related question of theirs), and **Sim signal** (the evidence from the runs). Rank by the user's biggest unmet objective first. Then `## Bring With You` (stories, the ask, a commitment, the top 2 questions to ask) and `## <Name>'s Tells` (recurring triggers from the private thoughts). Simulated stories are invented. Never present them as the user's facts; turn them into bracketed slots. Also append **two** condensed numbered lists to the meeting note's `## Archive` → `### <Name> Meeting Prep` section (fallback: today's daily note), and refresh the note's `## Exec Summary` from them, both linking [[Prep Sheet]]: `#### Prep: Questions <Name> Will Ask Me` (question → one-line answer shape) and `#### Prep: Questions to Ask <Name>` (question ← the concern it covers).


- Fill Gameplan.md `## Results`: `[[Recap]]` link + top 3 runs with scores
- Add a one-line pointer in the meeting note's prep section (append, never overwrite): `- 📽️ Simulation: [[Recap]] — top strategy: <slug>`

**Output target: the meeting note.** Find the note for this conversation in the domain's meetings folder (e.g. `Notes/🏢 <Employer>/👤 Meetings/**/🏢 YYMMDD <Name>*.md`; match on date + name). Layout under its H1: **`## Exec Summary` first**, then **`## Archive`**, which holds all detailed prep (briefs, simulated conversations, full question lists) inside a `### <Name> Meeting Prep` section, with every heading demoted to fit and existing content never overwritten. The Exec Summary is the one screen the user reads before walking in, and it's rewritten (not appended) whenever new prep lands. It has: **Goal** (one line), **Headline** (one repeatable line), `### The Arc` (5–7 numbered beats of what the user will say, in order), `### Must-Ask` (the 3–4 questions to ask even if time runs short), `### Playbook: If <Name> ___ → Do ___` (a table, one row per likely move by them, with the user's response; built from the questions they'll ask + the simulations' triggers), `### Avoid` (one line), and `### Bring` (bracketed real-world items + links to [[Prep Sheet]] and the Archive). If no meeting note exists, ask once: create one (suggest a path that follows the CLAUDE.md naming conventions) or fall back to today's daily note (`Calendar/YYYYMMDD.md`).
- Report to the user: leaderboard top 3, the biggest positive and negative triggers, and anything that failed

## Guidelines

- **Leader blindness is the point** — never put the IC's pre-brief, strategy, prep, or thoughts in the leader's prompt (and vice versa for the leader's pre-brief and prep)
- **Strategies, not scripts** — the IC plays an approach authentically, weaknesses included; don't let every run converge on the "perfect" answer
- **Executive formatting** in every output file — one-line bullets, quotes, no prose paragraphs
- **Pronouns** — use those the user gives; otherwise they/them
- For a single scripted ideal-scenario conversation (no runs), use `vp-simulator` or `ic-simulator` instead
