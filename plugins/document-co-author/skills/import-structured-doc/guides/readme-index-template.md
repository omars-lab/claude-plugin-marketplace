# Folder-README-as-Navigation-Index Template

An alternative target template for `import-structured-doc`: instead of restructuring a loose source
document, you **author (or repair) a folder's README so it doubles as a navigation index** for that
folder and its children. Use this when the "source" is a directory tree rather than a single note — the
README is generated *from* the folder's contents and sub-folders.

Like every template in this skill, nothing here is hardcoded. The docs root, the link format, the
frontmatter fields, and the author id are all confirmed with the user in Phase 1. The examples below use a
docs-site convention (frontmatter + slug-based links); adapt the link syntax and frontmatter shape to the
target site generator (Docusaurus, Jekyll, MkDocs, a wiki, or plain relative Markdown links).

## When to use this template

- A folder of content has no README, or a stub README, and readers can't tell what the folder is for or
  what's inside it.
- A documentation tree needs consistent, self-describing index pages at every level.
- You want each folder to explain **what it is, why it exists, how it differs from sibling folders**, and
  **link to its documents and child folders**.

## Section order

A folder README following this template contains these parts in order:

1. **Frontmatter**
2. **Intent & Purpose** (what this folder represents, why it exists, what it solves)
3. **Distinction from Sibling Folders** (how it differs from related folders)
4. **What You'll Find Here** (the kinds of content, themes, examples)
5. **Key Documents & Child Folders** (linked index of the folder's files and sub-folder READMEs)

Always emit all five parts, even for a sparse folder — extract what you can and keep the skeleton
consistent so every index page reads the same way.

## 1. Frontmatter

Generate frontmatter shaped like the configured convention. A typical docs-site shape:

```
---
slug: <folder-name>
title: '<Human-readable section title>'
description: '<one-line summary of what this folder contains — used for SEO and nav>'
authors: [<author-id>]
tags: [<tag1>, <tag2>, ...]
draft: false
---
```

- **slug**: usually matches the folder name; keep it URL-safe.
- **description**: one line; this is what shows in navigation and search results, so make it specific.
- The exact field set, author id, and `draft` semantics come from the user's configured convention. If
  the target site doesn't use frontmatter, omit this part.

## 2. Intent & Purpose

Open with a one-sentence definition of the folder, then a short section that answers:

- **What this folder represents** — the core concept, purpose, or theme.
- **Why it exists** — the intent behind organizing content this way.
- **What problems it solves** — how this organization helps a reader navigate and understand the content.

```markdown
# <Folder Title>

<One-sentence definition of what lives here and why.>

## What Is <Folder Title>?

<Folder Title> represents **<core idea>**:
- <facet 1>
- <facet 2>
- <facet 3>
```

## 3. Distinction from Sibling Folders

Explain how this folder differs from the folders next to it. This is the part readers rely on to pick the
right folder. Contrast against the *actual* siblings you find in the parent directory — don't invent
comparisons.

```markdown
## Difference from <Sibling Folder>

**<This Folder>** vs **<Sibling Folder>**:
- **<This Folder>** → <its defining trait>
- **<Sibling Folder>** → <its defining trait>

<One or two sentences making the boundary unambiguous.>
```

## 4. What You'll Find Here

A short list of the *kinds* of content in the folder — themes, topics, and the sort of thing a reader can
expect to discover. This is categorical, not a file-by-file list (that's part 5).

```markdown
## What You'll Find Here

- <kind of content 1>
- <kind of content 2>
- <kind of content 3>
```

## 5. Key Documents & Child Folders

The navigation index proper. List and **link** the folder's documents and the READMEs of its child
folders, organized logically (by category, date, or topic — whatever fits). Match the link format to the
target site generator:

- **Docusaurus / slug-routed sites**: link by route without file extension — `/docs/<path>` for documents,
  `/docs/<folder>` for a child folder's README (the README resolves at the folder path).
- **Jekyll / MkDocs / wikis**: use the generator's own link convention.
- **Plain Markdown**: use relative paths — `./child-doc.md`, `./sub-folder/README.md`.

```markdown
## Key Documents

### <Category or grouping>
- [<Doc Title>](<link>) - <one-line description>
- [<Doc Title>](<link>) - <one-line description>

### Sub-Folders
- [<Child Folder Title>](<folder-link>) - <what the child folder covers>
  - See the [<Child Folder> README](<folder-link>) for its full contents.
```

## Recursive processing

When you author or repair a README for a parent folder, propagate the pattern down the tree:

1. **List the child folders** of the current folder.
2. For each child folder, **check whether a README exists**.
   - If missing → create one following this same five-part template.
   - If present → review and repair it to match.
3. **Recurse** into each child folder and repeat.
4. **Update the parent README** with links to every child folder's README (part 5).

```
1. Author/repair parent folder README
   ├─ 2. List child folders
   ├─ 3. For each child folder:
   │     ├─ README missing? → create with the five-part template
   │     ├─ README present? → review + repair
   │     └─ recurse into its children
   └─ 4. Update parent README with links to all children
```

Keep the recursion bounded to the tree the user scoped in Phase 1, and confirm before creating a large
number of new files.

## Quality checklist

Before considering a folder README complete:

- [ ] Frontmatter complete and valid (or intentionally omitted for non-frontmatter sites)
- [ ] Intent & purpose clearly explained
- [ ] Distinction from sibling folders documented against the real siblings
- [ ] "What You'll Find Here" lists the kinds of content
- [ ] All documents in the folder are listed and linked
- [ ] All child-folder READMEs are linked
- [ ] Links use the target generator's correct format and resolve
- [ ] Every child folder was checked for a README; missing ones were created
- [ ] Child READMEs were repaired/created recursively
- [ ] Content is well-organized and easy to navigate

## Notes

- A folder README serves as both a **navigation aid** and a **conceptual guide** — it should let a reader
  understand the organization and find relevant content quickly.
- Keep structure consistent across sibling folders so the whole tree reads predictably.
- When in doubt, prioritize clarity and navigation over brevity.
- Preserve any substantive prose already in an existing README — you are restructuring it into this
  template, not discarding its content (the skill's core rule applies here too).
