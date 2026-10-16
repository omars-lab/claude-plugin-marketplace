# organize-by-project: commit words can't pick a project; only names can

## What was tried

`match_projects.py shots` first scored each Desktop screenshot's OCR text against every
project's "signals": the folder name, the repo name, the README title and the words in its
last 15 commit messages. Rarer words counted more. A screenshot was matched when the top
project beat the runner-up by a clear margin.

## What the evidence showed

On a Desktop of about 270 screenshots, the word score matched about 90 and most of those
matches were wrong. The words came from commit messages, and the same words show on every
kind of screen:

- a job-site page went to a career-notes repo because the word "career" showed on it;
- a chat window went to a NotePlan plugins fork on the words "following", "something" and
  "changes";
- a tile-pattern photo went to a geometry repo on "tile", "pattern" and "small";
- a one-word hit such as "mark" or "callback" was enough to pick a project.

Tuning the word list (a noise list, a cap on how many projects share a word) made it look
better but not right. The weak evidence and the strong evidence were added into one score,
so a pile of common words could beat a real name.

## What replaced it

Matching now goes by tiers, and the weak tier never decides on its own:

1. **Names.** The project's folder name, repo name, or a hand-written alias (kept next to the
   project list, in the private projects folder) shows on screen. The project with the most
   name hits wins, if it has more than every other project.
2. **Name parts** ("homework" from `homework-cli`). These count only when no other project
   shows anything at all.
3. **Org names** (the two businesses). When no project's name shows but a business's does,
   the screenshot goes to that business's own folder.
4. **Everything else** is `unclear`. The top three projects by commit words are passed along
   as hints for a look at the image itself (Vision), which makes the call.

The cost is that more screenshots need a visual check (about 160 of 270 here). That is the
right trade: a wrong move into the wrong project folder is silent and hard to spot later,
while a visual check is cheap.
