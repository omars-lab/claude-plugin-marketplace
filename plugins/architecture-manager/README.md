# Architecture Manager

Covers the full architecture lifecycle — from evaluating options when nothing is decided, to capturing what was decided, to iterating based on feedback. Everything produced is text-based (PlantUML markup, Markdown) and version-controllable.

## Getting Started

```bash
/architecture-manager:introduce
```

## Skills (6)

| Phase | Skill | What it does |
|---|---|---|
| **Discovery** | `introduce` | Explain capabilities and guide to the right skill |
| **Design** | `design-architecture` | Evaluate options for unknown architecture — pros/cons, cost analysis, comparison matrix, recommendation |
| **Capture** | `generate-erd` | Generate ERDs from schemas, data models, or live ServiceNow tables |
| **Capture** | `generate-diagram` | Generate any PlantUML diagram: sequence, C4, component, deployment |
| **Capture** | `capture-architecture` | Create ADRs and architecture overview documents |
| **Iterate** | `iterate-architecture` | Act on feedback — update diagrams, supersede ADRs, trace what changed and why |

## The Architecture Lifecycle

```
Design                →     Capture              →     Iterate
(architecture unknown)      (architecture known)       (feedback / change)

design-architecture         generate-erd               iterate-architecture
                            generate-diagram
                            capture-architecture
```

## What Each Skill Produces

| Skill | Primary artifact | Secondary artifacts |
|---|---|---|
| `design-architecture` | `DESIGN-NNNN-<title>.md` | Option diagrams (.puml + .svg) |
| `generate-erd` | `<name>_erd.puml` | `<name>_erd.svg` |
| `generate-diagram` | `<name>.puml` | `<name>.svg` |
| `capture-architecture` | `ADR-NNNN-<title>.md` | `OVERVIEW.md` |
| `iterate-architecture` | Updated .puml + ADRs | `CHANGELOG.md` entry |

## Scripts (per skill)

Each skill ships a `scripts/` directory for standalone use outside of Claude:

| Skill | Script | Purpose |
|---|---|---|
| `generate-erd` | `scripts/gen_diagram.py` | Render any .puml file to SVG/PNG |
| `generate-diagram` | `scripts/gen_diagram.py` | Render any .puml file to SVG/PNG |
| `design-architecture` | `scripts/design_init.py` | Scaffold a DESIGN-NNNN document |
| `capture-architecture` | `scripts/adr_init.py` | Scaffold an ADR-NNNN document |
| `iterate-architecture` | `scripts/changelog_entry.py` | Append to architecture CHANGELOG.md |

## Requirements

- Python 3.8+ (for all scripts)
- Internet access to `plantuml.com` for diagram rendering (or the PlantUML MCP tool)
- ServiceNow CEG plugin (optional — used by `generate-erd` for live schema queries)

---

**Part of**: [oeid-claude-plugin-marketplace](https://github.com/oeid/claude-plugins)
