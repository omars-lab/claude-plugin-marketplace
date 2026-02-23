# OEID Claude Plugin Marketplace

## Mental Model

- **Plugins are roles** — each plugin represents a domain or responsibility (e.g. `experiment-manager`, `noteplan-manager`)
- **Skills are actions (verbs)** — each skill is something you *do* within that role (e.g. `asking-what-if`, `fix-filenames`, `extract-knowledge`)
- Name skills as verbs/actions, not nouns. The plugin provides the noun context.

## Discovery

Each plugin has an `introduce` skill that explains its capabilities:

- `/noteplan-manager:introduce` — NotePlan management (20 skills)
- `/experiment-manager:introduce` — What-if analysis and experiment ideation (2 skills)
- `/discover-oeid-plugins:explore-plugins` — See all plugins and installation status

Plugin-level README files are minimal pointers. The `introduce` skill is the authoritative reference for each plugin's capabilities and workflows.

## After Making Changes

Run validation after adding or modifying plugins:

```bash
make validate-plugins          # Validate all plugins
make validate-plugin PLUGIN=experiment-manager  # Validate one plugin
```

This checks: plugin.json validity, version-tracking, introduce skill, YAML frontmatter, task management references, AskUserQuestion usage, README size, and marketplace.json registration.

## Installation

Always use the Makefile for installing plugins:

```bash
make install    # Install all plugins
make update     # Check for changes, bump versions, then update
```

**Never** manually create symlinks to `~/.claude/plugins/` or copy files there by hand. The Makefile handles caching, version tracking, and `installed_plugins.json` correctly. Manual symlinks bypass all of that and will cause version drift or conflicts.

## Shell Scripts and Line Endings

Shell scripts (`.sh`) in this repo **must use LF line endings**, not CRLF. OneDrive silently converts LF → CRLF on sync, which causes bash to treat the `\r` as part of each command and fail with `: command not found` errors on every line.

A `.gitattributes` file at the repo root enforces LF for all `.sh` files:
```
*.sh text eol=lf
```

**If a shell script fails with `: command not found` on blank or comment lines**, it has CRLF endings. Fix with:
```bash
python3 -c "
path = 'path/to/script.sh'
with open(path, 'rb') as f: data = f.read()
with open(path, 'wb') as f: f.write(data.replace(b'\r\n', b'\n'))
"
```
Then commit the fix and bump the plugin version so the corrected file reaches the install cache.

## NotePlan Frontmatter Convention

**Real note files** (plans, meetings, ideas, thoughts, questions — everything outside `@Templates/`) use `---` (triple dash) — standard YAML.

**Template files** (`@Templates/*.md`) have a two-section structure:
1. **`---` outer block** — NotePlan template metadata (`title`, `type: empty-note`). This is standard YAML consumed by NotePlan itself.
2. **`--` inner block** — The note frontmatter template containing EJS placeholders (`<%- field %>`). This uses `--` intentionally — it is EJS source that generates frontmatter in the created note, not YAML itself.

When a template is used to create a note, the `--` EJS block is evaluated and the output becomes a `---` frontmatter block in the new note file.

Skills working on **real notes** (`flatten-plans`, `update-plan-status`, `fix-frontmatter`) validate and use `---`. The `fix-frontmatter` skill skips template files' `--` inner blocks (EJS source, not YAML to fix).
