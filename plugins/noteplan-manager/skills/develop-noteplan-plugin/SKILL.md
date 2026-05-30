---
name: develop-noteplan-plugin
description: Full lifecycle for building, testing, and deploying a NotePlan JavaScript plugin — scaffold, dev loop, test, install via Makefile, and update
---

# Develop NotePlan Plugin

You are a NotePlan plugin development assistant. Your job is to guide the user through the full lifecycle of building, testing, and deploying a NotePlan JavaScript plugin hosted in `oeid-claude-plugin-marketplace`.

---

## Environment

```bash
MARKETPLACE="$HOME/workspace/oeid-claude-plugin-marketplace"
NOTEPLAN_PLUGINS="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Plugins"
```

---

## Phase 0: Prerequisites

```bash
node --version    # any modern version — no version constraint for this repo
# npc (@noteplan/cli) is NOT on npm — scaffold manually (see Phase 1)
```

Verify the marketplace Makefile is present:

```bash
ls "$MARKETPLACE/Makefile"
make -C "$MARKETPLACE" help | grep noteplan
```

---

## Phase 1: Scaffold a New Plugin

`npc` is not available. Scaffold manually:

```bash
PLUGIN_SLUG="oeid-noteplan-{slug}"   # e.g. oeid-noteplan-quicknote
mkdir -p "$MARKETPLACE/plugins/$PLUGIN_SLUG/__tests__"
```

### `plugin.json` (required fields)

```json
{
  "noteplan.minAppVersion": "3.4.0",
  "plugin.id": "oeid.noteplan-{slug}",
  "plugin.name": "Human-Readable Name",
  "plugin.description": "One-line description",
  "plugin.author": "Omar Eid",
  "plugin.version": "1.0.0",
  "plugin.script": "script.js",
  "plugin.url": "https://github.com/omars-lab/claude-plugin-marketplace",
  "plugin.commands": [
    {
      "name": "Command Name",
      "alias": ["shortname"],
      "description": "What this command does",
      "jsFunction": "functionName"
    }
  ]
}
```

`jsFunction` must match the exact top-level function name in `script.js`.

### `script.js` skeleton

```javascript
/* global DataStore, Editor, CommandBar */

// ─── Config ───────────────────────────────────────────────────────────────────
// (static maps and constants)

// ─── Helpers ──────────────────────────────────────────────────────────────────
// (pure utility functions — keep these free of NotePlan globals so they can be unit tested)

// ─── Commands ─────────────────────────────────────────────────────────────────

async function functionName() {
  // use DataStore, Editor, CommandBar here
}

// Allow pure-function testing in Node.js
// (module is undefined in NotePlan's JS context — safe to include)
if (typeof module !== 'undefined') {
  module.exports = { /* export pure helpers here */ }
}
```

**Key rule**: keep pure utility functions (date formatting, filename construction, template builders) free of NotePlan globals. Export them via the `module.exports` guard so they can be unit tested in Node.

### `package.json` (for tests only)

```json
{
  "name": "oeid-noteplan-{slug}",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage"
  },
  "devDependencies": { "jest": "^29.0.0" },
  "jest": {
    "testEnvironment": "node",
    "testMatch": ["**/__tests__/**/*.test.js"]
  }
}
```

---

## Phase 2: NotePlan API Reference

All globals are injected by NotePlan — no imports needed in `script.js`.

### DataStore

