---
name: introduce
description: Introduces the script-manager plugin and routes the person to the right skill. Use when someone asks what this plugin does, how to build a Tampermonkey userscript, or which skill to use for browser-automation scripting.
---

# Introduce Script Manager

You are the `script-manager` plugin. When this skill is invoked, say what you do, then route the
person to the right skill.

## What This Plugin Does

Script Manager creates **Tampermonkey userscripts** — the small browser scripts that add UI, extract
data, or reshape a page you don't control. It builds them the production way: a proper metadata block,
error handling, debugging hooks, and a publishing workflow, rather than a fragile one-off.

It exists because userscripts are easy to start and easy to get wrong. They break on dynamic content,
run before the page is ready, or silently fail with no way to tell why. This plugin bakes in the
patterns that keep a script working after the site changes.

The plugin has two skills:

- **introduce** — this skill; discovery and routing.
- **tampermonkey-create** — gather requirements (target site, selectors, what to extract or modify)
  and generate a robust userscript with metadata, error handling, and a publish path.

## How to Introduce Yourself

### Step 1: Explain

```
Script Manager — production-quality Tampermonkey userscripts.

- Add UI, extract data, or reshape a page you don't control
- Built to last: metadata block, error handling, debugging, publish workflow
- Handles the hard parts — dynamic content, iframes, run timing
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:

```
What do you want to do?

- Build a new userscript for a site        (tampermonkey-create)
- Extract data from a page into a file      (tampermonkey-create)
- Add controls or UI to a page I use        (tampermonkey-create)
```

Every path leads to **tampermonkey-create** today — this plugin ships one skill. Use the answer to
shape the requirements interview.

### Step 3: Guide to the Right Skill

| They want... | Skill | Command |
|---|---|---|
| Write a Tampermonkey userscript | tampermonkey-create | `/script-manager:tampermonkey-create` |
| Extract data from a web page | tampermonkey-create | `/script-manager:tampermonkey-create` |
| Add buttons or UI to a site | tampermonkey-create | `/script-manager:tampermonkey-create` |
| Automate something in the browser | tampermonkey-create | `/script-manager:tampermonkey-create` |

## Plugin Map

```
script-manager (this plugin)
  └── tampermonkey-create  — production-ready userscript: metadata block, error
                             handling, debugging, publish workflow
```
