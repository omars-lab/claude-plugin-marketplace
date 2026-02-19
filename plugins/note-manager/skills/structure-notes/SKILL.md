# Structure Notes

Transform unstructured notes into professional, scannable documentation following proven principles.

## Core Philosophy

Documentation should be **findable, scannable, complete, accurate, and non-duplicative**. Every piece of information lives in exactly ONE place.

---

## Critical Rules

When structuring notes, follow these principles:

1. **Single source of truth** - Each fact in ONE place, link from others
2. **Progressive disclosure** - Start simple (overview) → link to details
3. **Scannable format** - Headers, bullets, tables, code examples (minimal prose)
4. **Show don't tell** - `command --flag` > "The command can be used to..."
5. **Max readability** - 300 lines per file, 150 for main overview
6. **No duplication** - Link instead of copy

---

## Document Structure Approach

### Question-Focused Sections

**Every section should answer specific questions.**

Instead of generic headers like "Introduction" or "Features", use:
- "What problem does this solve?"
- "How do I get started?"
- "When should I use this?"
- "Where does each type of content belong?"

Add **Essential Questions** at the start of each section:
```markdown
## How do I configure X?

**Essential Questions:**
- What are the configuration options?
- Where is the config file?
- When do I need to restart?
```

### Standard Document Types

| Document Type | Purpose | Max Lines | Contents | Style |
|---------------|---------|-----------|----------|-------|
| **README** | Project overview | 150 | What/why/quick start/links | Ultra-concise |
| **QUICKSTART** | Get running fast | 100 | Prerequisites/install/first steps | Step-by-step |
| **GUIDE** | Complete user guide | 300 | Features/workflows/examples | Task-organized |
| **REFERENCE** | Quick lookup | 200 | Commands/options/config tables | Tables, alphabetical |
| **TROUBLESHOOTING** | Problem solving | 200 | Common issues/fixes | Problem → Solution |
| **ARCHITECTURE** | Technical design | 300 | System design/patterns | Diagrams, concise |

---

## Your Workflow

When the user asks you to structure notes, follow this process:

### Phase 1: Audit Current State

1. **Analyze the raw notes**:
   - What topics are covered?
   - Are there duplicated concepts?
   - What's the intended audience?
   - What format is it currently in?

2. **Identify document types needed**:
   - Single concept? → One document
   - Multiple features? → README + GUIDE + REFERENCE
   - Tutorial content? → QUICKSTART
   - Problems discussed? → TROUBLESHOOTING section

3. **Check line counts** if existing docs:
   ```bash
   wc -l *.md
   ```
   Flag anything > 300 lines for splitting.

### Phase 2: Create Structure

1. **Define clear sections** based on questions the content answers

2. **Use this template for each section**:
   ```markdown
   ## [Question-focused header]

   **Essential Questions:**
   - Question 1?
   - Question 2?
   - Question 3?

   [Concise content with examples]
   ```

3. **Apply formatting rules**:
   - **Headers**: Every 50-100 lines for easy navigation
   - **Bullets**: For lists and feature descriptions
   - **Tables**: For comparisons, options, commands
   - **Code blocks**: For all examples with comments
   - **Links**: Cross-reference instead of duplicating

### Phase 3: Eliminate Duplication

1. **Find repeated content**:
   - Search for same concept explained multiple times
   - Look for redundant examples
   - Identify overlapping sections

2. **Choose single source**:
   - Pick the best location for each concept
   - Remove duplicates
   - Add links from other locations

3. **Example pattern**:
   ```markdown
   # GUIDE.md
   ## Installation
   [Complete installation steps]

   # QUICKSTART.md
   ## Installation
   See [complete installation guide](GUIDE.md#installation).
   For quick start: `npm install && npm start`
   ```

### Phase 4: Enhance Scannability

1. **Add visual structure**:
   - Use **bold** for key terms
   - Use `code` for commands/values
   - Use > blockquotes for important notes
   - Use --- for section breaks
   - Use tables for comparisons

2. **Ensure every concept has an example**:
   ```markdown
   ❌ Bad: "The search command filters results by keyword"

   ✅ Good:
   \```bash
   search --query authentication  # Find all auth-related items
   \```
   ```

3. **Keep prose minimal**:
   - Target 50% fewer words
   - One idea per sentence
   - Max 3 lines per paragraph

### Phase 5: Validate

Check the structured documentation:

- [ ] **No duplication** - Each fact in ONE place
- [ ] **Scannable** - Can find info in < 30 seconds
- [ ] **Question-focused** - Clear what each section answers
- [ ] **Examples present** - Every command/concept has one
- [ ] **Line counts** - All files < 300 lines (< 150 for README)
- [ ] **Links valid** - All cross-references work
- [ ] **Consistent style** - Same formatting throughout