```javascript
DataStore.folders                        // string[] — all folder paths (no leading slash, no "Notes/" prefix)
                                         // e.g. ["🏢 ServiceNow/📆 Plans", "🏢 ServiceNow/📆 Plans/🧑🏻‍💻 Development"]
DataStore.newNote(title, folder)         // → filename string or '' on failure
DataStore.newNoteWithContent(title, folder, content)  // → filename string — creates + sets content in one call
DataStore.noteByFilename(filename)       // → TNote or null
DataStore.projectNoteByFilename(filename)// → TNote or null
DataStore.projectNotes                   // TNote[] — all non-calendar notes
DataStore.calendarNotes                  // TNote[] — all calendar/daily notes
DataStore.invokePluginCommandByName(commandName, pluginID, args)  // call another plugin command
DataStore.invokePluginCommand(pluginID, commandIndex, args)       // call by index
DataStore.settings                       // plugin settings object
DataStore.hashtags                       // string[] — all hashtags in vault
DataStore.mentions                       // string[] — all @mentions in vault
DataStore.createFolder(folderPath)       // create folder
DataStore.moveNote(filename, newFolder)  // move note
DataStore.trashNote(filename)            // trash note
```

### Editor (= NotePlan.editors[0] for main window)

```javascript
Editor.content                           // string (read/write) — full note text
Editor.openNoteByFilename(filename)      // → Promise — opens note in active editor
Editor.note                              // TNote — current note
Editor.save()                            // save active note
Editor.title                             // string — current note title
Editor.type                              // 'Calendar' | 'Notes'
Editor.filename                          // string — current note filename
Editor.windowType                        // 'main' | 'split' | etc.
Editor.customId                          // string — set by plugin for identification
Editor.windowRect                        // {x, y, width, height}
Editor.id                                // UUID string
// Insert/append methods available — see NotePlan.editors proto for full list
```

### NotePlan

```javascript
NotePlan.htmlWindows                     // HTMLView[] — open HTML windows (ONLY populated when showWindowWithOptions is awaited)
NotePlan.editors                         // Editor[] — all open editor panes
NotePlan.environment.version             // e.g. "3.20.1"
NotePlan.environment.versionNumber       // e.g. 3201
NotePlan.environment.platform            // "macOS" | "iOS"
NotePlan.environment.screenWidth/Height  // screen dimensions
NotePlan.openURL(url)                    // open URL in default browser
NotePlan.selectedSidebarFolder           // currently selected folder in sidebar
```

### CommandBar

```javascript
await CommandBar.showOptions(options, placeholder)
// options: string[] or {label, value}[]
// → {value, index} or null if cancelled

await CommandBar.textPrompt(heading, placeholder, defaultValue)
// → string or null/'' if cancelled

await CommandBar.prompt(title, message, buttonLabels)
// → button index pressed
```

### Discover workstreams dynamically (never hardcode)

```javascript
function getWorkstreams(planRoot) {
  const prefix = planRoot + '/'
  return DataStore.folders
    .filter(f => f.startsWith(prefix) && !f.slice(prefix.length).includes('/'))
    .map(f => f.slice(prefix.length))
    .sort()
}
// e.g. getWorkstreams('🏢 ServiceNow/📆 Plans')
//   → ["⚙️ AI Club", "🧑🏻‍💻 Development", "🎯 Impact", ...]
```

---

## Phase 3: Writing Tests

Tests go in `__tests__/*.test.js`. Stub the NotePlan globals at the top of each file:

```javascript
global.DataStore = { folders: [] }
global.Editor = {}
global.CommandBar = {}

const { myHelper, myTemplate } = require('../script.js')
```

**What to test:**
- Date formatting functions
- Filename construction (cover each domain — verify emoji placement, space rules)
- Frontmatter generators (correct keys per domain: `workstream` vs `plantype`)
- Template body builders (H1 matches title, wikilinks present, correct sections)
- `getWorkstreams` with mocked `DataStore.folders` (immediate children only, no project subfolders)

