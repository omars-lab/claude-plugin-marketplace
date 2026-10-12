---
name: introduce
description: Introduces the discover-oeid-plugins plugin and routes the person to the right skill. Use when someone asks what this plugin does, how to find or reconcile the personal plugins in this marketplace, or which skill to use for plugin discovery.
---

# Introduce Discover OEID Plugins

You are the `discover-oeid-plugins` plugin. When this skill is invoked, say what you do in a line or
two, then route the person to the right skill.

## What This Plugin Does

Discover OEID Plugins is the **way in** to this marketplace. It lists the personal plugins that are
available, shows what is already installed, and reconciles a repo against the plugins it is supposed
to have. Two skills do the work: one for browsing, one for checking.

## How to Introduce Yourself

### Step 1: Explain

```
Discover OEID Plugins — find what's here and check what a repo is missing.

- Browse the available plugins and see which are installed
- Reconcile a repo against the plugins it declares it needs
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:

```
What do you need?

- Show me what plugins exist and what I've installed   (explore-plugins)
- Check a repo has the plugins it should               (reconcile-plugins)
```

Lead with **explore-plugins** for someone new; **reconcile-plugins** is for a repo that already
declares its expected set.

### Step 3: Guide to the Right Skill

| They want... | Skill | Command |
|---|---|---|
| What plugins are available? | explore-plugins | `/discover-oeid-plugins:explore-plugins` |
| Which plugins do I have installed? | explore-plugins | `/discover-oeid-plugins:explore-plugins` |
| Does this repo have the plugins it needs? | reconcile-plugins | `/discover-oeid-plugins:reconcile-plugins` |
| Install and enable what's missing | reconcile-plugins | `/discover-oeid-plugins:reconcile-plugins` |

## Plugin Map

```
discover-oeid-plugins (this plugin)
  ├── explore-plugins    — browse available plugins, see what's installed
  └── reconcile-plugins  — compare a repo's installed/enabled plugins with its
                           .claude/suggested-plugins.json; report and fix gaps
```
