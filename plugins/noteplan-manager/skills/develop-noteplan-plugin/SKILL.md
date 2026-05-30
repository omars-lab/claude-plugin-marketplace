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
DataStore.noteWithFilename(filename)     // → TNote or null
DataStore.projectNotes                   // TNote[] — all non-calendar notes
DataStore.calendarNotes                  // TNote[] — all calendar/daily notes
DataStore.invokePluginCommandByName(pluginName, commandName, args)  // call another plugin
```

### Editor

```javascript
Editor.content                           // string (read/write) — full note text
Editor.openNoteByFilename(filename)      // → Promise — opens note in active editor
Editor.note                              // TNote — current note
Editor.save()                            // save active note
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

Run tests:
```bash
cd "$MARKETPLACE/plugins/oeid-noteplan-{slug}"
npm install   # first time only
npm test
npm run test:coverage
```

---

## Phase 4: Dev Loop

Edit `script.js` → install to NotePlan → verify in-app:

```bash
# One command: copy files + reload
make -C "$MARKETPLACE" install-noteplan-{slug}
# (reload-noteplan target reloads without copying, if NotePlan is already running)
make -C "$MARKETPLACE" reload-noteplan
```

Test in NotePlan: Cmd-J → type the alias (e.g. `/plan`) → step through prompts.

If NotePlan is not running, open it first; the install target copies files even when closed.

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
	@osascript -e 'tell application "NotePlan 3" to reloadPlugins' 2>/dev/null \
		&& echo "$(GREEN)✓ Plugins reloaded$(NC)" \
		|| echo "$(YELLOW)⚠ NotePlan not running — reload manually$(NC)"

reload-noteplan: ## Reload NotePlan plugins via AppleScript (shared across all plugins)
	# (already defined — one target serves all plugins)

uninstall-noteplan-{slug}: ## Remove oeid-noteplan-{slug} from NotePlan
	@rm -rf "$(NOTEPLAN_PLUGINS_DIR)/oeid.noteplan-{slug}"
	@osascript -e 'tell application "NotePlan 3" to reloadPlugins' 2>/dev/null || true
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
├── plugin.json          # three commands: plan/meeting/note
├── script.js            # dynamic workstream discovery, all domains
├── package.json         # jest setup
└── __tests__/
    ├── formatDate.test.js
    ├── filenames.test.js
    └── templates.test.js
```

Key patterns to follow:
- `getWorkstreams()` uses `DataStore.folders` — never hardcoded arrays
- `module.exports` guard at bottom enables unit testing
- One `script.js`, no build step
- Makefile handles install/reload
