# Note Manager Plugin

Manage and analyze notes, training materials, and documentation - structure notes, analyze transcripts, clean ebook exports, and generate reference guides.

## Skills Included

### structure-notes

Transform unstructured notes into professional, scannable documentation.

**Use when:**
- "Structure these meeting notes"
- "Organize this documentation"
- "Clean up these notes following best practices"
- "Remove duplication from these docs"

**What it does:**
1. Analyzes current structure and identifies document types needed
2. Creates question-focused sections with Essential Questions
3. Eliminates duplication by choosing single source of truth
4. Enhances scannability with tables, bullets, examples
5. Validates against best practices (no duplication, < 300 lines, etc.)
6. Provides document map and next steps

### analyze-training-transcripts

Analyze training course transcripts and generate comprehensive one-page quick reference guides with diagrams, decision tables, use cases, and best practices.

**Use when:**
- Analyzing training materials or course transcripts
- Generating quick reference guides from learning content
- Creating PlantUML architecture and class diagrams from training content

### training-faq

Interactive FAQ for training materials. Searches FAQ first, falls back to transcript analysis, and auto-updates the FAQ with new Q&A pairs.

**Use when:**
- Asking questions about training content
- Building up a FAQ from training transcripts
- Quick lookups on training material

### training-template

Provides a parameterized template for analyzing training courses.

**Use when:**
- Structuring a training analysis prompt
- Understanding the analysis format
- Customizing analysis for different course types (technical, process, conceptual)

### clean-inkling-ebook

Clean up markdown files exported from Inkling ebooks by removing HTML conversion artifacts, duplicate titles, URL metadata blocks, excessive indentation, and normalizing formatting.

**Use when:**
- Processing Inkling ebook exports
- Cleaning up converted training materials
- Normalizing markdown from ebook conversions

## Installation

```bash
# Using the discover-oeid-plugins skill
"Install the note-manager plugin"

# Or manually
cp -r note-manager ~/.claude/plugins/
```

## Related Plugins

- **noteplan-manager** - For organizing NotePlan notes
- **knowledge-manager** - For knowledge extraction and mapping

## License

MIT License - see [LICENSE](../../LICENSE) for details

## Author

Omar Eid (omar.eid@servicenow.com)
