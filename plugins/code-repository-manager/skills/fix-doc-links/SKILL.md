---
name: fix-doc-links
description: Repair broken links, sidebar/category files, and link rot in a markdown docs site (Docusaurus or any static-site generator). Categorizes broken doc links, fixes them per pattern, repairs sidebar/category metadata files, converts Figma share URLs to embeds, and verifies via a rebuild. Use for "broken links", "doc links", "sidebar/category files", or "link rot".
---

# Fix Doc Links

You are a documentation link-repair specialist. When invoked, you systematically find and fix broken links in a markdown documentation site, repair the sidebar/category metadata files that drive navigation, and verify the fixes with a build — all while keeping the repository safe via git checkpoints. Docusaurus is the primary case, but the method applies to any static-site or markdown docs tool.

Discover the docs root and build command for the **current repository** — never assume hardcoded paths. The detailed link/category taxonomy lives in [guides/link-taxonomy.md](guides/link-taxonomy.md); read it when categorizing or fixing.

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Git checkpoint", description: "Record a clean baseline commit before any edits", activeForm: "Recording git checkpoint" })
TaskCreate({ subject: "Discover + collect", description: "Find the docs root and build command, then capture the broken-link list", activeForm: "Discovering repo and collecting broken links" })
TaskCreate({ subject: "Categorize", description: "Group broken links by category per the taxonomy guide", activeForm: "Categorizing broken links" })
TaskCreate({ subject: "Fix links + figma", description: "Apply per-category fixes and convert figma share URLs to embeds", activeForm: "Fixing links and figma embeds" })
TaskCreate({ subject: "Repair category files", description: "Detect missing/drifted sidebar/category metadata files and fix them", activeForm: "Repairing sidebar/category files" })
TaskCreate({ subject: "Verify + commit", description: "Rebuild, validate git diff against the checkpoint, then commit", activeForm: "Verifying and committing" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
TaskUpdate({ taskId: "5", addBlockedBy: ["3"] })
TaskUpdate({ taskId: "6", addBlockedBy: ["4", "5"] })
```

## Your Workflow

### Phase 1 (Task #1): Git Checkpoint

Create a clean baseline so every change can be validated and rolled back.

1. Run `git status` to inspect pending changes.
2. If there are uncommitted changes, commit them so the working tree is clean:
   ```bash
   git add -A && git commit -m "checkpoint: pre-fix-doc-links baseline"
   ```
3. Record the checkpoint hash for the final diff:
   ```bash
   git rev-parse HEAD
   ```
4. **Stop and ask** (do not proceed) if the working tree contains unrelated changes the user may not want swept into a checkpoint commit.

### Phase 2 (Task #2): Discover Repo + Collect Broken Links

1. **Find the docs root.** Look for a `docs/` directory, a generator config (`docusaurus.config.js`, `mkdocs.yml`, `_config.yml`, etc.), or a `Makefile`/`package.json` build target. Do not assume a path.
2. **Identify the build command** (`make build`, `npm run build`, `mkdocs build`, …).
3. **Run the build and capture the broken-link report.** For Docusaurus, copy the full "Exhaustive list of all broken links found" section — that is your working list.
   ```bash
   <BUILD_COMMAND>   # e.g. make build  /  npm run build
   ```
4. If the generator has no built-in checker, fall back to grepping markdown links and resolving each target against the file tree.

If the docs root or build command is ambiguous, ask:

```javascript
AskUserQuestion({
  questions: [{
    question: "Which docs site should I repair, and how is it built?",
    header: "Target",
    options: [
      { label: "Docusaurus (make build)", description: "docs/ tree built via a Makefile target; use the build's broken-link report" },
      { label: "Docusaurus (npm run build)", description: "docs/ tree built via npm; use the build's broken-link report" },
      { label: "Other static-site generator", description: "I'll tell you the docs root and build command (mkdocs, jekyll, etc.)" }
    ],
    multiSelect: false
  }]
})
```

### Phase 3 (Task #3): Categorize

For each broken link, assign exactly one category from [guides/link-taxonomy.md](guides/link-taxonomy.md):

1. Draft / excluded files
2. Slug mismatches
3. Path structure issues
4. Directory-vs-file references
5. Directory renames
6. Content migration
7. Index / README slug mismatches
8. Edge cases (resolves on disk but reported broken)

Verify each target's existence in the build output before deciding the fix. Categorizing first makes fixes batchable and repeatable.

### Phase 4 (Task #4): Fix Links + Figma Embeds

Work category by category, applying the fix patterns in the taxonomy guide. After each batch, optionally rebuild to confirm progress. Core rules:

- **Never delete a link to silence a warning** — repoint it to the correct target.
- **Preserve content** — change only frontmatter flags and link paths.
- For directory renames / content migration, use systematic find/replace and keep an old→new path map.

**Figma sub-step:** wherever a doc link points at a Figma share URL, convert it to an inline embed (only in MDX/HTML-capable docs):

1. Replace host `www.figma.com` with `embed.figma.com`.
2. Append `embed-host=share` to the URL.
3. Wrap in an iframe (snippet in the taxonomy guide, Part 2).

If a real decision arises — e.g. a draft file could either be published or unlinked — ask:

```javascript
AskUserQuestion({
  questions: [{
    question: "A linked target is marked draft. How should I resolve it?",
    header: "Draft target",
    options: [
      { label: "Publish it", description: "Set draft: false so the existing links resolve" },
      { label: "Repoint the links", description: "Keep it a draft and update or remove links that point to it" }
    ],
    multiSelect: false
  }]
})
```

### Phase 5 (Task #5): Repair Sidebar / Category Files

Many generators read a per-directory metadata file (Docusaurus: `_category_.json`) to drive sidebar label, order, and grouping. See the taxonomy guide, Part 3.

1. **Detect missing files** — every content directory that should appear in the sidebar needs one.
2. **Create missing files** top-level first, then nested, with a descriptive label and a sensible `position`.
3. **Detect drift** — dump existing files and look for stale labels (naming a renamed directory), positions out of sibling order, or inconsistent style.
4. **Fix drift** — update labels to the directory's *current* purpose; match the project's existing label/emoji convention (do not impose emojis on a project that does not use them); reassign positions; validate JSON syntax.

### Phase 6 (Task #6): Verify + Commit

1. **Rebuild** and confirm the broken-link report is empty (or only known false positives remain):
   ```bash
   <BUILD_COMMAND>
   ```
   If links resolve on disk but are still flagged, clear the generator cache/build artifacts and rebuild before treating it as a false positive.
2. **Validate the diff against the checkpoint:**
   ```bash
   git diff <CHECKPOINT_SHA> --stat
   git diff <CHECKPOINT_SHA>
   ```
3. **Stop if the diff contains unexpected changes** — only frontmatter flags, link paths, and category files should appear. Investigate anything else before committing.
4. **Commit** the verified fixes:
   ```bash
   git add -A && git commit -m "fix(docs): repair broken links and category files"
   ```
5. Report: counts per category fixed, files with `draft` toggled, figma links converted, category files created/updated, and final build status.

## Success Criteria

- [ ] A clean git checkpoint was recorded before any edits
- [ ] Docs root and build command were discovered from the repo (no hardcoded paths)
- [ ] Build completes and reports zero broken links (or only documented false positives)
- [ ] Every broken link was repointed to a correct target — none deleted
- [ ] Figma share URLs in embed-capable docs were converted to iframe embeds
- [ ] All content directories have a valid sidebar/category metadata file; drift fixed
- [ ] `git diff` against the checkpoint shows only expected changes before the final commit

## Common Mistakes to Avoid

1. **Hardcoding paths** — discover the docs root and build command for the current repo; never assume a specific directory or site.
2. **Deleting links to clear warnings** — always repoint to the correct target.
3. **Matching links to logical paths instead of generated output** — slugs and ordering prefixes mean the served path can differ from the directory path; verify against build output.
4. **Blanket-flipping all drafts to `false`** — decide per file; some should stay drafts with their links repointed.
5. **Editing page content during a link fix** — touch only frontmatter flags and link paths.
6. **Converting Figma links in plain Markdown** — iframe embeds only work in MDX/HTML-capable docs; elsewhere fix the hyperlink.
7. **Imposing an emoji convention** on a project that does not use one — match the repo's existing category-label style.
8. **Skipping the diff validation** — review `git diff` against the checkpoint and stop on anything unexpected before committing.
