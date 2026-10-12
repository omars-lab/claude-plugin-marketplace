# Page comments: pictures may be up to 8 MB, not 2 MB

**Status:** decided in development-manager 1.1.0
**Affects:** `plugins/development-manager/shared/scripts/lib/shots.mjs` (`SHOT_MAX`); design section 9

## What changed

The design caps uploads at 2 MB. The server takes a picture up to 8 MB and refuses a larger one
with 413.

## Why

The cap is there to stop a runaway upload, not to shape pictures. A picture is up to 600 CSS
pixels wide at twice the density, so 1200 pixels wide, but its height follows the element. A tall
element, such as a long list or a whole section, makes a PNG well over 2 MB. With a 2 MB cap the
picture would fail for exactly the comments where seeing the element helps most.

8 MB still bounds memory and disk use. The page sends the picture after the comment is saved, so
a picture refused for size never loses the comment; the thread records why there is no picture.
