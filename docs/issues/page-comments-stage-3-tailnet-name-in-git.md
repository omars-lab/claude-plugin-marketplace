# Page comments: the phone setting puts the Mac's tailnet name and login in git

**Status:** decided in development-manager 1.2.0, with a warning
**Affects:** `.page-comments/config.json` and `.page-comments/install.json` in each repo; `plugins/development-manager/skills/enable-page-comments/scripts/enable.mjs` (`phoneReport`)

## What happens

`enable.mjs --phone` writes into `config.json`:

```json
"phone": { "host": "<mac>.<tailnet>.ts.net", "port": 8766, "logins": ["<login>"] }
```

and adds a `tailscale-serve` record with the same name to `install.json`. Both files are tracked
in git, as the design says, so committing them records the Mac's tailnet name and the Tailscale
login in the repo's history. Pushed to a public remote, that tells anyone the tailnet's name and
whose it is. It does not let them in: the name only resolves inside the tailnet, and the server
refuses any login not on the list.

## What was decided

The design keeps the phone setting in `config.json`, and the server reads it from there. Moving it
to an untracked file would mean a second place to look for settings, and would lose the phone setting
when someone clones the repo onto another Mac. So the setting stays where the design put it, and
enable says so out loud. After `--phone` it prints:

> config.json and install.json now name this Mac on your tailnet and your Tailscale login. Both are
> committed with the repo…

The skill passes that line on word for word, and the person decides whether to commit it.

**Confirmed by the owner, 2026-10-12:** it is fine for the comment files and settings to carry the
Tailscale address of the Mac that hosts the comments. The setting stays in `config.json` and the
warning stays, so someone pushing to a public remote still sees it.

## If this needs to change

For a public repo, the clean fix is a `config.local.json` that git ignores, read after
`config.json`, with the phone setting moved there. That was not built: page comments are meant
for private repos, and the owner confirmed the address in git is fine there.
