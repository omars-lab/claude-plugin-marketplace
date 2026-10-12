# Instagram Manager

Turn your Instagram saved posts into something you use: import them from your data export, tag
them by topic and city, pull out the places and ideas each post names, and build a private hub
that feeds your other projects.

## Getting Started

```bash
# Install
/plugin install instagram-manager@oeid-claude-plugins

# Learn what this plugin can do
/instagram-manager:introduce
```

## Skills (3)

| Category | Skill | What it does |
|---|---|---|
| **Intro** | `introduce` | Explain the plugin and route to the right skill |
| **Route** | `manage-saves` | Pick the next step: import, tag, split, media, hub, send |
| **Import** | `import-saves` | Read the saved posts and collections out of your export zip, in memory |

## Where your data lives

The plugin holds code only. Your saves, tags and media live in a private data repo, found
through `INSTAGRAM_HOME` (default `~/Workspace/git/instagram`). Nothing personal goes in this
public repo.

## Requirements

- Python 3 (standard library only)
- An Instagram data export (Settings → Your activity → Download your information), HTML or JSON

---

**Part of**: [OEID Claude Plugin Marketplace](../../README.md)
