# Link & Category Reference

Reference material for the `fix-doc-links` skill. The main workflow is in `../SKILL.md`; this file holds the long-form taxonomy so the skill body stays scannable.

---

## Part 1 — Broken Link Categories

Group every broken link into one of these categories before fixing. Each category has a detection signal, a fix pattern, and a verification check. Examples use placeholder paths — substitute the repo's actual `docs/` root and section names.

### 1. Draft / Excluded Files

**Signal:** The link target exists as a source file but is marked `draft: true` (or an equivalent exclude flag) in frontmatter, so the static-site generator omits it from the build.

**Detect:**
```bash
grep -rn "draft: true" <DOCS_DIR> --include="*.md" --include="*.mdx"
```

**Fix:** If the file is meant to be linkable, set `draft: false`. If it should stay a draft, remove or repoint the link instead. Decide per file — do not blanket-flip drafts.

```yaml
# before
---
slug: my-page
draft: true
---

# after
---
slug: my-page
draft: false
---
```

### 2. Slug Mismatches

**Signal:** A link uses the file's *name* but the page is served at a different `slug` declared in frontmatter.

**Detect:**
```bash
grep -rn "^slug:" <DOCS_DIR> --include="*.md" --include="*.mdx"
```

**Fix:** Point the link at the real slug, not the filename.
```markdown
[Link](/docs/section/filename)        # before
[Link](/docs/section/actual-slug)     # after
```

### 3. Path Structure Issues

**Signal:** A link is missing one or more subdirectory segments in the URL path.

**Fix:** Add the missing segment(s) so the path matches the real directory nesting.
```markdown
[X](/docs/area/components/widget)                 # before — missing a level
[X](/docs/area/components/embedding/widget)       # after
```

### 4. Directory-vs-File References

**Signal:** A link points at a directory that has no index page, instead of a specific file inside it.

**Fix:** Point at the section's index/README page or a concrete child file.
```markdown
[Section](/docs/section/subsection)               # before
[Section](/docs/section/subsection/subsection)    # after (index page)
```

### 5. Directory Renames

**Signal:** Links still reference an old directory name after a folder was renamed/reorganized.

**Detect:** grep for the old name across docs, then map old → new.
```bash
grep -rn "/docs/<OLD_DIR>/" <DOCS_DIR> --include="*.md" --include="*.mdx"
```

**Fix:** Systematic find/replace of every instance, then confirm the new directory exists. Keep a written old→new mapping so the change is auditable.

### 6. Content Migration

**Signal:** Content moved between sections; links still point at the previous location.

**Fix:** Build an old-path → new-path map, update links in batches, and verify the new paths resolve after each batch. This differs from a rename in that the *parent section* changed, not just the folder name.

### 7. Index / README Slug Mismatches

**Signal:** A link uses a directory name, but that directory's index page is served at a slug that differs from the directory name (common when directories carry numeric ordering prefixes like `2-techniques/` but the slug is `techniques`).

**Detect:** Compare frontmatter slugs against generated output paths.
```bash
grep -rn "^slug:" <DOCS_DIR> --include="*.md" --include="*.mdx"
# then inspect the generated output tree (see SKILL.md "Verify" phase)
```

**Fix:** Point links at the *generated* path, not the logical directory path.

### 8. Edge Cases — Resolves on Disk but Reported Broken

**Signal:** The target file exists in build output yet the generator still flags the link.

**Try, in order:**
1. Clear generator cache and build artifacts, then rebuild.
2. Toggle trailing slash on/off in the link.
3. Try a relative path instead of an absolute one.
4. Inspect the generator's route manifest (e.g. a generated routes file) for the actual route.
5. If it genuinely works in a browser but the checker disagrees, document it as a known false positive rather than mangling a working link.

---

## Part 2 — Figma Link → Embed Conversion

When a doc link points at a Figma share URL (`www.figma.com/...` or `figma.com/file/...`), the better representation is an inline embed rather than a plain link.

**Conversion rule:**
1. Replace the host `www.figma.com` with `embed.figma.com`.
2. Append the query parameter `embed-host=share` to the URL.
3. Wrap the result in an iframe.

```jsx
<iframe
  style={{ border: "1px solid rgba(0, 0, 0, 0.1)" }}
  width="100%"
  height="600"
  src="<EMBED_FIGMA_URL>"
  allowFullScreen
/>
```

Only convert where an embed is appropriate (MDX or HTML-capable docs). In plain Markdown that cannot render iframes, leave the link as a corrected hyperlink instead.

---

## Part 3 — Sidebar / Category Metadata Files

Some static-site generators read a per-directory metadata file to control sidebar label, ordering, and grouping (Docusaurus uses `_category_.json`; other tools use `_index.md` frontmatter, `sidebar` entries, etc.). The principles below are generic; swap in whatever file your generator uses.

### Missing-file detection

Every content directory that should appear in the sidebar needs its metadata file. Find directories lacking one:
```bash
find <DOCS_DIR> -type d | while read -r dir; do
  if [ "$(basename "$dir")" != "$(basename "<DOCS_DIR>")" ] && [ ! -f "$dir/_category_.json" ]; then
    echo "Missing category file: $dir"
  fi
done
```

### Structure

```json
{
  "label": "<emoji> <Title Case Label>",
  "position": <integer>
}
```

- **label** — concise, descriptive, title case. Prefix with a single leading emoji for visual scanning *if the project already follows that convention* — match the repo's existing style; do not impose emojis on a project that does not use them.
- **position** — integer ordering among siblings. Use alphabetical ordering with consecutive numbers (1, 2, 3, …) unless the project has an explicit intentional order.

### Drift detection

"Folder drift" = the directory structure changed but metadata files kept stale labels/positions. Audit for it:
```bash
# Dump every category file for review
find <DOCS_DIR> -name "_category_.json" -exec echo "=== {} ===" \; -exec cat {} \;
```

Look for: labels naming a renamed directory, labels missing the project's emoji convention, positions that no longer reflect sibling order, and inconsistent casing.

### Fix process

1. Create missing files first (top-level directories, then nested).
2. Update stale labels to match the *current* directory's purpose, not its old name.
3. Apply the project's existing emoji/label convention consistently across siblings.
4. Reassign `position` so siblings sort sensibly.
5. Validate JSON syntax (a malformed file breaks the build).

---

## Part 4 — Prevention

- **Rename links before renaming directories**, not after. Keep an old→new mapping.
- **Plan content moves**; update links in the same change set.
- **Fix in categorized batches** and rebuild after each batch.
- **Verify slugs vs. directory names** — links must match generated output paths, not logical paths.
- **Audit category files** whenever directories are added, renamed, or reordered.
- **Never delete a link to silence a warning** — repoint it to the correct target.
