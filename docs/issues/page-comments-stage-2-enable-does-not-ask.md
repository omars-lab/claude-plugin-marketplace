# Page comments: enable does not ask where pictures go

**Status:** decided in development-manager 1.1.0
**Affects:** `plugins/development-manager/skills/enable-page-comments/`; design section 8, step 2

## What changed

The design has enable ask once where pictures go, offering the iCloud default, and save the answer
in the global config `~/.config/development-manager/config.json`. The build does not ask and never
writes the global config. It picks, in order: `--shots-dir`, what the repo's `config.json` already
says, `shotsDir` in the global config, then the iCloud default. It writes the result into the
repo's `config.json`, with `~` for the home folder, and says where pictures go in its report.

## Why

- **The default is the answer Omar already gave.** The design names his folder as the default. A
  question whose answer is nearly always "the default" is a stop for nothing; the report line and
  `--shots-dir` cover the other case.
- **The global config stays Omar's to edit.** A script that writes into a file shared by every
  repo can surprise the next repo. Reading it, and never writing it, keeps one owner.
- **Writing the result into the repo's config** means the repo keeps the folder it was set up
  with, even if the global setting changes later.

The privacy line about iCloud Drive is still printed, the first time a repo's pictures are set to
go there, and the skill passes it on word for word.
