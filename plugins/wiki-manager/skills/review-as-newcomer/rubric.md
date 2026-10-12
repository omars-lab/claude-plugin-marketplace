# Newcomer-read rubric

The standard a wiki article is judged against. Read this at run time — it sharpens without the
skill changing.

**The persona.** You are a competent engineer who has never seen this vault, does not know the
projects, and arrived at this page from a search or a `[[link]]`. You have **two minutes**. You
want the answer to the question in the title, and nothing else.

---

## The tenets (everything below is a means to these)

Every rule in this rubric is mechanical, and a mechanical rule applied past its purpose damages the
page. These three are the purpose. When a rule and a tenet disagree, the tenet wins and the rule
gets a note in the verdict explaining why it was not applied.

1. **The answer reads honestly and usefully.** It says what is actually known, credits what it
   borrowed, and is worth the reader's two minutes.
2. **It does not bombard the reader on arrival.** Volume and density in the first three seconds is
   what stops someone reading at all. Front-load the answer; make everything else visibly skippable.
3. **Concepts with shape get a real diagram.** A sequence, a decision, a hierarchy, a state machine,
   parts of a whole — draw it. See §7.

**1 and 2 pull against each other, deliberately.** Tenet 1 alone justifies every caveat, citation
and cross-reference, since each is individually honest and individually useful — that is how the
pages became overwhelming in the first place. Tenet 2 alone justifies cutting until the page is
confident and thin — that is lying by omission. A page is right when it satisfies both at once, and
tenet 3 is how it escapes the trade-off: a diagram carries structure that would otherwise cost
paragraphs, buying honesty back without spending attention.

So: **"this line matches a pattern I am told to delete" is not sufficient reason to delete it.** The
question is whether the page is still honest, still useful, and still unintimidating without it.
That is a judgement — make it by reading the line, never by matching it.

---

## 0. Read the raw file, and check it mechanically (do this before anything else)

**Read the `.md`.** Not a screenshot of it. An earlier version of this rubric opened every review
with a NotePlan render, and the user closed that loop deliberately: the same content is in the raw
file, the render costs a round trip and an image read per page, and it is the *slower* way to see
almost everything. Renders are now reserved for one job — checking how a **new markdown or editing
technique** lands in the app, once, before it is used on thirty pages. Everything else is read.

What that gives up is small, and already written down. NotePlan's render limits are **knowledge you
carry**, not a measurement you repeat per page: it has no callout syntax (`> [!context]` prints as
literal italic text), HTML comments are visible body text, a remote `http://` image never loads at
all (see `docs/issues/noteplan-renders-only-local-image-attachments.md`), and inline markup broken
across a wrapped line does not take. Every one of those is findable in the source once you know to
look. Dimmed asterisks and backticks around applied formatting are the editor showing its work,
never a finding.

What the raw file gives back is the class of defect a render is blind to, because the app draws a
plausible page over the top of it. Run the structure checker on **every** file you touched:

```bash
python3 .claude/hooks/note_structure.py <page.md> <its verdict.md>
```

It lives in the vault (`.claude/hooks/`), not in this plugin, because the Stop hook calls it too.
Four codes: `TITLE` (the first line after the frontmatter must be `# <Title>`, matching the
filename), `FM_HASH` (a `#` comment inside frontmatter), `FM_UNCLOSED`, and `SPAN` (an unbalanced
bold delimiter or `[[link]]` across a hard newline). It exits 1 on any issue, prints nothing clean.

This earned its place four times in one session, and the lesson behind it is the one to keep:
**a page can be hash-fresh, validator-clean and structurally broken at the same time.**
`check_evidence.py` reads frontmatter and links; `check_verdicts.py` hashes whatever is there;
neither looks at the H1. So none of them noticed a stray `kd` line, a page that had lost its whole
`sources:` block, a verdict whose prose tripped `SPAN` — or a page whose entire `# ` heading had
been reduced to the three characters `ar?` by a NotePlan partial-buffer write-back, which **shipped
in a commit already reported as verified**.

Two traps in that command, both paid for:

