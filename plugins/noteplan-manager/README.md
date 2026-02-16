# NotePlan Manager

Comprehensive plugin for managing all aspects of your NotePlan workflow - from organizing daily notes to managing templates and reference links.

## Overview

NotePlan Manager consolidates all NotePlan-related functionality into a single, powerful plugin. Whether you're organizing daily files, creating new notes, managing templates, or cleaning up references, this plugin has you covered.

## Skills

### Daily Organization

#### organize-daily
**Usage:** `/noteplan-manager:organize-daily`

Organize daily note files and maintain a clean NotePlan structure.

**Features:**
- Daily file organization
- Task management
- Note cleanup
- Structure maintenance

#### move-content
**Usage:** `/noteplan-manager:move-content`

Move content between NotePlan notes while maintaining links and references.

**Features:**
- Safe content migration
- Link preservation
- Reference updates
- Structure validation

### Reference Management

#### fix-reference
**Usage:** `/noteplan-manager:fix-reference`

Clean up and organize reference links with MLA-style citations and metadata extraction.

**Features:**
- YouTube metadata extraction (title, author, summary, duration)
- Article and documentation formatting
- Smart grouping by topic
- MLA-style citation formatting
- Git-based safety
- Duplicate detection

**Reference Types Supported:**
- YouTube videos
- Articles and blog posts
- Documentation and technical resources
- Research papers
- Generic web links

### Note Creation

#### create-note
**Usage:** `/noteplan-manager:create-note`

Create structured notes following existing conventions and patterns.

**Features:**
- Interactive note design
- Pattern analysis and application
- Template selection
- Location determination
- Connection establishment
- Convention following

**Note Types:**
- Project notes
- Area notes (ongoing responsibilities)
- Resource notes (reference material)
- Meeting notes
- Custom note types

#### quick-note
**Usage:** `/noteplan-manager:quick-note`

Rapidly create simple notes with minimal friction.

**Features:**
- Minimal questions
- Smart defaults
- Fast creation
- Basic structure
- Essential metadata

**Quick Note Types:**
- Simple notes
- Task lists
- Ideas
- References
- Meeting captures

### Structure Analysis

#### analyze-structure
**Usage:** `/noteplan-manager:analyze-structure`

Analyze your NotePlan structure and identify patterns, conventions, and organizational systems.

**Features:**
- Structure mapping
- Pattern detection
- Convention identification
- Organization analysis

#### suggest-improvements
**Usage:** `/noteplan-manager:suggest-improvements`

Get actionable suggestions for improving your NotePlan organization and workflow.

**Features:**
- Structure recommendations
- Workflow optimization
- Convention suggestions
- Best practice guidance

### Template Management

#### create-template
**Usage:** `/noteplan-manager:create-template`

Create new NotePlan templates based on existing patterns or custom specifications.

**Features:**
- Pattern-based template creation
- Custom template design
- Metadata configuration
- Variable support

#### list-templates
**Usage:** `/noteplan-manager:list-templates`

List and browse available NotePlan templates.

**Features:**
- Template discovery
- Template preview
- Usage statistics
- Quick access

#### manage-templates
**Usage:** `/noteplan-manager:manage-templates`

Manage, update, and organize your NotePlan templates.

**Features:**
- Template editing
- Template organization
- Template validation
- Template deletion

## NotePlan Location

Default: `$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3`

All skills automatically detect this path and work within the appropriate NotePlan directories.

## Installation

```bash
/plugin install noteplan-manager@oeid-claude-plugins
```

## Common Workflows

### Morning Routine
1. `/noteplan-manager:organize-daily` - Organize yesterday's notes
2. `/noteplan-manager:quick-note` - Capture quick thoughts
3. `/noteplan-manager:create-note` - Start structured project work

### Research Session Cleanup
1. `/noteplan-manager:fix-reference` - Organize saved links
2. `/noteplan-manager:move-content` - Migrate notes to proper locations
3. `/noteplan-manager:create-note` - Synthesize into structured notes

### Template Workflow
1. `/noteplan-manager:list-templates` - Browse available templates
2. `/noteplan-manager:create-note` - Create note from template
3. `/noteplan-manager:manage-templates` - Update templates based on usage

### Structure Optimization
1. `/noteplan-manager:analyze-structure` - Understand current organization
2. `/noteplan-manager:suggest-improvements` - Get recommendations
3. `/noteplan-manager:organize-daily` - Implement improvements

## Features

- **Pattern-Aware**: Analyzes and follows your existing conventions
- **Context-Intelligent**: Places content in appropriate locations
- **Git-Safe**: Works within git repositories with proper safety checks
- **Metadata-Rich**: Extracts and formats metadata from various sources
- **Template-Integrated**: Leverages templates for consistency
- **Link-Preserving**: Maintains all connections between notes

## Requirements

- NotePlan 3 installation
- Git repository at NotePlan root (recommended)
- (Optional) YouTube MCP server for enhanced video metadata in fix-reference

## Safety Features

- Git-based change tracking
- Validation before modifications
- Link preservation
- Content verification
- Backup recommendations

---

**Part of**: [OEID Claude Plugin Marketplace](../../README.md)
