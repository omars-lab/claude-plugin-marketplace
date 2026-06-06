# Blog / Technical Post Structure

A reusable structure for turning a technical artifact (a prompt, tool, workflow, or system) into an engaging, scannable blog/doc post. Targets MDX/Markdown doc sites (Docusaurus and similar). Use when authoring or normalizing a technical post; pairs with `manage-ai-metadata` for self-healing stats.

Nothing here is project-specific — supply the target directory, author, and links at runtime.

## Frontmatter

```yaml
---
title: "Succinct Title (3-4 words)"      # fits sidebar nav; descriptive, not generic
date: YYYY-MM-DD
tags: ["..."]
description: "What this does and its value"
author: "<author>"
---
```

Right after the title, link to the source artifact (e.g. its GitHub file); repeat source + repo links at the end as an emoji blockquote.

## Section skeleton

1. **High-level overview** — intent/problem, usage context, value prop, target audience.
   - **Estimated annual time savings** (a recurring high-value section): weekly time saved → annual hours; indirect benefits; ROI (e.g. at a chosen hourly rate). Template:
     ```markdown
     **Estimated Annual Time Savings: [X-Y] hours/year**
     - Weekly: [X-Y] min saved vs. manual
     - Annual: [X-Y] hours direct
     - Additional: reduced mental overhead, focus, less duplication
     - ROI: at $[rate]/hour ≈ $[X-Y]/year
     ```
2. **Technical documentation** — inputs, outputs, process flow, prerequisites.
3. **Visual representation** — a component diagram (`graph LR`: inputs → black-box → outputs) and a `sequenceDiagram` (user ↔ system, with approval/validation steps).
4. **Usage metrics & analytics** — usage stats, performance, feedback, trends (feed from `manage-ai-metadata` if self-updating).
5. **Maturity assessment** — Experimental / Developing / Mature / Production + quality indicators + improvement areas (see `claude-manager` maturity-dimensions).
6. **Practical examples** — real use cases, before/after, edge cases, integrations.

## Reusable templates

**Before/After**
```markdown
### 🧹 Real Use Case: [Name]
#### Before
❌ [Problem]  ❌ [Problem]
#### After
✅ [Solution]  ✅ [Solution]
```

**Metrics table**
```markdown
| Metric | Value | Impact |
|--------|-------|--------|
| **[Metric]** | [Value] | [Impact + emoji] |
```

**Key takeaways table**
```markdown
| Benefit | Impact | Value |
|---------|--------|-------|
| **🤖 [Benefit]** | [Impact] | [Value type] |
```

## Readability rules

Emojis in section headers · `---` between major sections · tables for metrics/comparisons · visual indicators (✅ ❌ 🎯 ⚡ 💰 🛡️) · short scannable chunks · always include a before/after · end with clear takeaways/CTA.

## Mermaid + MDX gotchas

- **Mermaid:** node IDs start with letters (`A`, not `1`); always quote labels (`A["Label"]`); `<br/>` for line breaks; validate syntax before embedding.
- **MDX:** avoid `<` before a number (`<0.3%` breaks MDX → write "less than 0.3%"); escape HTML-like syntax; don't use JSX-looking tags; confirm the page compiles.

## Folder placement (doc-site repos)

Mirror the source repo's structure under the docs tree; create sidebar category files (e.g. `_category_.json`) per subdirectory with labels + emojis. Discover the docs root from the repo — don't hardcode an absolute path.
