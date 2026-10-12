export const meta = {
  name: 'simulate-conversations',
  description: 'Run N leader <-> IC simulated conversations with private pre-briefs, prep, thoughts and debriefs; one file per run, then recap what impressed vs hurt',
  whenToUse: 'Invoked by the profile-manager:simulation-manager skill after Gameplan.md is written',
  phases: [
    { title: 'Prep', detail: 'leader preps once (shared by all runs); IC preps per strategy' },
    { title: 'Simulate', detail: 'one leader agent + one IC agent per turn, per run; both debrief at the end' },
    { title: 'Write', detail: 'one back-and-forth file per run + the leader prep file' },
    { title: 'Recap', detail: 'compare runs, find divergence points, write Recap.md' },
  ],
}

// args: {
//   folder: absolute path of the simulation subfolder,
//   shared: facts BOTH people know (Gameplan "Shared Context"),
//   leaderBrief: what ONLY the leader walks in with (Gameplan "Pre-brief: <Leader>"),
//   icBrief: what ONLY the IC walks in with (Gameplan "Pre-brief: IC"),
//   gameplan: legacy fallback — used as shared context when shared/leaderBrief/icBrief are absent,
//   leader: the VP's name in this instance (e.g. 'Doug') — used in dialogue only; labels use the role 'VP'
//   ic: the IC's name in this instance, or "IC",
//   maxTurns: 6,
//   model: optional model override for the conversation agents (e.g. 'sonnet'),
//   durationMin: meeting length in minutes (default 30) — both sides see the clock,
//   runs: [{ id: '01', slug: 'Scope-First', strategy: 'what the IC leads with / how they play it' }]
// }
const { folder, leader, ic, runs } = args
const shared = args.shared || args.gameplan
const leaderBrief = args.leaderBrief || '(no private pre-brief provided)'
const icBrief = args.icBrief || '(no private pre-brief provided)'
const maxTurns = args.maxTurns || 6
const model = args.model ? { model: args.model } : {}
const durationMin = args.durationMin || 30
const minPerTurn = durationMin / (maxTurns + 1)

const NO_PLACEHOLDER = 'Do not use any tools. Never return placeholder or test values — every field must be real, in-character content.'
const strList = (min = 1) => ({ type: 'array', minItems: min, items: { type: 'string', minLength: 8 } })
const OBJECTIVES_MET = {
  type: 'array', minItems: 1,
  items: {
    type: 'object',
    properties: {
      objective: { type: 'string', minLength: 8 },
      met: { type: 'string', enum: ['yes', 'partly', 'no'] },
      evidence: { type: 'string', minLength: 15, description: 'What was said that shows it' },
    },
    required: ['objective', 'met', 'evidence'],
  },
}