**Golden Rule test** — always verify filename stem = H1:
```javascript
test('H1 matches filename exactly', () => {
  const title = '🏢260422🧑🏻‍💻 Build Plugin'
  expect(planBody(title, fm, 0)).toContain(`# ${title}`)
})
```

### jsBridge — The Official Pattern

**Source of truth:** `np.Shared/requiredFiles/pluginToHTMLCommsBridge.js` in the NotePlan/plugins repo.

```javascript
window.webkit.messageHandlers.jsBridge.postMessage({
  code: '(async function() { await DataStore.invokePluginCommandByName("Cmd", "plugin.id", [arg]); })()',
  onHandle: '',   // ← EMPTY STRING — not a function name, not omitted, not null
  id: '1',
})
```

**Critical rules:**
- `onHandle: ''` means "run code, skip callback". This is the only safe value.
- A **named** `onHandle` (e.g. `'onCreated'`) causes NotePlan to call that function back into the HTML window. If the window is closing when that callback fires → **crash**.
- **Omitting** `onHandle` entirely causes NotePlan to silently drop the message — code never runs.
- Plugin functions are **not** accessible by name in jsBridge eval'd code (they live in NotePlan's plugin IIFE scope). Always dispatch via `DataStore.invokePluginCommandByName`.

**Closing an HTML window — confirmed working pattern (NotePlan 3.20.2+):**

```javascript
// showWindowWithOptions resolves on OPEN (not on close) — returns the Window object.
// The plugin function completes; the window stays open independently.
async function showCreateForm() {
  await HTMLView.showWindowWithOptions(html, 'Title', {
    width: 460, height: 520, shouldFocus: true, customId: 'my-form',
  })
}

// Cancel/Create buttons dispatch this via jsBridge invokePluginCommandByName:
async function closeMyForm() {
  for (const win of NotePlan.htmlWindows) {
    if (win.customId === 'my-form') { win.close(); return }
  }
}
```

**`win.close()` quits the entire app in NotePlan ≤ 3.20.1** — fixed in 3.20.2+. See the investigation log below. If targeting older versions, replace body innerHTML with a success message and rely on ⌘W.

This was exhaustively debugged. See the full investigation log below.

---

### HTML Window Close — Debugging Investigation Log

**Confirmed facts:**
- `window.close()` (in WKWebView JS) — silent no-op; NotePlan does not implement `webViewDidClose:` delegate
- `HTMLView.closeWindow()` — does not exist (TypeError)
- `NotePlan.htmlWindows` — **only populated when `showWindowWithOptions` is called with `await`**. Without `await`, the array stays empty and `win.close()` is never reached.
- `NotePlan.htmlWindows[i].close()` — correct API, finds the window when `await` is used, BUT **quits the entire NotePlan application** (clean quit, no crash report)
- `win.runJavaScript('window.close()')` — no crash, but also does NOT close the window
- Native ✕ button and ⌘W close the window safely without crash. Esc does NOT close HTML windows.
- `win.close()` immediately resolves the `showWindowWithOptions` Promise — any code still on the call stack after `win.close()` runs concurrently with the resuming `showCreateForm`, which causes the quit

**Critical sequencing rules (if attempting `win.close()`):**
1. `await HTMLView.showWindowWithOptions(...)` — required for `htmlWindows` to be populated
2. `showCreateForm` must have **zero code** after the `await` line
3. `win.close()` must be the **absolute last** operation in `closeQuickNote` before `return`
4. Even with these rules, `win.close()` still quits the app in most cases — under active investigation

**Crash type:** Clean application quit. No crash report generated (not a signal/exception). This is a NotePlan bug.

**Hypotheses tried and outcomes:**

| Hypothesis | Outcome |
|---|---|
| Named `onHandle` → crash (callback into closing window) | **Confirmed** — use `onHandle: ''` |
| Removing `await` from `showWindowWithOptions` fixes JSC reentrancy | **Refuted** — removes crash but `htmlWindows` is empty so window is never found |
| WKWebView focus timer (60ms setTimeout) causes crash | **Refuted** — crash happened at 700ms, long after timer fired |
| `win.close()` from within jsBridge eval code causes JSC reentrancy | **Confirmed pattern** — dispatching via `invokePluginCommandByName` is safer but still crashes |
| Code after `win.close()` causes concurrent execution → quit | **Confirmed** — log line added after `win.close()` always caused quit; removing it allowed Cancel to work once |
| Cancel with zero post-close code — does it work reliably? | **Inconclusive** — worked once, then regressed; currently investigating |
| `win.runJavaScript('window.close()')` | **Confirmed no-op** — no crash but window stays open |

**Resolution:** `win.close()` was a NotePlan bug fixed in 3.20.2. Calling it from any JS context (plugin invocation, jsBridge eval, owning context) quit the app in 3.20.1. Works correctly in 3.20.2+.

**Key discoveries during investigation:**
- `showWindowWithOptions` resolves on **OPEN**, not on close — the plugin function finishes immediately; no concurrent execution issue
- `setTimeout` does not fire in plugin JSContext after function returns — context torn down on return
- `Promise.resolve` is undefined in plugin JSContext — only `async/await` sugar works
- Module-level variables reset on each plugin invocation — no shared state between commands
- `onHandle: 'fnName'` calls global scope — plugin functions are in closure scope, not accessible (ReferenceError)
- `win.runJavaScript(code)` uses synchronous WebKit API — Promise return values cause "unsupported type" error

**Reference:** `dwertheimer.Forms/src/windowManagement.js` documents a related crash from window REUSE (same customId reopened before prior window fully closes). Their mitigation: unique timestamp-suffixed customIds.

### HTML Form Testing (jsdom)

If the plugin uses `HTMLView.showWindowWithOptions`, test `submit()` by parsing the form HTML with jsdom and capturing jsBridge calls. Install jsdom v20 (v21+ has ESM deps incompatible with Jest's CJS transform):

```bash
npm install --save-dev jsdom@20
```

Inject a mock jsBridge BEFORE the main `<script>` runs (scripts execute synchronously during JSDOM parse):

```javascript
const { JSDOM, VirtualConsole } = require('jsdom')
const silentConsole = new VirtualConsole()

