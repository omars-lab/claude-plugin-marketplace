# AI Metadata Block Schema

The self-healing metadata block embedded in a markdown doc. Hidden from readers (collapsed `<details>`), machine-readable by AI agents. Works in any markdown tree — keep all paths repo-relative, never absolute or user-specific.

## Block format

Placed at the end of the doc, collapsed by default:

```html
<details>
<summary>🤖 AI Metadata (Click to expand)</summary>

```yaml
# AI METADATA - DO NOT REMOVE OR MODIFY
# AI_UPDATE_INSTRUCTIONS:
#   1. SCAN_SOURCES: <what to scan and where (repo-relative)>
#   2. EXTRACT_DATA:  <what data to extract and how>
#   3. UPDATE_CONTENT: <how to update the content>
#   4. VERIFY_CHANGES: <how to confirm updates are correct>
#   5. MAINTAIN_FORMAT: <how to preserve formatting/structure>
#
# CONTENT_PATTERNS:
#   - <name>: <description + regex if applicable>
#
# DATA_SOURCES:
#   - <name>: <repo-relative path + description>
#
# UPDATE_TRIGGERS:
#   - <trigger>: <when this should cause an update>
#
# FORMATTING_RULES:
#   - <rule>: <how to keep formatting consistent>
#
# ITERATION_HISTORY:
#   - <YYYY-MM-DD>: <descriptive title> - <summary of ALL changes that day>
#
# EVALUATION_CRITERIA:        # optional — for iteratively-improved docs
#   1. <name>: <what to evaluate and how to measure>
#
# CONTENT_FEEDBACK_LOOP:      # optional — pairs with EVALUATION_CRITERIA
#   - Evaluate against all criteria before major edits
#   - Identify coverage gaps / quality issues
#   - Prioritize by impact and user need
#   - Keep consistent with existing format/quality
#   - Update criteria from new insights
#
# UPDATE_FREQUENCY: <how often to check/update>
```

</details>
```

## Field reference

- **AI_UPDATE_INSTRUCTIONS** — the step-by-step the executor follows: scan → extract → update → verify → maintain-format.
- **CONTENT_PATTERNS** — what updatable content looks like; include regex when it helps the executor locate it.
- **DATA_SOURCES** — files/dirs to read for fresh data. Repo-relative only.
- **UPDATE_TRIGGERS** — conditions that mean the doc is stale.
- **FORMATTING_RULES** — constraints that keep edits consistent with the doc's style.
- **ITERATION_HISTORY** — one entry per day with a descriptive title; summarize same-day changes together.
- **EVALUATION_CRITERIA / CONTENT_FEEDBACK_LOOP** — include for docs with quality standards that evolve (story banks, portfolios, technical docs, multi-stakeholder resources).
- **UPDATE_FREQUENCY** — cadence hint for periodic refresh.

## Discovery markers (execute mode)

- Modern: `<details><summary>🤖 AI Metadata (Click to expand)</summary>` with YAML inside.
- Legacy: `<!-- AI METADATA - DO NOT REMOVE OR MODIFY -->`.

## Examples of dynamic content worth tracking

File counts/stats ("15 files", "3,037 insertions") · time-savings/ROI ("25–40 hours/year") · version numbers · file paths/dir structures · dependency/tool versions · config options · lists & inventories (files, features, capabilities) · cross-references between docs.

## Common update types (execute mode)

1. Statistics & metrics (time savings, ROI, counts, benchmarks)
2. File/directory inventories (new files, path changes, dependency versions)
3. Content inventories (feature lists, use-case diagrams, reference links)
4. Cross-references (inter-doc links, consistent terminology, version compatibility)

## Inject quality checklist

- [ ] Instructions specific and actionable
- [ ] Patterns defined with examples/regex
- [ ] Data sources accurate and repo-relative
- [ ] Triggers well-defined
- [ ] Formatting rules preserve structure
- [ ] Block collapsed (hidden from readers)
- [ ] Comprehensive enough for an agent to act unattended
- [ ] EVALUATION_CRITERIA + feedback loop included when the doc is iteratively improved
