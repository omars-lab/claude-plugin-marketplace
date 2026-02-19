---
name: clean-inkling-ebook
description: Clean up markdown files exported from Inkling ebooks by removing HTML conversion artifacts, duplicate titles, URL metadata blocks, excessive indentation, and normalizing formatting. Use when processing Inkling ebook exports or cleaning up converted training materials.
---

# Clean Inkling Ebook Exports

You are a markdown formatting specialist. When this skill is invoked, clean up markdown files that were exported from Inkling ebooks, removing HTML/Inkling conversion artifacts and normalizing formatting while preserving all content and semantic meaning.

## What to Do

1. **Analyze the directory structure** provided by the user
2. **Identify file types**:
   - Concept files (usually in `concepts/` directories)
   - Lab files (usually in `labs/` directories)
   - README files (verify only, typically already clean)
3. **Apply transformations** systematically
4. **Commit changes** in organized batches
5. **Provide summary** of what was cleaned

## Common Inkling Export Issues

### Concept Files (100% affected in typical exports)
1. **Duplicate titles** - Title appears on line 1 and line 7
2. **URL metadata blocks** - Lines 3-5 contain Inkling URL and separator
3. **8-space leading indentation** - All content has excessive base indentation
4. **Excessive blank lines** - 2-3+ consecutive blank lines throughout
5. **Paragraph line breaks** - Sentences unnecessarily split across lines
6. **HTML whitespace artifacts** - Empty nested indentation blocks

### Lab Files (100% affected in typical exports)
1. **Duplicate titles with variations** - Title on lines 1, 7-8
2. **12-18 indented blank lines** - After horizontal rule, before content
3. **URL metadata blocks** - Same as concept files
4. **Time format variations** - "25–30 Minutes" vs "25-30 minutes" (inconsistent)
5. **Nested list indentation** - Mixed tabs/spaces
6. **Field specification formatting** - "Field: value" vs "Field | value" (inconsistent)

## Transformation Rules

### For ALL Files (Concepts & Labs)

**1. Remove duplicate title:**
- Keep the H1 title on line 1
- Remove the duplicate H1 on line 7 (after URL metadata block)

**2. Remove URL metadata block:**
- Remove line 3: `**URL:** https://...`
- Remove line 4: blank line
- Remove line 5: `---` separator
- Remove line 6: blank line

**3. Remove excessive indented blank lines:**
- Remove lines containing only whitespace (especially 8-22 spaces)

**4. Remove leading indentation:**
- Strip 8 spaces (or detected base indentation) from beginning of content lines
- Preserve list indentation structure (relative nesting)
- Preserve code blocks exactly as-is

**5. Normalize blank lines:**
- Replace 2+ consecutive blank lines with exactly 1 blank line
- Ensure sections are separated by single blank line

**6. Join paragraph lines intelligently:**
- Join lines within paragraphs when safe:
  - Current line doesn't end with: `.` `!` `?` `:` `;` `---`
  - Next line doesn't start with: `#` `-` `*` `1.` (list markers)
  - Next line doesn't have more indentation (continuation)
- Don't join across code blocks (between ``` markers)
- Don't join across blank lines
- Don't join navigation paths (e.g., "All > Menu > Item")
- Don't join URLs that span lines

### For LAB Files Only

**7. Normalize time format:**
- Convert all variations to standard: "XX-XX minutes" (lowercase, regular dash)
- Examples:
  - "25–30 Minutes" → "25-30 minutes"
  - "10–15 Minutes" → "10-15 minutes"
  - "60-90 Minutes" → "60-90 minutes"

**8. Fix nested list indentation:**
- Convert tabs to 4 spaces
- Ensure nested lists use 4-space increments consistently
- Maintain proper list nesting hierarchy

**9. Normalize field formatting:**
- Standardize to "Field: value" format
- Convert "Field | value" → "Field: value"
- Ensure consistent spacing around colons

## Formats to Preserve

**CRITICAL: Do not modify these formats:**

