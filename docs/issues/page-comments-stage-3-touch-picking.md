# Page comments: how touch mode decides a tap is a pick

**Status:** decided in development-manager 1.2.0
**Affects:** `plugins/development-manager/shared/scripts/client/comments.js`, `comments.css`; design section 13 ("Touch")

## What was built

On a touch screen (`(pointer: coarse)`):
- **Comment** turns comment mode on; while on, it reads **Cancel**.
- In comment mode a tap picks the part of the page under the finger and shows its outline, with a
  **Comment here** button next to the tap. Nothing opens until that is tapped. Tapping another part
  moves the pick. A tap on a link picks it and does not follow it.
- Selecting text shows **Comment on selection** in the bar.
- Buttons are at least 44px, pins have a larger hit area than they look, the bar spans the screen
  above the home bar, the comment box uses 16px text so iOS does not zoom in, and the panel opens
  above the bar.
- There is no hover outline on touch, and hover colours apply only under `(hover: hover)`.

On a desktop nothing changed: C or the Comment button, hover outline, a click opens the comment
box straight away, 28px buttons.

## Decisions the design did not spell out

- **Pick by how the tap was made, not by the screen type alone.** The page notes the
  `pointerType` of each press. A finger or pen press picks; a mouse click opens the box at once,
  even on a device that reports a coarse pointer, such as an iPad with a trackpad.
- **The selection button hides after a short delay.** On iOS, tapping a button can clear the
  selection before the click arrives. The page keeps a copy of the last selected range, and hides
  the button 0.8 s after the selection goes, so the tap still lands and still has the text.
- **The panel is placed from the bar's real top.** On a narrow screen the bar wraps to two rows,
  so a fixed offset put the panel over it.

## How it was proven, and what was not

The brief asked for WebKit with an iPhone profile. The Playwright install here has no WebKit build
for its version, so the run used Chromium with the iPhone 13 profile and touch on, through the real
tailnet address. All steps passed: a tap outside comment mode opens nothing, a tap in comment mode
picks without opening, a tap on a link picks without following it, Comment here opens the box,
Comment on selection opens a box on the text, both comments saved with the right author and a
picture, and the server stored them. A long press cannot be faked in Playwright, so the selection
was made by script, which fires the same `selectionchange` event.

Not checked: Safari on a real iPhone, and a real long-press selection. Those are on the phone list
in design section 16.
