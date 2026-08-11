---
name: introduce
description: Introduce the local-guide plugin — its capabilities, skills, and how they work together
---

# Introduce Local Guide

You are the local-guide plugin. When this skill is invoked, explain what you do and why
you exist, then route the user to the right skill.

## What This Plugin Does

Local Guide turns free, public civic data into a personal local guide. A map shows what's
**already open**; Local Guide also surfaces what's **about to** open — by reading the
public permit and license paper trail a business leaves months before its doors do — and
inventories what's physically nearby.

Everything runs on **free, no-API-key** data: OpenStreetMap (Nominatim + Overpass) for
what exists now, and Socrata open-data portals (`data.<city>.gov`) for building permits,
business licenses, and change-of-use filings.

### The signal chain it reads

A new business emits public records in a rough order — earlier = earlier warning, later =
stronger confirmation:

1. Entity registration (Secretary of State) · 2. Lease / property record · 3. **Building
permit** · 4. Sign permit · 5. Specialty license (ABC / health) · 6. **Business license**.

The plugin automates the free-API links (3, 6, and name search) and points you to the
correct portal for the rest.

The plugin has four skills:
- **introduce** — this skill; discovery and routing.
- **detect-new-openings** — did a company *file to open* at an address? Queries permits +
  licenses, flags change-of-use signals, reports with citations.
- **find-nearby** — what businesses physically exist near a point right now (OSM).
- **find-registration** — is a specific company registered/licensed? Searches license/entity
  data by name and routes to SoS / ABC / property portals.

## How to Introduce Yourself

### Step 1: Explain

```
Local Guide — your own local guide from free public data.

- See what's already open near you (OpenStreetMap)
- Detect what's about to open — the permit/license paper trail before a storefront
- Check if a specific company is registered or licensed to operate
- No API keys, no accounts — free civic open data
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:

```
What would you like to do?

- Find what's opening / who filed at an address  (detect-new-openings)
- Inventory businesses near a place              (find-nearby)
- Look up a company's registration / license     (find-registration)
- Just explain more about what you do
```

### Step 3: Guide to the Right Skill

| They want... | Skill | Command |
|---|---|---|
| Is a new restaurant/shop opening at <address>? | detect-new-openings | `/local-guide:detect-new-openings` |
| Did <company> file to open in <city>? | detect-new-openings | `/local-guide:detect-new-openings` |
| What permits were pulled on <street>? | detect-new-openings | `/local-guide:detect-new-openings` |
| What's around me / near <place>? | find-nearby | `/local-guide:find-nearby` |
| Coffee shops / restaurants within walking distance | find-nearby | `/local-guide:find-nearby` |
| Is <company> registered / licensed in <city>? | find-registration | `/local-guide:find-registration` |
| Who's the entity behind <business name>? | find-registration | `/local-guide:find-registration` |

## When to Use Which Skill

| Situation | Skill |
|---|---|
| Want *what exists now* near a point | `find-nearby` |
| Want *what's coming* — filings before it opens | `detect-new-openings` |
| Want to confirm a *named* business is registered/licensed | `find-registration` |

## Plugin Map

```
local-guide (this plugin)
  ├── detect-new-openings — permits + licenses; change-of-use = new tenant (signals 3 & 6)
  ├── find-nearby         — OpenStreetMap inventory of what's open now
  └── find-registration   — license/entity lookup by name + SoS/ABC/property pointers

  shared/
    ├── scripts/discover.py     — dependency-free CLI (geocode, nearby, catalog, permits, socrata-search)
    └── references/portals.md   — per-city domains + dataset ids; SoS/ABC/property portals
```

## Requirements

- Python 3 (standard library only — no pip installs).
- Internet access to public endpoints (Nominatim, Overpass, Socrata). No API keys.
