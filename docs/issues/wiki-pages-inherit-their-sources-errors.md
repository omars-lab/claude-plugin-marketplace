# Wiki pages inherit their sources' errors, and reading cannot catch it

## What happened

During the newcomer-review sweep of `🌐 General`, two published wiki pages turned out to be
confidently wrong. Both had passed an earlier authoring pass and neither looked wrong on the page.

**1. `How do nested Kotlin apply blocks resolve this?`**

The page stated that inside a nested `apply`, `this@apply` "still refers to outerObject" — i.e.
that the qualified form escapes the inner scope. That is what the raw source said: a chat
transcript in `🗑️ Unorganized/development-tips/Kotlin ....md`, whose line 89 carries the claim as
a code comment.

It is false. Both blocks carry the same implicit label (`apply`), and the nearest one wins, so
`this@apply` binds to the *inner* receiver exactly like a bare `this`. Verified by running it:

```kotlin
class Outer { var tag = "outer-untouched" }
class Inner { var tag = "inner-untouched" }

val inner = Inner()
val outer = Outer().apply {
    inner.apply {
        this@apply.tag = "WRITTEN-BY-this@apply"
    }
}
println("outer.tag = " + outer.tag)   // outer-untouched
println("inner.tag = " + inner.tag)   // WRITTEN-BY-this@apply
```

Against Kotlin 2.4.20. The labelled form (`this@outer`) does reach the outer object, which is why
labelling the blocks is the only reliable escape and is now what the page recommends.

**2. `How do you attach a Chrome DevTools MCP server to Chrome when it expects Chrome Canary?`**

The page led with `--remote-debugging-port` plus a scratch `--user-data-dir` as the fix. Reading
the raw transcript (`q cli Tried to install canary with`, 189 lines) shows that is the step the
session tried **first**, at lines 103–127, and the MCP server refused to attach anyway; line 127 is
the session's own conclusion that the tool looks for the Canary binary specifically. Installing
Canary is where the session actually went.

So the page was recommending, as its headline answer, a path its own evidence had already closed.

## Why this class of error survives

Neither error is visible from the page. Both pages were internally consistent, sourced, and
plausible — the Kotlin one is *especially* plausible, because `this@label` escaping an inner scope
is exactly what the syntax looks like it should do, and that is presumably why the transcript's
author believed it.

The common cause: **a derived page inherits every error in its source, and a source that is a chat
transcript has two error channels** — what the tool or model got wrong in the moment, and what the
session author concluded about it afterwards. Summarising faithfully preserves both.

Reading more carefully does not help, because the page is a faithful summary. Reasoning about it
does not help either; in the Kotlin case reasoning actively misleads, since the wrong answer is the
intuitive one.

## What changed

`plugins/wiki-manager/skills/review-as-newcomer/rubric.md`, §2 gained a sixth check: **if any claim
on the page is testable, test it — do not reason about it.** The section names both cases as worked
examples and lists what "test" means in practice, cheapest first: read the raw source *to its end*
and see what actually happened, check the man page or official docs, or run the snippet. Installing
a toolchain to settle a claim is explicitly in scope — `brew install kotlin` cost one command and
settled a question that a wiki page had been getting wrong.

Two supporting rules came with it:

- When a test contradicts the source, **the page follows the test**, and both the page's `## Gaps`
  and the verdict record that the source was wrong and how it was checked. The page is allowed to
  contradict its own source; it is not allowed to do so silently.
- When a claim is testable but could not be tested, `## Gaps` says so. The Canary page ends with
  exactly that: the transcript stops at the `cp -R` and never shows the server connecting, so the
  page recommends where the session went, not a confirmed success.

§0 also gained the NotePlan ordering constraint that shaped how these fixes were applied — edit
first, render second, because a note NotePlan holds open is written back from its stale buffer and
silently undoes an edit made after the render. (§0 has since been rewritten around reading the raw
file rather than rendering — see `wiki-reviews-read-raw-not-rendered.md` — but that constraint
survives unchanged, because it is a property of the app rather than of the workflow.)

## A third case, and the worst one: a guardrail that never fires

**`How does the phase gate stop the config agent from writing to the live system during planning?`**

The source is not a chat transcript this time — it is the project's own design note, asserting that
a `can_use_tool` callback keeps enforcing a phase policy even under
`permission_mode="bypassPermissions"`. Checked against the Claude Agent SDK, it does not:
`bypassPermissions` auto-approves the call before the callback is consulted, and so does a bare
whole-tool entry in `allowed_tools`. The gate reads correctly and never runs.

Three things make this the sharpest instance of the class:

1. **The failure is silent by construction.** A guardrail that is never reached produces no error,
   no log line and no denied call — only the absence of a denial nobody was watching for. A
   guardrail that reads correctly and never runs is worse than none, because nobody goes looking for
   the hole it was supposed to cover.
2. **The error had already propagated.** Three pages carried it: the phase gate page itself, the
   Anthropic-questions page (which recorded the write-tools-during-planning question as *resolved*
   by the phase gate), and the space index (which listed the pattern as a reusable technique worth
   promoting to `🌐 General`). Fixing the base page is not enough — the sweep has to follow
   `leads_to:` and the index, because a wrong fact in a `kind: base` page has already been spent
   downstream.
3. **An internal design note is a *weaker* source than a transcript, not a stronger one.** A
   transcript at least records what happened; a design note records what was intended. Authority
   inside the vault is not evidence, and check 6 applies to it with more force, not less.

The correction that generalises — and the part worth promoting out of the employer space — is not
the phase gate at all: it is that `bypassPermissions` and whole-tool `allowed_tools` entries both
short-circuit `can_use_tool`, and that `PreToolUse` is the hook that actually gates every call.

## Scope

This is not a Kotlin or Chrome problem. Every `kind: base` page is a summary of a raw note, and a
large share of those raw notes are chat transcripts. The remaining spaces in the sweep — notably
`📦 Past Work`, the largest — should be reviewed with check 6 applied, on the assumption that more of
these exist.
