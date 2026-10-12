---
name: write-obsidian-note
description: Write a Markdown note meant to be read in Obsidian — a status page, a "what is waiting on me" list, a decision digest, a runbook, a generated register — so it reads short-first, with Obsidian callouts for the one line to act on and foldable callouts for pictures, steps and detail. Use when creating or restyling a .md file inside an Obsidian vault (a folder with .obsidian/), when a note "is a wall of text", when embedding screenshots in a note, when asked to open a note in Obsidian, or when a script generates Markdown that will be read in Obsidian.
---

# Authoring Markdown for Obsidian

A note in a vault is read by a person deciding what to do next. The shape below comes from a
generated "what is waiting on you?" note, where the callout for the recommendation and the fold
for extra pictures were the parts the reader singled out as working. Read `rubric.md` before
handing a note over, and use `example.md` as the skeleton.

## The short version

1. **Headings are questions a stranger could answer**, each ending in its count when it holds a
   list: `## Which choices are waiting on you? — 4`.
2. **Open with one paragraph that counts everything in bold** and says why the first section
   is first. Then one line on where the items really live and how to change them.
3. **Lift the one line a reader acts on into a callout**: `> [!tip] Recommended`.
4. **Fold everything secondary**: pictures after the first, steps, needs, notes, in
   `> [!example]-` or `> [!note]-`. The fold's title says what is inside and how much:
   "5 more pictures from the page", "What you need, and the steps".
5. **Show, don't only link**: embed the top of a page as a picture right under its item.
6. **End each item with the action**: "To choose: [open the options page] · [read the
   record], then tell Claude which one."
7. **Minor items are one line each**: `- **[Title](path.md)** — first sentence.`
8. **Options are screenshots side by side**: each option mocked into the real app, in a
   table with one column per option. Never ASCII art.
9. **Open it and look**: `open "obsidian://open?path=<absolute path>"`, then take a screenshot
   and check that the callouts, folds and pictures render.

## Tone

Plain words, no house jargon. Second person ("waiting on **you**"). Short sentences. Every
empty state says what it means and what to do: "None. Every question has an answer on
record." "*No pictures yet: run the picture script.*" A fold's title is written as a phrase
a reader would say, never as a label like "Details" or "More".

Order is the argument: what only the reader can move comes first, and what moves slowest
comes last. Say that ordering in one sentence at the top, so the reader trusts it.

## Callouts: the mechanism

```markdown
> [!tip] Recommended
> B — a sidebar that collapses: the page keeps its width and the menu is one tap away.

> [!example]- 2 more pictures from the page
> **What does the app do today?**
>
> ![What does the app do today?](waiting-on-you/nav-layout-1.png)
>
> **How does each layout fit on a phone?**
>
> ![How does each layout fit on a phone?](waiting-on-you/nav-layout-2.png)
```

- `> [!type] Title` opens a callout. `-` after the type folds it **closed**, `+` folds it
  open, and no sign means it cannot fold.
- **Every line inside starts with `>`, and a blank line inside is a bare `>`.** A truly blank
  line ends the callout, so the rest spills out as a plain quote. In a generator, prefix every
  body line: `lines.map(l => l ? "> " + l : ">")`.
- Pick the type for its **meaning and colour**, and use each type for one job per note:

  | type | looks | use it for |
  | --- | --- | --- |
  | `tip` | teal, flame | the recommendation, the one line to act on |
  | `example` | purple, list | folded pictures and samples |
  | `note` | blue, pencil | folded steps, needs, procedures |
  | `warning` | orange | a real risk the reader must see before acting |
  | `question` | yellow | an open question put to the reader |
  | `info` | blue, i | background that is not a step |

- Do not stack callouts on everything. One `tip` per item, at most one fold per kind of
  detail. A note that is all callouts has no emphasis left.

## Pictures

- Embed with **standard Markdown and a path relative to the note**:
  `![caption](folder/name.png)`. It renders in Obsidian **and** on GitHub and a static site.
  Use `![[name.png]]` only in a vault nobody reads outside Obsidian.
- Keep pictures in a folder named after the note (`waiting-on-you/` next to
  `waiting-on-you.md`), so the note and its pictures move together.
- **The caption is the section heading it was taken under.** In a fold, repeat it in bold
  above the picture, because Obsidian does not show alt text.
- Show the first picture (usually the top of the page) inline; fold the rest.
- Take pictures of the real thing at the size it is used, served the way it is served. A page
  with live parts (iframes) must be loaded over HTTP, not `file://`, or they come out empty.
  Check the pictures yourself before you embed them.

## Options: real screenshots side by side, never ASCII art

