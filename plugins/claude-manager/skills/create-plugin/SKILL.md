---
name: create-plugin
description: Scaffold a new plugin with proper structure, introduce skill, plugin.json, minimal README, and framework compliance
---

# Create Plugin

You are a Claude plugin scaffolding assistant. When this skill is invoked, you'll create a properly structured plugin that follows all framework conventions, including mandatory patterns like the `introduce` skill, task management, and git safety.

## What This Skill Does

This skill:
1. **Gathers requirements** for the new plugin via AskUserQuestion
2. **Scaffolds the full plugin structure** (directories, plugin.json, README, introduce skill)
3. **Creates the first skill** based on user requirements
4. **Registers the plugin** in the marketplace
5. **Validates the result** against framework standards

## Plugin Framework Standards

Every plugin in the marketplace MUST have:

### Required Files

```
plugins/{plugin-name}/
  .claude-plugin/
    plugin.json              # Plugin metadata (name, version, description, author)
  skills/
    introduce/
      SKILL.md               # MANDATORY - explains plugin capabilities
    {first-skill}/
      SKILL.md               # At least one functional skill
  README.md                  # MINIMAL - name, install command, skill table (<50 lines)
```

### plugin.json Format

```json
{
  "name": "{plugin-name}",
  "description": "{One-line description of plugin purpose}",
  "version": "1.0.0",
  "author": {
    "name": "Omar Eid",
    "email": "omar.eid@servicenow.com"
  },
  "license": "MIT"
}
```

### README.md Format (Minimal)

```markdown
# {Plugin Name}

{One-line description}

## Getting Started

\`\`\`bash
# Install
/plugin install {plugin-name}@oeid-claude-plugins

# Learn what this plugin can do
/{plugin-name}:introduce
\`\`\`

## Skills ({count})

| Category | Skill | What it does |
|---|---|---|
| **Intro** | `introduce` | Explain plugin capabilities |
| **{Category}** | `{skill-name}` | {One-line description} |

## Requirements

- {Requirement 1}
- {Requirement 2}

---

**Part of**: [OEID Claude Plugin Marketplace](../../README.md)
```

### Mandatory Skill Patterns

Every skill MUST include:

1. **Task Management** - `TaskCreate`/`TaskUpdate` for multi-step workflows
2. **AskUserQuestion** - For all user decisions and confirmations
3. **Git Safety** - Pre-commit, checkpoint, diff validation (for file-modifying skills)
4. **YAML Frontmatter** - `name` and `description` fields

### introduce Skill Template

The `introduce` skill MUST:
- Explain what the plugin does in plain language
- List all skills grouped by category with one-line descriptions
- Show common workflows (which skills to use when)
- Use `AskUserQuestion` to let users explore specific categories
- Include common scenarios with skill recommendations

## Task Management (MANDATORY)

```javascript
// Task #1: Gather plugin requirements
TaskCreate({
  subject: "Gather plugin requirements",
  description: "Use AskUserQuestion to collect:\n- Plugin name\n- Plugin description\n- Target marketplace\n- First skill name and purpose\n- Category",
  activeForm: "Gathering requirements"
})

// Task #2: Scaffold plugin structure
TaskCreate({
  subject: "Scaffold plugin structure",
  description: "Create:\n- Plugin directory under plugins/\n- .claude-plugin/plugin.json\n- skills/ directory\n- skills/introduce/SKILL.md\n- README.md (minimal)",
  activeForm: "Scaffolding plugin"
})

// Task #3: Create first skill
TaskCreate({
  subject: "Create first functional skill",
  description: "Create the user's requested first skill with:\n- Proper SKILL.md structure\n- Task management section\n- AskUserQuestion usage\n- Git safety (if file-modifying)\n- Examples and success criteria",
  activeForm: "Creating first skill"
})

// Task #4: Register in marketplace
TaskCreate({
  subject: "Register plugin in marketplace",
  description: "Add plugin entry to marketplace.json:\n- name, version, category fields\n- Verify no name conflicts with existing plugins",
  activeForm: "Registering in marketplace"
})

// Task #5: Validate and report
TaskCreate({
  subject: "Validate plugin against framework standards",
  description: "Run health checks:\n- plugin.json valid\n- introduce skill exists\n- First skill has mandatory patterns\n- README is minimal\n- marketplace.json updated\n- No naming conflicts",
  activeForm: "Validating plugin"
})

// Dependencies
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
TaskUpdate({ taskId: "5", addBlockedBy: ["4"] })
```

## Workflow

When invoked, **ALWAYS follow this exact workflow:**

### Step 0: Task Setup (MANDATORY FIRST STEP)

Create all 5 tasks with dependencies before doing any work. Display the task plan:

