---
name: introduce
description: Explains role-manager capabilities and guides users to the right skill
---

# Role Manager

Manage personalbook roles: structure, validate, migrate, reorganize, and archive.

## What This Plugin Does

The role-manager plugin helps you organize and maintain your personalbook role system. Roles represent different hats you wear in life (self-development, software-development, business-development, family, etc.).

## Available Skills

### Role Management

| Skill | When to Use | Invoke |
|-------|-------------|--------|
| **structure-role** | Structure or refactor a role directory | `/role-manager:structure-role` |
| **validate-role** | Check if a role follows conventions | `/role-manager:validate-role` |
| **migrate-content** | Move content between roles safely | `/role-manager:migrate-content` |
| **reorganize-roles** | Move roles between categories | `/role-manager:reorganize-roles` |
| **archive-role** | Remove or merge a role | `/role-manager:archive-role` |

### Plugin Extraction

| Skill | When to Use | Invoke |
|-------|-------------|--------|
| **extract-skill** | Extract a skill from a role to the plugin marketplace | `/role-manager:extract-skill` |
| **convert-role-to-plugin** | Convert an entire role into a plugin | `/role-manager:convert-role-to-plugin` |

## Quick Decision Guide

**"I want to organize a messy role directory"**
→ Use `/role-manager:structure-role`

**"I want to check if my role is properly structured"**
→ Use `/role-manager:validate-role`

**"I need to move content from one role to another"**
→ Use `/role-manager:migrate-content`

**"I want to move a role to a different category"**
→ Use `/role-manager:reorganize-roles`

**"I want to remove or merge a role I no longer need"**
→ Use `/role-manager:archive-role`

**"I want to share a specific skill from a role as a plugin"**
→ Use `/role-manager:extract-skill`

**"I want to convert an entire role into a shareable plugin"**
→ Use `/role-manager:convert-role-to-plugin`

## Role Categories

Roles are organized by what they **develop**:

| Category | What It Develops | Examples |
|----------|------------------|----------|
| `roles-self-development/` | The person (you) | Self Reflector, Learner, Self Master |
| `roles-software-development/` | Software systems | Developer, Architect, Data Engineer |
| `roles-business-development/` | Businesses | CTO, Manager, Entrepreneur |
| `roles/` | Life experiences | Adventurer, Foodie, Entertainer |
| `roles-family/` | Family relationships | Father, Spouse |
| `roles-creative/` | Creative works | Writer, Artist |

## Key Concepts

Every role can have these components:

| Component | What It Is | Example |
|-----------|-----------|---------|
| **Skills** | How to do things | `skills/reflecting-on-progress/SKILL.md` |
| **Habits** | Regular practices | `habits/weekly-review/HABIT.md` |
| **Expectations** | Standards to embody | `expectations/breaking-molds.md` |
| **Artifacts** | Personal outcomes | `artifacts/learning-plans.md` |
| **Knowledge** | Background info | `knowledge/prioritization.md` |
| **Decisions** | One-time choices | `decisions/grad-school/` |

## Reference Guides

Detailed guides are available under the structure-role skill:
- `guides/conventions.md` - **Naming, frontmatter schemas, enums, validation commands**
- `guides/generalizing-skills.md` - How to create skills
- `guides/generalizing-habits.md` - How to create habits
- `guides/organizing-artifacts.md` - How to organize artifacts
- `guides/role-groupings.md` - Role category conventions
- `guides/verifying-content-preservation.md` - Content migration verification
