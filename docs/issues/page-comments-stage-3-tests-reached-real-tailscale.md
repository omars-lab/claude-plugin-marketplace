# Page comments: a test reached the real Tailscale app

**Status:** fixed in development-manager 1.2.0
**Affects:** `plugins/development-manager/skills/enable-page-comments/scripts/enable.mjs` (`findTailscale`); `plugins/development-manager/shared/scripts/test/helpers.mjs`, `enable.test.mjs`, `fake-tailscale.mjs`

## What happened

The tests run `enable.mjs --phone` against a fake Tailscale command line, named by the
`PAGE_COMMENTS_TAILSCALE` environment variable. The test for "Tailscale is not installed" set that
variable to an empty string. `findTailscale` treated empty as "not set" and fell back to the real
app at `/Applications/Tailscale.app/Contents/MacOS/Tailscale`. Tailscale was running, so the test
added a real `tailscale serve` entry on port 8766, from a throwaway repo.

It was caught by reading `tailscale serve status` straight after the run, and turned off with
`tailscale serve --https=8766 off`. The status then matched the one saved before the work began.
Funnel was never involved, and no other entry was touched.

## The fix

- When `PAGE_COMMENTS_TAILSCALE` is set at all, even to an empty string, `findTailscale` uses only
  that file, and reports "not found" when it does not exist. It never falls back to PATH or the app.
- `test/helpers.mjs`, which every test file loads, sets the variable to a path that does not exist.
  A test that forgets to name the fake now gets "Tailscale not found", never the real one.
- The "not installed" test expects that answer (exit 3).

## The lesson

A test of code that changes shared machine state needs the real tool fenced off for every test by
default, not only in the tests that remember to. The fake is opt-in; the real tool should never be.
