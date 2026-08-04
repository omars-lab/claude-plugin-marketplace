# OEID Claude Plugin Marketplace

## Guiding Principles

### Plugins are roles, skills are abilities

- A **plugin** represents a domain or responsibility — it is the noun (`noteplan-manager`, `experiment-manager`)
- A **skill** is something you *do* within that role — it is the verb (`fix-filenames`, `asking-what-if`)
- The plugin provides context; the skill provides action. Never put the noun in the skill name.

### Every plugin must have an `introduce` skill

The `introduce` skill is the authoritative reference for what a plugin does. It is what gets surfaced when someone asks "what can this plugin do?" Plugin READMEs are minimal pointers only.

### Skills should be atomic and focused

One skill = one clear action. If a skill is doing multiple unrelated things, split it. Meta-skills (orchestrators that route to other skills) are fine, but their job is routing, not doing.

### Prefer meta-skills over flat lists

When a plugin has many skills, group them under a small set of meta-skills that route by intent. This keeps the plugin surface area small and discoverable.

### Refine skills with session learnings

After completing a sweep, migration, or long guided session, **update the skill's SKILL.md** with key observations that would have made the process smoother. Look for:
- Edge cases not covered by existing rules (e.g. personal content in work notes, meeting notes in daily notes)
- Patterns the user corrected you on mid-session (e.g. routing 1-1 meeting content to actual meeting files)
- Ambiguity points where the skill was unclear (e.g. contributors as routing signals)
- Quality-of-life improvements to prompts or checks (e.g. top-5 scoring, user note handling)

Update SKILL.md, bump the plugin version (minor), and run `make update`. This ensures the next session benefits from hard-won observations without requiring the user to re-explain them.

### Skill examples must be abstract, never real user data

This marketplace is **public**. When refining a skill with session learnings, the *lesson* is welcome but the *example* must be invented — never the user's actual numbers, employers, products, or identifying context.

- **Abstract every example.** Keep the teaching shape (a reversed-causality bullet, an NDA reframe) but swap in invented specifics. Use round, generic figures ("$40M from 8 experiments", "a new consumer product") rather than the real ones from the session that taught the lesson.
- **No identifying combinations.** Even with names stripped, a distinctive cluster of metrics + domain can fingerprint a real person or engagement. Vary the numbers and domain enough that the example traces to no one.
- **Never echo NDA/confidential terms** a user flagged in-session, even as a "for instance." Replace with a neutral stand-in.
- **Rule of thumb:** if you can recognize whose résumé an example came from, it's not abstract enough. Sanitize before committing.

### Build user self-knowledge from note inspection

Long-running skills (especially `sweep-daily-notes`) read many notes and passively accumulate knowledge about the user. **Capture this as structured reflections** at the end of the session, written to the user's own notes:

- `🏡💭 Thoughts/🪞 Reflections/🏡💭💻 GenAI Thoughts/Observations.md` — factual: collaborators, interests, recurring topics
- `🏡💭 Thoughts/🪞 Reflections/🏡💭💻 GenAI Thoughts/Gaps.md` — friction: untracked areas, stuck tasks, orphaned ideas
- `🏡💭 Thoughts/🪞 Reflections/🏡💭💻 GenAI Thoughts/Superpowers.md` — strengths: expertise domains, patterns of excellence

Write with care and specificity. Only write what's verifiable from the notes actually read. Append a dated entry each session — never overwrite prior observations.

---

## Plugin File Structure

```
plugins/<plugin-name>/
├── README.md                          # Minimal pointer only (link to introduce skill)
├── .claude-plugin/
│   ├── plugin.json                    # Plugin metadata (name, version, description, author)
│   └── version-tracking.json         # Auto-managed by Makefile — do not edit by hand
└── skills/
    ├── introduce/
    │   └── SKILL.md                   # Required: self-description skill
    └── <skill-name>/
        └── SKILL.md                   # One SKILL.md per skill
```

`plugin.json` minimum shape:
```json
{
  "name": "<plugin-name>",
  "description": "One-line description",
  "version": "1.0.0",
  "author": { "name": "Omar Eid", "email": "omar_eid21@yahoo.com" },
  "license": "MIT"
}
```

---

## Naming Conventions

### Plugin names

`<domain>-manager` is the standard pattern. Single-purpose plugins may omit `-manager`: `experiment-manager`, `discover-oeid-plugins`.

### Skill names

**Verb-first kebab-case** — the action comes first, followed by the object:

| Verb prefix | Example skills | Notes |
|---|---|---|
| `fix-` | `fix-filenames`, `fix-frontmatter` | Corrects existing problems |
| `create-` | `create-plugin`, `create-skill` | Produces something new |
| `update-` | `update-plan-status` | Modifies something existing |
| `setup-` | `setup-claude-md` | One-time configuration |
| `audit-` | `audit-plugins` | Reads and reports, no writes |
| `evaluate-` | `evaluate-skill` | Scores or assesses quality |
| `suggest-` | `suggest-groupings` | Advisory output only |
| `research-` | `research-claude-md` | Mines/synthesizes data |
| `configure-` | `configure-statusline` | Wires configuration |
| `monitor-` | `monitor-prices` | Watches something over time; snapshot → re-run → drift report |
| `manage-` | `manage-skills` | Meta-skill orchestrator |
| `introduce` | `introduce` | Every plugin's self-description |

