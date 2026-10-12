# Page comments: when a comment's saved place in the page is trusted

**Status:** decided in development-manager 1.3.0
**Affects:** `plugins/development-manager/shared/scripts/client/comments.js` (`labelAgrees`,
`find`)

## What the design said

Section 4, anchor 2: the saved CSS path is "accepted only when the tag and label still agree".

## What was built

"Agree" is read as: same tag, and either the same label, or a label at least 80% alike (the same
threshold as the text match) **and** no other element with that tag has a label that alike. The
second part is the departure. Without it, deleting one card of a list of similar cards ("Day 2:
coast", "Day 3: coast") shifts the saved path onto its neighbour, whose label is close enough to
pass, and the comment would be shown on the wrong card. That is a guess, which section 4 forbids.

When the path is rejected, the comment falls through to its quoted text (exact, then fuzzy) and
then to an exact label match, as the design orders.

## Limits

- **Exact duplicates still pass.** Two elements with the same tag and the same label (two "Buy"
  buttons) agree exactly, so a path that shifted from one to the other is accepted. The design's
  rule allows this; a `data-comment-id` is the fix for pages that need it.
- **Near-duplicates are rejected even when the path is right.** If a page has two cards whose
  labels are 80% alike and one is lightly edited, the path is not trusted and the comment relies
  on its quote. The worst case is "not found", never the wrong card.
- To keep page loads quick, the near-duplicate scan stops at 2,000 elements of one tag; past that,
  only an exact label agrees.
