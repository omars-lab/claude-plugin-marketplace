# Local Guide

Be your own local guide — discover businesses near a location and detect whether a company has filed to open at a specific address, using free no-API-key public data (OpenStreetMap + Socrata open-data portals).

## Getting Started

```bash
# Install
/plugin install local-guide@oeid-claude-plugins

# Learn what this plugin can do
/local-guide:introduce
```

## Skills (4)

| Category | Skill | What it does |
|---|---|---|
| **Intro** | `introduce` | Explain plugin capabilities and route to the right skill |
| **Detect** | `detect-new-openings` | Did a company *file to open* here? Query permits + licenses, flag change-of-use signals, cite the record |
| **Inventory** | `find-nearby` | What businesses physically exist near a point right now (OpenStreetMap) |
| **Registration** | `find-registration` | Is a company registered/licensed? Search license/entity data by name; route to SoS / ABC / property portals |

## Requirements

- Python 3 (standard library only — no pip installs)
- Internet access to public endpoints (Nominatim, Overpass, Socrata) — no API keys

---

**Part of**: [OEID Claude Plugin Marketplace](../../README.md)
