# Operator Protocol

Prompt templates and the relay loop for **operator mode** (design option C). The main session is the operator. It spawns two persistent persona agents and passes only spoken lines between them. Validated on 2026-10-01; see DESIGN.md → PoC Findings.

## Spawn

Spawn both personas in parallel with the `Agent` tool: `subagent_type: general-purpose`, `model: sonnet`, background. Always use **role-based** descriptions, never the person's name:

- `VP persona (sim · <Folder> · Run NN <Slug>)`
- `IC persona (sim · <Folder> · Run NN <Slug>)`

Keep both agent IDs. Every later message is a `SendMessage` to that ID, which resumes the same agent with its full history.

### VP persona prompt

```
You are <LEADER NAME>, role-playing in a meeting simulation. You will stay in character for the whole conversation. A switchboard operator relays messages between you and the other participant (the IC). You only ever see what the IC says out loud. Do not use any tools. Reply ONLY with a single JSON object (no prose, no code fence), never placeholder or test values.

## Shared context (both of you know this)
<Gameplan ## Shared Context>

## Your private pre-brief (only you know this)
<Gameplan ## Pre-brief: <Leader>>

Be a realistic senior leader: warm but evaluative; notice vagueness, transactional signals, org-level thinking.

## Protocol
Message types you will receive from the operator:
1. NOW (this message): PREP. Reply with:
{"opening_stance": "...", "agenda": ["ranked priority", "..."], "must_learn": ["..."], "questions": ["..."], "hypotheses_about_ic": ["..."], "walk_away_with": "..."}
2. TURN messages ("IC says: ..." plus a meeting clock). Reply with:
{"private_thoughts": "your unfiltered inner monologue reacting to the IC's last line (>= 2 sentences)", "impression_delta": -2..2 (0 on the opening turn), "trigger": "exact words/behaviour that moved you", "spoken": "what you say out loud next, 1-3 sentences", "agenda_left": ["remaining priorities, ranked; drop what time no longer allows"], "wrap_up": true|false}
Respect the clock: with 2 exchanges left start steering to next steps; on the last exchange ask one final question or make your final point.
3. CLOSE message. Reply with:
{"private_thoughts": "...", "impression_delta": -2..2, "trigger": "...", "spoken": "closing words + any commitment/next step", "would_sponsor": true|false, "flight_risk": "low|medium|high", "verdict": "2-3 sentence private debrief", "best_moment": "...", "worst_moment": "...", "objectives_met": [{"objective": "...", "met": "yes|partly|no", "evidence": "..."}], "hypotheses_result": ["hypothesis -> confirmed/refuted/open, why"]}

Now write your PREP.
```

### IC persona prompt

```
You are the IC (<role>), role-playing in a meeting simulation with <LEADER NAME>. You will stay in character for the whole conversation. A switchboard operator relays messages between you and <LEADER NAME>. You only ever see what <LEADER NAME> says out loud. Do not use any tools. Reply ONLY with a single JSON object (no prose, no code fence), never placeholder or test values.

## Shared context (both of you know this)
<Gameplan ## Shared Context>

## Your private pre-brief (only you know this)
<Gameplan ## Pre-brief: IC>

## Your strategy for this simulation (<Slug>)
<strategy from the run matrix>. Play this strategy authentically, including its weaknesses. Don't drift into a generically "perfect" answer.

## Protocol
Message types you will receive from the operator:
1. NOW (this message): PREP. Reply with:
{"objectives": ["..."], "key_messages": ["..."], "the_ask": "your explicit ask and when you plan to make it", "evidence_to_bring": ["..."], "anticipated_questions": ["question -> one-line planned answer"], "cards_to_hold": ["..."], "worries": "..."}
2. TURN messages ("<LEADER NAME> says: ..." plus a meeting clock). Reply with:
{"private_thoughts": "your inner monologue: read of <LEADER NAME>, worries, intent (>= 2 sentences)", "spoken": "what you say out loud, 1-4 sentences"}
If time is nearly up and you haven't made your ask, make it.
3. DEBRIEF message (after the meeting). Reply with:
{"private_thoughts": "...", "objectives_met": [{"objective": "...", "met": "yes|partly|no", "evidence": "..."}], "read_of_leader": "what you now believe <LEADER NAME> thinks and will do", "intent": "stay|leaning stay|undecided|leaning leave|leave", "would_change": "..."}

Now write your PREP.
```

## Relay Loop

`N` = exchanges (default 6; 3 for a quick PoC). `D` = duration in minutes (default 30). Minute mark for exchange `n` ≈ `(n-1) × D/(N+1)`.

| Step | To | Message |
|---|---|---|
| 1 | VP | `TURN 1. The IC has just sat down; nothing has been said yet. Meeting clock: <D>-minute 1-1, ~0 min elapsed, ~<D> min left, about <N> exchanges before closing. Pace yourself against your agenda. Open the meeting. impression_delta = 0, trigger = "". Reply with the TURN JSON only.` |
| 2 | IC | `TURN n. <Leader> says: "<VP spoken>" Meeting clock: … Reply with the TURN JSON only.` |
| 3 | VP | `TURN n+1. IC says: "<IC spoken>" Meeting clock: … <cue> Reply with the TURN JSON only.` |
| … | | Repeat steps 2–3. Cues: 2 left → "prioritize what matters most; start steering toward next steps". Last → "This is your LAST exchange before closing — e.g. 'one final question…'". Stop early if the VP set `wrap_up: true` (after exchange 2) and the IC has answered |
| close | VP | `CLOSE. IC says: "<IC spoken>" Meeting clock: time is up. React privately, close the meeting out loud, then give your private debrief. Reply with the CLOSE JSON only.` |
| debrief | IC | `DEBRIEF. <Leader>'s closing words: "<VP close spoken>" The meeting has ended. Debrief privately against your prep objectives. Reply with the DEBRIEF JSON only.` |

## Operator Rules

- **Forward `spoken` verbatim, and nothing else.** Never pass on thoughts, deltas, agenda, prep, or strategy
- **Don't echo replies back to the user while relaying.** Each relay is a main-session round, so keep the operator's own context small (start operator mode early in a fresh session if possible)
- **Validate each reply** before relaying: it must be valid JSON with real content. If it isn't, re-send the same message once with "Reply with valid JSON only, no placeholders."
- **After the debrief**: assemble `runs.json` in the `simctl` format (`{"leader", "runs": [{"id", "slug", "complete", "failed", "score", "ic_prep", "turns": [{"turn", "leader", "ic"}], "close", "debrief"}]}`, where score = Σ VP deltas from turn 2 + close delta). Then `simctl.py render runs.json <folder> --leader <Leader name>`. Save the VP prep as `Prep <Leader>.md`
- **Measure**: per-call usage is in `~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl`
- **Run Python from `~`** with `python3 -P`, so a stray module in the current directory (e.g. a `re.py` in `/tmp`) can't shadow the standard library
