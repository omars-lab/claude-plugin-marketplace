---
name: verify-sweep-review
description: Verify the interactive sweep review mechanism (noteplan-sweep CLI + server + review UI + executor) when extending, developing, or debugging it. Runs the automated suite first, then a SAFE manual dogfood against a real vault with hard guardrails (pre-sweep commit, abort-not-finalize, restart-server). Use whenever you change sweep_manifest / sweep_session / sweep_executor / sweep_api / review_ui / ui_common / movement.
---

# Verify Sweep Review Mechanism

Use this when you touch the interactive sweep review pipeline: the manifest schema, the executor (hash-anchored apply / finalize validation), the server API, or the review UI. It has two layers — **automated (the real regression guard)** and **manual dogfood (visual/UX only, against a real vault)**. Do the automated layer every time; do the manual layer only when you need to confirm rendering/UX that fixtures can't cover.

```bash
BIN="$HOME/workspace/oeid-claude-plugin-marketplace/plugins/noteplan-manager/bin"
PY="$BIN/.venv/bin/python"          # venv has pytest + pytest-playwright + chromium
VAULT="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
```

## Module map (what each file owns)

| File | Owns | Test |
|---|---|---|
| `sweep_manifest.py` | schema, raw-line hashing, validation, fold/split | `test_manifest.py` |
| `sweep_session.py` | decisions journal + fold → state, seq | `test_manifest.py` |
| `sweep_executor.py` | `find_anchor`, `apply_move`, finalize validation, abort, `dest_existence_issues` | `test_executor.py`, `test_finalize.py` |
| `sweep_api.py` | pure `(root,…)→(code,dict)` handlers + CLI cmds | `test_sweep_api.py` |
| `review_ui.py` | the page; pure JS core on `window.__sweepTest` | `test_review_ui_js.py`, `test_review_ui_integration.py` |
| `ui_common.py` | shared `BASE_CSS` + `JS_HELPERS` | (snapshot byte-equivalence, below) |
| `movement.py` | `insert_into_section` (shared apply/append) | `test_movement_refactor.py` |

## Layer 1 — Automated (ALWAYS run; this is the guard)

**When you change behavior, add or extend a test in the same commit.** A bug that reached the UI is a bug that lacked a test — pin it.

```bash
cd "$BIN"
PYTHONPATH="$BIN" "$PY" -m pytest noteplan_sweep/tests/ -q -p no:cacheprovider
```

**JS changes** (anything in `review_ui.py` / `ui_common.py`): first syntax-check the rendered script, then run the browser suite. A stray backslash or unescaped brace in the embedded JS silently breaks `window.__sweepTest`, which hangs `wait_for_function` for 30s per test — `node --check` catches it in a second.

```bash
PYTHONPATH="$BIN" "$PY" -c "import re,noteplan_sweep.review_ui as r,pathlib; \
  pathlib.Path('/tmp/page.js').write_text('\n'.join(re.findall(r'<script>(.*?)</script>',r.build_review_ui_html('x'),re.S)))"
node --check /tmp/page.js
PYTHONPATH="$BIN" "$PY" -m pytest noteplan_sweep/tests/test_review_ui_js.py -q -p no:cacheprovider
```

**Pure UI logic** goes on `window.__sweepTest` and is unit-tested there (selection, split, provenance, status, `canFinalize`, `wordDiff`, `locateRun`). If a UI bug is in pure logic, extract the function and test it — don't rely on the manual dogfood to catch it.

**Snapshot byte-equivalence** (only if you touched `ui_common.BASE_CSS` or `sweep_review._build_snapshot_html`): the legacy snapshot HTML must stay byte-identical. Capture a golden before, regenerate after, `diff`:

```bash
PYTHONPATH="$BIN" "$PY" - <<'PYEOF'
from noteplan_sweep import sweep_review as sr
open('/tmp/snap.html','w').write(sr._build_snapshot_html(
  run_id='r', date_str='2026-07-09', sha='abc', stat_text='1 file changed',
  diff_text='diff\n', seed_comments=[], narrative=[], changed_calendar_files=[],
  base_commit='x', pre_classification=[], cross_row_issues=[], dest_outcomes=[]))
PYEOF
# ...make change, regenerate to /tmp/snap2.html, then:  diff /tmp/snap.html /tmp/snap2.html
```

## Layer 2 — Manual dogfood against a REAL vault (visual/UX only)