function makeFormDOM(initialType) {
  const html = buildFormHTML(initialType, mockWorkstreams)
  const mockScript = `<script>
    window.__messages = [];
    window.webkit = { messageHandlers: { jsBridge: {
      postMessage: function(m) { window.__messages.push(m); }
    } } };
  </script>`
  const testHtml = html.replace(/(<script>\s*\nconst C =)/, mockScript + '\n$1')
  return new JSDOM(testHtml, { runScripts: 'dangerously', virtualConsole: silentConsole }).window
}

test('work plan params', () => {
  const win = makeFormDOM('plan')
  win.document.getElementById('title').value = 'Build Feature'
  win.submit()
  const createMsg = win.__messages.find(m => m.id === 'create')
  expect(createMsg.onHandle).toBe('')   // must be empty string
  const match = createMsg.code.match(/\[("(?:[^"\\]|\\.)*")\]/)
  const params = JSON.parse(JSON.parse(match[1]))
  expect(params).toMatchObject({ domain: 'work', type: 'plan', title: 'Build Feature' })
})
```

`buildFormHTML` must be exported via the `module.exports` guard so the test can call it.

### Live Integration Testing (requires NotePlan running)

Test the full pipeline — x-callback-url → NotePlan dispatch → `createNote` → filesystem — with a poll loop:

```javascript
// scripts/live-test.js pattern
function triggerCreateNote(params) {
  const arg0 = encodeURIComponent(JSON.stringify(params))
  execSync(`open "noteplan://x-callback-url/runPlugin?pluginID=PLUGIN_ID&command=ALIAS&arg0=${arg0}"`)
}

async function test(desc, params, folder, filename, contentChecks) {
  // 1. cleanup stale file
  if (existsSync(fullPath)) unlinkSync(fullPath)
  // 2. create
  triggerCreateNote(params)
  // 3. poll (up to 10s) until file exists with all expected content
  // 4. validate
  // 5. cleanup (unless --keep)
}
```

Add a `createNote` alias in `plugin.json` so x-callback-url can address it:
```json
{ "name": "Create Note (API)", "alias": ["createNote"], "hidden": true, "jsFunction": "createNote" }
```

Run tests:
```bash
cd "$MARKETPLACE/plugins/oeid-noteplan-{slug}"
npm install   # first time only
npm test                                           # unit + form (no NotePlan needed)
node scripts/e2e.js                               # filesystem e2e (no NotePlan needed)
make -C "$MARKETPLACE" live-test-noteplan-{slug}  # live (NotePlan must be running)
```

### Three-Tier Test Strategy

| Tier | Command | NotePlan needed | What it covers |
|---|---|---|---|
| Unit + Form | `npm test` | No | Pure functions, form submit() params via jsdom |
| E2E filesystem | `node scripts/e2e.js` | No | `createNote()` with real filesystem stub |
| Live integration | `make live-test-noteplan-{slug}` | Yes | x-callback-url → createNote → real files |

---

## Phase 4: Dev Loop

**Preferred: use the NotePlan MCP** (when active in the Claude Code session):

```
noteplan_plugins → install / reload / list
```

The `.mcp.json` in the NotePlan repo root wires in `@noteplanco/noteplan-mcp`. MCP servers load at session start — if you added it mid-session, restart Claude Code first.

**Fallback: Makefile targets** (terminal, CI, or when MCP is not connected):

```bash
# Copy files + quit/relaunch NotePlan
make -C "$MARKETPLACE" install-noteplan-{slug}

# Relaunch only (no file copy)
make -C "$MARKETPLACE" reload-noteplan
```

**How reload works without MCP**: NotePlan's AppleScript dictionary (`Scriptable.sdef`) does not expose a plugin-reload command — only `selectedNoteUrl`, `selectedNoteTitle`, and `addNote`. The `reload-noteplan` target quits via `tell application "NotePlan" to quit` and relaunches with `open -a NotePlan`. Plugins load fresh on startup.

**In-app alternative**: Cmd-J → "Install or Update Plugins" → rescan without relaunching.

Test: Cmd-J → type the alias (e.g. `/plan`) → step through prompts.

---

## Troubleshooting

### Command doesn't appear in Cmd-J

1. `jsFunction` in `plugin.json` doesn't match the exact top-level function name in `script.js`
2. Plugin not reloaded after install — run `make install-noteplan-{slug}` (quits and relaunches NotePlan)
3. `plugin.json` has a JSON syntax error — validate with `node -e "require('./plugin.json')"`
4. Function is marked `"hidden": true` — hidden commands don't show in the command bar but are callable by alias

### jsBridge postMessage fires but nothing happens

- `onHandle` is omitted entirely → NotePlan silently drops the message. Must be `onHandle: ''`
- `code` string has a syntax error → eval fails silently. Test by pasting the code string into a JS REPL
- `DataStore.invokePluginCommandByName` arg order is `(commandName, pluginID, [args])` — pluginID second, not first

### Plugin runs but `NotePlan` / `DataStore` / `Editor` is undefined

- Running in Node.js (tests or e2e scripts) without mocking globals. Add at top of test file:
  ```javascript
  global.NotePlan = { htmlWindows: [] }
  global.DataStore = { folders: [], projectNotes: [] }
  global.Editor = { openNoteByFilename: jest.fn().mockResolvedValue(true), content: '' }
  ```

### HTML form script has a syntax error (all functions undefined in jsdom)

Syntax errors prevent hoisting — no function is accessible. Diagnose:
```javascript
const html = buildFormHTML('plan', mockWorkstreams)
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1]
try { new Function(script) } catch(e) { console.log(e.message) }
```

**Common cause**: `\'` inside a template literal becomes `'` in the output, breaking JS string literals. Use `data-*` attributes instead of inline `onclick="fn('value')"` strings, or write `\\'` (two backslashes + quote) to produce `\'` in the output.

