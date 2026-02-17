# Documentation Manager Plugin

Professional documentation management for Claude Code - transform messy notes into clear, scannable, non-duplicative documentation.

## What This Plugin Does

Helps you structure and organize documentation following proven principles:

- **Single source of truth** - Eliminate duplication via linking
- **Question-focused** - Every section answers specific questions
- **Scannable format** - Headers, bullets, tables, minimal prose
- **Example-driven** - Show don't tell with code examples
- **Size-conscious** - Max 300 lines per file (150 for README)
- **Progressive disclosure** - Overview → Details via links

## Skills Included

### 📝 structure-notes

Transform unstructured notes into professional documentation.

**Use when:**
- "Structure these meeting notes"
- "Organize this documentation"
- "Clean up these notes following best practices"
- "Remove duplication from these docs"
- "Make this more scannable"

**What it does:**
1. Analyzes current structure and identifies document types needed
2. Creates question-focused sections with Essential Questions
3. Eliminates duplication by choosing single source of truth
4. Enhances scannability with tables, bullets, examples
5. Validates against best practices (no duplication, < 300 lines, etc.)
6. Provides document map and next steps

**Example:**

```
User: "Structure these meeting notes following best practices"

AI uses structure-notes skill to:
- Split raw notes into Summary, Key Decisions, Action Items, Discussion Points
- Add question-focused headers
- Create tables for action items
- Remove redundant explanations
- Ensure < 300 lines
- Output structured markdown
```

## Installation

```bash
# Clone or copy this plugin to your plugins directory
cp -r documentation-manager ~/.claude/plugins/

# Or use the discover-oeid-plugins skill to install
# In Claude session:
"Install the documentation-manager plugin"
```

## Documentation Principles

This plugin follows these core principles:

### 1. Single Source of Truth
Every piece of information lives in exactly ONE place. Link instead of duplicating.

❌ **Bad**: Same explanation in multiple files
✅ **Good**: Detailed explanation in GUIDE.md, links from other files

### 2. Question-Focused Sections
Headers should pose questions the section answers.

❌ **Bad**: "## Features"
✅ **Good**: "## What features are available?"

### 3. Essential Questions
Start each section with bullets showing what questions it addresses.

```markdown
## How do I configure authentication?

**Essential Questions:**
- What authentication methods are supported?
- Where is the config file?
- When do I need to restart after config changes?
```

### 4. Scannable Format
- **Headers**: Every 50-100 lines for navigation
- **Bullets**: For lists and features
- **Tables**: For comparisons and options
- **Code blocks**: For all examples
- **Minimal prose**: 50% fewer words, 3 lines max per paragraph

### 5. Examples Always
Every command, feature, or concept gets an example.

```bash
search --query auth --limit 10  # Find auth-related items
```

### 6. Size Limits
- README: 150 lines max (2-minute read)
- All other docs: 300 lines max (5-minute read)
- Split into subdirectory if longer

## Document Types

| Type | Purpose | Lines | Contents |
|------|---------|-------|----------|
| README | Project overview | 150 | What/why/quick start/links |
| QUICKSTART | Setup guide | 100 | Prerequisites/install/first steps |
| GUIDE | Complete guide | 300 | Features/workflows/examples |
| REFERENCE | Quick lookup | 200 | Commands/options/config tables |
| TROUBLESHOOTING | Problem solving | 200 | Common issues → solutions |
| ARCHITECTURE | Technical design | 300 | System design/patterns/diagrams |

## Use Cases

### Meeting Notes
Transform raw bullets into structured format:
- Summary (2-3 sentences)
- Key Decisions (with rationale)
- Action Items (who/what/when table)
- Discussion Points (organized by topic)

### Technical Documentation
Clean up dense docs:
- Split into README + GUIDE + REFERENCE + ARCHITECTURE
- Eliminate duplication via linking
- Add question-focused headers with Essential Questions
- Convert paragraphs to bullets and tables
- Ensure every concept has example

### Project Documentation
Organize multiple overlapping files:
- Audit current structure and line counts
- Map content to document types
- Move content to appropriate files
- Create missing documents (e.g., QUICKSTART)
- Eliminate duplication
- Add navigation to README

## Common Transformations

### Before
```markdown
# My Project

This project does X and Y. It also does Z.

To install, you can use npm install or yarn install.
You might also want to configure the settings in config.json.
There are various options...

[Dense paragraphs continue for 600 lines]
```

### After
```
README.md (120 lines)
├── What is this project?
├── Key features (bullets)
├── Quick start (3 commands)
└── Links to detailed docs

docs/
├── QUICKSTART.md (95 lines)
│   ├── Prerequisites
│   ├── Installation (step-by-step)
│   └── First commands
├── GUIDE.md (280 lines)
│   ├── How do I configure X?
│   ├── What workflows are supported?
│   └── Where do files go?
└── REFERENCE.md (180 lines)
    ├── Command reference table
    └── Configuration options table
```

## Writing Style

### Conciseness
- **50% fewer words** than first draft
- **One idea per sentence**
- **3 lines max per paragraph**

### Active Voice
❌ "The command can be used to..."
✅ "Use this command to..."

### Examples Over Explanation
❌ "The search feature allows filtering by keywords"
✅ `search --query auth  # Find authentication items`

### Links Not Duplication
```markdown
❌ Copy entire authentication section to 3 files

✅ Detailed auth guide in GUIDE.md, link from others:
   See [authentication guide](GUIDE.md#authentication)
```

## Validation Checklist

Well-structured documentation should be:

- [ ] **Findable** - Users locate info in < 30 seconds
- [ ] **Scannable** - Headers, bullets, tables throughout
- [ ] **Complete** - Every concept has examples
- [ ] **Non-duplicative** - Single source of truth
- [ ] **Size-appropriate** - All files < 300 lines (< 150 for README)
- [ ] **Question-focused** - Clear what each section answers
- [ ] **Example-driven** - Show don't tell

## Success Metrics

Good documentation is:
- ✅ 50% shorter than original (via conciseness + duplication removal)
- ✅ 3x more scannable (headers every 50-100 lines)
- ✅ 100% example coverage (every command/concept has one)
- ✅ < 30 seconds to find any piece of information
- ✅ < 5 minutes to read any single file

## Related Tools

This plugin works well with:
- **noteplan-manager** - For organizing NotePlan notes
- **config-manager** - For maintaining configuration docs
- Git version control - For tracking documentation changes

## Contributing

Found a bug or have a suggestion?
- Report issues at [GitHub Issues](https://github.com/oeid/claude-plugins/issues)
- Follow conventions in [DEVELOPMENT.md](../../DEVELOPMENT.md)

## License

MIT License - see [LICENSE](../../LICENSE) for details

## Author

Omar Eid (omar.eid@servicenow.com)

---

**Quick Start**: Just say "structure these notes" in a Claude session and the AI will apply all these principles automatically.
