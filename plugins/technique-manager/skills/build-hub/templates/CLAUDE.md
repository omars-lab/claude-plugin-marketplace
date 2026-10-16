# Technique hub

Private repo: specs, replacements, pre-context, notes and page-comment threads for Claude
techniques. It holds real names, so it is pushed only to the remotes in `hub.json`
(a pre-push hook refuses others). Never copy anything from here into a public repo.

- `make serve` builds the hub and serves it with page comments (press C on any element).
- `make hub [SLUG=…]` re-renders after a spec edit. Always run it before replying to a comment.
- Specs: `specs/<slug>.json`. Shared replacements: `specs/_redactions.json`.
- Built site: `.cache/hub/` (gallery `index.html`, `waiting.html`, `internal/`, `post/`). Never edit it by hand.
- Day to day, `/technique-manager:manage-hub` routes the request: what's waiting, comments, back stories, sync.
- While no session is open, the background responder answers comments (`make responder-on|off|status`,
  on macOS). It never confirms a suggestion, commits or pushes; unclear comments get a question back.

## Answering comments

Follow `development-manager:answer-page-comments` for the loop. This table says what each
comment asks for. Comments anchor to `data-comment-id`s: `<slug>` (card, or an item on the
waiting page), `<slug>:b<i>` (terminal block i), `<slug>:focus`, `<slug>:suggested`,
`<slug>:context`. A comment records the id of the element clicked, not of its parent, so a
comment on a word inside a block has `commentId: null`. Then read its CSS path: the step
`div.cu-block:nth-child(k)` under `.cu-screen` is block `k - 1` on an internal page. On a
trimmed post page, count only the `.cu-block` siblings, because the `⋯` lines are not blocks.
The page path (`/internal/<slug>.html`) gives the slug.

| Comment on | Says something like | Do |
|---|---|---|
| A terminal block `:b<i>` | "this is the point", "this proves it" | Add `i` to `focus.blocks`; if there's no `focus.line`, propose one in the reply |
| The focus line | a new wording, "the real focus is …" | Set `focus.line`, `focus.confirmed: true`, `focus.source: "comment"` |
| The suggestion | "yes", "use this" | Copy the suggestion into `focus.line` or `backstory`, confirmed |
| Anything | "fetch the PR / what led here / the hook file" | `make context SLUG=…` with that source, then reply with what it found |
| Anything | "find the transcript", "search the studio for …", "what else did I say about …" | `make transcripts GREP="<distinctive words>"` (add `SINCE=<the spec's taken date>` if common). Reply with how many sessions match and the 1–2 snippets that matter, in your own words; delete the temp folder after. Never quote a copied session into the spec, notes or post |
| Any text | "don't show this", "rename X" | Add a replacement (per-spec; shared if it says "everywhere"), re-scan, re-render |
| Card or page | "drafting" / "ready" / "posted at <url>" | Set `status` (and `post.published`) |
| The page | "trim the post" / "show it all" | Set `post.trim` |
| The page | "pair with <other>" | Add a line to `notes/<slug>.md` and the other's notes |
| Anything else | a question or a thought | Answer; if it's a note to keep, append it to `notes/<slug>.md` |

Rules: change only what the comment asks. A change to the shared component library is a
proposal in the reply, not an edit. Anything that reaches the post view (focus line, back story,
replacements) passes `scan_privacy.py --post` before you reply. Reply in one line saying what
changed, with the post preview link when it changed.
