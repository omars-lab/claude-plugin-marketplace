# organize-by-project: asking about dozens of unclear screenshots

## What was tried

Step 6 asked about the unclear screenshots with `AskUserQuestion`: group them, ask about the
biggest groups, 4 questions at a time.

## What the evidence showed

- After the image check, one Desktop still had a few dozen unsure screenshots, plus an
  undecided folder and two folders held back for key files. That is 4–5 rounds of 4
  questions, each one needing the image paths opened by hand to answer.
- A chat question can't show the picture. The user has to open each path to answer it.
- The first automatic grouping, by time (shots within 30 minutes on the same day), made 40
  groups, most of a single screenshot. Screens of the same site taken weeks apart landed in
  different groups, so the same question would have been asked several times.

## What replaced it

- **A review doc in Obsidian** (`review_doc.py`): one section per group with the pictures
  side by side, what the image check saw on each, and a tick box per choice. The user answers
  in their own time, and uses the review-md plugin to comment when a box isn't enough. `read`
  turns the ticks into the same answers file the chat path wrote, plus alias rules and the
  key-file plan flags, so Steps 7 and 8 didn't change.
- **Chat questions stay** for 1–4 groups, where a doc is more trouble than it's worth.
- **Groups are merged by topic by hand** after `draft`: Claude reads the captions and puts
  every screen of one site or one tool together (40 groups became 15). The time grouping is
  only a starting point; it is not good enough to write unedited.
- The doc lives in its own vault (`<projects root>/_review`) so Obsidian never indexes the
  code folders that moved into the projects folder, and the scans skip `_review`.
