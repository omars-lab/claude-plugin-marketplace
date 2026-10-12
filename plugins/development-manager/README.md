# development-manager

Comment on your local web pages, and have Claude answer.

Open a page on localhost, press C, and leave a comment on an element or on selected text.
The comment is saved as a file in the repo, so git tracks it.
Claude hears about it, fixes or answers it at the source, commits, and replies on the page.
It closes the thread only once the fix is in.

## Install

```text
/plugin install development-manager@oeid-claude-plugins
```

Or, from a checkout of this marketplace, `make install` installs every plugin in it.

## Start

Run `/development-manager:introduce` for a tour, or turn comments on in a repo:

```text
/development-manager:enable-page-comments
```

One run sets up everything:
- the Comment button on the repo's pages, through a small server on `127.0.0.1:8766`;
- the plugin turned on in the repo's `.claude/settings.json`, so every session there hears comments;
- a short note in the repo's `CLAUDE.md` that points Claude to `answer-page-comments`.

It ends with a check that posts a test comment and confirms Claude would see it.
`--undo` takes it all out again and keeps your comments.

## Skills

| Skill | What it does |
|---|---|
| `introduce` | What the plugin does and how its skills fit together |
| `manage-development` | Sends a request to the right skill |
| `enable-page-comments` | Turns comments on in a repo, checks the loop, or undoes it |
| `answer-page-comments` | The routine Claude follows for each comment |

## Needs

- Node 18 or later. No packages to install, in the plugin or in your repo.
- Claude Code with plugin monitors, so the watcher starts with each session.

## Tests

```text
make test-development-manager
```

The design is in `docs/design/localhost-comments/design.md` in this marketplace.
