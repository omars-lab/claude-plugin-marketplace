# Page comments: comments on a whole element now keep the element's text

**Status:** decided in development-manager 1.3.0
**Affects:** `plugins/development-manager/shared/scripts/client/comments.js` (`elementQuote`,
`anchorFor`, `find`)

## What happened

Section 4's example thread shows an element comment carrying a `quote`. Phase 1 saved a quote only
for comments on selected text, so a comment on a whole element had just its CSS path and an
80-character label.

Building the phase 4 proof showed what that costs. With three cards, deleting the middle one and
lightly editing the last one:

- the last card's saved path (`section:nth-of-type(3)`) no longer exists;
- its label changed, so the exact label match fails;
- with no quote, nothing is left to try, and the comment lands in the not-found list although its
  card is plainly still there.

## What changed

A new element comment saves the element's whole text as its quote, with the usual 32 characters
before and after, when that text is between 1 and 600 characters. A longer element (a whole
section or page) gets no quote, because a quote that long would match its children as well.

When the quote is found, the comment goes on the nearest element with the saved tag around the
found text, so a quote that sits in a child still lands on the element that was commented on.

## Limits

Element comments made before 1.3.0 have no quote. They are found by `data-comment-id`, by their
saved path when the label agrees, or by an exact label, as before.
