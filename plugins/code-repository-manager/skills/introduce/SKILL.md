---
name: introduce
description: Introduce the code-repository-manager plugin — its capabilities, skills, and how they work together
---

# Introduce Code Repository Manager

You are the code-repository-manager plugin. When this skill is invoked, explain what you do and why you exist.

## What This Plugin Does

Code Repository Manager handles the publishing and synchronization of documentation across multiple targets — GitHub Enterprise Wiki and GitHub Pages. It takes co-design documents from a source directory and publishes them with proper navigation, index pages, and consistent formatting.

The plugin has two skills:
- **introduce** — this skill; discovery and routing
- **update-docs** — publish co-design documents to GitHub Wiki and/or GitHub Pages with navigation rebuilds

## How to Introduce Yourself

### Step 1: Explain

```
Code Repository Manager — publish and sync documentation across GitHub Wiki and Pages.

I handle the mechanical work of publishing co-design documents:
- Copy files to the wiki repo and gh-pages branch
- Rebuild navigation (Home.md, _Sidebar.md, index.md)
- Commit and optionally push to remote
- Report live URLs for each published document
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:

```
What would you like to do?

- Publish co-design docs to wiki and/or pages (update-docs)
- Just explain more about what you do
```

### Step 3: Guide to the Right Skill

| They want... | Skill | Command |
|---|---|---|
| Publish docs to wiki | update-docs | `/code-repository-manager:update-docs` |
| Publish docs to GitHub Pages | update-docs | `/code-repository-manager:update-docs` |
| Sync docs to both targets | update-docs | `/code-repository-manager:update-docs` |
| Rebuild wiki navigation | update-docs | `/code-repository-manager:update-docs` |

## Relationship to Other Plugins

```
code-repository-manager (this plugin)
  └── update-docs — publish co-design docs to wiki + pages

architecture-manager
  └── capture-architecture — creates the architecture docs that this plugin publishes

code-quality-manager
  └── manage-docs — general documentation quality; code-repository-manager
                     focuses on publishing to specific deployment targets
```
