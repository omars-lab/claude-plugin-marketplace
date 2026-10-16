# Page comments: several repos share the same ports

## What went wrong

Turning page comments on in a second repo on the same Mac went wrong in three ways:

- **detect guessed the wrong site.** The repo's Makefile set `PORT ?= 8765` and ran
  `--port $(PORT)`. detect could not read that, so it fell back to a guess. Even with the port
  read right, another repo's server held 8765, and this repo's own site had moved to another port.
  The comment server would have put comments on the other repo's pages.
- **enable always took 8766 for the comment server.** That port was already held by an older
  comment server, so `make comments` would fail. Nothing said so, and enable still printed
  "Start it: make comments".
- **check passed anyway.** Its test server runs on a spare port, so it never noticed that the
  real port was taken or that the target was another repo's site.
- **serve on a busy port died with a stack trace** (`EADDRINUSE`), naming neither the holder nor a
  way out.

## What changed

- `shared/scripts/lib/ports.mjs` finds who listens on a port (lsof) and which repo that process
  runs from (its git folder, compared by real path, so worktrees count as the same repo).
- **detect** reads the port from `VAR ?= n`, `VAR := n` and `$(or $(VAR),n)`. It then looks at
  what is really listening. When the port is another repo's and this repo's server runs on
  another port, it points there. Otherwise it says "Careful".
- **enable** takes the first free comment port from 8766 when none is given or saved. It prints a
  `careful:` line when a given port is taken or the target is another repo's server.
- **check** has two port lines: the comment port is free, and a local target is this repo's
  server. Another repo's server on either port is a FAIL that names the fix.
- **serve** on a busy port says who holds it and names a free port, with no stack trace.

## Left out

When `core.hooksPath` points at a folder committed in the repo (like `.githooks/`), the
post-commit hook is still skipped. Adding it there would show up in git for everyone. An opt-in
for that case is a separate change.
