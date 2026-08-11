---
name: find-nearby
description: Inventory the businesses that physically exist near a point right now — restaurants, shops, services — from OpenStreetMap, no API key. Use when the user asks "what businesses/coffee shops/restaurants are near me", "what's around <address>", or "what's within walking distance of <place>". For what's *about to* open (permits/filings) use detect-new-openings instead.
---

# Find nearby

You inventory what businesses **currently exist** near a location, from OpenStreetMap.
Read-only, no API key. This answers "what's here now" — for "what's coming" (the permit
paper trail), route to `detect-new-openings`.

## What this skill does

Given an address or lat/lon, it lists nearby businesses (name, type, address, website,
phone, hours where OSM has them), grouped by category, distinguishing chains from
independents (the OSM `brand` tag).

## The tool

A bundled, dependency-free Python CLI (**no API key**):

```bash
python3 "$CLAUDE_PLUGIN_ROOT/shared/scripts/discover.py" nearby \
    --address "<place>" --radius <meters> --category <food|retail|services|all> --table
```

Sources: Nominatim (geocode) + Overpass (nearby), both OpenStreetMap.

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Resolve the point", description: "Geocode the address, or accept provided lat/lon", activeForm: "Resolving location" })
TaskCreate({ subject: "Query nearby businesses", description: "Run nearby with radius + category; summarize by type", activeForm: "Querying nearby" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
```

## Workflow

### 1. Resolve the point

If given lat/lon, pass them directly (skips a geocode call + its 1-sec rate sleep):
```bash
python3 "$CLAUDE_PLUGIN_ROOT/shared/scripts/discover.py" nearby --lat 37.7955 --lon -122.3937 ...
```
Otherwise geocode the address by passing `--address`. If the address is ambiguous or the
user hasn't said how far, use `AskUserQuestion` to confirm the **radius** (walkable ≤ 800m)
and **category** (food / retail / services / all).

### 2. Query and summarize

```bash
python3 "$CLAUDE_PLUGIN_ROOT/shared/scripts/discover.py" nearby \
    --address "Ferry Building, San Francisco" --radius 400 --category food --table
```
Summarize by type (how many cafés, restaurants, bars), call out notable independents vs.
chains, and surface websites/hours when present. Keep radius ≤ 800m unless the user wants
a wider sweep — Overpass gets slow and noisy on large radii.

## Safety checks

- **Read-only** — prints results, modifies nothing.
- **Polite API use** — Nominatim ~1 req/sec (CLI sleeps); on an Overpass timeout, retry
  once after a short pause rather than hammering.
- OSM coverage is uneven — absence in OSM is *not* proof a place doesn't exist. For "is a
  specific thing there / coming", use `detect-new-openings`.

## Example usage

```
User: coffee shops near the Ferry Building?
→ nearby --address "Ferry Building, San Francisco" --radius 400 --category food --table
→ summarize the cafés, note Blue Bottle/Peet's (chains) vs. independents
```

## Related skills

- `detect-new-openings` — what has *filed to open* nearby (permits/licenses).
- `find-registration` — look up a specific business by name in license/entity data.
- `introduce` — overview of the local-guide plugin.