Only for what fixtures can't check: real note variety, rendering, hunk framing, provenance colors. **These guardrails are non-negotiable — a wrong step mutates the user's actual notes.**

### Guardrails (MUST)

- **Pre-sweep commit first.** `git -C "$VAULT" add -A && git commit -m "Pre-sweep snapshot"`. This is what makes `abort` able to restore everything. Never dogfood on a dirty tree.
- **Abort, never finalize**, when testing mechanics — unless the user explicitly asks for a real finalize. `finalize` creates a commit and runs clear-source (drops unrouted open tasks). `abort` reverts every touched file and deletes created files.
- **Restart the server after every Python change.** `cmd_serve` imports the modules once at startup; edits do NOT hot-reload. Kill the process on the port and relaunch, or you'll test stale code.
- **Clean up `sweeps/` scratch** (`.sweep-base`, `.sweep-id`, `<run_id>.manifest.json`, `<run_id>.decisions.jsonl`) when done — they're uncommitted bookkeeping.

### Steps

1. **Base + session:** pre-sweep commit → `noteplan-sweep sweep-start` (writes `sweeps/.sweep-id`, `.sweep-base`).
2. **Build a manifest from REAL lines** (read the actual daily note; compute hashes with `sm.line_hash` — you choose the classifications, the script only assembles JSON). Cover varied cases: verbatim, transformed (date/IOU tag), a multi-line block with an indented child, and a genuinely-new-file create. Confirm the "new file" really doesn't exist (see gotchas).
3. **Validate + register:** `noteplan-sweep sweep-manifest-validate sweeps/<run_id>.manifest.json` — must pass with no errors (drift warnings are OK).
4. **Serve:** `noteplan-sweep serve >/tmp/sweep-serve.log 2>&1 &` (restart on every code change).
5. **Drive the UI.** Prefer real Chrome via `mcp__claude-in-chrome__*`. If the extension isn't connected, drive headless Chromium with the venv's Playwright — capture `pageerror` + console, screenshot, and assert on the DOM. Verify per move: provenance rows (`.crow.prov-*`), the **source pane highlights ALL outgoing lines** (`.crow.out` — the line-shift regression), the dest hunk shows the insertion rule, new-file preview renders the create block.
6. **Approve one move → assert disk changed** (line gone from the daily note, present in the destination) and the queue chip flips to `✓`. Then exercise skip / re-route / rebase as needed.
7. **Abort → verify restore:** the daily note is intact, created files removed, tracked destinations reverted. `git -C "$VAULT" status --porcelain` should show only `sweeps/` scratch and unrelated files.

### Playwright driver skeleton (headless fallback)

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())          # abort uses confirm()
    pg.goto("http://localhost:4242/review/<run_id>")
    pg.wait_for_selector(".q-move")
    out = pg.eval_on_selector_all("#src-code .crow.out .ctxt", "els=>els.map(e=>e.textContent)")
    pg.click("button:has-text('Approve')")
    pg.wait_for_function("store.state.counts.applied > 0")
    # ...assert disk via pathlib; screenshot; then click 'Abort session'
    assert not errs
```

## Gotchas learned (check these first when something's off)

- **Server module caching** — Python edits require a server restart; otherwise you're testing old code.
- **Line-shift display** — after an approved move shifts a daily note, later moves' source lines move too. The source pane must content-anchor (`locateRun`, mirroring `find_anchor`), never trust the manifest's line numbers for display.
- **New-file that already exists** — a `destination.exists=false` + create block pointing at a file already on disk: `sweep-manifest-validate` now errors on this. If you bypass it, `apply_move` appends to the real file and the UI shows a misleading "NEW FILE" preview. Always confirm the file is absent before marking it new.
- **NotePlan open-note race** — if a swept note is open and dirty in the app, NotePlan can re-save its buffer over an applied move. Ask the user to close affected notes during review.
- **Emoji paths** — git plumbing quotes non-ASCII paths; the CLI uses `-z` / `core.quotepath=false`. Don't hand-parse quoted paths.

## After fixing a bug

1. Add/extend the automated test that would have caught it (Layer 1) — prefer a pure-function unit test on `window.__sweepTest` over a browser test where possible.
2. Bump `plugin.json` (patch for fixes), commit + push the marketplace repo.
3. Update the install: `env -u CLAUDECODE claude plugin update noteplan-manager@oeid-claude-plugins --scope project` (from the vault dir). Restart Claude to load it.