const LEADER_PREP = {
  type: 'object',
  properties: {
    opening_stance: { type: 'string', minLength: 40, description: 'Your mindset walking in, fresh from what you were just in' },
    agenda: { ...strList(3), description: 'Ranked priorities for this meeting, most important first' },
    must_learn: { ...strList(2), description: 'What you must find out before you leave' },
    questions: { ...strList(3), description: 'Questions you plan to ask' },
    hypotheses_about_ic: { ...strList(2), description: 'What you currently believe/suspect about the IC — to confirm or refute' },
    walk_away_with: { type: 'string', minLength: 30, description: 'What a successful meeting gives you' },
  },
  required: ['opening_stance', 'agenda', 'must_learn', 'questions', 'hypotheses_about_ic', 'walk_away_with'],
}
const IC_PREP = {
  type: 'object',
  properties: {
    objectives: { ...strList(2), description: 'What you want to walk out with, most important first' },
    key_messages: { ...strList(2), description: 'Points you intend to land' },
    the_ask: { type: 'string', minLength: 20, description: 'Your explicit ask, if any, and when you plan to make it' },
    evidence_to_bring: { ...strList(1), description: 'Examples, numbers, stories you have ready' },
    anticipated_questions: { ...strList(3), description: `Questions you expect from ${leader}, with a one-line planned answer each` },
    cards_to_hold: { ...strList(1), description: 'Things you will not volunteer unless asked' },
    worries: { type: 'string', minLength: 30 },
  },
  required: ['objectives', 'key_messages', 'the_ask', 'evidence_to_bring', 'anticipated_questions', 'cards_to_hold', 'worries'],
}
const LEADER_TURN = {
  type: 'object',
  properties: {
    private_thoughts: { type: 'string', minLength: 60, description: `${leader}'s unfiltered inner monologue reacting to the IC's last line — never spoken` },
    impression_delta: { type: 'integer', minimum: -2, maximum: 2, description: 'How the IC\'s last line moved your impression. 0 on the opening turn' },
    trigger: { type: 'string', description: 'The exact words/behaviour that moved you (empty on opening turn)' },
    spoken: { type: 'string', minLength: 20, description: 'What you say out loud next (1-3 sentences)' },
    agenda_left: { type: 'array', items: { type: 'string' }, description: 'Your remaining priorities for this meeting, most important first — drop what time no longer allows' },
    wrap_up: { type: 'boolean', description: 'true if you got what you need and want to move to closing now' },
  },
  required: ['private_thoughts', 'impression_delta', 'trigger', 'spoken', 'agenda_left', 'wrap_up'],
}
const IC_TURN = {
  type: 'object',
  properties: {
    private_thoughts: { type: 'string', minLength: 60, description: 'IC inner monologue — read of the leader, worries, intent' },
    spoken: { type: 'string', minLength: 20, description: 'What the IC says out loud (1-4 sentences)' },
  },
  required: ['private_thoughts', 'spoken'],
}
const LEADER_CLOSE = {
  type: 'object',
  properties: {
    private_thoughts: { type: 'string', minLength: 60 },
    impression_delta: { type: 'integer', minimum: -2, maximum: 2 },
    trigger: { type: 'string' },
    spoken: { type: 'string', minLength: 20, description: 'Closing words + any commitment / next step' },
    would_sponsor: { type: 'boolean', description: 'Would you sponsor the IC to lead a team?' },
    flight_risk: { type: 'string', enum: ['low', 'medium', 'high'] },
    verdict: { type: 'string', minLength: 60, description: '2-3 sentence private debrief: what you now believe about the IC' },
    best_moment: { type: 'string', minLength: 20 },
    worst_moment: { type: 'string', minLength: 20 },
    objectives_met: { ...OBJECTIVES_MET, description: 'Score each item of your prep "walk away with" / must_learn' },
    hypotheses_result: { ...strList(1), description: 'Each prep hypothesis about the IC → confirmed / refuted / open, with why' },
  },
  required: ['private_thoughts', 'impression_delta', 'trigger', 'spoken', 'would_sponsor', 'flight_risk', 'verdict', 'best_moment', 'worst_moment', 'objectives_met', 'hypotheses_result'],
}
const IC_DEBRIEF = {
  type: 'object',
  properties: {
    private_thoughts: { type: 'string', minLength: 60, description: 'Your honest reaction walking out' },
    objectives_met: { ...OBJECTIVES_MET, description: 'Score each of your prep objectives' },
    read_of_leader: { type: 'string', minLength: 40, description: `What you now believe ${leader} thinks of you and will do` },
    intent: { type: 'string', enum: ['stay', 'leaning stay', 'undecided', 'leaning leave', 'leave'] },
    would_change: { type: 'string', minLength: 20, description: 'What you would say differently if you could replay it' },
  },
  required: ['private_thoughts', 'objectives_met', 'read_of_leader', 'intent', 'would_change'],
}

// one retry on null (schema-validation give-up or transient error) before the run is dropped
const ask = async (prompt, opts) => (await agent(prompt, opts)) || agent(prompt, { ...opts, label: `${opts.label} · retry` })

