# Page comments: the element's picture was cut off at the bottom

**Status:** resolved in development-manager 1.1.0
**Affects:** `plugins/development-manager/shared/scripts/client/comments.js` (`capture`)

## What happened

The first picture of a heading, taken in the browser proof on a Vite page, showed only the top
part of the text. The bottom was cut off.

modern-screenshot copies the element into a fresh document and draws the copy. On the root of the
copy it removes the margin from the inline style. That brings back the browser's own default
margin for the tag: an `<h1>` gets `0.67em` top and bottom. The copy was then drawn inside a box
the size of the original element, so the margin pushed the text down and out of the box.

## What we did instead

`capture` passes `style: { margin: "0" }` to `domToCanvas`, so the copy has no margin at all.
The next proof drew the whole heading. The picture size matched the element, plus the 16 pixel
border the client adds.

No automated test covers this; the page script is checked by hand in a real browser. Any element
whose tag has a default margin (`h1` to `h6`, `p`, `ul`, `figure`, `blockquote`) would have
shown the same fault.
