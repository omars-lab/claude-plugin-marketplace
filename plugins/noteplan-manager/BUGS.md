# Bugs — noteplan-manager

Tracked issues in the sweep review portal and related tools.
Auto-updated when new issues are found during development.

---

## Open

<!-- BUGS:OPEN -->

| ID | Component | Description | Fixed in |
|---|---|---|---|
| B-15 | `classifyRow` (lost) | **Redirect-stub FP**: when a destination plan has been migrated to a new namespace (e.g. `🏡260313👨🏻‍💻 Developing Bikar` → `☕️260313🎨 Developing Bikar`), the old stub contains only a `> Migrated: see [[...]]` pointer. Lines classified as lost against the stub should follow the redirect and re-check the linked destination. | — |

<!-- /BUGS:OPEN -->

---

## Fixed

<!-- BUGS:FIXED -->

| ID | Component | Description | Fixed in |
|---|---|---|---|
| B-01 | `classifyDestLines` | Index-skew: filtered `removedNorms` array used wrong index to look up `removedLines`. Section headers like `# EarlBear` normalized to empty, shifting all subsequent indices. Fixed by preserving `origIdx` through the filter. | 3.87.0 |
| B-02 | `isNoiseLine` (JS) | `SyntaxWarning \s` in f-string: `/^#+\s/` in JS template needed `\\s` inside Python f-string. | 3.88.0 |
| B-03 | `classifyRow` | `destPairIds` declared with `const` inside `if` block, referenced outside — block-scope bug. Hoisted to `let`. | 3.89.0 |
| B-04 | `classifyRow` | `movedCount > total` → `lostCount = -1`. Section headers passed `removedEntries` filter (normLine.length > 3) but excluded from `countableRemoved` by `isNoiseLine`. Fixed by adding `!isNoiseLine(e.line)` to `removedEntries` filter. | 3.90.0 |
| B-05 | `isLineInDestFile` | Lines moved by THIS sweep are present in dest file → `countableRemoved = 0` → classified as `anomaly` instead of `move`. Fixed by removing `isLineInDestFile` from denominator filters; kept only in `lostLines` filter. | 3.91.0 |
| B-06 | Empty file detection | Checked `b/${destRaw}.md\nnew file` but actual diff path has `b/Calendar/20260424.md` prefix. Fixed to `/${destRaw}.md\nnew file`. | 3.92.0 |
| B-07 | `sectionHeaderMatches` | Parent-section false match: "config agent" matched "config agent arb" via prefix check. Fixed by rejecting when `nameLower.startsWith(stripped + ' ')`. | 3.93.0 |
| B-08 | `sectionHeaderMatches` | Short-token miss: "arb" (3 chars) filtered by `length > 3` → never matched `## ARB & Governance`. Fixed with last-token word-boundary check. | 3.94.0 |
| B-09 | `injectMixedLostSubRow` | ⚡ badge persisting after sub-row injection — early-return guard skipped badge upgrade on repeat calls. Fixed by setting `displayType='move'` in `updateRowBadge` for mixed rows directly. | 3.95.0 |
| B-10 | `showSectionModal` | focusLost amber header repeated in source panel when row was mixed. Fixed with clean `lostLineHtmlClean` without section header for focusLost path. | 3.95.1 |
| B-11 | `showSectionModal` | "No lost lines detected" — `isLineInDestFile` filtered all lost lines in `showSectionModal`'s panel. Fixed by removing from `lostLines` filter in modal (dest-file check only belongs in classification, not display). | 3.96.0 |
| B-12 | `renderNarrative` | `day-sep-row` used `colspan="6"` in a 7-column table. Fixed to `colspan="7"`. | 3.97.0 |
| B-13 | `classifyRow` + audit Python | **Cross-row anomaly FP**: multiple breadcrumb rows to same dest each see full dest additions as untraced. Fixed with two-layer subtraction: (1) sibling row removed norms (`getDestSiblingNorms()`); (2) global diff removed norms. Lines claimed by either layer are not anomalous for the current row. JS-17 regression test. 13 anomalies remain — those need V-47 (section scope) fixes. | 3.100.3 |
| B-14 | `classifyRow` + audit Python | **New-file FP**: newly created plan/note files classified as anomaly because all diff additions (frontmatter + boilerplate + content) had no matching source removed lines. Fixed: `parseDiff` sets `isNewFile=true`; JS `classifyRow` returns `empty` when `total===0 && isNewFile`; Python audit returns `empty` with `new_file` issue tag. 25→13 anomaly on run 2026-04-21-14. | 3.100.2 |
| V-47a | `extractSectionLines` + audit Python | **Fuzzy section name matching**: breadcrumb section names (e.g. "Anthropic GitHub refs") didn't match `##` headers in dest diff block (e.g. "## References") because exact/last-token checks failed. Added `v47aScore()` with de-plural stem prefix overlap ("refs"→"ref" matches "references" → score 0.7 ≥ 0.5). `extractSectionLines` refactored to inner `doExtract(activeName, strictBoundary)` with `sectionEntered` tracking. `sectionFound` return flag prevents full-file fallback even for empty scoped sections. Python mirror `_extract_section_lines_scoped` added. JS-19 regression test. 13→12 anomaly on run 2026-04-21-14. | 3.100.4–5 |
| B-16 | audit `classify_row` | **Multi-commit sweep FP (disk confirmation)**: sweep creates separate commits for content removal and breadcrumb addition; snapshot only captures one diff. Source removal missing → `removed=[]` → unclaimed dest additions → false anomaly. Fix: if ALL unclaimed additions in the V-47a-scoped section are confirmed present in dest file on disk, classify `empty` (tag: `disk_confirmed`). 12→0 anomaly on run 2026-04-21-14. Python-only (JS portal can't check disk). | 3.100.6 |

<!-- /BUGS:FIXED -->

---

## How to add a bug

When a bug is found during development or remediation, append to the Open section:

```markdown
| B-NN | Component | Short description of the bug and its root cause | — |
```

When fixed, move the row to Fixed and fill in the version.

Hooks auto-update this file when issues are logged via `quality-log.jsonl`.
