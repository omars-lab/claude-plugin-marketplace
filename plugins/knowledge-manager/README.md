# Knowledge Manager Plugin

Transform unstructured markdown notes into structured, navigable knowledge bases combining Zettelkasten-style atomic notes with organized decision records, patterns, and glossaries.

## What This Plugin Does

Extracts the essence of scattered notes and organizes them into a queryable knowledge base:

- **Atomic notes** - One concept per file, max 150 lines, interlinked with `[[wiki-links]]`
- **Decision records** - ADR-style records capturing rationale and alternatives
- **Patterns** - Recurring approaches with problem/solution/examples
- **Visual maps** - Mermaid diagrams showing relationships between knowledge atoms
- **Cited answers** - Query the knowledge base and get answers traced back to sources

## Skills Included

### extract-knowledge

**Usage:** `/knowledge-manager:extract-knowledge`

The core skill. Reads markdown files and produces a structured `_knowledge/` directory.

**What it does:**
1. Discovers and catalogs input markdown files
2. Analyzes content in 4 passes (atoms, relationships, themes, audiences + key questions)
3. Generates concepts, decisions, patterns, glossary, audience guide, index, and relationship map
4. Validates cross-links and completeness
5. Presents summary with gap analysis

**Depth options:**
- **Quick**: Concepts + index only
- **Standard**: Full extraction (all artifact types)
- **Deep**: Full + reading paths + cluster analysis

**Output structure:**
```
_knowledge/
  _index.md          # Master overview with tables
  _map.md            # Mermaid relationship diagram
  _audiences.md      # Inferred audiences with key questions per audience
  concepts/          # Atomic notes (one per file)
  decisions/         # ADR-style records
  patterns/          # Problem/solution files
  glossary.md        # Key terms table
```

### knowledge-map

**Usage:** `/knowledge-manager:knowledge-map`

Visualize relationships in a knowledge base or raw notes.

**What it does:**
1. Analyzes relationships and identifies clusters
2. Generates Mermaid diagrams (overview, mindmap, dependency chains, cluster details)
3. Builds navigation aids: thematic index, learning paths, density report, gap analysis

**Diagram conventions:**
- Rectangles = Concepts
- Diamonds = Decisions
- Rounded rectangles = Patterns
- Max 20 nodes per diagram (splits into sub-diagrams for larger bases)

### knowledge-query

**Usage:** `/knowledge-manager:knowledge-query`

Ask questions and get cited answers from a knowledge base.

**Query types:**

| Type | Example | Answer Format |
|------|---------|---------------|
| Factual | "What is X?" | Definition + details |
| Rationale | "Why did we choose X?" | Decision + rationale + alternatives |
| Pattern | "How do we handle X?" | Problem + solution |
| Comparison | "X vs Y?" | Side-by-side table |
| Synthesis | "Our approach to X?" | Multi-source narrative |
| Gap | "Do we have guidance on X?" | Coverage assessment |

Every claim cited with `[source: [[filename]]]`. Honest about gaps.

### organize-by-questions

**Usage:** `/knowledge-manager:organize-by-questions`

Reorganize a document (or set of related documents) under key-question headers — without modifying the content itself.

**What it does:**
1. Reads input files and inventories every content block (paragraphs, bullets, code blocks, tables)
2. Identifies the key question each block answers ("What is X?", "How do I Y?", "Why was Z chosen?")
3. Presents the proposed question structure for confirmation
4. Reorganizes all content under question headers, preserving every block verbatim
5. Adds cross-references when content is relevant to multiple questions

**Key constraint**: Content is **moved, not modified**. Paragraphs, bullets, code blocks, and tables are preserved exactly as written. Only the section headers change.

**Use when:**
- A document has good content but poor organization
- Notes from multiple related sources need merging into one navigable document
- Existing section headers are topic-based ("Authentication") and you want question-based ("How does authentication work?")

## Common Workflows

### Full extraction workflow
```
1. /knowledge-manager:extract-knowledge    # Extract from notes
2. /knowledge-manager:knowledge-map        # Visualize relationships
3. /knowledge-manager:knowledge-query      # Ask questions
```

### Quick exploration
```
1. /knowledge-manager:knowledge-map        # Map raw notes directly
2. /knowledge-manager:extract-knowledge    # Then extract if the map looks useful
```

### Reorganize a messy document
```
1. /knowledge-manager:organize-by-questions  # Restructure under question headers
   # Content stays verbatim, only headers change
```

### Merge related notes, then extract
```
1. /knowledge-manager:organize-by-questions  # Merge scattered notes into one organized doc
2. /knowledge-manager:extract-knowledge      # Extract atomic knowledge from the organized doc
```

### Knowledge Q&A
```
1. /knowledge-manager:knowledge-query      # Query existing knowledge base
   "What is our approach to authentication?"
   "Why did we choose PostgreSQL?"
   "Do we have guidance on error handling?"
```

## Knowledge Base Structure Reference

| Directory | Contains | File Pattern | Max Lines |
|-----------|----------|-------------|-----------|
| `concepts/` | Atomic notes | `concept-name.md` | 150 |
| `decisions/` | Decision records | `decision-name.md` | No limit |
| `patterns/` | Recurring approaches | `pattern-name.md` | No limit |
| `_index.md` | Master overview | Single file | No limit |
| `_map.md` | Relationship diagram | Single file | No limit |
| `_audiences.md` | Audiences + key questions | Single file | No limit |
| `glossary.md` | Key terms table | Single file | No limit |

## Cross-Linking

Uses `[[wiki-link]]` notation throughout, compatible with:
- NotePlan
- Obsidian
- Most modern markdown tools

Links use filename without extension: `[[concept-name]]` links to `concepts/concept-name.md`.

## Design Principles

- **Hybrid Zettelkasten + ADR**: Atomic notes for concepts, structured records for decisions and patterns
- **150-line limit**: Forces truly atomic notes — if it's longer, it's multiple concepts
- **Source attribution**: Every atom links back to the original source file
- **Honest gaps**: Flags areas where source material is thin rather than inventing knowledge
- **Mermaid diagrams**: Renders natively in markdown viewers, no external tooling needed

## Installation

```bash
# Via the discover plugin
"Install the knowledge-manager plugin"

# Or manually
cp -r knowledge-manager ~/.claude/plugins/
```

## Related Plugins

- **documentation-manager** - For structuring general documentation
- **noteplan-manager** - For managing NotePlan notes directly

## License

MIT License - see [LICENSE](../../LICENSE) for details

## Author

Omar Eid (omar.eid@servicenow.com)

---

**Quick Start**: Say "extract knowledge from my notes in `<path>`" and the AI will walk you through the full extraction process.
