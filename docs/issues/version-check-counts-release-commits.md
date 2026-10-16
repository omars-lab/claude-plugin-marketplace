# The version check now counts a commit that raises the version as a release

**What it did.** `make version-check` (and `make update`, which runs it) listed what changed in a
plugin since the commit named in its `version-tracking.json` (`versionCommit`). On 2026-10-16 it
flagged seven plugins as needing a bump. Five of them were false alarms: in each, the commit that
changed the skills had also raised the version in `plugin.json` (one commit on 2026-09-01 did this
for four plugins at once; a note-manager commit on 2026-10-01 did it for one). A commit can't write
its own hash into `versionCommit`, so the marker pointed at the commit before, and the check kept
reporting that commit's skill changes as unreleased. Bumping again would have shipped a version
with nothing new in it, and repointing the five markers by hand would only last until the next
commit that bumps in place.

**What changed.** `scripts/cli` has a `release_base` helper: the newest commit after
`versionCommit` that changed `plugin.json`'s version, or `versionCommit` when none did. Both
`version-check` and `version-bump-all` diff from it. The normal flow (a change, then
`make version-bump` in its own commit) gives the same answer as before, because the bump commit
only adds the version line. `version-bump-all` also gained the "plugin.json changed only its
version" step that `version-check` already had, so it no longer bumps a plugin a second time right
after a bump.

**How it was checked.** On the real history: the five false alarms cleared; document-co-author (one
guide line changed in the skill-manager rename, never bumped) and instagram-manager (about 95
commits since 0.4.0) were still flagged; screenshot-manager and development-manager, which use the
normal bump flow, still read up to date.
