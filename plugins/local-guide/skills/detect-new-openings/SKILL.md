---
name: detect-new-openings
description: Detect whether a company has *filed to open* at a specific address or street — by querying a city's free Socrata open-data portal for recent building permits and business licenses and flagging change-of-use signals (existing_use ≠ proposed_use). Use when the user asks "is a new <business> opening at <address>", "did <company> file to open in <city>", "what permits were pulled on <street>", or "is anything new coming to my block". Read-only; queries public data with no API key.
---

# Detect new openings

You help the user find public evidence that a business has **filed to open** at a
location — the permit/license paper trail that appears months before a storefront does.
This is read-only: it queries free public APIs and reports what it finds, with citations.

## What this skill does

Given a street/address + city, it:
1. Resolves the city's open-data portal and the right permit/license dataset.
2. Queries recent filings on that street, newest first.
3. Flags the strongest signal — a **change of use** (`existing_use` ≠ `proposed_use`,
   e.g. `office → retail sales`, `retail → food/beverage`) — plus license registrations.
4. Reports each hit with **permit number, filing date, cost, status, and source** so the
   user can verify. It never asserts "X is opening" from a single filing.

## The signal chain (mental model)

A new business emits public records roughly in this order — earlier = earlier warning,
later = stronger confirmation:

1. Entity registration (Secretary of State) — earliest, often just a mailing address.
2. Lease / property record (county) — tenant change.
3. **Building / alteration permit (city)** — buildout; *this skill's primary signal.*
4. Sign permit — named tenant appears.
5. Specialty license — alcohol (ABC), food/health.
6. **Business license (city)** — clearest confirmation; *also queried here.*

This skill automates 3 and 6 (and full-text search across them). For 1, 2, 5 point the
user to `find-registration` or the portals reference.

## The tool

A bundled, dependency-free Python CLI (`urllib` + `json` only, **no API key**):

```bash
python3 "$CLAUDE_PLUGIN_ROOT/shared/scripts/discover.py" <subcommand> ...
```

Relevant subcommands: `geocode`, `catalog`, `permits`, `socrata-search`. City domains and
dataset ids live in `$CLAUDE_PLUGIN_ROOT/shared/references/portals.md`.

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Resolve portal + dataset", description: "Map city to its Socrata domain and permit/license dataset id (portals.md or catalog)", activeForm: "Resolving portal" })
TaskCreate({ subject: "Query filings on the street", description: "Run permits/socrata-search filtered by street + since-date", activeForm: "Querying filings" })
TaskCreate({ subject: "Flag & report signals", description: "Filter change-of-use, report each with permit #, date, source; corroborate across signals", activeForm: "Reporting signals" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
```

## Workflow

### 1. Resolve the portal + dataset

Identify the city from the address. Look it up in
`$CLAUDE_PLUGIN_ROOT/shared/references/portals.md` (e.g. San Francisco → `data.sfgov.org`,
permits `i98e-djp9`; NYC → `data.cityofnewyork.us`, permits `ipu4-2q9a`; Chicago →
`data.cityofchicago.org`, permits `ydr8-5enu`).

If the city isn't listed, discover the dataset:
```bash
python3 "$CLAUDE_PLUGIN_ROOT/shared/scripts/discover.py" catalog \
    --domain <guessed-domain> --query "building permits" --table
```

If you can't determine the domain, use `AskUserQuestion` to ask the user for their
city's open-data portal, or offer to web-search "`<city> open data building permits socrata`".

### 2. Learn the real column names, then query

**Column names vary by city.** Pull one raw record first and read its keys — don't assume
`street_name`/`permit_creation_date` exist everywhere:
```bash
python3 "$CLAUDE_PLUGIN_ROOT/shared/scripts/discover.py" socrata-search \
    --domain data.sfgov.org --dataset i98e-djp9 --query "restaurant" --limit 1
```
Then query the street, newest first, setting `--address-col`/`--date-col` to the real names:
```bash
python3 "$CLAUDE_PLUGIN_ROOT/shared/scripts/discover.py" permits \
    --domain data.sfgov.org --dataset i98e-djp9 \
    --address-col street_name --near "Valencia" \
    --date-col permit_creation_date --since 2024-01-01 --table
```

### 3. Flag the signals

From the JSON, surface:
- **Change of use** — `existing_use` ≠ `proposed_use`. The clearest "new tenant" flag.
- **`description`** — mentions "new restaurant", "change of use", "tenant improvement".
- **`estimated_cost`** — a large buildout is a serious filing, not a cosmetic one.
- **`status`** — filed / issued / complete tells you how far along it is.

To check a **specific company**, full-text search the license/registration dataset:
```bash
python3 "$CLAUDE_PLUGIN_ROOT/shared/scripts/discover.py" socrata-search \
    --domain data.sfgov.org --dataset g8m3-pdis --query "Blue Bottle" --table
```

### 4. Report — verify, don't assert

For each hit, give the **record and its evidence**, not a conclusion:

> A change-of-use permit to `food/beverage` was filed at 510 Valencia St on 2024-09-09
> (permit 202409090359, $120k, status *issued*): "existing vacant retail space to be
> converted into a restaurant." — source: data.sfgov.org/resource/i98e-djp9

Then note confidence from **convergence**: permit + license + still-absent-from-a-map =
"building out, not yet open." A single permit is weak — permits get withdrawn, licenses
lapse. Say so.

## Safety checks

- **Read-only.** This skill only reads public APIs and prints results — it modifies no
  files and needs no git safety.
- **Be a polite API citizen.** Nominatim allows ~1 req/sec (the CLI sleeps); Overpass and
  Socrata can rate-limit under load — retry once after a short pause on failure.
- **Cite every claim** with permit number + date + source URL.
- **Never fabricate a dataset id or column.** If `catalog` finds nothing, say the city
  isn't covered rather than guessing.

## Example usage

```
User: Is anything new opening on Valencia St in SF?
→ portals.md: SF = data.sfgov.org, permits i98e-djp9
→ permits --near "Valencia" --since 2024-01-01
→ filter existing_use ≠ proposed_use → 27 use-changes
→ report top signals (restaurant conversion at 510, retail at 1031, …) with permit #s
```

## Related skills

- `find-nearby` — what's *already* open near a point (OpenStreetMap inventory).
- `find-registration` — look up a business license or entity registration by company name.
- `introduce` — overview of the local-guide plugin.
