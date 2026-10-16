# organize-by-project: folder names alone left half the folder screenshots unexamined

## What was tried

`match_projects.py folders` first matched each Desktop folder to a project by its **name**
only: the Desktop's own folders, plus one level inside `Debugging/` and `Developing/` (both
names written into the code). A folder whose name matched no repo was left where it was. Its
contents were never read.

## What the evidence showed

On one Desktop, about 2,000 screenshots sat inside Desktop folders. The name match planned to
move the folders holding about half of them. The other half were in about 60 folders it never
opened:

- most were life admin (orders, government forms, career, trips), which is right to leave;
- but some were project work with a name that says nothing: a `Development/` folder, a
  `project-<old name>/` folder for a renamed blog, a `debugging-<tool>/` folder whose
  screenshots all show one repo's name in the terminal;
- folders of folders other than `Debugging/` and `Developing/` (`Learning/`,
  `Entrepreneurship/`, an archive folder) were never opened, so nothing inside them was seen;
- loose screenshots directly inside `Developing/` were never read.

## What replaced it

1. **Folders of folders are found by shape**, not by a fixed list: `Debugging/`,
   `Developing/`, or any folder with 3+ subfolders and fewer loose images than subfolders.
   Their subfolders are matched one by one.
2. **Life folders are skipped by a word in their name** (receipt, paperwork, family, trip,
   visa ...) plus a hand-kept `_skip` list in the private aliases file.
3. **Every other unplaced folder is looked inside** (`to-read`, then `inside`): its
   screenshots are read, and the same name match used for Desktop screenshots runs on them.
   A folder where one project's name dominates moves whole; one where only some shots name a
   project gives up just those shots; one with no names sends 5 sample shots to the image
   check, and 3 agreeing answers move it.
4. **A folder named for keys** (`api-keys`) is held like one with key files in it. The first
   look inside wanted to move `api-keys` to a company folder because its screenshots showed
   the company's name.
5. **One stray name does not split a folder.** A job-onboarding folder had one screenshot where
   a one-word project name showed as an ordinary word; splitting needs 2 or more.

On the same Desktop this added 3 folders and 11 screenshots to the plan. It sent 81 sample
shots from 32 folders to the image check, and all of them came back as not project work, which
is the expected result for dated life folders.

## Fingerprints (added the same day)

The user asked for every screenshot folder to keep a `fingerprint.md`: its sites, paths, words
and dates, plus a Guidance section of their answers, so new screenshots can be filed by it and
the skill learns from each question it asks. The lesson from
`organize-by-project-word-matching.md` holds here too. Words from a fingerprint never decide.
A site or path only one place has is a hint for the image check, or, for a shot already judged
"not project work", a pointer to the life folder it belongs in.
