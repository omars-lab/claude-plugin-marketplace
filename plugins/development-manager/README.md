# development-manager

Comment on your local web pages, and have Claude answer.

Open a page on localhost, press C, and comment on an element or on selected text.
The comment is saved as a file in the repo, so git tracks it, with a picture of the element.
Claude hears about it, fixes or answers it at the source, commits, and replies on the page.
It closes the thread only once the fix is in.

## Install and start

```text
/plugin install development-manager@oeid-claude-plugins
/development-manager:enable-page-comments
```

One run adds the Comment button (through a small server on `127.0.0.1:8766`), turns the plugin on
in the repo's `.claude/settings.json`, adds a note to its `CLAUDE.md`, and proves the loop with a
test comment. `--undo` takes it all out and keeps your comments and screenshots.
`/development-manager:introduce` gives a tour.

## Worth knowing

- **Screenshots stay out of git.** By default they go to `CloudDesktop/data` in iCloud Drive, so
  they show in the Files app on a phone. Apple can read iCloud Drive unless Advanced Data
  Protection is on; pick a local folder with `--shots-dir <path>` if that matters.
- **Comments follow the page as it changes.** A comment whose element moved is found again; one
  whose element is gone is listed under "Not found on this page". It is never pinned to a guess.
- **From your phone,** `--phone` serves the comment server on your own Tailscale network (never
  Funnel), and only your own login may comment. It writes the Mac's tailnet name and your login
  into the repo's `.page-comments/` files, so think twice before pushing them to a public remote.
- **Other ways in:** `--vite` adds the button through a Vite dev server, `--userscript` writes a
  Tampermonkey script for pages you can't proxy, and an MCP server gives Claude the commands as tools.

The details are in the `enable-page-comments` skill.

## Skills

| Skill | What it does |
|---|---|
| `introduce` | What the plugin does and how its skills fit together |
| `manage-development` | Sends a request to the right skill |
| `enable-page-comments` | Turns comments on in a repo, checks the loop, or undoes it |
| `answer-page-comments` | The routine Claude follows for each comment |

Needs Node 18 or later, and Claude Code with plugin monitors. Tests: `make test-development-manager`.
Pictures are taken by [modern-screenshot](https://github.com/qq15725/modern-screenshot) 4.7.0 (MIT),
bundled in the plugin. The design is in `docs/design/localhost-comments/design.md`.
