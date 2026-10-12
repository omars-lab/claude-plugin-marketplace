# Page comments: the pins were rebuilt on every poll

**Status:** resolved in development-manager 1.0.0
**Affects:** `plugins/development-manager/shared/scripts/client/comments.js`

## What happened

The page asks the server for changes every 4 seconds. After each answer the client redrew
everything: the pins, the comment list and any open thread. It did this even when the server said
nothing had changed.

Found in the browser proof on the adventures planner. A click on a pin, made by the test browser,
failed with "the element did not become interactive". The pin had been swapped for a fresh copy
between the moment the tool found it and the moment it clicked. A person clicking at the wrong
moment would miss the same way. A scrolled comment list would also jump back to the top every
4 seconds.

## What we did instead

The poll redraws only when the threads changed, or when an element a pin points at has moved. A
small layout key (each shown pin's thread id and its element's position and size) is saved on
each redraw, and compared on each poll. Buttons, window resizes and the server's own changes still
redraw at once.

Checked in the browser: the same pin element survived two polls, and the test browser's click on
it then opened the thread.