1. **Code blocks** - Skip all transformations between ``` markers
2. **Lists** - Maintain proper nesting (4-space increments)
3. **Bold text** - Preserve `**emphasis**` markers
4. **Navigation paths** - Keep "All > Menu > Item" on one line
5. **URLs** - Don't break across lines
6. **Tables** - Preserve table syntax exactly (pipes, alignment)
7. **Blockquotes** - Preserve intentional indented emphasis sections
8. **Inline code** - Preserve \`code\` markers

## Implementation Approach

### Recommended: Parallel Sub-Agents

Use multiple Bash sub-agents in parallel to process different modules simultaneously:

```
1. Create feature branch: git checkout -b feature/markdown-formatting-cleanup
2. Spawn parallel agents (one per module or grouped modules)
3. Each agent processes files and commits separately
4. Merge back to main when complete
```

### Per-Module Workflow

For each module:

1. **Find files:**
   ```bash
   find module-XX-*/concepts -name "*.md" | sort
   find module-XX-*/labs -name "*.md" | sort
   ```

2. **Process each file:**
   - Read file content
   - Apply transformations in order (1-9)
   - Write cleaned content back

3. **Commit separately by type:**
   ```bash
   git add module-XX-*/concepts/*.md
   git commit -m "Clean up formatting for module XX concept files"

   git add module-XX-*/labs/*.md
   git commit -m "Clean up formatting for module XX lab files"
   ```

4. **Verify changes:**
   ```bash
   git diff HEAD~1 --stat
   git diff HEAD~1 <sample-file>
   ```

## Conservative Logic

### Paragraph Joining (Rule 6)
Only join lines if ALL conditions are met:
- Line doesn't end with sentence-ending punctuation (. ! ? :)
- Next line doesn't start with list marker (- * 1. #)
- Not inside code block
- Not separated by blank line
- Next line has same or less indentation

### Indentation Removal (Rule 4)
- Detect the base indentation level (usually 8 spaces)
- Remove only the base indentation
- Preserve relative indentation for nested lists
- Example: If base is 8 spaces:
  - "        Item" → "Item" (remove 8)
  - "            Nested" → "    Nested" (remove 8, keep 4 relative)

### Blank Line Normalization (Rule 5)
- Keep at least 1 blank line between sections
- Reduce 2+ consecutive blank lines to exactly 1
- Don't remove blank lines that separate content

## Validation Strategy

### Automated Checks (Per File)
- Character count delta: Flag if >25% reduction
- Line count delta: Flag if >35% reduction
- Header count: Verify same number of `#` headers
- List marker count: Verify list markers still present
- Code block count: Verify ``` markers still balanced

### Manual Verification
**Per-Module:**
- Visual diff of 2-3 sample files
- Spot-check 1-2 files with full read

**Final:**
- Review git log and commit messages
- Verify README files intact (should need no changes)
- Check overall stats with `git diff main --stat`
- Read 5-10 randomly selected files completely

## Success Criteria

### Must-Have (Blocking)
- ✅ All files processed without errors
- ✅ No content loss (verified by spot-checks)
- ✅ All technical instructions remain accurate
- ✅ Lists, headers, code blocks preserved
- ✅ Git history clean and traceable
- ✅ No file >25% character reduction without manual verification

### Should-Have
- ✅ Average line reduction of 15-30%
- ✅ <5 files flagged for manual review
- ✅ All commits clean and well-documented
- ✅ Consistent formatting across all files

## Output Structure

When complete, provide:

1. **Statistics summary:**
   - Total files processed (concepts + labs + verified READMEs)
   - Total commits created
   - Net line reduction
   - Files flagged for review (if any)

2. **Module-by-module breakdown:**
   - Number of files per module
   - Line changes per module
   - Commit references

3. **Verification results:**
   - README files status
   - Any issues encountered
   - Files that needed manual review

4. **Next steps:**
   - How to merge to main
   - How to view diffs
   - How to push to remote

## Example Usage

### Single Module
```
/note-manager:clean-inkling-ebook /path/to/ebook/module-01-*/
```

### Entire Ebook
```
/note-manager:clean-inkling-ebook /path/to/ebook/
```

### With Specific File Pattern
```
/note-manager:clean-inkling-ebook /path/to/ebook/ --pattern "*/concepts/*.md"
```

## Quality Checklist

Before marking complete, verify:

- [ ] All duplicate titles removed
- [ ] All URL metadata blocks removed
- [ ] All excessive indentation removed
- [ ] All blank lines normalized
- [ ] Paragraphs joined where appropriate
- [ ] Lab time formats standardized
- [ ] Lab field formatting standardized
- [ ] Code blocks untouched
- [ ] Lists properly formatted
- [ ] Tables preserved
- [ ] All commits created and documented
- [ ] No merge conflicts
- [ ] Visual diff spot-checks passed
- [ ] README files verified

## Instructions

When this skill is invoked:

1. **Ask for directory path** if not provided
2. **Analyze structure** to identify file organization
3. **Create feature branch** for isolation
4. **Process files** using parallel sub-agents when possible
5. **Commit systematically** by module and file type
6. **Verify results** with spot-checks
7. **Provide detailed summary** with statistics
8. **Offer next steps** (merge, push, etc.)

Be thorough, preserve all content, and ensure the markdown is clean, readable, and properly formatted.
