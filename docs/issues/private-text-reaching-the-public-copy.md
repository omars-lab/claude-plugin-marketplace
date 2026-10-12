# Private text reaching the public GitHub copy

## What happened

This repo is published to a public GitHub copy by `make sync-remote`. gitleaks guards every commit,
but it only knows secrets: keys and tokens. A review before a sync found text that is private but
is not a secret:

- a Tailscale machine address in a docs/issues page;
- the names of private employers, used as example wiki spaces in skills, references and test
  fixtures.

gitleaks passed all of it, so nothing would have stopped the sync.

## What changed

- **A second check, `scripts/check-never-public.sh`.** It looks at added lines only, so text that
  is already in the repo doesn't block unrelated work. It reads two lists:
  - `scripts/never-public.patterns` (public): generic shapes, namely Tailscale host names and
    addresses.
  - `.claude/never-public.txt` (private): the specific names. The sync leaves this file out of
    the public copy, as it does `.claude/plans` and `.claude/memory`.
- **Pre-commit** runs it on staged lines, right after gitleaks.
- **The sync** runs it before pushing:
  - If any commit in the range adds private text, the range is published as one commit. That's
    because replaying each commit would publish the bad commit even after a later commit fixes
    it.
  - The commit message lists each subject line, and any subject that names something private
    shows as "(subject withheld)".
  - Then the net change and the messages are checked again, and the push is refused if anything
    is still found.
- **The examples were reworded** to "Work" and "Past Work", and the address to `<render-host>`.
  A real wiki vault keeps its own list of spaces.

`make test-never-public` tests the check and both sync paths on a throwaway repo.
`make check-never-public-range` shows what the next sync would flag.

## What it does not fix

- Text that was already public before this check stays in the public history. The check never
  flags it, because it is not newly added.
- Removing that text means rewriting the public history (`make sync-remote-init`, a force-push).
  Forks and caches would still hold copies.

## A bug found on the first run

The list used to pick which subjects to withhold still had its blank lines in it. A blank pattern
matches everything, so all 62 subjects were withheld. The fix strips blank lines and comments
before matching, and the self-test now also checks that a clean subject is kept.
