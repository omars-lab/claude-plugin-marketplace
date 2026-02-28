---
name: update-docs
description: Publish co-design documents to both the GitHub Enterprise wiki and GitHub Pages. Copies co-design files, rebuilds navigation, commits, and optionally pushes. Use when co-design docs have been added or updated.
---

# Update Docs

Publish co-design documents from the `docs` repo to two targets:

1. **GitHub Enterprise Wiki** — `docs.wiki` sibling repo (flat structure, sidebar navigation)
2. **GitHub Pages** — `gh-pages` branch with Jekyll (browsable site with index)

Both targets get the same co-design content. Use Makefile targets for the mechanical work.

## Deployment Targets

### Wiki

- **Live**: `https://code.devsnc.com/omar-eid/docs/wiki`
- **Repo**: `git@code.devsnc.com:omar-eid/docs.wiki.git` (sibling folder `../docs.wiki`)
- **Structure**: Flat — all pages at wiki repo root (GitHub wiki limitation)
- **Page URL**: `https://code.devsnc.com/omar-eid/docs/wiki/<page-name>`

### GitHub Pages

- **Live**: `https://code.devsnc.com/pages/omar-eid/docs/` (GitHub Enterprise Pages URL)
- **Branch**: `gh-pages` (orphan branch, separate from `main`)
- **Structure**: Flat — Jekyll serves markdown files from root
- **Page URL**: `https://code.devsnc.com/pages/omar-eid/docs/<page-name>`

## Source Scope

**Co-designs only.** Source directory: `architecture/co-designs/`

Files synced:
- `CO-DESIGN-*.md` — all co-design documents (HLD, summary, v1 archives)
- `diagrams/` — image assets referenced by co-design docs (copied to both targets)

Files NOT synced: `architecture/reverse-engineering/`, `scripts/`, `Makefile`, skills, etc.

## Makefile Targets

All sync operations are driven by Makefile targets. The skill orchestrates when to run them.

| Target | What It Does |
|--------|-------------|
| `make sync-wiki` | Copies co-design files to `../docs.wiki/`, rebuilds `Home.md` + `_Sidebar.md`, stages changes |
| `make sync-pages` | Copies co-design files to `gh-pages` branch (via worktree), rebuilds `index.md`, stages changes |
| `make sync-docs` | Runs both `sync-wiki` and `sync-pages` |
| `make push-wiki` | Commits + pushes wiki changes |
| `make push-pages` | Commits + pushes gh-pages changes |
| `make push-docs` | Commits + pushes both targets |

## Workflow

### Phase 1 — Determine Scope

Use `AskUserQuestion`:

**What do you want to publish?**
1. "All co-designs" — sync everything under `architecture/co-designs/`
2. "A specific file" — user provides the path

**Where?**
1. "Both wiki and pages" (Recommended)
2. "Wiki only"
3. "Pages only"

**Push to remote?**
1. "Yes — commit and push"
2. "No — commit only (I'll push manually)"

### Phase 2 — Sync

Run the appropriate Makefile target:

```bash
# Both targets
make sync-docs

# Or individually
make sync-wiki
make sync-pages
```

Review the output. The scripts will show:
- Files discovered and copied
- Navigation files rebuilt
- Any warnings (missing wiki repo, no gh-pages branch yet — scripts handle first-time setup)

### Phase 3 — Review Changes

Show the user what changed in each target:

**Wiki:**
```bash
cd ../docs.wiki && git status && git diff --stat
```

**Pages** (the sync-pages script prints a diff summary from the worktree).

### Phase 4 — Commit and Push

Run the push targets based on the user's Phase 1 choice:

```bash
# Both targets
make push-docs

# Or individually
make push-wiki
make push-pages
```

### Phase 5 — Report

Present a summary with live URLs:

```
Docs published

  Co-designs synced:  N files
  Targets:            Wiki ✓  |  Pages ✓

  Wiki:
    Home: https://code.devsnc.com/omar-eid/docs/wiki
    - https://code.devsnc.com/omar-eid/docs/wiki/CO-DESIGN-0001-implementation-agents-hld
    - https://code.devsnc.com/omar-eid/docs/wiki/CO-DESIGN-0001-implementation-agents-summary
    ...

  Pages:
    Home: https://code.devsnc.com/pages/omar-eid/docs/
    - https://code.devsnc.com/pages/omar-eid/docs/CO-DESIGN-0001-implementation-agents-hld
    - https://code.devsnc.com/pages/omar-eid/docs/CO-DESIGN-0001-implementation-agents-summary
    ...
```

## Edge Cases

| Situation | Handling |
|-----------|----------|
| Wiki repo doesn't exist | Script errors: "Run `git clone git@code.devsnc.com:omar-eid/docs.wiki.git ../docs.wiki` first" |
| No `gh-pages` branch yet | `sync-pages` creates it as an orphan branch automatically |
| File has no H1 heading | Use filename (title-cased, hyphens→spaces) as fallback title |
| Wiki has uncommitted changes | Script warns, asks to stash or abort |
| Push fails (auth, network) | Report error, remind user to push manually |
| No co-design files found | Warn and exit |
| Diagrams directory exists | Copied to both targets alongside markdown files |