- **Sweep the verdicts too — never `-not -path "*@Verdicts*"`.** The Stop hook reports issues by
  `os.path.basename(p)`, and a verdict has *the same basename as the article it reviews*. Excluding
  the verdict tree does not merely miss the defect: it confirms the wrong file clean, twice, while
  the hook goes on firing. The sweep that is actually correct is
  `find "Notes/📚 Wiki" -name "*.md" -print0 | xargs -0 python3 .claude/hooks/note_structure.py`.
- **A verdict that quotes markup trips its own check.** `SPAN` counts bold delimiters per physical
  line and cannot tell that a stray pair sits inside a code span. When writing *about* markup — and
  verdicts do this constantly — spell the character out ("asterisks", "a bold span") rather than
  quoting it bare.

So the per-page loop is: **Read source → judge → edit → `grep -c` a phrase you added →
`note_structure.py` → hash → verdict.** The `grep -c` is not optional and is not paranoia: a note
NotePlan holds open is rewritten from its stale in-memory buffer seconds later, silently undoing
what you just wrote. A `0` there means you were clobbered and the edit must be reapplied.

**A page can go stale without anyone editing it.** NotePlan rewrites percent-encoded characters in
link paths when it saves a note — a diagram attached as `…detect%3F_attachments/floor.png` comes
back as `…detect?_attachments/floor.png` — so every page carrying a diagram drifts out of hash
freshness on its own, with no content change. When `check_verdicts.py` reports a page stale, diff it
before re-reading it: if the only change is link encoding, refresh the `page_hash` and log one line
in the verdict saying why, rather than either re-reviewing a page nobody touched or silently
re-hashing it. Do **not** "fix" the encoding back — it is the app's own normalisation, it will drift
again, and there is no evidence either form fails to render.