### Template literal escape gotcha

Inside `buildFormHTML`'s backtick template literal:
- `\'` → `'` (backslash dropped — not an escape in template literals)
- `\\'` → `\'` (double backslash → single backslash, then literal `'`)
- `\\` → `\`

To embed a JS string using single quotes inside an `onclick` attribute, use a `data-*` attribute instead:
```javascript
// ✗ breaks — \'  becomes ' in template literal output
html += '<div onclick="pick(\'' + val + '\')">...</div>'

// ✓ safe — no quoting issues
html += '<div data-val="' + val + '" onclick="pick(this.dataset.val)">...</div>'
```

### `win.close()` behavior by NotePlan version

- **≤ 3.20.1**: `win.close()` quits the entire application — do not call. Workaround: replace body innerHTML with a success message, user closes with ⌘W.
- **≥ 3.20.2**: `win.close()` works correctly. Call from a `closeQuickNote`-style command dispatched via jsBridge.

### `showWindowWithOptions` — promise resolves on OPEN, not close

The returned `Promise<Window>` resolves when the window **appears**, not when it's dismissed. The plugin function returns immediately. The window stays open independently until `win.close()` is called.

```javascript
// showCreateForm returns as soon as the window is visible
async function showCreateForm() {
  await HTMLView.showWindowWithOptions(html, 'Title', { customId: 'my-form', ... })
  // returns here — window still open
}
```

### Plugin doesn't reload after `make install`

`make install-noteplan-{slug}` quits and relaunches NotePlan. If it's hanging: check if a NotePlan dialog or unsaved note is blocking quit. Kill manually: `pkill NotePlan3`, then `open -a NotePlan`.

### `NotePlan.htmlWindows` is empty

`htmlWindows` is only populated when `showWindowWithOptions` is called with `await`. Without `await`, the array stays empty — `win.close()` will never be reached.

### Diagnostic snippet — inspect live window state

Paste this into the Plugin Console or run as a hidden command to dump all inspectable state:

```javascript
async function debugWindowInfo() {
  function safe(fn) { try { return fn() } catch(e) { return 'ERR:' + e } }
  const lines = ['htmlWindows: ' + NotePlan.htmlWindows.length]
  NotePlan.htmlWindows.forEach((w, i) => {
    lines.push('  [' + i + '] customId=' + safe(() => w.customId)
      + ' displayType=' + safe(() => w.displayType)
      + ' id=' + safe(() => w.id))
  })
  lines.push('HTMLView proto: ' + safe(() => Object.getOwnPropertyNames(Object.getPrototypeOf(HTMLView)).join(', ')))
  lines.push('NotePlan proto: ' + safe(() => Object.getOwnPropertyNames(Object.getPrototypeOf(NotePlan)).join(', ')))
  const out = lines.join('\n')
  console.log(out)
  await CommandBar.prompt('Debug', out, ['OK'])
}
```

---

## Phase 5: Update an Existing Plugin

1. Edit `src/` or `script.js`
2. Run tests: `npm test`
3. Reinstall: `make install-noteplan-{slug}`
4. Bump `version` in `plugin.json`:
   - Patch (bug fix): `1.0.0 → 1.0.1`
   - Minor (new command or feature): `1.0.0 → 1.1.0`
   - Major (breaking change): `1.0.0 → 2.0.0`
5. Commit:
   ```bash
   cd "$MARKETPLACE"
   git add plugins/oeid-noteplan-{slug}/
   git commit -m "feat(oeid-noteplan-{slug}): describe change"
   ```

---

## Phase 6: Makefile Targets Convention

Every NotePlan plugin in this marketplace should have these three Makefile targets. Add them alongside the existing `install-noteplan-quicknote` block:

```makefile
install-noteplan-{slug}: ## Install oeid-noteplan-{slug} into NotePlan and reload
	@mkdir -p "$(NOTEPLAN_PLUGINS_DIR)/oeid.noteplan-{slug}"
	@cp plugins/oeid-noteplan-{slug}/plugin.json "$(NOTEPLAN_PLUGINS_DIR)/oeid.noteplan-{slug}/"
	@cp plugins/oeid-noteplan-{slug}/script.js "$(NOTEPLAN_PLUGINS_DIR)/oeid.noteplan-{slug}/"
	@echo "$(GREEN)✓ Installed oeid.noteplan-{slug}$(NC)"
	@osascript -e 'tell application "NotePlan" to reloadPlugins' 2>/dev/null \
		&& echo "$(GREEN)✓ Plugins reloaded$(NC)" \
		|| echo "$(YELLOW)⚠ NotePlan not running — reload manually$(NC)"

