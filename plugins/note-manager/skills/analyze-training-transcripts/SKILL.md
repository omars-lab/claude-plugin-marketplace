---
name: analyze-training-transcripts
description: Analyze training course transcripts and generate comprehensive one-page quick reference guides with diagrams, decision tables, use cases, and best practices. Use when analyzing training materials, course transcripts, or learning content.
---

# Analyze Training Transcripts

You are a training content analyzer. When this skill is invoked, analyze the training transcripts in the specified directory and generate comprehensive documentation.

## What to Do

1. **Read all transcript files** from the directory path provided (supports `.md`, `.txt`, `.pdf`)
2. **Extract key information**:
   - Core concepts, APIs, classes, patterns
   - Use cases and real-world applications
   - Best practices and recommendations
   - Relationships and dependencies between concepts
3. **Generate structured outputs**:
   - One-page quick reference guide
   - PlantUML architecture diagrams
   - UML class diagrams (if applicable)
   - Deliverables summary

## Output Structure

### 1. Quick Reference Guide (`[topic]-quick-reference.md`)

Create a scannable one-pager with these sections:

**🔑 HIGH-LEVEL DEFINITIONS & ANALOGIES (START HERE)**
- Begin with clear definitions using familiar parallels
- Draw analogies to known technology (e.g., "Like an ORM", "Similar to React hooks", "Like database triggers")
- Help readers connect new concepts to existing knowledge

**📋 CORE CONCEPTS/TYPES**
- Comparison tables categorizing main concepts
- Embed UML class diagram (if applicable) with edit URL
- Show relationships and hierarchies

**🎯 DECISION TABLES (5-6 tables)**
Format: **Feature | When to Use | Key Factors | Avoid When | Performance Notes**
- Compare related features showing when to pick one over another
- Include performance implications
- Provide clear decision criteria

**💡 USE CASES (10-15 customer perspective)**
Format: "As a [user type], I would use **[Feature X]** when I need to **[do Y]**"
- Extract real-world scenarios from transcripts
- Write from user perspective
- Cover diverse use cases

**🌟 BEST PRACTICES (CONSOLIDATED 10-12 items)**
- Single consolidated table
- Group by category (Approach, Performance, Security, Code Quality)
- Actionable, specific guidance (1-2 lines each)
- High-impact practices only

**🔄 COMMON PATTERNS**
- Pattern categories with code examples
- Best practice implementations
- Anti-patterns to avoid

**🗺️ ARCHITECTURE DIAGRAM**
- Embed at end with edit URL and SVG file

### 2. Architecture Diagram (`[topic]-architecture.puml` + `.svg`)

Create a PlantUML diagram showing:
- Component relationships and architecture
- Workflow interactions and data flow
- Execution contexts (color-coded)
- Performance considerations (annotations)
- Include analogies in diagram notes
- Add legend explaining colors and patterns

### 3. UML Class Diagram (`[topic]-classes-diagram.puml` + `.svg`) (if applicable)

If content includes classes/APIs:
- Partition by context or execution environment
- Show inheritance, dependencies, communication patterns
- Include analogies, performance notes, security implications
- Color-code by category
- Add legend

### 4. FAQ (`[topic]-FAQ.md`)

Generate a comprehensive FAQ based on the training content:

**Structure:**
```markdown
# [Topic] Frequently Asked Questions

> Interactive FAQ for [Topic]. Use /note-manager:training-faq to ask questions.

## Getting Started

### Q: What is [main concept]?
**A:** [Clear explanation with examples]

### Q: When should I use [feature]?
**A:** [Practical guidance]

## Common Questions

### Q: How do I [common task]?
**A:** [Step-by-step answer]

### Q: What's the difference between [A] and [B]?
**A:** [Comparison with decision criteria]

## Troubleshooting

### Q: Why does [problem] happen?
**A:** [Root cause and solution]

## Advanced Topics

### Q: How do I [advanced task]?
**A:** [Detailed answer with code examples]

## Additional Questions

<!-- New questions will be added here by training-faq skill -->
```

**Content Guidelines:**
- Extract 20-30 common questions from transcripts
- Provide clear, concise answers
- Include code examples where relevant
- Group by category (Getting Started, Common, Troubleshooting, Advanced)
- Leave space for additional questions to be added

### 5. Deliverables Summary (`DELIVERABLES-SUMMARY.md`)

Document what was created and how to use it.

Include note about using the FAQ skill:
```markdown
## Interactive FAQ

The generated FAQ can be used interactively:

    /note-manager:training-faq /path/to/[topic]-FAQ.md

This allows you to:
- Ask questions about the training material
- Get answers from the FAQ
- Fallback to transcript analysis if not in FAQ
- Automatically update FAQ with new Q&A
```

## File Naming

Generate file names based on the topic/directory name:
- Use kebab-case slugs (e.g., `application-dev`, `scripting-fundamentals`)
- Infer topic from directory name or transcript content

## Quality Criteria

✅ One-pager STARTS with definitions & analogies
✅ Scannable in under 2 minutes
✅ Diagrams embedded with edit URLs and SVG files
✅ Decision tables with clear comparison factors
✅ 10-15 real-world use cases from user perspective
✅ 10-12 consolidated best practices in single section
✅ Code examples for common patterns
✅ Visual hierarchy (headers, tables, code blocks)
✅ Performance comparisons with specific metrics
✅ Both diagrams generated as SVG using PlantUML tool

## Instructions

When invoked with a directory path:
1. Read all transcript files completely
2. Identify the main topic/subject
3. Extract and categorize all key information
4. Generate all deliverables following the structure above
5. Save files to the specified directory
6. Provide a summary of what was created

Be thorough, extract maximum value, and present information in a highly actionable, scannable format.