const clock = (t) => {
  const turnNo = t.filter(x => x.who === leader).length + 1
  const elapsed = Math.round((turnNo - 1) * minPerTurn)
  const left = maxTurns - turnNo + 1
  const cue = left <= 1 ? 'This is your LAST exchange before closing — e.g. "one final question…" or make your final point.'
    : left === 2 ? 'Two exchanges left — prioritize what matters most; start steering toward next steps.'
    : 'Pace yourself against your agenda.'
  return `## Meeting clock\nThis is a ${durationMin}-minute 1-1. ~${elapsed} min elapsed, ~${durationMin - elapsed} min left (about ${left} exchange${left === 1 ? '' : 's'} before closing). ${cue}`
}
const lastAgenda = (t) => [...t].reverse().find(x => x.who === leader && x.agenda_left)?.agenda_left

const spokenLog = (t) => t.length ? t.map(x => `${x.who}: "${x.spoken}"`).join('\n') : '(meeting has not started)'
const ownThoughts = (t, who) => t.filter(x => x.who === who).map((x, i) => `- turn ${i + 1}: ${x.private_thoughts}`).join('\n') || '(none yet)'
const bullets = (xs) => xs.map(x => `- ${x}`).join('\n')

const fmtLeaderPrep = (p) => `Opening stance: ${p.opening_stance}
Agenda (ranked):\n${p.agenda.map((a, i) => `${i + 1}. ${a}`).join('\n')}
Must learn:\n${bullets(p.must_learn)}
Questions:\n${bullets(p.questions)}
Hypotheses about ${ic}:\n${bullets(p.hypotheses_about_ic)}
Walk away with: ${p.walk_away_with}`
const fmtIcPrep = (p) => `Objectives:\n${bullets(p.objectives)}
Key messages:\n${bullets(p.key_messages)}
The ask: ${p.the_ask}
Evidence ready:\n${bullets(p.evidence_to_bring)}
Anticipated questions:\n${bullets(p.anticipated_questions)}
Cards to hold:\n${bullets(p.cards_to_hold)}
Worries: ${p.worries}`

// ---------- prompts (information walls: leader never sees icBrief / strategy / IC prep / IC thoughts) ----------

const leaderContext = () => `## Shared context (both of you know this)
${shared}

## Your private pre-brief (only you know this)
${leaderBrief}`

const icContext = (run) => `## Shared context (both of you know this)
${shared}

## Your private pre-brief (only you know this)
${icBrief}

## Your strategy for this run (${run.slug})
${run.strategy}
Play this strategy authentically — including its weaknesses. Don't drift into a generically "perfect" answer.`

const leaderPrepPrompt = () => `You are ${leader}. In a few minutes you have a ${durationMin}-minute 1-1 with ${ic}. Prepare for it privately, in character.

${leaderContext()}

Write your own prep notes. ${NO_PLACEHOLDER}`

const icPrepPrompt = (run) => `You are ${ic}. In a few minutes you have a ${durationMin}-minute 1-1 with ${leader}. Prepare for it privately, in character.

${icContext(run)}

Write your own prep notes, consistent with your strategy. ${NO_PLACEHOLDER}`

const leaderPrompt = (t, closing, prep) => `You are ${leader}, role-playing in a simulated meeting. Stay fully in character.

${leaderContext()}

## Your prep notes
${fmtLeaderPrep(prep)}

## Conversation so far (spoken words only)
${spokenLog(t)}

## Your earlier private thoughts
${ownThoughts(t, leader)}

${closing ? `## Meeting clock\nTime is up — ${durationMin} minutes.` : clock(t)}

## Your remaining agenda
${(lastAgenda(t) || prep.agenda).map((a, i) => `${i + 1}. ${a}`).join('\n')}

${closing
    ? 'The meeting is ending. React privately to the IC\'s last line, close the meeting out loud, then give your private debrief — including how each prep objective and hypothesis played out.'
    : t.length ? 'React privately to the IC\'s last line, then say your next line — follow up, probe, or move to your next priority. Update agenda_left. Set wrap_up if you have what you need.' : 'Open the meeting. Set agenda_left from your prep agenda.'}
Be a realistic senior leader: warm but evaluative, notice vagueness, transactional signals, and org-level thinking. ${NO_PLACEHOLDER}`

const icPrompt = (t, run, prep) => `You are ${ic}, an individual contributor, role-playing in a simulated meeting with ${leader}. Stay fully in character.

