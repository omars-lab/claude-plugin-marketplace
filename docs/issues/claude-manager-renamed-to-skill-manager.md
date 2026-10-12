# The claude-manager plugin is now skill-manager

**Status:** resolved in skill-manager 3.0.0 (2026-10-12)
**Affects:** `plugins/skill-manager/` (was `plugins/claude-manager/`), `.claude-plugin/marketplace.json`,
and every place that names the plugin or its commands

## What broke

Newer Claude Code (seen on 2.1.296) refuses plugin names that look like Anthropic's own. `make validate`
runs `claude plugin validate` on the marketplace, and it failed with:

```
✘ Found 1 error:

  ❯ plugins[4].name: Plugin name "claude-manager" is reserved: it passes as one of Anthropic's own. A third party's plugin name cannot start with "claude-", "anthropic-", "anthropics-", or "cc-plugin-", be "claude", "anthropic", "anthropics", "claude-code", or "claude-mods", or put "official" beside "claude" or "anthropic". Name it for what it does.

✘ Validation failed
```

It was the only name the check rejected. The marketplace name `oeid-claude-plugins` passes, because
"claude" is not at the start. The config-manager skill `claude-permissions` also passes:
`claude plugin validate` on each plugin folder found no reserved skill names.

## Why skill-manager

Omar chose `skill-manager` on 2026-10-12. The plugin creates, updates and checks skills, plugins and
CLAUDE.md files, and skills are most of what it is used for. The name follows the marketplace's
`<domain>-manager` pattern and does not start with a reserved word.

## What changed

- The folder moved from `plugins/claude-manager` to `plugins/skill-manager`.
- `plugin.json` and the `marketplace.json` entry are named `skill-manager`, at version 3.0.0. It is a
  major bump because every old command name stops working.
- Commands are now `/skill-manager:...`, for example `/skill-manager:introduce`,
  `/skill-manager:manage-plugins`, `/skill-manager:manage-skills` and
  `/skill-manager:manage-claude-config`. The skill names inside the plugin did not change.
- The plugin's own README and skills, the marketplace README, CLAUDE.md and Makefile (`make install-lite`),
  and the skills of code-quality-manager, plan-manager, profile-manager, role-manager and
  document-co-author now say `skill-manager`.
- Moving the folder makes every line in it count as new, so the never-public check (which stops
  private names reaching the public copy) caught a private employer's name in the default OneDrive
  path of the research-claude-md script. That default now looks in any `OneDrive-*/workspace`
  folder, so it finds the same folder without naming the account.
- Dated records were left as written: older research findings and dated memory lines still say
  `claude-manager`, with a short note where it helps.

## What every Mac with it installed must do

The old plugin does not turn into the new one by itself. On each Mac:

1. Pull the marketplace and refresh it in Claude Code: `claude plugin marketplace update oeid-claude-plugins`.
2. Remove the old plugin: `claude plugin uninstall claude-manager@oeid-claude-plugins`.
3. Add the new one: `claude plugin install skill-manager@oeid-claude-plugins`.
4. In every settings file that lists it, change the `enabledPlugins` entry
   `"claude-manager@oeid-claude-plugins": true` to `"skill-manager@oeid-claude-plugins": true`.
   Look in the user settings (`~/.claude/settings.json`) and in each repo's `.claude/settings.json`
   and `.claude/settings.local.json`. Uninstall works on one scope at a time (user by default; add
   `--scope project` or `--scope local` for the others), so check each file afterwards.
5. Some repos also list the plugin in `.claude/suggested-plugins.json`
   (`"plugin": "claude-manager@oeid-claude-plugins"`). Change those to `skill-manager` too.
6. Anything you type or keep in notes as `/claude-manager:<skill>` becomes `/skill-manager:<skill>`.
