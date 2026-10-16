# Page comments: the comment bar was on a port nobody opened

## What went wrong

Comments were on in two repos, and the person still saw no comment bar.
Each repo had two servers:

- the site's own server (`make serve`), on the address the person always opens, like
  `http://127.0.0.1:8765/`;
- the comment server (`make comments`), in front of it on another port, like 8768.

Only the second one had the bar. The person kept opening the first, which is what they had
bookmarked and what every other note in the repo pointed at. Nothing on that page said the
comment bar lived somewhere else. Having two commands and two addresses for the same pages was
the problem, not any one bug.

## What changed

- **`serve --behind '<command>'`** (`shared/scripts/lib/behind.mjs`). The comment server takes
  the port the person already opens. It starts the repo's own server on a spare port behind it,
  with `{port}` in the command (and `PORT` in its environment) set to that port, and proxies to
  it. It holds its own port first, so a busy port fails before the site's server starts. It
  waits until the site's server answers, and fails with that server's exit code if it stops
  first. On Ctrl-C or a stop it stops the site's server too, and if the site's server stops on
  its own, the comment server stops with its code. The site's server runs in its own process
  group, so a command like `make site && python3 serve.py` is stopped as a whole.
- **`serve` with no mode** uses the one saved in `.page-comments/config.json`, so
  `.page-comments/run serve` is enough.
- **enable `--behind '<command>'`** saves the command in `config.json`, where no Makefile
  quoting can change it.
- **enable leaves `make comments` out** when one of the repo's own targets already runs
  `.page-comments/run serve`, and takes out an old one. A repo changes its `serve` recipe to
  `.page-comments/run serve --port <its port> --behind '<its command>'`, re-runs enable, and
  `make serve` is then the one command. Undo warns when that recipe still calls the launcher it
  removed.

## Left out

A site server that listens on the network for a phone (for example a `--lan` flag) cannot go
behind the comment server, which only listens on `127.0.0.1`. Such a repo keeps the plain
command for that case; the phone reaches comments through `--phone` instead.
