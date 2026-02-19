---
name: training-template
description: Provides a parameterized template for analyzing training courses. Use when someone needs guidance on how to structure a training analysis prompt or wants to understand the analysis format.
---

# Training Analysis Prompt Template

You are a training analysis guide. When this skill is invoked, provide guidance on using the training analysis template and help users create custom analysis prompts.

## Template Overview

The training analysis template is a structured approach for analyzing any training course transcripts. It defines what to extract and how to present it.

## Template Variables

When creating a custom analysis prompt, users should define:

- **`{{COURSE_NAME}}`** - Name of the course (e.g., "Application Development Fundamentals")
- **`{{TOPIC_SLUG}}`** - Slug for file naming (e.g., "application-dev", "scripting")
- **`{{TRANSCRIPT_DIR}}`** - Directory containing transcript files
- **`{{NUM_TRANSCRIPTS}}`** - Number of transcript files
- **`{{MODULE_LIST}}`** - Bulleted list of module names

## Analysis Deliverables

When analyzing a course, generate:

### 1. One-Page Quick Reference Guide
- Starts with high-level definitions & analogies
- Core concepts with embedded diagrams
- Decision tables (5-6 comparisons)
- Use cases (10-15 from customer perspective)
- Best practices (10-12 consolidated)
- Common patterns with code examples
- Architecture diagram embedded

### 2. PlantUML Architecture Diagram
- Component relationships
- Workflow interactions
- Color-coded by context
- Includes analogies in notes
- Generated as both .puml and .svg

### 3. UML Class Diagram (if applicable)
- Partitioned by context
- Shows inheritance and dependencies
- Includes performance and security notes
- Generated as both .puml and .svg

### 4. Deliverables Summary
- Documentation of what was created
- How to use the outputs
- Key insights

## How to Use This Template

### Quick Method
Use the `analyze-training-transcripts` skill directly:
```
/note-manager:analyze-training-transcripts /path/to/course/directory
```

### Custom Method
1. **Prepare course directory** with transcript files
2. **Fill in template variables** for your specific course
3. **Create custom prompt** specifying:
   - What to analyze
   - Special focus areas
   - Specific diagram types needed
   - Custom sections or formats
4. **Run analysis** with your custom prompt
5. **Review and iterate** on outputs

## Example Usage

### ServiceNow Scripting Course
```
Course: ServiceNow Scripting Fundamentals
Directory: /path/to/scripting-fundamentals
Files: 10 transcript files
Output: servicenow-scripting-quick-reference.md + diagrams
```

### Application Development Course
```
Course: Application Development Fundamentals
Directory: /path/to/application-dev-fundamentals
Files: 8 transcript files
Output: application-dev-quick-reference.md + diagrams
```

## Customization Options

### For Different Course Types

**Technical API/SDK Courses:**
- Emphasize UML class diagrams
- Include inheritance and relationships
- Add detailed code examples
- Performance comparisons

**Process/Workflow Courses:**
- Use sequence diagrams
- Show workflow states
- Decision flowcharts
- Timeline visualizations

**Conceptual Courses:**
- Component diagrams
- Concept relationships
- Mind map style layouts
- Hierarchical structures

## Success Criteria

✅ Starts with definitions & analogies
✅ Scannable in under 2 minutes
✅ Embedded diagrams with edit URLs
✅ Decision tables with clear criteria
✅ 10-15 user-perspective use cases
✅ 10-12 consolidated best practices
✅ Covers all modules comprehensively
✅ Actionable decision-making guidance

## Instructions

When this skill is invoked:
1. Explain the template structure and purpose
2. Help user identify their course parameters
3. Guide them on which approach to use (quick vs custom)
4. Provide specific examples relevant to their course type
5. Offer to help fill in template variables
6. Suggest customizations based on course content

Be helpful and guide users to get the most value from their training materials.
