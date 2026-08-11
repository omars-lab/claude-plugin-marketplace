---
name: find-registration
description: Look up whether a specific company is registered or licensed to operate — search a city's business-license/registration open data by company name, and point to the right Secretary of State / ABC / property portal for signals that aren't free APIs. Use when the user asks "is <company> registered in <city>", "does <business> have a license", "who's the entity behind <name>", or "where do I check business registrations". Read-only.
---

# Find registration

You confirm whether a named business is **registered or licensed** to operate at a
location — the confirmation end of the signal chain. Read-only, no API key for the
Socrata parts; the rest are pointers to the correct public portal.

## What this skill does

1. **Searches city business-license / registration open data** by company name (DBA or
   legal name) and reports the registration record — address, start date, activity, id.
2. **Routes to non-API signals** — Secretary of State entity search, state ABC (alcohol)
   applications, county property/lease records — naming the exact portal per jurisdiction
   from the portals reference, since these are web lookups, not free APIs.

## The tool

Bundled dependency-free CLI (**no API key**) for the Socrata portion:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/shared/scripts/discover.py" socrata-search \
    --domain <domain> --dataset <license-dataset-id> --query "<company>" --table
```

Domains, license dataset ids, and the SoS/ABC/property portal links are in
`$CLAUDE_PLUGIN_ROOT/shared/references/portals.md`.

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Pick the right dataset/portal", description: "Map city+signal to license dataset id or the SoS/ABC/property portal", activeForm: "Selecting source" })
TaskCreate({ subject: "Search by company name", description: "Run socrata-search on the license/registration dataset, or route to the web portal", activeForm: "Searching registration" })
TaskCreate({ subject: "Report the record", description: "Report registration with id/date/address + source, or hand off the portal link", activeForm: "Reporting registration" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
```

## Workflow

### 1. Pick the source (which signal?)

- **City business license / registration** (queryable here): SF `g8m3-pdis` (registered
  businesses), NYC `w7w3-xahh` (DCA-licensed), Chicago `r5kz-chrr` (business licenses).
  See `portals.md` for the address/name/date columns each uses.
- **Secretary of State entity** (web portal): the LLC/corp record. `portals.md` lists the
  per-state search URL (CA bizfileonline, NY apps.dos.ny.gov, FL sunbiz, etc.), plus
  opencorporates.com as a multi-state aggregator.
- **ABC (alcohol)** / **county property** (web portal): for bar/restaurant and lease
  signals — again, portal links per state/county in `portals.md`.

If unsure which signal the user wants (license vs. entity vs. alcohol), use
`AskUserQuestion` to disambiguate before searching.

### 2. Search or route

Queryable license/registration data — search by name:
```bash
python3 "$CLAUDE_PLUGIN_ROOT/shared/scripts/discover.py" socrata-search \
    --domain data.sfgov.org --dataset g8m3-pdis --query "Blue Bottle" --table
```
Inspect one raw record first to learn the real column names (they vary by city), then read
DBA/legal name, address, and start date.

For **non-API signals**, don't pretend the CLI covers them — give the user the exact
portal URL from `portals.md`, or offer to drive it with the browser tools
(`claude-in-chrome`) for a live lookup.

### 3. Report

State the record and its source plainly: "*Acme Coffee LLC* is registered at 900 Valencia
St, DBA start 2024-02-01 (SF cert #…, data.sfgov.org/resource/g8m3-pdis)." If you only
have a portal pointer, say that a manual/portal check is required and hand off the link —
don't imply confirmation you didn't get.

## Safety checks

- **Read-only.**
- **Be explicit about coverage.** Clearly separate "I confirmed this in open data" from
  "here's the portal where you can confirm it." Never present a pointer as a result.
- **Cite** dataset + record id + source URL for anything found.

## Example usage

```
User: Is "Blue Bottle" registered in San Francisco?
→ portals.md: SF registered businesses = g8m3-pdis
→ socrata-search --dataset g8m3-pdis --query "Blue Bottle"
→ report matching registrations (DBA, address, start date) with source
```

## Related skills

- `detect-new-openings` — permits/use-changes (earlier in the signal chain).
- `find-nearby` — what physically exists near a point (OpenStreetMap).
- `introduce` — overview of the local-guide plugin.