reload-noteplan: ## Reload NotePlan plugins via AppleScript (shared across all plugins)
	# (already defined — one target serves all plugins)

uninstall-noteplan-{slug}: ## Remove oeid-noteplan-{slug} from NotePlan
	@rm -rf "$(NOTEPLAN_PLUGINS_DIR)/oeid.noteplan-{slug}"
	@osascript -e 'tell application "NotePlan" to reloadPlugins' 2>/dev/null || true
```

Note: `NOTEPLAN_PLUGINS_DIR` is already defined at the top of the Makefile.

---

## Phase 7: Publishing to NotePlan Marketplace (optional)

To submit to the official NotePlan plugin marketplace:

1. Fork `https://github.com/NotePlan/plugins`
2. Copy your plugin folder into `plugins/`
3. Ensure `plugin.json` has all required fields
4. Run their validation: `npm run validate` in their repo
5. Submit a PR

---

## Existing Plugin Reference

The `oeid-noteplan-quicknote` plugin is the canonical example in this repo:

```
plugins/oeid-noteplan-quicknote/
├── plugin.json              # commands: plan/meeting/note + hidden createNote (alias: createNote)
├── script.js                # dynamic workstream discovery, all domains; exports buildFormHTML
├── package.json             # jest + jsdom@20
├── __tests__/
│   ├── formatDate.test.js   # unit
│   ├── filenames.test.js    # unit
│   ├── templates.test.js    # unit
│   ├── createNote.test.js   # unit
│   └── form.test.js         # jsdom form simulation
└── scripts/
    ├── e2e.js               # filesystem e2e (no NotePlan needed)
    └── live-test.js         # live integration via x-callback-url (NotePlan must be running)
```