${icContext(run)}

## Your prep notes
${fmtIcPrep(prep)}

## Conversation so far (spoken words only)
${spokenLog(t)}

## Your earlier private thoughts
${ownThoughts(t, ic)}

${clock(t.slice(0, -1))}
If time is nearly up and you haven't made your ask, make it now.

Respond to ${leader}'s last line. ${NO_PLACEHOLDER}`

const icDebriefPrompt = (t, close, run, prep) => `You are ${ic}. The 1-1 with ${leader} just ended. Debrief privately, in character.

${icContext(run)}

## Your prep notes
${fmtIcPrep(prep)}

## The conversation (spoken words only)
${spokenLog(t)}
${leader}: "${close.spoken}"

## Your private thoughts during the meeting
${ownThoughts(t, ic)}

Score each prep objective, say what you now believe ${leader} thinks and will do, and what you'd change. ${NO_PLACEHOLDER}`

// ---------- rendering ----------

const sign = (n) => `${n >= 0 ? '+' : ''}${n}`
const scorecard = (objs) => objs.map(o => `- ${o.met === 'yes' ? '✅' : o.met === 'partly' ? '🟡' : '❌'} ${o.objective} — ${o.evidence}`)

const fmtRun = (r) => {
  const { run, t, close, score, icPrep, debrief } = r
  const lines = [
    `# Run ${run.id} ${run.slug}`,
    '',
    `**Strategy:** ${run.strategy}`,
    `**Outcome:** impression ${sign(score)} · sponsor: ${close.would_sponsor ? 'yes' : 'no'} · flight risk: ${close.flight_risk} · ${ic} intent: ${debrief.intent}`,
    `**${leader}'s verdict:** ${close.verdict}`,
    `**${ic}'s read:** ${debrief.read_of_leader}`,
    '',
    `## ${ic} Prep`,
    ...fmtIcPrep(icPrep).split('\n'),
    `- ${leader}'s prep: [[Prep ${leader}]] (shared by all runs)`,
    '',
    '## Conversation',
  ]
  let running = 0, turn = 0
  for (const x of t) {
    if (x.who === leader) {
      turn++
      lines.push('', `### Turn ${turn} · ~${Math.round((turn - 1) * minPerTurn)} min`)
    }
    lines.push('', `**${x.who}:** "${x.spoken}"`)
    if (x.who === leader) {
      running += x.impression_delta
      lines.push(`> 💭 *${leader} thinks:* ${x.private_thoughts}`)
      if (x.agenda_left?.length) lines.push(`> 📋 *Agenda left:* ${x.agenda_left.join(' · ')}`)
      if (turn > 1) lines.push(`> Impression ${sign(x.impression_delta)} → ${sign(running)} · trigger: ${x.trigger}`)
    } else {
      lines.push(`> 💭 *${ic} thinks:* ${x.private_thoughts}`)
    }
  }
  lines.push('', '### Close', '', `**${leader}:** "${close.spoken}"`,
    `> 💭 *${leader} thinks:* ${close.private_thoughts}`,
    `> Impression ${sign(close.impression_delta)} → ${sign(score)} · trigger: ${close.trigger}`,
    '', `## Debriefs`, '', `### ${leader}`,
    `- **Best moment:** ${close.best_moment}`, `- **Worst moment:** ${close.worst_moment}`,
    ...scorecard(close.objectives_met), ...close.hypotheses_result.map(h => `- 🔎 ${h}`),
    '', `### ${ic}`, `> 💭 ${debrief.private_thoughts}`,
    ...scorecard(debrief.objectives_met), `- **Would change:** ${debrief.would_change}`, '')
  return lines.join('\n')
}

const writeFile = (path, content, label) => agent(`Write this exact content to the file at the path below using the Write tool. Do not alter a single character. Return "ok".\n\nPATH: ${path}\n\nCONTENT:\n${content}`,
  { label, phase: 'Write', effort: 'low' })

// ---------- run ----------

