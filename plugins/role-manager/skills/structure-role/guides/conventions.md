# Personalbook Conventions Reference

Quick reference for naming, frontmatter schemas, validation patterns, and enums used across the personalbook role system.

---

## Naming Conventions

### Directory and File Names

| Rule | Bad | Good |
|------|-----|------|
| **Lowercase kebab-case** | `Reflecting on Value.md` | `reflecting-on-value.md` |
| **No spaces** | `My Learning Plans.md` | `learning-plans.md` |
| **.md extension** | `identifying-interests.txt` | `identifying-interests.md` |
| **Verb-based skills** | `reflection.md` | `reflecting-on-progress.md` |
| **Noun-based artifacts** | `What I Learned.md` | `learnings.md` |

### Role Directory Names

| Category | Pattern | Examples |
|----------|---------|----------|
| Self-development | `The [Noun]` | `The Self Reflector`, `The Learner` |
| Technical | `The [Noun]` | `The Developer`, `The Automator` |
| Career | `The [Title]` | `The CTO`, `The Manager` |
| Life | `The [Role]` | `The Father`, `The Spouse` |

### Skill/Habit Directory Names

```
skills/[verb-based-name]/SKILL.md      # e.g., skills/reflecting-on-progress/
habits/[noun-based-name]/HABIT.md      # e.g., habits/weekly-review/
processes/[noun-based-name]/PROCESS.md # e.g., processes/code-review/
```

---

## Frontmatter Schemas

### SKILL.md Frontmatter

```yaml
---
name: reflecting-on-progress          # Required: kebab-case, matches directory
description: Brief description        # Optional: for plugin skills
scope: Goals, plans, priorities       # Optional: comma-separated focus areas
extends: parent-skill-name            # Optional: if extending another skill
status: established                   # Optional: maturity level
started_date: 2024-01-15              # Optional: when you started developing
established_date: 2024-06-01          # Optional: when it became established
---
```

### HABIT.md Frontmatter

```yaml
---
name: weekly-reflection               # Required: kebab-case, matches directory
frequency: weekly                     # Required: daily | weekly | monthly | quarterly | yearly
timing: Sunday evening                # Required: when the habit is practiced
duration: 30 minutes                  # Optional: how long it takes
skills_combined:                      # Optional: skills used in this habit
  - reflecting-on-progress
  - reviewing-priorities
status: establishing                  # Required: maturity level
started_date: 2024-01-15              # Optional
established_date: null                # Optional: filled when established
---
```

### PROCESS.md Frontmatter (Technical Roles)

```yaml
---
name: code-review                     # Required: kebab-case
frequency: per-PR                     # Required: when triggered
timing: before merge                  # Required: when in workflow
status: established                   # Required: maturity level
---
```

### Artifact Frontmatter

```yaml
---
intent: What this artifact captures   # Required: one-line purpose
habits:                               # Optional: habits that update this
  - weekly-review
  - quarterly-planning
initiative: home-automation           # Optional: if part of an initiative
---
```

### Knowledge Frontmatter

```yaml
---
topic: Design Patterns                # Required: topic name
status: reference                     # Required: always "reference"
---
```

### Expectation Frontmatter

```yaml
---
source: industry, role models         # Required: who expects this
observed: 2020-05-20                  # Required: when you documented it
---
```

### Initiative Overview Frontmatter

```yaml
---
status: active                        # Required: active | paused | completed | abandoned
started: 2021-04                      # Required: when started
completed: null                       # Optional: when completed
---
```

### Deprecated/Extracted Content

```yaml
---
status: deprecated
extracted_to: plugin-name:skill-name  # Where it moved
extraction_date: 2024-06-01
---
```

---

## Enum Values

### Status: Skills and Habits

| Status | Code | Description |
|--------|------|-------------|
| Ideating | `ideating` | Considering whether to develop |
| Establishing | `establishing` | Actively building/developing |
| Practicing | `practicing` | Exists, requires effort |
| Established | `established` | Fully integrated, automatic |
| Paused | `paused` | Temporarily on hold |
| Retired | `retired` | No longer relevant |

### Status: Initiatives

| Status | Code |
|--------|------|
| Active | `active` |
| Paused | `paused` |
| Completed | `completed` |
| Abandoned | `abandoned` |

### Status: Knowledge

| Status | Code |
|--------|------|
| Reference | `reference` |

### Frequency: Habits/Processes

| Frequency | Code |
|-----------|------|
| Daily | `daily` |
| Weekly | `weekly` |
| Monthly | `monthly` |
| Quarterly | `quarterly` |
| Yearly | `yearly` |
| Per-event | `per-PR`, `per-deploy`, etc. |

### Role Categories

| Category | Directory | What It Develops |
|----------|-----------|------------------|
| Self-development | `roles-self-development/` | The person (you) |
| Software-development | `roles-software-development/` | Software systems |
| Business-development | `roles-business-development/` | Businesses |
| Family | `roles-family/` | Family relationships |
| Creative | `roles-creative/` | Creative works |
| Life | `roles/` | Life experiences |

---

## Validation Commands

### Check Frontmatter Exists

```bash
# Check if file has frontmatter (starts with ---)
head -1 "[file]" | grep -q "^---$" && echo "Has frontmatter" || echo "Missing frontmatter"

# Validate all skills have frontmatter
for f in $(find "[role]/skills" -name "SKILL.md"); do
  if ! head -1 "$f" | grep -q "^---$"; then
    echo "Missing frontmatter: $f"
  fi
done
```

