# oeid-noteplan-quicknote

Three slash commands that create correctly-named, correctly-placed NotePlan notes across all domains — Work, Personal, NaqshCoffee, and EarlBear.

## Commands

| Command | Alias | What it does |
|---|---|---|
| New Plan | `/plan` | Creates a plan note — prompts for domain, workstream/activity, title, status |
| New Meeting | `/meeting` | Creates a meeting note — prompts for domain, title, days ago |
| New Note | `/note` | Creates a freeform note — prompts for domain, title |

### Naming conventions followed

| Type | Filename |
|---|---|
| Work plan | `🏢YYMMDD{workstreamEmoji} Title` |
| Personal plan | `🏡YYMMDD{activityEmoji} Title` |
| NaqshCoffee plan | `☕️YYMMDD{workstreamEmoji} Title` |
| EarlBear plan | `👥YYMMDD{workstreamEmoji} Title` |
| Any meeting | `{domainEmoji} YYMMDD Title` (space after emoji) |
| Any note | `{domainEmoji}📝 Title` |

### Dynamic workstream discovery

Workstream and activity dropdowns are populated at runtime from `DataStore.folders` — no hardcoded lists. Adding a new workstream folder surfaces it automatically.

### Project subfolder routing

When workstream = `🧑🏻‍💻 Development` (Work or EarlBear), an additional prompt asks for project subfolder (`🤖 Config Agent`, `💡 esgenius`, `⚗️ Experiments`, `🔧 Setup`). The project emoji is used in the filename instead of the workstream emoji.

## Install

```bash
make install-noteplan-quicknote
```

Copies `plugin.json` and `script.js` to NotePlan's Plugins directory and relaunches NotePlan to load the new commands. Requires the `oeid-claude-plugin-marketplace` Makefile.

## Development

```bash
# Run tests
cd plugins/oeid-noteplan-quicknote
npm install
npm test
npm run test:coverage

# Edit → install → test in-app
make install-noteplan-quicknote
```

In NotePlan: Cmd-J → `/plan` (or `/meeting`, `/note`) → step through prompts.

## Programmatic API

Other plugins can create notes without UI prompts via:

```javascript
await DataStore.invokePluginCommandByName(
  'oeid.noteplan-quicknote',
  'Create Note (API)',
  [JSON.stringify({
    domain: 'work',       // 'work' | 'personal' | 'coffee' | 'earlbear'
    type: 'plan',         // 'plan' | 'meeting' | 'note'
    title: 'Build Something',
    workstream: '🧑🏻‍💻 Development',  // plans only
    status: '🟢 Started',              // plans only (default: '🚦 Ready')
    daysAgo: 0,                        // meetings only (default: 0)
  })]
)
```

## Tests

53 tests across 4 suites covering date formatting, filename construction (all domains × types), frontmatter correctness, template bodies, `getWorkstreams` with mocked `DataStore`, and the full `createNote` API including guard clauses.
