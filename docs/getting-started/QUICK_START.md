# Quick Start Guide

Get started with the OEID Claude Plugin Marketplace in minutes.

## Installation

### Step 1: Add the Marketplace

```bash
/plugin marketplace add /Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace/oeid-claude-plugin-marketplace
```

### Step 2: Install Discovery Plugin

```bash
/plugin install discover-oeid-plugins@oeid-claude-plugins
```

### Step 3: Explore Plugins

```bash
/discover-oeid-plugins:explore-plugins
```

This will show you all available plugins with their installation status.

## Install Plugins

### Option 1: Install Individual Plugins

```bash
# Template management
/plugin install noteplan-templates@oeid-claude-plugins

# Daily note organization
/plugin install noteplan-daily-organizer@oeid-claude-plugins

# Structure analysis
/plugin install noteplan-structure-analyzer@oeid-claude-plugins

# Note creation
/plugin install noteplan-note-creator@oeid-claude-plugins
```

### Option 2: Install All at Once

```bash
cd /Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace/oeid-claude-plugin-marketplace
make install-all
```

### Verify Installation

After installation, verify all plugins are correctly installed:

```bash
make verify-installs
```

This checks that each plugin is properly installed with all required files.

## First Steps

### 1. Understand Your Organization

```bash
/noteplan-structure-analyzer:analyze-structure
```

This gives you insights into your current NotePlan organization.

### 2. Review Your Templates

```bash
/noteplan-templates:list-templates
```

See what templates you have available.

### 3. Process Today's Daily Note

```bash
/noteplan-daily-organizer:organize-daily
```

Move content from today's daily note to permanent notes.

### 4. Create a New Note

```bash
/noteplan-note-creator:create-note
```

Create a new note that follows your conventions.

## Common Workflows

### Daily Review Routine

1. **Analyze daily note**: `/noteplan-daily-organizer:organize-daily`
2. **Move content**: Let the plugin suggest where items should go
3. **Create new notes**: Use `/noteplan-note-creator:quick-note` for new items
4. **Update templates**: Refine templates based on patterns

### Weekly Organization

1. **Structure analysis**: `/noteplan-structure-analyzer:analyze-structure`
2. **Get suggestions**: `/noteplan-structure-analyzer:suggest-improvements`
3. **Implement improvements**: Follow prioritized recommendations
4. **Update templates**: Reflect organizational changes

### Template Management

1. **List templates**: `/noteplan-templates:list-templates`
2. **Create new**: `/noteplan-templates:create-template`
3. **Maintain existing**: `/noteplan-templates:manage-templates`

## Troubleshooting

### Marketplace Not Found

```bash
# Check marketplace is added
/plugin marketplace list

# If not listed, add it again
/plugin marketplace add /Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace/oeid-claude-plugin-marketplace
```

### Plugin Not Working

```bash
# Update marketplace
/plugin marketplace update

# Update plugin
/plugin update <plugin-name>

# Reinstall if needed
/plugin uninstall <plugin-name>
/plugin install <plugin-name>@oeid-claude-plugins
```

### Check Installation Status

```bash
# Use discovery plugin (interactive)
/discover-oeid-plugins:explore-plugins

# Or use Make target (shows status)
make list-plugins

# Verify installations (for automation/CI)
make verify-installs
```

## Getting Help

### View Available Make Targets

```bash
make help
```

### Check NotePlan Paths

```bash
make noteplan-info
```

### Validate Marketplace

```bash
make validate
```

### Detailed Makefile Documentation

For comprehensive documentation on the Makefile commands, scripts, and automation, see:
- [Makefile Guide](../guides/MAKEFILE_GUIDE.md)

## Next Steps

1. **Customize**: Adapt the plugins to your workflow
2. **Create patterns**: Establish conventions that work for you
3. **Maintain regularly**: Use plugins for consistent organization
4. **Iterate**: Refine your system over time

## Tips

- Start with the structure analyzer to understand your current organization
- Use quick-note for fast capture, create-note for structured notes
- Process daily notes regularly to maintain organization
- Create templates for recurring note types
- Review and update your structure periodically

---

**Need more help?** Check the [main README](../../README.md) or individual plugin documentation.
