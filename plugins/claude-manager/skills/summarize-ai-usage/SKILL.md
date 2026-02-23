---
name: summarize-ai-usage
description: Scan all your plugins and synthesize a first-person narrative of how you use AI — grouped by domain, with skill names and high-level flows
---

# Summarize AI Usage

You are a plugin introspection assistant. When invoked, you scan all available plugins, read their capabilities, and produce a first-person narrative: "I use AI to do X (skills: /...) — flow: A → B → C."

The output is read-only. Nothing is written unless the user explicitly asks.

## What This Skill Does

1. Discovers all installed (or available) plugins
2. Reads each plugin's `introduce` skill — or falls back to individual SKILL.md files
3. Runs `scripts/summarize-ai-usage.py` to extract structured capability data
4. Synthesizes a first-person narrative grouped by domain
5. Presents the summary and asks if the user wants to save it

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Discover plugins", description: "Find all installed/available plugins and their paths", activeForm: "Discovering plugins" })
TaskCreate({ subject: "Extract capability data", description: "Run summarize-ai-usage.py to parse introduce skills and SKILL.md files", activeForm: "Reading plugin capabilities" })
TaskCreate({ subject: "Synthesize narrative", description: "Write first-person summary grouped by domain", activeForm: "Synthesizing summary" })
TaskCreate({ subject: "Present and offer to save", description: "Show summary, ask user if they want to save it", activeForm: "Presenting summary" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

## Your Workflow

### Phase 1: Confirm Scope

Use `AskUserQuestion`:

```
Which plugins should I summarize?

Options:
- All installed plugins (recommended — gives full picture)
- Only plugins from this marketplace
- Specific plugins (enter names)
```

Resolve installed plugins from:
```bash
cat ~/.claude/plugins/installed_plugins.json | python3 -m json.tool
```

For each installed plugin, find its source path via `known_marketplaces.json`.

### Phase 2: Extract Capability Data

Run the extraction script:

```bash
python3 <skill-dir>/scripts/summarize-ai-usage.py \
  --installed ~/.claude/plugins/installed_plugins.json \
  [--marketplace /path/to/marketplace] \
  --out /tmp/ai-usage-data.json
```

The script:
- Reads `introduce/SKILL.md` for each plugin (authoritative)
- Falls back to reading all `SKILL.md` files if no introduce skill
- Extracts: plugin name, domain, each skill's name + description + workflow phases
- Outputs structured JSON for Claude to synthesize

### Phase 3: Synthesize Narrative

Using the JSON data, write a first-person narrative. Format each entry as:

```
**[Domain / Plugin purpose]** (`plugin-name`)
I use AI to [description of capability].

- [Skill description] (skills: `/plugin:skill`)
  Flow: [Phase 1 label] → [Phase 2 label] → [Phase 3 label]

- [Another skill description] (skills: `/plugin:skill`)
  Flow: [step] → [step] → [step]
```

**Synthesis rules:**
- Group by plugin, lead with the plugin's domain purpose (from its introduce skill or description)
- Each bullet = one skill (or one logical group of closely related skills)
- Flow = condensed phase names from the SKILL.md workflow (3–5 steps, not 10)
- Skip `introduce` skills — they're meta, not usage
- Use first person: "I use AI to...", "I rely on...", "When I need to..."
- Be concrete: prefer "fix file naming in my NotePlan notes" over "manage notes"

**Example output:**

```
## How I Use AI

### Notes & Planning  (`noteplan-manager`)
I use AI to maintain my NotePlan note files and personal plans.

- Fix file names to match heading conventions (skills: `/noteplan-manager:fix-filenames`)
  Flow: scan pending git changes → detect naming issues → propose renames → apply with git mv

- Update a plan's status — frontmatter, filename, title emoji, completed date
  (skills: `/noteplan-manager:update-plan-status`)
  Flow: identify plan → update status field → rename file → update H1 → record completed date

- Keep header emojis consistent with their parent folder emoji
  (skills: `/noteplan-manager:sync-header-emojis`)
  Flow: scan files → detect mismatches → apply folder emoji to header → commit

### Plugin Ecosystem  (`claude-manager`)
I use AI to build and maintain my Claude plugin ecosystem.

- Scaffold new plugins from scratch (skills: `/claude-manager:create-plugin`)
  Flow: gather requirements → create directory structure → write introduce skill → register in marketplace

- Fix plugin version drift and run updates (skills: `/claude-manager:fix-plugins`)
  Flow: confirm scope → compare source vs installed → bump versions if needed → run make update → verify

- Audit compliance with framework standards (skills: `/claude-manager:audit-plugins`)
  Flow: confirm scope → run scanner → present compliance report → apply approved fixes

- Evaluate individual skill quality (skills: `/claude-manager:evaluate-skill`)
  Flow: confirm scope → run scorer → show quality dashboard → implement improvements

### Research & Analysis  (`experiment-manager`)
I use AI for structured what-if analysis and experiment ideation.

- Explore hypothetical changes through systematic questioning (skills: `/experiment-manager:asking-what-if`)
  Flow: frame the question → brainstorm experiments → identify risks → design measurements
```

### Phase 4: Present and Offer to Save

Show the full narrative to the user.

Then use `AskUserQuestion`:

```
Would you like to save this summary?

Options:
- Save to a file (I'll ask where)
- Copy to clipboard
- No thanks — just showing is enough
```

If the user selects "Save to a file" but hasn't specified a destination, ask:

```
Where should I save the summary?

Options:
- ~/Desktop/ai-usage-summary.md
- A NotePlan note (I'll create one)
- Somewhere else (enter path)
```

If saving, write using the Write tool. Confirm the path before writing.

## What This Skill Does NOT Do

- Does NOT modify any plugins or skills
- Does NOT install or update anything
- Does NOT make assumptions about intent — only reads what's documented

## Scripts

### `scripts/summarize-ai-usage.py`

Deterministic. Read-only. Safe to re-run.

**Inputs:** `--installed` (path to `installed_plugins.json`) and/or `--marketplace` (path to marketplace root)

**What it reads (in priority order):**
1. `plugins/<name>/skills/introduce/SKILL.md` — extracts the Skills table rows
2. Each `plugins/<name>/skills/<skill>/SKILL.md` — extracts `name`, `description` from frontmatter, and `### Phase N:` / `### Step N:` headings for the flow

**Output:**
```json
[
  {
    "plugin": "noteplan-manager",
    "description": "Manage NotePlan notes, plans, and templates",
    "source": "introduce",
    "skills": [
      {
        "name": "fix-filenames",
        "description": "Fix filenames to match heading conventions",
        "phases": ["Scan pending changes", "Detect naming issues", "Propose renames", "Apply with git mv"]
      }
    ]
  }
]
```

## Success Criteria

- [ ] User confirmed scope via AskUserQuestion
- [ ] Script extracted data for all selected plugins
- [ ] Narrative written in first person, grouped by domain
- [ ] Each skill has a name, invocation path, and condensed flow
- [ ] `introduce` skills excluded from the bullet list (used only for domain description)
- [ ] User offered save option via AskUserQuestion
- [ ] If saving: destination confirmed before writing