## Wiki-Specific Details

**GitHub wikis are flat.** All `.md` files must be at the wiki repo root — no subdirectories. The sync script flattens `architecture/co-designs/CO-DESIGN-0001-foo.md` → `CO-DESIGN-0001-foo.md` at root.

**Home.md structure:**
```markdown
# Co-Design Documents

Last synced: YYYY-MM-DD

| Document | Description |
|----------|-------------|
| [Implementation Agents — HLD (v2)](CO-DESIGN-0001-implementation-agents-hld) | ... |
| [Implementation Agents — Summary](CO-DESIGN-0001-implementation-agents-summary) | ... |
```

**_Sidebar.md structure:**
```markdown
**Co-Designs**
- [HLD (v2)](CO-DESIGN-0001-implementation-agents-hld)
- [HLD (v1)](CO-DESIGN-0001-implementation-agents-hld-v1)
- [Summary](CO-DESIGN-0001-implementation-agents-summary)

---
[Home](Home)
```

## Pages-Specific Details

### Architecture

The `gh-pages` branch contains:
- `_config.yml` — Jekyll config (Cayman theme, optional-front-matter plugin)
- `_layouts/default.html` — Custom layout overriding Cayman's default (styled tables, Mermaid JS, custom CSS)
- `index.md` — Auto-generated landing page (grouped by CO-DESIGN number, hardcoded titles/descriptions)
- `CO-DESIGN-*.md` — The co-design documents themselves
- `diagrams/` — Image assets

### Index Generation

The sync script generates `index.md` by:
1. Grouping files by `CO-DESIGN-NNNN` prefix
2. Using **hardcoded titles and descriptions** per filename suffix (`-summary`, `-hld`, `-hld-v1`) — NOT extracted from file content
3. This avoids the problem of raw markdown (links, bold, reference-style syntax) breaking table rendering in Jekyll

When adding a new co-design, add a new `case` entry to `scripts/sync-pages.sh` and `scripts/sync-wiki.sh` for its suffix pattern.

### Mermaid Rendering

GitHub wiki renders Mermaid natively. GitHub Pages (Jekyll) does **not** — it requires client-side JavaScript.

The custom layout at `_layouts/default.html` handles this:
1. After page load, finds all `<pre><code class="language-mermaid">` blocks (how Jekyll renders ` ```mermaid `)
2. Replaces each with a `<div class="mermaid">` element
3. Loads `mermaid.min.js` from CDN (only if mermaid blocks exist)
4. Mermaid initializes and renders diagrams client-side

### Updating the Frontend (Layout, CSS, Theme)

When the Pages site needs visual improvements, the changes go to `_layouts/default.html` on the `gh-pages` branch — NOT the sync scripts or main branch.

**Workflow:**
1. Set up the worktree: `git worktree add .gh-pages-worktree gh-pages`
2. Edit `.gh-pages-worktree/_layouts/default.html` — this is the single file that controls all styling
3. Key sections in the layout:
   - `<style>` block — all custom CSS (table styles, colors, spacing, mermaid container, etc.)
   - `<header class="page-header">` — site header with title and tagline
   - `<main class="main-content">` — where Jekyll injects the rendered markdown
   - `<script>` block — Mermaid JS initialization
4. Preview locally (optional): `cd .gh-pages-worktree && bundle exec jekyll serve`
5. Commit and push: `cd .gh-pages-worktree && git add -A && git commit -m "..." && git push origin gh-pages`
6. Clean up: `git worktree remove .gh-pages-worktree`

**What NOT to do:**
- Don't edit `_config.yml` to change themes — Cayman is overridden by our custom layout
- Don't add `assets/css/` files — all CSS lives in the `<style>` block in the layout
- Don't modify the Mermaid script block unless upgrading the CDN version

**Common changes:**
- Table styling → `.main-content table` selectors in the `<style>` block
- Header colors → `.page-header` background gradient
- Mermaid container → `.mermaid` selector
- Strikethrough appearance → `.main-content del` selector
- Blockquote callouts → `.main-content blockquote` selector

### Scripts

Both sync scripts use **zsh** (not bash) because macOS ships bash 3.2 which lacks `mapfile` and associative arrays. The Makefile also uses `SHELL := /bin/zsh`.

## Notes

- Wiki links omit the `.md` extension — the wiki resolves them automatically.
- Mermaid diagrams render natively on GitHub wikis but need JS on Pages (handled by custom layout).
- Do NOT modify source `.md` files during sync — the skill only writes to targets.
- The skill only writes to `docs.wiki/` and `gh-pages` branch — never to `main` branch content.
- Scripts use hardcoded titles/descriptions — when adding new co-designs, update the `case` blocks in both sync scripts.