---

## Specific Scenarios

### Scenario: Raw Meeting Notes

**Input**: Unstructured bullet points from a meeting

**Output Structure**:
```markdown
# [Meeting Topic] - YYYY-MM-DD

## Summary
[2-3 sentences: what was decided/discussed]

## Key Decisions
- Decision 1 and rationale
- Decision 2 and rationale

## Action Items
| Who | What | When |
|-----|------|------|
| Name | Task | Date |

## Discussion Points

### [Topic 1]
- Point A
- Point B

### [Topic 2]
- Point C
- Point D

## Related
- [Link to related doc]
- [Link to follow-up issue]
```

### Scenario: Technical Notes

**Input**: Dense technical documentation with duplicated explanations

**Approach**:
1. Split into: README (overview) + ARCHITECTURE (design) + REFERENCE (API)
2. Identify duplicated concepts (e.g., authentication flow explained 3 times)
3. Choose single source (ARCHITECTURE.md for detailed flow)
4. Replace duplicates with links
5. Add question-focused headers
6. Add Essential Questions to each section
7. Convert dense paragraphs to bullets and tables

### Scenario: Project Documentation

**Input**: Multiple markdown files with overlapping content

**Approach**:
1. Audit what exists: `wc -l docs/*.md`
2. Map content to document types (see table above)
3. Create missing documents (e.g., no QUICKSTART exists)
4. Move content to appropriate files
5. Eliminate duplication via linking
6. Add navigation/TOC to README
7. Ensure each file < 300 lines

---

## Writing Style Rules

### Conciseness
- **50% fewer words** than first draft
- **One idea per sentence**
- **3 lines max per paragraph**

### Active Voice
❌ "The command can be used to search"
✅ "Use this command to search"

### Examples Always
```markdown
## Search Command

**What it does**: Filters items by keyword

**Example**:
\```bash
search --query auth --limit 10
\```

**When to use**: Finding specific items quickly
```

### Links Not Duplication
```markdown
❌ Bad: Copy entire section to multiple files

✅ Good:
# In overview.md
For authentication details, see [authentication.md](authentication.md)

# In authentication.md
[Complete authentication documentation]
```

---

## Common Mistakes to Avoid

1. **Duplicating content** → Link instead
2. **Dense paragraphs** → Use bullets/headers
3. **Missing examples** → Add one for every concept
4. **Generic headers** → Use question-focused headers
5. **Too many words** → Cut by 50%
6. **No structure** → Add headers every 50-100 lines
7. **Files too long** → Split at 300 lines

---

## Output Format

When you finish structuring notes, provide:

1. **Summary of changes**:
   - What structure was applied
   - How many files created/modified
   - What was eliminated (duplication)

2. **Document map**:
   ```
   README.md (120 lines) - Project overview
   docs/
   ├── QUICKSTART.md (95 lines) - Setup guide
   ├── GUIDE.md (280 lines) - Complete guide
   └── REFERENCE.md (150 lines) - Command reference
   ```

3. **Next steps** (if any):
   - Files still over 300 lines that need splitting
   - Sections that need more examples
   - Areas that could use diagrams

---

## Integration with Version Control

If the notes are in a git repository:

1. **Before structuring**:
   ```bash
   git status
   # Commit any existing changes first
   git add -A && git commit -m "Pre-structure snapshot"
   ```

2. **After structuring**:
   ```bash
   git add docs/
   git commit -m "docs: restructure notes for clarity and scannability"
   ```

---

## Success Criteria

Well-structured documentation is:
- ✅ **Findable** - Users locate info in < 30 seconds
- ✅ **Scannable** - Headers, bullets, tables throughout
- ✅ **Complete** - Every concept has examples
- ✅ **Accurate** - Reflects current state
- ✅ **Non-duplicative** - Single source of truth
- ✅ **Readable** - 5-minute read max per file

---

## Quick Reference

**For the AI using this skill:**

```
1. Audit → Analyze structure, identify doc types needed, check line counts
2. Structure → Create question-focused sections with Essential Questions
3. Eliminate → Find and remove duplication, add cross-references
4. Enhance → Add tables/bullets/examples, reduce prose by 50%
5. Validate → Check duplication, scannability, examples, line counts
6. Output → Summary + document map + next steps
```

**Remember:**
- Every section answers specific questions
- Every concept has an example
- Every file < 300 lines (< 150 for README)
- Link don't duplicate
- Show don't tell
