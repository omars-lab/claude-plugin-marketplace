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

## Skills (4)

| Category | Skill | What it does |
|---|---|---|
| **Intro** | `introduce` | Explain the plugin and route to the right skill |
| **Route** | `manage-saves` | Pick the next step: import, tag, split, media, hub, send |
| **Import** | `import-saves` | Read the saved posts and collections out of your export zip, in memory |
| **Tag** | `tag-saves` | Topics and places per save: collection rules, then `save-tagger` agents on batches |

## Agents (1)

| Agent | What it does |
|---|---|
| `save-tagger` | Reads one batch file of saves and writes their topics and places to its answers file (Haiku) |

No script calls a model. Scripts write batch files and check the answers; the Claude Code session
starts the agents, on the plan it is logged in with. No API key.

## Where your data lives

The plugin holds code only. Your saves and tags live in a private data repo, found through
`INSTAGRAM_HOME` (default `~/Workspace/git/instagram`). Media goes to a folder of your choosing,
`INSTAGRAM_MEDIA_DIR`, outside git. Nothing personal goes in this public repo.

## Requirements

- Python 3, plus PyYAML (the tagger and the data check)
- Claude Code, for the agents
- An Instagram data export (Settings → Your activity → Download your information), HTML or JSON

---

**Part of**: [OEID Claude Plugin Marketplace](../../README.md)
