# Skill references that point at nothing Claude can call

## What was found

Skills and READMEs told Claude to run `/plugin:name` commands that don't exist. There were about
100 of them across 8 plugins. They fell into three kinds:

- **A skill inside a routing skill's folder.** For example, `/skill-manager:create-plugin` lives
  at `skills/manage-plugins/create-plugin/SKILL.md`. Claude Code never lists it, so the command
  reaches nothing. Most of the broken references were this kind.
- **A skill that moved to another plugin.** For example, config-manager's README still named
  `claude-md-setup`, which now lives in skill-manager.
- **A skill that was never built.** plan-manager's `move-plan` and `plan-changelog` were offered
  as "coming soon". role-manager and skill-manager also used examples that looked like real
  commands.

## What Claude Code lists

This was checked in a real session. A plugin's callable names are:

- its top-level skills, `skills/<name>/SKILL.md`;
- its commands, `commands/<name>.md`;
- its agents, `agents/<name>.md`.

A `SKILL.md` one folder deeper is read only when its routing skill sends Claude there. So the
house style for naming one is `` `/skill-manager:manage-skills` → evaluate-skill ``: the routing
skill you can call, then the skill inside it.

## The fix

- `scripts/check-skill-refs.py` finds every `plugin:name` in a plugin's Markdown and JSON whose
  name isn't callable. It only checks names of plugins in this marketplace, so
  `plugin@marketplace` and other text with a colon are left alone.
  - `--fix` rewrites a reference to a nested skill into the house style.
  - It leaves the other two kinds for a person to fix, because only a person can pick the new
    target.
- `validate-plugins.sh` runs the script for each plugin and fails when anything is left.
- The same change adds a check that hook and monitor commands quote `${CLAUDE_PLUGIN_ROOT}`. The
  consumer plugin's hook didn't, and the path can contain a space.
- The ones the script couldn't fix were fixed by hand:
  - unbuilt skills are listed under "Not built yet" and are no longer offered;
  - made-up examples use plugin names that can't be mistaken for real ones;
  - moved skills point at their new plugin.