phase('Prep')
const leaderPrep = await ask(leaderPrepPrompt(), { label: `prep · VP`, phase: 'Prep', schema: LEADER_PREP, ...model })
if (!leaderPrep) return { error: `${leader} prep failed — nothing simulated` }
const leaderPrepWritten = writeFile(`${folder}/Prep ${leader}.md`, `# Prep ${leader}\n\n${fmtLeaderPrep(leaderPrep)}\n`, `write prep VP`)

const simulate = async (run) => {
  const label = `run ${run.id} ${run.slug}`
  const icPrep = await ask(icPrepPrompt(run), { label: `${label} · IC prep`, phase: 'Prep', schema: IC_PREP, ...model })
  if (!icPrep) return null
  const t = []
  for (let turn = 1; turn <= maxTurns; turn++) {
    const l = await ask(leaderPrompt(t, false, leaderPrep), { label: `${label} · VP ${turn}`, phase: 'Simulate', schema: LEADER_TURN, ...model })
    if (!l) return null
    t.push({ who: leader, ...l, impression_delta: turn === 1 ? 0 : l.impression_delta })
    if (l.wrap_up && turn > 2 && turn < maxTurns) log(`${label}: ${leader} wraps up early at turn ${turn}`)
    const i = await ask(icPrompt(t, run, icPrep), { label: `${label} · IC ${turn}`, phase: 'Simulate', schema: IC_TURN, ...model })
    if (!i) return null
    t.push({ who: ic, ...i })
    if (l.wrap_up && turn > 2) break
  }
  const close = await ask(leaderPrompt(t, true, leaderPrep), { label: `${label} · close`, phase: 'Simulate', schema: LEADER_CLOSE, ...model })
  if (!close) return null
  const debrief = await ask(icDebriefPrompt(t, close, run, icPrep), { label: `${label} · IC debrief`, phase: 'Simulate', schema: IC_DEBRIEF, ...model })
  if (!debrief) return null
  const score = t.filter(x => x.who === leader).reduce((s, x) => s + x.impression_delta, 0) + close.impression_delta
  return { run, t, close, score, icPrep, debrief }
}

const results = (await pipeline(
  runs,
  run => simulate(run),
  async (r) => {
    if (!r) return null
    const path = `${folder}/Run ${r.run.id} ${r.run.slug}.md`
    await writeFile(path, fmtRun(r), `write run ${r.run.id}`)
    return { ...r, path }
  },
)).filter(Boolean)
await leaderPrepWritten

if (results.length < runs.length) log(`${runs.length - results.length} run(s) failed and are excluded from the recap`)

phase('Recap')
const metCount = (objs) => `${objs.filter(o => o.met === 'yes').length}/${objs.length} (+${objs.filter(o => o.met === 'partly').length} partly)`
const digest = results.map(r => ({
  run: `${r.run.id} ${r.run.slug}`, strategy: r.run.strategy, final_score: r.score,
  would_sponsor: r.close.would_sponsor, flight_risk: r.close.flight_risk, verdict: r.close.verdict,
  leader_objectives: metCount(r.close.objectives_met), leader_objectives_detail: r.close.objectives_met, hypotheses: r.close.hypotheses_result,
  ic_prep: { objectives: r.icPrep.objectives, the_ask: r.icPrep.the_ask, cards_to_hold: r.icPrep.cards_to_hold },
  ic_objectives: metCount(r.debrief.objectives_met), ic_objectives_detail: r.debrief.objectives_met,
  ic_intent: r.debrief.intent, ic_read_of_leader: r.debrief.read_of_leader, ic_would_change: r.debrief.would_change,
  turns: r.t.filter(x => x.who === leader).map((x, i) => ({
    turn: i + 1, leader_said: x.spoken, ic_reply: r.t[r.t.indexOf(x) + 1]?.spoken,
    reaction_to_previous_ic_line: { delta: x.impression_delta, trigger: x.trigger, thoughts: x.private_thoughts },
  })),
  close: { delta: r.close.impression_delta, trigger: r.close.trigger, thoughts: r.close.private_thoughts },
}))

