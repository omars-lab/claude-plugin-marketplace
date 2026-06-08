---
name: reconcile-plugins
description: Reconcile a repo's installed + enabled plugins with the plugins it should have (its .claude/suggested-plugins.json). Dry-run by default; reports missing / not-enabled / stale plugins with exact fix commands, and on confirmation installs missing plugins and enables them in .claude/settings.json. Never auto-updates stale plugins.
---

# Reconcile Plugins

Bring a repo's **installed + enabled** plugins in sync with the plugins it
*should* have, as declared in its committed `.claude/suggested-plugins.json`.
This closes the silent-failure gap where `enabledPlugins: true` on a
**not-installed** plugin is a no-op — the capability simply never appears, with
no error.

This skill shares one classification engine with the global SessionStart hook:
[`scripts/compare-plugins.sh`](../../scripts/compare-plugins.sh), documented in
[`guides/comparison-contract.md`](guides/comparison-contract.md). The hook
*reports* on session start; this skill *reports and, on confirmation, fixes*.

## Safety rules (read first)

- **Dry-run by default.** Always print the report first. Only mutate after the
  user confirms.
- **Other-repo writes require confirmation.** If the target repo is not the cwd
  repo, use `AskUserQuestion` to confirm before writing to its
  `.claude/settings.json` — these are outward-facing changes.
- **Never auto-update stale plugins.** Surface the `claude plugin update` hint;
  let the user run it.
- **Idempotent.** Re-running when already in sync makes no changes and says so.
- **Read-only classification.** The comparison itself never writes or hits the
  network.

## Workflow

### 1. Resolve the target repo

Default to the cwd repo. If the user named another repo, note that writes there
will need confirmation (rule above).

### 2. Run the comparison (dry-run report)

Source the shared engine and classify every suggested plugin:

```bash
source "<discover-oeid-plugins>/scripts/compare-plugins.sh"
gov_compare "<repo>"   # TSV: status<TAB>plugin@marketplace<TAB>detail
```

(The plugin dir resolves under the marketplace's `installLocation`; from this
skill it is two levels up from `skills/reconcile-plugins/`.)

Group the output and print a concise report. If there is **no** manifest, say so
and stop — there is nothing to reconcile. If every line is `ok`, report
"already in sync" and stop (idempotent no-op).

Otherwise present, per category, the exact fix command:

```
plugin governance — <repo>
  missing:     foo@oeid-claude-plugins   → claude plugin install foo@oeid-claude-plugins
  not-enabled: bar@oeid-claude-plugins   → enable in .claude/settings.json (claude plugin enable bar@oeid-claude-plugins)
  stale:       baz@oeid-claude-plugins 1.1.0<1.3.0 → claude plugin update baz@oeid-claude-plugins
```

### 3. Apply (only after confirmation)

When the user confirms (and, for an other-repo target, after the
`AskUserQuestion` confirmation):

- **missing** → run `claude plugin install <ref>` at the correct scope. Then it
  becomes a `not-enabled` case — proceed to enable it.
- **not-enabled** → add `"<ref>": true` to the repo's `.claude/settings.json`
  `enabledPlugins` (preserve key order and formatting; create the
  `enabledPlugins` object if absent). Prefer editing the JSON directly so the
  change is reviewable in the diff; `claude plugin enable <ref>` is the
  equivalent CLI path.
- **stale** → **do not update.** Print the `claude plugin update <ref>` hint and
  leave it to the user.

After applying, re-run `gov_compare` and report the new state to confirm the
fixes landed (missing/not-enabled should clear; stale remains until the user
updates).

### 4. Optional: `--prune`

If the user asks to prune, report `enabledPlugins` entries that are **not** in
the manifest (enabled-but-not-suggested). **Report only — never auto-remove.**
These are often intentional; let the user decide.

## When there is no manifest

Offer to seed one. A starter `.claude/suggested-plugins.json`:

```json
{
  "$schema": "oeid-suggested-plugins/v1",
  "plugins": [
    { "plugin": "document-co-author@oeid-claude-plugins", "required": true,
      "reason": "why this repo needs it" }
  ]
}
```

Seed it from the repo's current `enabledPlugins` (the oeid-marketplace ones), or
from the user's stated intent. Then re-run the workflow.

## Self-check (headless-safe)

The shared engine has a fixture-backed self-test driven by the hook's
`--self-test` mode (see `~/.claude/hooks/check-suggested-plugins.sh --self-test`).
It asserts the missing / not-enabled / stale / ok classification against fixture
install + registry JSON, with no live `~/.claude` and no interactive auth — so it
runs in cron/CI.