Makefile targets:
- `make test-noteplan-quicknote` — unit + form (Jest)
- `make test-noteplan-quicknote-all` — unit + form + e2e filesystem
- `make live-test-noteplan-quicknote` — live integration (NotePlan must be running)

Key patterns to follow:
- `getWorkstreams()` uses `DataStore.folders` — never hardcoded arrays
- `module.exports` guard at bottom enables unit testing; export `buildFormHTML` for form tests
- One `script.js`, no build step
- jsBridge `onHandle` must be `''` (empty string) — named callbacks crash when window closes, omitting it silently drops the message
- jsBridge `code` string: use raw string (never `JSON.stringify` the code — causes double-encoding)
- To call a plugin function from jsBridge: `DataStore.invokePluginCommandByName(commandName, pluginID, [args])` — plugin functions are not globals accessible by name in jsBridge eval'd code
- **Closing HTML window**: `NotePlan.htmlWindows[i].close()` quits the entire app — see investigation log above. Safe workaround: replace body innerHTML with success message, user closes with ⌘W.
- `DataStore.newNoteWithContent(title, folder, content)` — creates a note with content in one call; prefer over `newNote` + `Editor.content =` for atomicity
- `NotePlan.htmlWindows` is only populated when `showWindowWithOptions` is called with `await`; without `await` the array stays empty
- Makefile handles install/reload