const recap = await agent(`You are a simulation analyst. Below are ${results.length} simulated conversations between ${leader} (leader) and ${ic} (IC), each with the IC playing a different strategy. Both prepared privately beforehand (${leader}'s prep is identical across runs; the IC's prep varies by strategy) and both debriefed privately after. Each leader turn includes ${leader}'s PRIVATE reaction (delta -2..+2, trigger, thoughts) to the IC's PREVIOUS line.

Write ${folder}/Recap.md (heading "# Recap") in terse executive style — one-line bullets, bold lead phrases, quotes in "…", no prose paragraphs, no trailing summary. Sections:

## Leaderboard
- table: Run | Strategy | Score | Sponsor | Flight risk | ${leader} objectives met | IC objectives met | IC intent — sorted by score desc

## Objectives Scorecard
- which of ${leader}'s prep objectives / must-learns were met most and least often across runs, and which IC strategies got them met
- which IC objectives were achieved most often, and by which strategies; where both sides won vs where one side won at the other's expense
- ${leader}'s hypotheses about the IC: which were confirmed/refuted and by what

## What Impressed ${leader}
- ranked by delta and by how often it recurs across runs; for each: the IC's exact words (quote), the run(s), and ${leader}'s private thought that shows why

## What Hurt
- same format, negative deltas

## Divergence Points
- moments where the same kind of question/topic got different answers across runs and ${leader}'s reaction split; show the spread (e.g. "+2 in Run 01 vs -2 in Run 09") and what the IC did differently

## Perception Gaps
- where the IC's debrief read of ${leader} differs from ${leader}'s actual verdict (IC thought it went well but it didn't, or vice versa)

## ${leader}'s Thinking Patterns
- recurring concerns, tests, and tells in ${leader}'s private thoughts — what ${leader} is really evaluating

## Top 5 Questions to Prepare For
- consolidate ${leader}'s questions across all runs (merge paraphrases); rank by frequency × impression swing (how much the answer moved the score)
- for each: ### N. "<canonical question>" — asked in X/${results.length} runs · swing −a..+b; then bullets: **Best response** (quote from the top run, tightened), **Why it lands** (${leader}'s private thought), **Avoid** (what tanked it, with run link)

## Composite Ideal Script
- best line per stage of the meeting, stitched from the top runs (A, B, C… with "${leader}:" and "IC:" lines)

## Recommendations for the Real Meeting
- 5-8 concrete do / avoid bullets, including what to put in the IC's own prep

ALSO write ${folder}/Prep Sheet.md (heading "# Prep Sheet") — the PRIMARY deliverable, with two question lists. First, ## Questions ${leader} Will Ask You: ${leader}'s likely questions merged across all runs + ${leader}'s prep questions, ranked by runs-asked × impression swing. For each: ### N. "<question>", then bullets **Asked** (X/${results.length} · swing), **${leader} is testing** (from private thoughts), **Answer shape** (strongest pattern with [brackets] for the user's real specifics — simulated stories are invented, never present them as the user's facts), **Avoid**. Then ## Questions to Ask ${leader}: the IC's concerns turned into questions. Sources: IC pre-brief doubts and hidden cards, IC prep worries, IC debrief objectives marked partly/no and would_change, and limits ${leader} revealed. For each give **Concern**, **When**, and **Sim signal**, ranked by the IC's biggest unmet objective first. Then ## Bring With You and ## ${leader}'s Tells.

Link each run as [[Run NN Slug]] and ${leader}'s prep as [[Prep ${leader}]]. Use the Write tool. Return a 3-line summary: top strategy, biggest positive trigger, biggest negative trigger.

## Shared context
${shared}

## ${leader}'s pre-brief
${leaderBrief}

## IC's pre-brief
${icBrief}

## ${leader}'s prep (all runs)
${fmtLeaderPrep(leaderPrep)}

## Runs (JSON)
${JSON.stringify(digest, null, 1)}`, { label: 'recap', phase: 'Recap' })

return {
  folder,
  runs: results.map(r => ({ run: `${r.run.id} ${r.run.slug}`, score: r.score, sponsor: r.close.would_sponsor, flight_risk: r.close.flight_risk, ic_intent: r.debrief.intent, path: r.path })),
  recap,
}