### Extract Frontmatter Fields

```bash
# Extract name field
head -20 "[file]" | grep "^name:" | cut -d: -f2 | xargs

# Extract status field
head -20 "[file]" | grep "^status:" | cut -d: -f2 | xargs

# Extract all frontmatter
sed -n '/^---$/,/^---$/p' "[file]"
```

### Validate Name Matches Directory

```bash
# Check skill name matches directory name
for dir in "[role]/skills/*/"; do
  dirname=$(basename "$dir")
  name=$(head -10 "$dir/SKILL.md" | grep "^name:" | cut -d: -f2 | xargs)
  if [ "$dirname" != "$name" ]; then
    echo "Mismatch: directory '$dirname' vs name '$name'"
  fi
done
```

### Validate Status Values

```bash
# Check for invalid status values in skills
valid_statuses="ideating|establishing|practicing|established|paused|retired"
grep -r "^status:" "[role]/skills/" | while read line; do
  status=$(echo "$line" | cut -d: -f3 | xargs)
  if ! echo "$status" | grep -qE "^($valid_statuses)$"; then
    echo "Invalid status '$status' in: $line"
  fi
done
```

### Check Required Fields

```bash
# Check HABIT.md has required fields
for f in $(find "[role]/habits" -name "HABIT.md"); do
  missing=""
  head -20 "$f" | grep -q "^name:" || missing="$missing name"
  head -20 "$f" | grep -q "^frequency:" || missing="$missing frequency"
  head -20 "$f" | grep -q "^timing:" || missing="$missing timing"
  head -20 "$f" | grep -q "^status:" || missing="$missing status"
  [ -n "$missing" ] && echo "Missing in $f:$missing"
done
```

---

## Migration Verification Commands

### Line Count Comparison

```bash
# Count lines in source vs destination
wc -l "[source-file]"
wc -l "[dest-file]"

# Git diff line count (after commit)
git diff --stat [baseline]..HEAD
```

### High-Value Content Detection

```bash
# Find URLs (must be preserved)
grep -n "https\?://" "[file]"

# Find #id: markers (must be preserved)
grep -n "#id:" "[file]"

# Find dates (temporal context)
grep -nE ">20[0-9]{2}|202[0-9]-[0-9]{2}" "[file]"

# Find TODOs (action items)
grep -ni "TODO" "[file]"

# All high-value markers in one command
grep -nE "#id:|https?://|>20[0-9]{2}|TODO" "[file]"
```

### Orphaned Content Detection

```bash
# Files outside standard directories
find "[role]/" -type f -name "*.md" | grep -v -E "(skills|habits|processes|artifacts|knowledge|decisions|expectations|initiatives)/"

# Files at root level (should only be Overview.md, Responsibilities.md)
ls "[role]/"*.md 2>/dev/null | grep -v -E "(Overview|Responsibilities)\.md"
```

### Cross-Reference Detection

```bash
# Find references to a role being archived
grep -rn "The [Role Name]" "[personalbook]/"
grep -rn "[role-directory-name]" "[personalbook]/"

# Find references to a skill being extracted
grep -rn "[skill-name]" "[role]/"
```

---

## Directory Structure Validation

### Required Files

| Role Type | Required Files |
|-----------|----------------|
| All roles | `Overview.md` |
| All roles | `Responsibilities.md` |

### Required Directories (Self-Development)

| Directory | When Required |
|-----------|---------------|
| `skills/` | If role has reusable processes |
| `habits/` | **Always** (even if only ideating status) |
| `artifacts/` | If role produces personal outcomes |
| `knowledge/` | If role requires domain learning |
| `decisions/` | If role involves major choices |
| `expectations/` | If role has standards to embody |

### Required Directories (Technical)

| Directory | When Required |
|-----------|---------------|
| `skills/` | If role has SOPs/runbooks |
| `processes/` | If role has regular workflows |
| `artifacts/` | If role produces notes/journals |
| `knowledge/` | If role requires domain learning |
| `initiatives/` | If role has multi-month projects |

### Check Structure

```bash
# List role structure
find "[role]/" -type d | head -20

# Check for required files
[ -f "[role]/Overview.md" ] && echo "✓ Overview.md" || echo "✗ Overview.md"
[ -f "[role]/Responsibilities.md" ] && echo "✓ Responsibilities.md" || echo "✗ Responsibilities.md"

# Check habits directory exists
[ -d "[role]/habits" ] && echo "✓ habits/" || echo "✗ habits/ (required)"
```

---

## Quick Reference: Content Type → Destination

| Content Type | Destination | Frontmatter |
|--------------|-------------|-------------|
| Reusable how-to | `skills/[name]/SKILL.md` | name, status |
| Regular practice | `habits/[name]/HABIT.md` | name, frequency, timing, status |
| Personal outcomes | `artifacts/[name].md` | intent, habits |
| Prerequisite info | `knowledge/[topic].md` | topic, status: reference |
| Major choices | `decisions/[name]/` | (directory with Overview.md) |
| Standards to embody | `expectations/[name].md` | source, observed |
| Multi-month projects | `initiatives/[name]/` | status, started |
