# Public data portals for new-business detection

Where to look for each signal in the "did they file to open here?" chain. Socrata
portals are queryable with `discover.py` (no key). SoS / ABC / property portals are
mostly web lookups — point the user there or drive with browser tools.

> **Verify column names.** Dataset ids below were confirmed live, but Socrata datasets
> get renamed/replaced. Always inspect one raw JSON record first, then set
> `--address-col` and `--date-col` to the real column names for that dataset.

---

## Socrata open-data portals (queryable with `discover.py`)

For each city: the `--domain`, plus the building-permit and business-license dataset
ids and the address/date columns to use.

### San Francisco — `data.sfgov.org`
- **Building permits**: `i98e-djp9` — address col `street_name`, date col `permit_creation_date`. Watch `existing_use` → `proposed_use`, `description`, `estimated_cost`, `status`.
- **Registered businesses (tax certificate)**: `g8m3-pdis` — `dba_name`, `ownership_name`, `full_business_address`, `dba_start_date`. Best "is the company registered?" check.
```bash
python3 scripts/discover.py permits --domain data.sfgov.org --dataset i98e-djp9 \
    --address-col street_name --near "Valencia" --since 2024-01-01 --table
python3 scripts/discover.py socrata-search --domain data.sfgov.org \
    --dataset g8m3-pdis --query "Blue Bottle" --table
```

### New York City — `data.cityofnewyork.us`
- **DOB permit issuance**: `ipu4-2q9a` — address cols `house__` + `street_name`, date col `issuance_date` (also `filing_date`). `job_type`, `permit_type`.
- **DOB NOW: Certificate of Occupancy**: `pkdm-hqz6` — occupancy = ready-to-open signal.
- **Legally Operating Businesses (DCA licenses)**: `w7w3-xahh` — `business_name`, `address_building` + `address_street_name`, `license_creation_date`.

### Chicago — `data.cityofchicago.org`
- **Building permits**: `ydr8-5enu` — date cols `application_start_date` / `issue_date`, `permit_type`, `work_description`. Street is split across `street_number`/`street_direction`/`street_name`.
- **Business licenses**: `r5kz-chrr` — `doing_business_as_name`, `legal_name`, `address`, `license_start_date`, `business_activity`.

### Other large Socrata portals (confirm dataset id with `catalog`)
- **Los Angeles** — `data.lacity.org` (building permits, active businesses)
- **Seattle** — `data.seattle.gov` (`Built Environment` / trade permits; business licenses via WA state)
- **Austin** — `data.austintexas.gov` (issued construction permits)
- **Dallas** — `www.dallasopendata.com`
- **Baltimore** — `data.baltimorecity.gov`
- **Boston** — `data.boston.gov` (CKAN, not Socrata — use its portal UI)
- **Washington DC** — `opendata.dc.gov` (ArcGIS, not Socrata)

When a city isn't listed, find its portal:
```bash
python3 scripts/discover.py catalog --domain <guessed-domain> --query "building permits" --table
# or web-search: "<city> open data building permits socrata"
```
Cross-domain discovery API: `https://api.us.socrata.com/api/catalog/v1?q=building+permits&domains=<domain>`.

---

## Secretary of State — entity registration (signal #1)

Free entity search, one per state (LLC/corp name → address + agent). Web lookups:
- **CA**: bizfileonline.sos.ca.gov/search/business
- **NY**: apps.dos.ny.gov/publicInquiry
- **TX**: mycpa.cpa.state.tx.us (Comptroller) + direct.sos.state.tx.us (SOSDirect, paid)
- **FL**: search.sunbiz.org
- **DE**: icis.corp.delaware.gov (name check; full record paid)
- **IL**: apps.ilsos.gov/businessentitysearch
- **WA**: ccfs.sos.wa.gov
- Others: search "<state> secretary of state business entity search".
- **Aggregator**: opencorporates.com covers most US states in one search (free tier).

---

## Alcohol (ABC) — pending liquor-license applications (signal #5, early)

A pending liquor license is a strong "restaurant/bar opening" signal, often
address-searchable and public:
- **CA**: abc.ca.gov → License Query System (search by address/city; shows pending)
- **NY**: sla.ny.gov → License Query / public notice of pending applications
- **TX**: tabc.texas.gov → Public Inquiry
- **FL**: myfloridalicense.com (DBPR)
- Others: search "<state> ABC liquor license lookup".

---

## Food / health permits (signal #5)

County or city health department; pending food-facility permits precede opening:
- Search "<county> environmental health food facility permit lookup".
- Many counties publish inspection + permit data; some on the Socrata portal above.

---

## Property / lease records (signal #2)

County assessor/recorder — tenant or ownership change. Rarely a free API:
- Search "<county> assessor property search" or "<county> recorder of deeds".
- Commercial-listing sites (LoopNet, Crexi) show leased/available storefronts.

---

## Sign permits (signal #4, early named-tenant signal)

Often a line item in the city building/permit dataset (filter `--near <street>` and
look for permit type or description containing "sign"), or a separate dataset — check
`catalog --query "sign permit"`.
