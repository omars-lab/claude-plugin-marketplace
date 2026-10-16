# make update: plugins listed as needing a bump right after their bump

## What happened

`make update` failed every time (exit 2), and its version check listed about 21 plugins as
changed since their last version bump, including ones bumped minutes earlier.

## What the evidence showed

- **The failure:** `oeid-noteplan-quicknote` is a NotePlan plugin listed in `marketplace.json`.
  It has no `.claude-plugin/plugin.json`, so `claude plugin update` refused it. `make install`
  already skipped such folders; update and uninstall didn't.
- **The false bumps, cause 1:** `version-bump` records the commit *before* the bump as the
  plugin's `versionCommit`, then commits the new version in `plugin.json`. The version check
  diffs `versionCommit..HEAD`, so the bump's own `plugin.json` edit always showed up.
- **The false bumps, cause 2:** the bump rewrote the whole `plugin.json` with `json.dump`,
  which turned `—` into `—` and dropped the final newline. Even a check that ignored the
  version line still saw a change.
- **The repeated names:** the check added a skill's name once per changed file, so a skill
  with 18 changed files was named 18 times.

## What replaced it

- `is_claude_plugin` in `scripts/cli`; install, update, uninstall and version-check skip a
  folder without `.claude-plugin/plugin.json`.
- The version check drops `plugin.json` from the changes when its contents, version aside,
  are the same as at `versionCommit` (compared as parsed JSON, so the old reformatting doesn't
  count).
- The bump edits only the version line of `plugin.json`, as it already did for
  `marketplace.json`.
- Each skill is named once.

After the fix, 8 plugins are listed, each with real edits since its last bump.
