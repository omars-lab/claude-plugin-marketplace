# NotePlan Daily Organizer

Move content from daily files to relevant notes with folder and emoji awareness.

## Overview

This plugin helps process daily notes by intelligently moving content to permanent notes while maintaining your organizational structure, emoji conventions, and linking patterns.

## Skills

### organize-daily

**Usage:** `/noteplan-daily-organizer:organize-daily`

Intelligently organize a daily note:
- Analyze daily file content
- Categorize tasks, notes, ideas, meetings
- Match content to appropriate permanent notes
- Move items with context preservation
- Clean up processed items
- Report on what was moved

### move-content

**Usage:** `/noteplan-daily-organizer:move-content`

Move specific content between notes:
- Targeted content movement
- Source and destination specification
- Context preservation (dates, links, tags)
- Hierarchical structure maintenance
- Clean source after move

## Features

- **Context-Aware**: Understands folder structure and organization patterns
- **Emoji Intelligence**: Recognizes and maintains emoji conventions
- **Smart Matching**: Finds the right destination for content
- **Link Preservation**: Maintains all note connections
- **Backlink Creation**: Adds source references to moved content

## NotePlan Directories

- **Daily Files**: `/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Calendar/`
- **Notes**: `/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/`

## Installation

```bash
/plugin install noteplan-daily-organizer@oeid-claude-plugins
```

## Use Cases

- Processing daily notes at end of day
- Moving tasks to project notes
- Organizing meeting notes to project files
- Clearing backlog from daily notes
- Maintaining inbox zero for daily files

## Workflow Example

1. Run `/noteplan-daily-organizer:organize-daily`
2. Review analysis of daily note content
3. Confirm or adjust destinations
4. Content moves with proper formatting
5. Daily note is cleaned up

---

**Part of**: [OEID Claude Plugin Marketplace](../../README.md)
