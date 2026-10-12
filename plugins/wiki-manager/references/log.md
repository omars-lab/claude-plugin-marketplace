---
title: Wiki — Log
type: wiki-log
---

# 📚 Wiki — Log

Append-only record of every ingest, move, cascade, and lint. A future session reads
the newest entry to find the "since last index" boundary for the Unorganized inbox.
**Newest entry on top. Never rewrite past entries.**

Each entry:

```
## YYYY-MM-DD — <ingest | reorganize | lint | query-archived>
- Scope: <what folder / how many notes>
- Ingested: [[raw-note]] → [[wiki-article]] (New | Update) — space: <🌐 General | 🏢 Work | …>
- Moved: [[raw-note]] → Notes/🗑️ Unorganized/<topic>/ (+ header added)
- Cascaded: [[wiki-article]] updated because <reason>
- Flagged: <secret/PII notes deferred for redaction — name the file, NOT the value>
- Space calls: <any note whose space was non-obvious + why; any fact promoted to 🌐 General>
- Notes: <anything a future session needs to know>
```

This log spans **all spaces** — always name the space on each ingested/cascaded line.

---

## YYYY-MM-DD — scaffold
- Created the wiki hub (index.md) + per-space indexes + log.md + @References/ templates
  (article, index, hub, log, spaces). Spaces: 🌐 General, 🏢 Work, 📦 Past Work, 🏡 Personal,
  ☕️ NaqshCoffee, 👥 EarlBear. No articles yet.
