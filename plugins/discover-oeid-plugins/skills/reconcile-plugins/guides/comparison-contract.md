# Suggested-vs-actual comparison contract

The single definition of how a repo's **suggested** plugins are compared against
what is actually **installed** and **enabled**. Both the `reconcile-plugins`
skill and the global SessionStart hook
(`~/.claude/hooks/check-suggested-plugins.sh`) consume the same engine —
[`scripts/compare-plugins.sh`](../../../scripts/compare-plugins.sh) — so there is
exactly one definition of each status.

## Inputs

- **Manifest** — `<repo>/.claude/suggested-plugins.json` (see the schema below).
  If absent, the comparison is a no-op (the hook is *manifest-gated*).
- **Install state** — directory existence at
  `~/.claude/plugins/marketplaces/<marketplace>/plugins/<name>/`.
- **Enable state** — `"<name>@<marketplace>": true` in the repo's
  `.claude/settings.json` `enabledPlugins`.
- **Registered version** — the plugin's entry in the marketplace's
  `marketplace.json` (kept accurate by the Part D version sync + parity check).
- **Installed version** — the installed plugin's `.claude-plugin/plugin.json`
  `version`.

## Manifest schema (`oeid-suggested-plugins/v1`)

```json
{
  "$schema": "oeid-suggested-plugins/v1",
  "plugins": [
    { "plugin": "document-co-author@oeid-claude-plugins", "required": true,
      "reason": "authoring blog posts + structured docs" }
  ]
}
```

- `plugin` — `"<name>@<marketplace>"`, exactly as it is keyed in `enabledPlugins`.
- `required` — advisory severity only; the comparison does not change behavior on
  it, but consumers may surface required-vs-optional differently.
- `reason` — human rationale; travels with the repo for review/diff.

## Status classification (precedence order)

Each suggested plugin resolves to exactly one status, checked in this order:

1. **missing** — no installed dir. Fix: `claude plugin install <ref>`.
2. **not-enabled** — installed but `enabledPlugins[ref]` is not `true`.
   Fix: add the key to `.claude/settings.json` (or `claude plugin enable <ref>`).
3. **stale** — installed and enabled, but installed `plugin.json` version `<`
   `marketplace.json` version. Detail payload is `"<installed><<registered>"`.
   Fix: `claude plugin update <ref>`. Never auto-update.
4. **ok** — installed, enabled, not behind. (Missing or unparseable versions are
   treated as *not stale* — staleness requires two comparable version tuples.)

## Output format

`gov_compare <repo>` prints one TSV line per suggested plugin:

```
<status>\t<plugin@marketplace>\t<detail>
```

`detail` is empty except for `stale`, where it is `"1.1.0<1.3.0"`. Empty overall
output means "no manifest → nothing to do".

## Guarantees

- **Read-only.** No writes, no network, no interactive auth — headless/CI safe.
- **Override hooks for tests.** `GOV_MARKETPLACES_DIR` and
  `GOV_KNOWN_MARKETPLACES` env vars repoint the install/registry roots at
  fixtures, so the logic is testable without a live `~/.claude`.