**If you do render** — a new technique, or a diagram you want to see at reader scale — the clobber
rule applies in its original form: **edit first, render second, never the reverse.** A render opens
the note in the app. If the render then reveals another edit is needed, render a **different** note
first (which moves NotePlan's open buffer off your file), then edit, then `grep -c` to confirm it
survived. The flags and the `-1743` Automation wall are in the **render-wiki-page** skill.

## 1. The lean-body shape (structural — mechanical, check first)

A page body is **only** these, in this order:

| Part | Purpose for the newcomer | Expected size |
|---|---|---|
| `**Short answer.**` | The whole answer, standalone. If they read nothing else, this is enough. | 1–3 sentences |
| `## Evidence` | How we know, with `— [[source]]` attributions. Skippable by design. | the bulk |
| `## Context` | Plain prose — why this matters, what it connects to. Read *if interested*. | 1 short para |
| `## Gaps` | Plain prose — what the sources do NOT settle. Read *if acting on it*. | 1 short para |

The split is deliberate: the **Short answer is the answer**, `## Evidence` is the receipts. A
page that answers the question twice — once in the bold line and again as a paragraph under the
next heading — is the repetition a newcomer feels as "overwhelming", and it is also how a
summary drifts from what it summarizes. (One page claimed a headline statistic for the wrong
cause precisely because the same claim was maintained in two places.)

**The restatement defect — check this on every page.** It is the commonest bloat in the wiki and
the cheapest to fix: *does the first paragraph of `## Evidence` add a fact the Short answer does
not already contain?* When it does not, the cause is always the same authoring order — a sourced
headline sentence gets promoted into Evidence first, and the Short answer is written from it
afterwards, so the reader pays for one claim two or three times before any new fact arrives. Six of
eight pages in one topic had it. The fix is never to delete the paragraph and leave a gap: replace
it with a **lead line that introduces the structure** of what follows — `The eleven, all in
scripts/hooks/:` — which is a sentence only Evidence can carry, and which earns the reader's next
three seconds instead of spending them.

**A markdown pipe table is available, and is sometimes the honest shape.** NotePlan renders
`| a | b |` tables natively (verified by render, which is exactly what a render is for), so a
comparison the page is genuinely making — four transforms against what each one costs, three
options against who they serve — can be a table instead of a paragraph that asks the reader to hold
eight numbers in their head. The test is the same one §7 applies to diagrams: the table must be a
comparison the answer actually makes, with the rows sharing a dimension. A table of unrelated facts
is the wall of text this rubric exists to remove, wearing a grid. Keep it small — five rows and two
or three columns is the size that reads; anything larger belongs in the source, not the page.
**Put the source's own figures in it**, not rounded ones: a table invites exactly the
column-to-column comparison that rounding distorts, and `check_evidence.py` check 2 flags the
rounded values as ungrounded, which is the check doing its job rather than a false positive.

Anything else in the body is a finding:

- **A provenance paragraph** — "The full statement states the same outcome, in fewer words", "both
  sources agree on the figure". That is a sentence about which source said what, and `sources:`
  frontmatter already records it. This is the user's rule applied literally: the notes a page is
  derived from belong in frontmatter, never in the reader's paragraph. Delete it, folding any fact
  it uniquely carried into the surviving lead line. A *disagreement* between sources is different
  and stays — that is a finding about the evidence, and it belongs in `## Gaps`.

- **`## Builds on` / `## Leads to` body sections** → must not exist. Cross-links are
  frontmatter (`prerequisites:` / `leads_to:`). Delete the section; make sure every link it held
  survives in frontmatter first.
- **`## Answer`** → the old name for `## Evidence`. Rename it.
- **`> [!context]` / `> [!gap]` markers** → NotePlan has no callout syntax; delete the marker line.
- **A `>` annotation on a RAW note** (inbox, not an article) → an annotation is a fenced code
  block. In a raw note the surrounding text is the user's, so a blockquote is backwards — the
  annotation is the intrusion, not the quotation. Leave `>` lines that arrived *with* the source
  (a pasted transcript, a quoted template) exactly as they are: those are content, and rewriting
  them breaks content-preservation.
- **A `>` on anything that is not a quotation** → most often the whole of `## Context` / `## Gaps`.
  A blockquote says "someone else's words", and NotePlan renders it as such (grey, italic, ruled),
  so quoting your own synthesis misattributes it and makes a light paragraph look heavy. Unquote it
  and **rejoin the wrapped lines into one physical line** — a blockquote flows its own wrap, plain
  prose in NotePlan does not, so unquoting without rejoining turns a paragraph into stubs. Those
  sections are exempt from grounding because of the section they are in, not because of a prefix.
- **HTML comments** → they are visible to the reader. Delete them from any page a reader opens.
  Only the `@References/` templates keep theirs, and only because their reader *is* the author.
- **`— [[note]]  (base)` attribution tails** on any evidence line → the provenance belongs in
  `sources:` / `prerequisites:` frontmatter, not tacked onto the end of every sentence. One page
  repeated the same `— [[Lana Fish Allergy]]  (base)` on four consecutive bullets. Lift the link
  into frontmatter **first**, then strip the tail, or the page loses the grounding
  `check_evidence.py` reads from its links. Look at **paragraphs** too, not just bullets: two
  thirds of the 272 tails migrated in 0.9.0 were on prose lines, including some stranded after a
  colon (`The questions, grouped as raised: — [[note]]  (base)`), which reads worse than the bullet
  case. Treat the parenthetical as noise whatever it says — the tags were hand-written and drifted
  (`(base fact from source)` is the same metadata in longer words).
  But a link the sentence is *built around* ("Because [[X]] establishes Y…", "see [[Z]], which
  implements it") stays — that is prose carrying information, not a tail the reader steps over.
  **A space index is the exception**: there the `— [[raw note]]` on each base fact *is* the column
  the reader came for, and an index has no `sources:` key for it to move to. Leave indexes alone.
- A section the template does not define (`## Notes`, `## See also`, `## References`, …) →
  fold it into `## Evidence`/`## Context` or drop it.
- Frontmatter that repeats what the body says, or body text that restates frontmatter.

`bin/migrate_body_shape.py --wiki <dir> --check` reports the first four mechanically;
`bin/migrate_attributions.py --wiki <dir> --raw <notes dir> --check` reports the tails, and lists
separately the lines it will **not** touch because a human has to judge whether the link earns its
place. Read every line it defers — it flags the whole line whenever any prose sits between a dash
and a link, so the list mixes genuine prose cross-references (keep) with half-bare lines that need
a hand edit. It also leaves any leftover `(derived)` fragment with no link in front of it; that is
orphaned schema noise and should just go.

## 2. The two-minute test (judgment — this is the real work)

Read the page cold, in order, and answer each:

1. **Does the Short answer actually answer the title question?** A Short answer that
   summarizes the *topic* instead of answering the *question* is the single most common
   failure. The title is a question; the first line owes it an answer.
   Then the paired check: **does `## Evidence` agree with it?** Every number and causal claim
   in the Short answer must be the same number, attached to the same cause, as the evidence
   below. A summary that drifts from its own receipts is a false fact the reader leaves with.
2. **Where did you stop needing to read?** Everything after that point is *skip* material.
   Name it in the verdict — that is the most useful thing the verdict says.
3. **Where did you get stuck?** An undefined acronym, a machine-generated identifier, a
   project name assumed known, a `[[link]]` you had to follow to parse the sentence. Each
   one is a fix: define it inline on first use, or make the prerequisite explicit in
   `prerequisites:`.
4. **Is the evidence doing work, or padding?** A block quote or code fence that the
   surrounding prose already states in full is padding. Grounding is not the same as bulk:
   one precise quote beats five.
5. **Would you trust it?** A claim in `## Evidence` with no `— [[source]]` and no "Because
   [[X]] establishes…" is unsourced. Flag it.
6. **Is any claim on this page testable? Then test it — do not reason about it.** This is the
   check that catches the worst defect a wiki can have: a page confidently repeating something
   its own source got wrong. Reading the page cannot find these, and neither can thinking
   carefully about them; only running the thing does. Two were caught this way in one sitting:

   - A Kotlin page said `this@apply` inside a nested block reaches the *outer* receiver, copied
     from a chat transcript that asserted it. Twelve lines of `.kts` run against the actual
     compiler showed it resolves to the **inner** receiver. The page now says the opposite of
     its source, and records why.
   - A Chrome DevTools page recommended `--remote-debugging-port` as the fix. The raw transcript
     showed that step being tried and **failing** before the session did something else. The
     page was leading readers down a path its own evidence had already closed.
   - A page said a `can_use_tool` phase gate keeps blocking writes under `bypassPermissions`,
     because the project's own design note said so. The SDK auto-approves before the callback is
     consulted, so the guardrail never fires. Two lessons: **an internal design note is a weaker
     source than a transcript, not a stronger one** — it records intent, not what happened — and a
     wrong fact in a `kind: base` page has already been spent downstream, so follow `leads_to:` and
     the space index before calling the fix done. Three pages carried this one.

   What counts as testing depends on the claim, and all of these are cheap: run the snippet
   (installing a compiler is fine — it took one `brew install`), read the man page, check the
   official docs, or — most often the winner — **read the raw source to its end and see what
   actually happened**, rather than what the page says happened. A page derived from a transcript
   inherits every one of that transcript's mistakes, plus any made while summarising it.

   When a test contradicts the source, the page follows the test, and both the page's `## Gaps`
   and the verdict record that the source was wrong and how it was checked. When a claim is
   testable but you could not test it, say that in `## Gaps` — "the transcript never shows this
   working" is a real finding, and far more useful than silence.
7. **Is the source a primary record, or a summary wearing one's clothes?** Open each entry in
   `sources:` and read its first ten lines before you trust anything built on it. Two cases found
   in one topic, both of which changed what the pages could claim:

   - A file named as a *retrospective* had an empty session-notes section and an appendix stating
     it was generated from a project tracker by a prompt — which the document then included. It
     contained no human retrospective content at all. Every page in the topic had been citing it
     for what the team concluded. Two of its dates had drifted from the tracker it was generated
     from, which is exactly the error that shape of source produces.
   - A file of contribution notes opened with *Based on the document, I can analyze…* and argued
     its conclusion from **frequency of mentions**. The page built on it had faithfully inherited
     its five buckets and its closing assessment, and nothing on it could be checked.

   The rule that falls out: **a generated summary of a source is a weaker source than the thing it
   was generated from, and it is usually sitting right there.** Add the primary source to
   `sources:` and rewrite from it. Where only the summary exists, say so in `## Gaps` — naming what
   a source is not is what makes the rest of the page credible. The tell is worth memorising: an
   opening line addressed to a reader, a stated derivation, categories that look like prompt
   output, or an assessment section that grades rather than evidences.

   **And when the source *is* primary, the first ten lines are still the wrong place to stop.** A
   whole topic of pages was written from one framework document's executive summary and every one
   of them was wrong in the same direction. The summary said the metrics were non-normal and so a
   t-test was unavailable; the appendix showed the team testing convergence of the sample mean, not
   normality of the data, and using a t-test on that basis. The summary said two weeks; a later
   section said four. The summary recommended a transform; the detail section showed that transform
   being tried, failing, and being replaced by something else entirely. Nothing was hidden — the
   corrections were simply further down. **An executive summary is written to be quotable; an
   appendix is written to be right.** So read the tables, the appendices and the attempts-that-
   failed sections before writing a single claim, and when the two halves of a document disagree,
   the page follows the detail and `## Gaps` records that the document contradicts itself. A page
   built from a summary of a primary source has the same defect as a page built from a secondary
   one, and it is harder to spot because the `sources:` entry is correct.

## 3. The framing fields — does this page know who it is for? (judgment)

Two frontmatter keys make a claim about the page's audience: `asked_by`, a flat list of user
stories (`as a <role doing something specific>, I need this to <task the answer unblocks>`), and
`matters_because`, one line saying what goes wrong when the answer is missing or wrong. They are
the only place a page argues for its own existence. A validator can check they are **present**; it
cannot check they are **true**, and you are the only reader in the pipeline who can, because you
just arrived at this page cold.

Do it in that order — **read the page first, then read these fields.** Knowing who the author
thinks you are contaminates the two-minute test, and the test is worth more than the convenience.
Then answer three questions:

1. **Do you recognise yourself in any entry?** You just were a newcomer on this page. If none of
   the stated stories is anything like the reason you were reading, the page is aimed at a reader
   who may not exist.
2. **Is one missing?** The commonest miss is the reader who arrives *from a failure* — the person
   debugging at 2am, not the person planning. The second commonest is the reader who arrives from
   a linked page rather than a search: look at `leads_to:` and ask what that reader needs from
   here. Name any miss; it is the most actionable thing this check produces.
3. **Does `matters_because` add something the entries do not?** It should name the stake, not
   restate a task. If deleting it would cost the reader nothing, it is decoration.

Failure shapes, all of them seen in real pages:

- **A bare role** — `- an engineer`. It names an audience without naming what the answer is for,
  and a claim with no "I need this to…" cannot be disagreed with, so it cannot be reviewed.
- **A story whose second half restates the title** — "as an engineer, I need this to know how the
  eval harness works", on the page called *How does the eval harness…*. That is the question again
  wearing a costume; a use case says what the reader does **next**.
- **`matters_because` paraphrasing the Short answer**, or the title ("matters because latency
  matters"). It is meant to say what is at stake, which is a different sentence.
- **Three entries that are one reader phrased three ways.** Two genuinely different arrival paths
  beat four synonyms.
- **An asker the page does not actually serve.** If an entry promises something the answer never
  delivers, that is a real finding — and the verdict must say whether the repair belongs in the
  field or in the page, because those are opposite fixes.

You may rewrite these fields; it is an ordinary fix under §6. But **record the finding in the
verdict even when you fixed it** — a page whose framing had to be rewritten on first read is
telling you something about how it was authored, and that signal is lost if the verdict shows only
the tidied result.

**A backfill is still a review, and the verdict says so.** Most pages predate this schema, so you
will often write `asked_by:` and `matters_because:` and then judge them minutes later. That is not a
reason to skip the `**Framing:**` line or to write a hollow one — it is a reason to be explicit
about what the line is: open it by saying the fields were backfilled this run, so a later reader
knows this is a judgement on fresh work rather than on someone else's. Then do the harder half:
**name the asker you considered and rejected, and why the page cannot serve them.** The rejected
entry is the honest part of the exercise, because the temptation on a backfill is to invent an
audience the content never earns — "someone who wants the working guardrail" on a page that only
documents the broken one, "a lead deciding what to fix first" on a list that prioritises nothing.
An asker you left out on purpose, with the reason, is worth more to the next reviewer than three
that merely sound plausible.

The verdict carries this in two places: a `**Framing:**` line in the body, and the frontmatter keys
`framing:` and `missing_use_cases:`, so the judgement is greppable across the whole wiki.

| `framing:` | Means |
|---|---|
| `agree` | The stated askers are real readers, the page serves them, and nothing important is missing. |
| `incomplete` | The entries are true as far as they go, but a use case the page genuinely serves is not listed. |
| `disagree` | An entry is not credible, restates the title, or names an asker the answer does not serve. |

`missing_use_cases:` is a flat list of the arrival paths still unlisted **after** your fixes — so
it is `[]` on a page you repaired, and the body line is where the history lives. Judge `framing:`
the way §5 judges the verdict word: on the page as it stands when you finish.

## 4. Cross-link wiring (metadata, not prose)

- Every prerequisite the answer genuinely leans on is in `prerequisites:` — and the reason is
  stated **inline in `## Evidence`** ("Because [[X]] establishes…"), never as a frontmatter gloss.
- `prerequisites` is the **authoritative** direction; `leads_to` is its mirror. If you add an edge,
  add both halves.
- A "see also" is not a prerequisite. If the answer still stands without reading the other page,
  it is **not** a prerequisite — leave it out. (Of 12 one-directional legacy edges audited during
  the migration, 11 were loose see-alsos.)
- **`kind` and `prerequisites` are independent — never "fix" one to match the other.** `kind`
  says where the facts came from: `base` = read off raw notes (`sources:`), `derived` = taken
  from other answers. `prerequisites:` says what a reader must already understand. A `base` page
  that also lists prerequisites is correct and common — 42 pages do it — because its facts came
  off a raw note *and* it still needs another answer read first. What IS a schema violation: a
  `base` page listing a wiki **article** in `sources:` (that is a prerequisite wearing the wrong
  key). Flag it; never silently rewrite `kind`.

## 5. The verdict word

| Verdict | Means |
|---|---|
| `lean` | A newcomer gets the answer and there is nothing to skip. Ship it. |
| `ok` | The answer is there, but some of the page is skippable, or one or two fixes are pending. |
| `bloated` | The newcomer has to work to find the answer: buried Short answer, padding, unexplained jargon, or leftover scaffolding. Fix it now. |

Be honest — a run of `lean` verdicts nobody believes is worth less than one `bloated` that got
acted on. If you applied fixes this run, judge the page **as it stands after the fixes**.

## 6. What a fix may touch

Only the article under review (and, when an edge is wired, the reciprocal `leads_to:` on the
other article). Never rewrite a quotation: raw sources are immutable and quoted verbatim. Never
move a page between spaces as a "fix" — that is a routing decision for `manage-wiki`. Never let a
credential, token or password into the page or the verdict.

## 7. Does this concept want a diagram? (tenet 3)

A diagram is the one edit that makes a page **more** honest and **less** intimidating at the same
time, which is why it gets its own section rather than a line in the fix list.

Ask it of every page: **does this answer have a shape?**

| Shape in the answer | Draw it as |
|---|---|
| Ordered steps, a handoff between parties | sequence diagram |
| "It depends" / branching criteria | activity or decision diagram |
| Parts of a whole, a layered stack | component diagram |
| Modes a thing moves between | state diagram |
| A hierarchy or taxonomy | mindmap |

If the answer has none of these — a definition, a single fact, a yes/no — it does **not** get a
diagram. A decorative diagram costs the reader the same three seconds as a useful one and returns
nothing, which is a tenet-2 violation dressed up as a tenet-3 win. Prose that is already clear is
not improved by being boxed.

Signals a page is asking for one: the Short answer contains "first… then…", the evidence bullets
are numbered stages, the prose says "on the one hand / on the other", or a newcomer had to build a
mental picture to follow it (you will notice, because you just did).

**How to add one.** One command does the whole pipeline:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/wiki_diagram.py" --page "<article>.md" --puml <src.puml> --key <name>
```

It renders on the **private** studio server (`$WIKI_PLANTUML_SERVER`, never a public one — the URL
carries the diagram's content, which is compartmented), **downloads** the PNG into the sibling
`<page name>_attachments/` folder (NotePlan will not display a remote `http://` image at all —
macOS ATS blocks the load and you get a silent empty gap), and splices the image in at the end of
`## Evidence`, so the Short answer still comes first. Re-running with the same `--key` replaces the
block, so a diagram can be iterated on.

The PlantUML source is saved under `@References/@Diagrams/<page path>/<key>.puml`, **not** printed
in the body: twenty lines of mindmap syntax between the diagram and `## Context` is the tenet-2
violation the diagram was meant to avoid, and the "it still reads if the fetch fails" argument does
not apply to a committed local attachment. `--fence` restores the old behaviour if a page really
wants it. It does not go in `_attachments/` either — NotePlan deletes any file there the note does
not reference, seconds after the note is saved. See
`docs/issues/wiki-article-diagrams-drop-the-source-fence.md`.

**Attaching a diagram edits the page, so hash after it, never before.** `wiki_diagram.py` splices
an image line into `## Evidence`; a `page_hash` taken before it runs is stale the moment the verdict
is written, and the Stop hook will say so. This cost two verdicts a same-day amendment. The rule is
already in §0's loop — the diagram is just the edit most easily forgotten, because it feels like
illustration rather than an edit.

**Then render the page and look at it** — one of the few renders still worth spending, because a
diagram is a new visual technique and the failure modes are all spatial: too wide for the column,
too small to read, or crowding the prose it was meant to relieve.

**PlantUML traps, all found against the private server.** It answers every syntax error with a bare
HTTP 400 and no message, so bisect the source against the server rather than reasoning about it:

- An arrow **into** a nested rectangle 400s when the rectangles carry inline `#BG;line:#COLOR;`.
- `rectangle "label" as alias #colour` — the alias must come before the colour.
- `state name as ALIAS` is a 400; `state "name" as ALIAS` renders.
- Two underscores are underline markup, not part of an identifier.
- Stereotypes render as a visible «name», so `hide stereotype` keeps the skinparam colours without
  showing the reader jargon that means nothing to them.

**The silent traps are the dangerous ones.** A 400 tells you something is wrong. These five return
HTTP 200 and a diagram that looks finished and is not, which is the whole reason the render above is
non-negotiable:

- **Mindmap colour, bracket spacing.** `***[#EDF3FB] label` colours the node. `*** [#EDF3FB] label`
  — one space — prints `[#EDF3FB]` as literal text and leaves the node grey. No error either way.
- **Legend colour swatches.** A `legend` table using cells of the form `|<#FAE8D8>  | text |`
  renders as uncoloured rows. Do not key a colour scheme with a legend; put the key in prose in a
  `note bottom of <alias>`, which reads better anyway: *orange is work the team did not know it had*
  beats a swatch the reader has to map back to a box.
- **Unconnected nodes do not lay out.** Boxes with no edges scatter diagonally down the canvas
  instead of forming the grid you pictured. Group them in a `package`, or join siblings with
  `-[hidden]right-`, whenever the comparison is the point and the arrows are not.
- **Inline markup does not span a `\n`.** A label written `"**A/A test — both groups got\nthe same
  treatment**\n…"` renders as a bullet: Creole bold does not cross a line break, so the orphaned
  opening marker at the start of the next line is parsed as a list item and the closing marker is
  left visible. Open and close bold on the same line — `"**A/A test**\nboth groups got the same
  treatment"` — which reads better as a label anyway, since the bold belongs on the name and not
  on the gloss.
- **`~` is PlantUML's escape character.** `about ~**1,000 agents** · **one site** only` escapes
  the first `*`, so the bold never opens, the later markers pair up wrongly, and the emphasis
  spills across the whole line. Write the word *about*, or escape the tilde. Note that a tilde
  *inside* bold — `**~80%**` — is fine; the trap is a tilde immediately before a markup character.

The generalisation worth carrying: **PlantUML fails colour, layout and inline markup silently.** A
diagram is not done when the fetch returns 200; it is done when you have looked at the PNG. Two of
the five traps above were found in a single topic, both in labels that read correctly in the source.

Record in the verdict either the diagram you added, or that you judged the page had no shape worth
drawing. "No diagram" is a finding with a reason, not a silence.