---

## Marketplace Skills

Use `claude-manager` to create and modify plugins and skills in this repo — it handles all the scaffolding, validation, and version bumping automatically:

| Task | Skill |
|---|---|
| Create a new plugin | `/claude-manager:manage-plugins` |
| Add a skill to an existing plugin | `/claude-manager:manage-skills` |
| Configure CLAUDE.md or MCP servers | `/claude-manager:manage-claude-config` |

Run `/claude-manager:introduce` to see the full capability list.

The manual steps below are the underlying mechanics — prefer the skills for day-to-day work.

---

## Lifecycle: Adding a New Plugin

1. Create `plugins/<name>/` with the structure above
2. Write `.claude-plugin/plugin.json`
3. Create `skills/introduce/SKILL.md`
4. Add the plugin entry to `.claude-plugin/marketplace.json`
5. Run `make install` to install, then `make validate-plugin PLUGIN=<name>`

**marketplace.json entry shape:**
```json
{
  "name": "<plugin-name>",
  "source": "./plugins/<plugin-name>",
  "description": "One-line description",
  "version": "1.0.0",
  "category": "<category>",
  "keywords": ["..."]
}
```

## Lifecycle: Adding a Skill to an Existing Plugin

1. Create `skills/<skill-name>/SKILL.md`
2. Update the plugin's `introduce` skill to mention the new skill
3. Bump the plugin version: `make version-bump PLUGIN=<name> TYPE=minor`
4. Run `make update` to push the change to the install cache
5. Run `make validate-plugin PLUGIN=<name>` to verify

## Lifecycle: Removing a Plugin

```bash
make uninstall          # Uninstall all plugins
```

To remove a plugin entirely: delete `plugins/<name>/`, remove its entry from `marketplace.json`, then run `make install` to re-sync.

**Never** manually remove symlinks from `~/.claude/plugins/`. Always go through the Makefile.

---

## Installation & Updates

```bash
make install            # Install all plugins
make update             # Check for changes, bump versions, then update
make verify-installs    # Verify all plugins are correctly installed
make doctor             # Diagnose installation issues
make uninstall          # Uninstall all plugins
```

**Never** manually create symlinks to `~/.claude/plugins/` or copy files there by hand. The Makefile handles caching, version tracking, and `installed_plugins.json` correctly. Manual symlinks bypass all of that and cause version drift or conflicts.

---

## Validation

Run after adding or modifying plugins:

```bash
make validate-plugins                        # Validate all plugins
make validate-plugin PLUGIN=<name>           # Validate one plugin
```

Checks: `plugin.json` validity, version-tracking, `introduce` skill, YAML frontmatter, task management references, AskUserQuestion usage, README size, marketplace.json registration.

---

## Discovery

Use the built-in skill to see what's installed and available — don't rely on the CLAUDE.md list, which goes stale:

```
/discover-oeid-plugins:explore-plugins
```

Each plugin's `introduce` skill is the authoritative reference for its capabilities:
```
/<plugin-name>:introduce
```

---

## Shell Scripts and Line Endings

Shell scripts (`.sh`) in this repo **must use LF line endings**, not CRLF. OneDrive silently converts LF → CRLF on sync, which causes bash to fail with `: command not found` on every line.

A `.gitattributes` file enforces LF:
```
*.sh text eol=lf
```

**If a script fails with `: command not found` on blank or comment lines**, it has CRLF endings. Fix with:
```bash
python3 -c "
path = 'path/to/script.sh'
with open(path, 'rb') as f: data = f.read()
with open(path, 'wb') as f: f.write(data.replace(b'\r\n', b'\n'))
"
```
Then commit the fix and bump the plugin version so the corrected file reaches the install cache.

---

## Background Jobs

Background Claude Code sessions follow these conventions:

**Log location:** `~/Library/Logs/<job-name>.log`

**Notification style:** macOS `display notification` via `osascript`
```bash
osascript -e 'display notification "<message>" with title "<Title> ⚠️" sound name "Basso"'
```

**Non-blocking failure rule:** If the agent cannot proceed, fire a notification and exit immediately. Never block or wait for input.

**Lockfile pattern:** `/tmp/<job-name>.lock` stores the running PID. Prevents duplicate runs.

**Nested session guard:** Prefix `claude` with `env -u CLAUDECODE` to prevent "nested Claude session" errors.

**Tool restrictions:** Use `--allowedTools` to scope each job to only what it needs.

**Model:** Use `claude-haiku-4-5-20251001` for background jobs — cheap, fast, sufficient for mechanical tasks.

**zsh background:** Use `&!` (background + disown) so the process survives after the terminal closes.
