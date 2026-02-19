# OEID Claude Plugin Marketplace

## Mental Model

- **Plugins are roles** — each plugin represents a domain or responsibility (e.g. `experiment-manager`, `noteplan-manager`)
- **Skills are actions (verbs)** — each skill is something you *do* within that role (e.g. `asking-what-if`, `fix-filenames`, `extract-knowledge`)
- Name skills as verbs/actions, not nouns. The plugin provides the noun context.

## Discovery

Each plugin has an `introduce` skill that explains its capabilities:

- `/noteplan-manager:introduce` — NotePlan management (16 skills)
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