```
Create Plugin - Task Workflow (5 Tasks)

#1 Gather plugin requirements [STARTING]
 └─► #2 Scaffold plugin structure
      └─► #3 Create first functional skill
           └─► #4 Register plugin in marketplace
                └─► #5 Validate and report
```

### Step 1 (Task #1): Gather Requirements

Use `AskUserQuestion` to collect information:

**Question 1: Plugin identity**
```
What kind of plugin do you want to create?

Options:
- Productivity (notes, tasks, planning)
- Development (code, CI/CD, tooling)
- Utilities (config, setup, maintenance)
- Custom (describe your own)
```

**Question 2: Plugin details**
- Plugin name (kebab-case, e.g., `my-manager`)
- One-line description
- What problem does it solve?

**Question 3: First skill**
- Skill name
- What does the skill do?
- Does it modify files? (determines git safety requirement)

**Question 4: Target marketplace**
```
Which marketplace?

Options:
- oeid-claude-plugins (personal)
- ceg-claude-plugins (work/team)
```

### Step 2 (Task #2): Scaffold Plugin Structure

**Determine the marketplace path:**
```bash
# oeid marketplace
MARKETPLACE="/Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace/oeid-claude-plugin-marketplace"

# ceg marketplace
MARKETPLACE="/Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace/ceg-claude-plugin-marketplace"
```

**Create directory structure:**
```bash
PLUGIN_DIR="$MARKETPLACE/plugins/{plugin-name}"

mkdir -p "$PLUGIN_DIR/.claude-plugin"
mkdir -p "$PLUGIN_DIR/skills/introduce"
mkdir -p "$PLUGIN_DIR/skills/{first-skill-name}"
```

**Create plugin.json:**
```bash
# Write plugin.json with collected metadata
```

**Create minimal README.md** following the template above.

**Create introduce skill** that:
- Describes the plugin
- Lists the first skill
- Shows when to use it
- Uses AskUserQuestion for exploration

### Step 3 (Task #3): Create First Skill

Create the first functional skill following `skill-create` patterns:

- YAML frontmatter with name and description
- Role statement ("You are a...")
- What This Skill Does section
- Task Management section (MANDATORY)
- AskUserQuestion usage (MANDATORY)
- Git Safety section (if file-modifying)
- Workflow with numbered steps
- Safety Checks
- Example Usage
- Related Skills

### Step 4 (Task #4): Register in Marketplace

**Read current marketplace.json:**
```bash
cat "$MARKETPLACE/.claude-plugin/marketplace.json"
```

**Add new plugin entry:**
```json
{
  "name": "{plugin-name}",
  "version": "1.0.0",
  "category": "{category}"
}
```

**Write updated marketplace.json.**

### Step 5 (Task #5): Validate

Run health checks against the new plugin:

```
Validating {plugin-name}...

✅ plugin.json exists and is valid
✅ introduce skill exists
✅ First skill ({skill-name}) has TaskCreate/TaskUpdate
✅ First skill ({skill-name}) has AskUserQuestion
✅ Git safety present (if applicable)
✅ README.md is minimal (< 50 lines)
✅ Registered in marketplace.json
✅ No naming conflicts with existing plugins

Plugin created successfully!

Location: $MARKETPLACE/plugins/{plugin-name}/
Skills: introduce, {first-skill-name}

Next steps:
1. Install: /plugin install {plugin-name}@{marketplace}
2. Test: /{plugin-name}:introduce
3. Add more skills: /claude-manager:skill-create
```

## Safety Checks

- **Name conflict detection**: Check existing plugins before creating
- **Marketplace validation**: Verify marketplace.json stays valid JSON after edit
- **No overwrite**: Never overwrite existing plugin directories
- **Framework compliance**: Validate against all mandatory patterns before completing

## Example Usage

```
User: /claude-manager:create-plugin

Claude: I'll help you create a new plugin.

[Creates 5 tasks with dependencies]

What kind of plugin do you want to create?
- Productivity
- Development
- Utilities
- Custom

User: Productivity

Claude: What should the plugin be called and what does it do?

User: journal-manager - helps manage daily journal entries with prompts and reflections

Claude: What should the first skill be?

User: write-entry - guided journal writing with reflection prompts

Claude: Got it. Let me scaffold the plugin...

[Creates directory structure, plugin.json, introduce skill, write-entry skill, README]
[Registers in marketplace.json]
[Validates against framework standards]

✅ Plugin created!

plugins/journal-manager/
  .claude-plugin/plugin.json
  skills/introduce/SKILL.md
  skills/write-entry/SKILL.md
  README.md

Install: /plugin install journal-manager@oeid-claude-plugins
Test: /journal-manager:introduce
```

## Related Skills

- **skill-create** - Create additional skills in existing plugins
- **skill-update** - Modify skills after creation
- **fix-plugins** - Audit plugin health and fix compliance issues
- **claude-md-setup** - Generate CLAUDE.md for the plugin's development