When a note puts options in front of a reader, each option is a **picture of the real thing**,
not a box drawn in characters. A character drawing only shows what the writer already
imagined; a screenshot shows what actually happens when the option meets the real screen, and
that is where the surprise is. (First found on a tap-and-hold options note: putting the
proposed button into the real app showed the top bar had no room for it. No drawing would have.)

- **Mock the option into the real app**, not into a blank page. Load the app, then run a short
  HTML and CSS script against the live page that adds what the option adds (clone an existing
  button and change its label, hide a bar, float a small menu). Keep each script in a `mocks/`
  folder beside the note's pictures, so every picture can be taken again.
- **Lay the options side by side in a table**: one column per option, one row per thing the
  reader does (tap, hold, get back). A picture in each cell with one line under it. Where two
  cells would hold the same picture, write "the same as …" instead of repeating it.
- In a table cell the width pipe must be escaped: `![caption\|190](folder/a.png)`, then `<br>`
  and the line under it. About 190 px per picture keeps three phone-sized columns readable.
- **A table cell shrinks its picture, and unevenly**: the column with the shortest text gets the
  least width, so a menu or a label in it can drop to ~130 px and stop being readable. Crop
  each picture to the part the option is about (the menu, not the whole phone), and when the
  detail still has to be read, add **one full-width picture of the options side by side** under
  the table, each labelled (`magick montage -label "A" a.png -label "B" b.png -tile 3x1 …`),
  made by the same script that takes the shots. Then open the note and check both.
- Keep the comparison of pros, cons and what each option commits you to in its own table
  under the pictures.

## Options that differ in timing: a looping GIF, its stills folded under it

When options differ in **order or gesture** (a tap against a hold, what appears first), a still
cannot show it and the reader is left guessing the sequence. Put a **looping GIF** in each cell
instead, recorded from the real app, with a mark where the finger is (a ripple for a tap, a ring
that fills while held) and a numbered label for each step. (First asked for on the same
tap-and-hold note: "The transition/timeline of this cx is unclear … can obsidian support gifs?")

- **GIF, not video.** Obsidian plays a GIF by itself and loops it, in both views. An `.mp4`
  embed needs a click and stops at the end. Animated WebP is larger and shows still on GitHub.
- **Phone-sized and small**: 390 px wide, 10 frames a second, 64 colours, the last frame held
  about 1.5 s so the end can be read before it loops, under 1 MB each, under about 7 seconds.
  Every option's clip the same length, so they can be compared.
- In a cell it is embedded like a picture: `![A, hold\|190](note/a-hold.gif)`. Under the
  table, **one GIF with every option side by side**, so they play in step at a readable size.
- Under each clip, its **steps as a strip of stills, folded shut**, for a reader who wants to
  stop on one moment and for anyone reading a printout:

  ```markdown
  > [!example]- A, step by step
  > ![A: 1 before, 2 finger down, 3 menu up](note/a-hold-strip.png)
  ```

- Commit the script that records the clips beside the note, like the mock scripts; never the
  raw recordings.
- Open the note in Obsidian and watch each clip play through once before handing it over.

## Line breaks

Obsidian may show every typed line break as a break (the "strict line breaks" setting off is
the default in many vaults), so text hard-wrapped at 100 columns breaks mid-sentence. Write
**one line per paragraph** in a note meant for Obsidian.

## Comments and stamps

Obsidian's editing view shows HTML comments (`<!-- -->`) as grey text at the top of the note.
Use `%% … %%` for anything a generator stamps (a "do not edit" line, a freshness hash): it is
hidden in both views. The cost is that GitHub shows `%%` lines as text, so use `<!-- -->`
instead when GitHub is where the note is mostly read.

## Links

- To another note: a relative path **with** `.md` (`[the backlog](backlog.md)`). It works in
  Obsidian, on GitHub, and on a site. Add `#anchor` for a heading.
- To the web: a full URL. Obsidian adds the ↗ mark itself.
- Link text says where it goes ("open the options page"), never "here".

## When a script writes the note

Generated notes are still author-mode writing: the plumbing lives in the script, not in the
note. Keep the script's renderer a pure function (every input is passed in) so a test can feed
it a made-up list and check the callouts, the folds and the empty states. Stamp the note with
a hash of its inputs in a `%%` comment, and have the repo's checks refuse a stale note. The
note's own words should never mention the hash, the renderer or the check.

## Opening and checking it

- Open by **path**, not by vault name, because several vaults can share a folder name like
  `docs`: `open "obsidian://open?path=/abs/path/to/note.md"`.
- The vault must already be registered in Obsidian (`~/Library/Application Support/obsidian/obsidian.json`).
  If it is not, add it there, then quit and relaunch Obsidian, because it caches the list.
- Look at it: `screencapture -o -x shot.png`, then read the PNG. Press Cmd+E to switch
  between the reading and editing views; check the editing view too, because it is where stray
  comments and broken callouts show.
