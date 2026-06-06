# Section Template & Extraction Rules

This guide details the **default** structured-doc template and the rules for mapping loose source content into it. The default is an example, not law — if the user supplied a custom section list in Phase 1, follow theirs and adapt these rules to match.

## Default Section Order

Output should contain these sections in **this exact order**:

1. **Frontmatter**
2. **Diagram / Embed**
3. **Questions**
4. **Decision**
5. **Strategy**
6. **References**
7. **Kinds of Action Items** (abstract, repeatable activities)
8. **Specific Action Items** (concrete, one-off tasks)

Always emit all sections, even when a source is sparse — extract what you can and keep the skeleton consistent. For minimal sources, note in **Specific Action Items** that strategic content was folded into the abstract categories.

## 1. Frontmatter

Generate frontmatter shaped like the configured convention. A typical shape:

```
---
slug: <root>-<subject>
title: '<emoji> <Title>'
description: '<one-line summary of what this doc covers>'
authors: [<author-id>]
tags: [<tag1>, <tag2>, ...]
draft: true
date: <today's date, e.g. 2026-06-05T10:00>
---
```

- **Title**: derive the core subject; strip filler/planning words ("planning", "managing", "organizing") when they obscure the real subject. Prefer specific terms over generic ones (avoid bare "developing", "building", "productivity" without a domain).
- **Emoji**: pick one relevant, professional emoji that represents the subject; avoid duplicates across docs in the same collection.
- **Tags**: relate to the subject; align with the taxonomy root used in sections 7–8.
- The exact field set, author id, and date format come from the user's configured convention.

## 2. Diagram / Embed

If the source contains a diagram/embed link (e.g. a board or design link), convert it to the collection's embed format. A common pattern for an embeddable iframe:

```jsx
<iframe
  style={{ border: "1px solid rgba(0, 0, 0, 0.1)" }}
  width="100%"
  height="600"
  src="<converted-embed-url>"
  allowFullScreen
/>
```

Conversion specifics (host swap, query params) depend on the embed provider — apply whatever the target collection uses. If there is **no** diagram link, leave a dated placeholder todo:

```markdown
- [ ] Add diagram/embed link >YYYY-MM-DD
```

## 3. Questions

Capture recurring questions the author asks themselves about the subject, as a bullet list.
- Pull sentences ending in `?`.
- Include "How will I…", "What should I…", "Why do I…" forms from anywhere in the source.

## 4. Decision

Consolidate the rationale — why the subject matters / why it's worth doing regularly.
- Look for statements of importance, necessity, or motivation.
- Capture "I need to…", "It's important to…", "This helps me…".

## 5. Strategy

Aggregate how the author approaches the subject — methods, recurring events, frequency.
- Pull process descriptions and approaches.
- Capture frequency cues (daily/weekly/monthly) and "how I do this" phrasing.

## 6. References

Capture standalone links, resources, and external references that are **not** actionable todos.
- Include standalone URLs, book/article/tool/platform mentions.
- Format as a bulleted list with descriptive text where possible.
- **Do not** pull references that are sub-bullets of a specific todo — those stay with their parent todo in Specific Action Items.
- Preserve links exactly as written.

## 7. Kinds of Action Items (abstract)

Abstract, generalizable activities — the *kinds* of things the author repeats, not specific tasks.

- Each theme gets a unique hashtag nested under a shared taxonomy root: `#<root>/<theme>`.
- **Each kind must explicitly list any essential "should/must/need to" activities using the author's exact language** — preserve concrete requirements inside the abstract category.
- **Strategic questions integration**: within each category, add a `Strategic Questions / Ask Yourself:` bullet with the relevant questions as sub-bullets, kept in natural question form (do not convert to statements).
- If the source only has granular todos, generalize the abstract activity behind them and add examples here.

Example:

```
### #<root>/<theme>
- Abstract activity 1
- Abstract activity 2
- Strategic Questions / Ask Yourself:
  - What should I consider when doing this?
  - How do I determine the best approach?
```

## 8. Specific Action Items (concrete)

Granular, one-off todos moved to the bottom **without editing their content**.

- **Preserve all context**: keep sub-bullets, references, links, and original indentation exactly.
- **Format sub-bullets by type**: actionable items use `- [ ] Item`; non-actionable items (references, notes) use `- Item`. Preserve original intent.
- **Group by theme, sort by importance**: group items under `### #<root>/<theme>` headers; within each theme put the most important first (urgency, impact, dependencies, completion status, strategic value). Treat a parent task plus its subtasks as a single unit when sorting.
- **Hashtag rules (critical)**:
  - Only root-level (un-indented) items get a `#<root>/<theme>` hashtag relating them to a "Kind of Action Item".
  - Sub-tasks (indented) **never** get hashtags — they inherit from their parent.
  - If an indented item has no sensible parent, un-indent it and give it the appropriate hashtag.

Correct:

```
### #<root>/<theme-a>
- [ ] Parent task #<root>/<theme-a>
  - Supporting reference or note
  - [ ] Subtask (no hashtag)

### #<root>/<theme-b>
- [ ] Another parent task #<root>/<theme-b>
```

Incorrect (subtasks must not carry hashtags):

```
- [ ] Parent task #<root>/<theme-b>
  - [ ] Subtask #<root>/<theme-b>   ❌
```

Every specific item's essence should already appear as a "Kind of Action Item" in section 7.

## Merging Into an Existing Doc

When Phase 5 decides to merge rather than create:
1. Add the import-tracking header to the source being merged.
2. Fold content into the existing doc: append new questions, enrich Decision/Strategy, **combine similar abstract themes** in Kinds of Action Items, and add new specific tasks.
3. Keep hashtags consistent across the merged material.
4. Preserve all content from both documents.

## Naming Convention

- Name the output file after its subject, aligned with the frontmatter `slug`, plus the collection's file extension.
- Determine the subject from the content's core activity; remove obscuring filler words; keep it specific and unambiguous.
- The exact pattern, directory, and extension come from the user's configured convention.

## Quality Checklist

- [ ] All original content preserved (nothing lost); original phrasing kept where possible.
- [ ] Output starts with frontmatter (no import header in the output file).
- [ ] All confirmed sections present, in the correct order.
- [ ] Title is specific (not generic) and reflects the actual subject; emoji is relevant.
- [ ] File saved with the configured naming convention + extension in the target directory.
- [ ] Diagram/embed links converted, or a dated placeholder todo added when absent.
- [ ] References section captures all standalone links/resources.
- [ ] Only root-level items have hashtags; sub-items have none; all tags follow `#<root>/<theme>`.
- [ ] Specific items grouped by theme with `### #<root>/<theme>` headers and sorted by importance; parent+subtasks moved as units.
- [ ] Kinds of Action Items hold abstract activities, include exact "need to…" statements, and integrate strategic questions in question form.
- [ ] Every specific item maps to at least one abstract category.
- [ ] If merged: content from both docs preserved; abstract themes combined; hashtags consistent.
- [ ] Source tracked per configuration (header added; optionally moved to done/); no other edits to the source.
