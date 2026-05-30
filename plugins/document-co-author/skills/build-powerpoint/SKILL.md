---
name: build-powerpoint
description: Build a branded PowerPoint deck from a YAML content spec using a corporate template — separating content from rendering for prompt-driven iteration
---

# Build PowerPoint

Build or iterate on a branded PowerPoint deck. Content lives in a YAML spec file; a Python renderer reads the spec and produces the `.pptx`. To make changes, you edit the spec and re-render — no code changes, no hunting through scripts.

## Core Pattern

```
deck-spec.yaml            ← lives with the project; you describe what goes on each slide
      ↓
skills/build-powerpoint/
  scripts/render_deck.py  ← lives in the skill; shared renderer; never changes for content updates
      ↓
output.pptx               ← always regenerated; never edit directly
```

**Renderer location:** `render_deck.py` is part of this skill, not the project. Reference it by its installed path:

```bash
python3 ~/.claude/plugins/document-co-author/skills/build-powerpoint/scripts/render_deck.py deck_spec.yaml
```

Or using the plugin marketplace path directly:

```bash
python3 <marketplace>/plugins/document-co-author/skills/build-powerpoint/scripts/render_deck.py deck_spec.yaml
```

**Iteration loop:** User says "change the Tier 1 slide title" → Claude edits `deck_spec.yaml` → re-runs the renderer → new `.pptx` saved.

## Phase 1 — Gather Requirements

Use `TaskCreate` to track progress, then ask:

```
AskUserQuestion({
  questions: [
    {
      question: "Do you have an existing deck spec to iterate on, or are we starting fresh?",
      header: "Starting point",
      options: [
        { label: "Starting fresh", description: "I'll help you define the content and generate both the spec and renderer" },
        { label: "Existing spec", description: "Tell me the path to deck_spec.yaml and what you want to change" }
      ]
    },
    {
      question: "What corporate template should we use?",
      header: "Template",
      options: [
        { label: "ServiceNow template", description: "Use the SN branded .pptx template (AI_Strategy or AXIS Success Stories)" },
        { label: "Other template", description: "Provide a path to your .pptx template file" },
        { label: "No template", description: "Generate a plain deck without a branded template" }
      ]
    }
  ]
})
```

## Phase 2 — Inspect Template Layouts (new decks only)

If building fresh, inspect the template to discover available slide layouts and their placeholder indices. Run:

```python
from pptx import Presentation
prs = Presentation("<template_path>")
for i, layout in enumerate(prs.slide_layouts):
    print(f"{i}: {layout.name}")
    for ph in layout.placeholders:
        print(f"  ph idx={ph.placeholder_format.idx} name='{ph.name}'")
```

Document the layouts relevant to the deck:

| Layout idx | Name | Placeholders |
|-----------|------|-------------|
| 0 | Cover Green | idx=0 (title), idx=10 (subtitle), idx=11 (date) |
| 10 | Title Only | idx=0 (title), idx=11 (footer) |
| 13 | Title and Content | idx=0, idx=13 (subtitle), idx=16 (body) |
| 15 | Title with Two Columns | idx=0, idx=1, idx=16/17 (col headers), idx=18/19 (col bodies) |
| 25 | Divider Green | idx=0 (title), idx=1 (subtitle) |
| 47 | Thank You Blue | idx=0 (title) |

## Phase 3 — Build or Update the Content Spec

The spec is a YAML file with two sections: metadata and a `slides` list.

### Spec schema

```yaml
title: "Deck Title"
template: "/path/to/template.pptx"
output: "/path/to/output.pptx"

slides:
  - type: cover_green
    title: "Main Title\nSecond Line"
    subtitle: "Subtitle text"
    date: "Context string | Date"

  - type: divider_green          # or divider_blue
    title: "Section Title"
    subtitle: "Section description"

  - type: title_content
    title: "Slide Title"
    subtitle: "Optional subtitle"
    bullets:
      - "Simple bullet"
      - ["Bold label", "rest of sentence after the label"]

  - type: two_column
    title: "Slide Title"
    subtitle: "Optional subtitle"
    left_header: "LEFT COL HEADER"
    left_bullets:
      - ["Label:", "description"]
    right_header: "RIGHT COL HEADER"
    right_bullets:
      - ["Label:", "description"]

  - type: scoring_table          # table with: #, Tier, Name, What-to-Assess, Weight, Score
    title: "Table Slide Title"
    subtitle: "Optional subtitle"
    criteria:
      - id: C1
        tier: 1                  # 1=Critical, 2=High Priority, 3=Important, 4=Strategic
        weight: "×4"
        name: "Criterion Name"
        assess: "What to assess in 1-2 sentences"

  - type: scoring_table_with_rubric   # scoring_table + scoring guide panel on the right
    title: "Table Slide Title"
    subtitle: "Optional subtitle"
    criteria: [...]              # same as scoring_table
    rubric:
      title: "Scoring Guide"
      rows:
        - score: "3"
          meaning: "Fully meets"
          detail: "Native support, no workarounds"
      weights:
        - tier: "Tier 1 (C1–C5)"
          weight: "×4"
          max: "60 pts"

  - type: thank_you_blue
    title: "Closing Title"
    next_steps:
      - "Step 1 text"
      - "Step 2 text"
```

### When iterating on an existing spec

1. Read the current `deck_spec.yaml` with the Read tool
2. Apply the requested change (edit title, add bullet, reorder slides, add new slide)
3. Write the updated spec with the Edit or Write tool
4. Re-run the renderer

## Phase 4 — Build or Update the Renderer

### If the renderer doesn't exist yet

Generate `render_deck.py` alongside the spec. The renderer must:

- Load the spec with `yaml.safe_load()`
- Call `clear_slides(prs)` to remove template's existing slides
- Dispatch each slide to a `render_<type>(prs, spec, slide_def)` function
- Map ServiceNow brand colors as constants (not inline hex)
- Save to `spec["output"]`

### If the renderer already exists

The renderer only needs updating when:
- A new `type:` is introduced that has no corresponding `render_<type>` function
- A table column layout changes significantly
- Brand colors or layout indices need updating

**Do not edit the renderer for content changes** — that's what the spec is for.

### Standard brand colors (ServiceNow)

```python
SN_TEAL      = RGBColor(0x00, 0xC7, 0xB1)
SN_NAVY      = RGBColor(0x29, 0x3E, 0x40)
SN_ORANGE    = RGBColor(0xF2, 0x6B, 0x43)
SN_WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
SN_LIGHT     = RGBColor(0xF5, 0xF5, 0xF5)
SN_DARK_GRAY = RGBColor(0x44, 0x44, 0x44)

TIER_COLORS  = {
    1: RGBColor(0xD6, 0x3B, 0x2F),   # critical — red
    2: RGBColor(0xF2, 0x6B, 0x43),   # high priority — orange
    3: RGBColor(0x00, 0x8B, 0x8B),   # important — teal
    4: RGBColor(0x5B, 0x7B, 0x8C),   # strategic — slate
}
```

## Phase 5 — Render and Verify

```bash
python3 ~/.claude/plugins/document-co-author/skills/build-powerpoint/scripts/render_deck.py <project>.deck_spec.yaml
```

The renderer runs two automatic validation passes on every render:

**Pre-render (spec validation):**
- All required top-level keys present (`template`, `output`, `slides`)
- Template file exists on disk
- Output directory exists
- All slide `type:` values are registered in `RENDERERS`
- Required fields per slide type are present

**Post-render (output validation):**
- Output file exists and is non-zero size
- No duplicate zip entries (the root cause of broken PPTX — see below)
- Slide count matches expected

Both passes exit with a clear error message on failure. Fix the reported issue, re-render.

If the output still looks wrong after validation passes, check:
1. Placeholder idx mismatch — re-inspect the layout with the inspection script
2. Text overflow — reduce font size in the renderer for that slide type
3. Table row height — adjust `Inches()` values in the renderer

### Extending Validation

Validations live in two functions in `render_deck.py`:

| Function | When it runs | How to extend |
|----------|-------------|---------------|
| `validate_spec()` | Before rendering | Add to `REQUIRED_SPEC_KEYS`, `REQUIRED_SLIDE_FIELDS`, or the loop body |
| `validate_output()` | After saving | Append a new check block; print a clear repair hint |

**Pattern for adding a new repair situation:**

When you discover a new failure mode (e.g. missing media, corrupt content types):
1. Reproduce the failure, identify what distinguishes the broken file from a clean one
2. Add a check in `validate_output()` that detects the symptom — include a `Root cause:` and `Fix:` comment
3. If it's also detectable in existing files (not just freshly rendered ones), add it to `check_needs_repair()` too
4. Update the docstrings in both functions to document the new case

**Known repair situations:**

| Symptom | Root cause | Fix |
|---------|-----------|-----|
| `UserWarning: Duplicate name: 'ppt/slides/slide1.xml'` | `clear_slides()` removed `<sldId>` XML but not the OPC relationship → old part stays in package graph → `next_slide_partname` reuses `slide1.xml` | `prs.part.drop_rel(rId)` before `xml_slides.remove(sld_id)` |

### Checking if an Existing File Needs Repair

To check a `.pptx` file without opening PowerPoint:

```bash
python3 ~/.claude/plugins/document-co-author/skills/build-powerpoint/scripts/render_deck.py --check-repair path/to/file.pptx
```

Returns exit code `0` (healthy) or `1` (needs repair). Prints a diagnosis including:
- Duplicate zip entries
- Unresolvable slide relationships (sldIdLst rId → part not found in zip)

Use this to audit a batch of files or verify a repaired file before distributing.

## Phase 6 — Iteration

When the user requests a change, determine what type it is:

| Change type | Action |
|-------------|--------|
| Edit slide text / bullets | Edit `deck_spec.yaml`, re-render |
| Add / remove a slide | Edit `deck_spec.yaml` slides list, re-render |
| Reorder slides | Reorder entries in `deck_spec.yaml`, re-render |
| Add a new slide type | Add `render_<type>()` to renderer, add entry to `RENDERERS` dict, update spec schema docs |
| Change brand colors / fonts | Edit renderer constants, re-render all slides |

**Key discipline:** The spec is always the source of truth. Never suggest editing the PPTX directly.

## Phase 5.5 — Create a Run Script

After first render, create a `<name>.command` file alongside the spec and output. On macOS, double-clicking a `.command` file in Finder opens Terminal and executes it — no code editor needed to re-render after a YAML edit.

```bash
#!/bin/zsh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPEC="$SCRIPT_DIR/<name>.deck_spec.yaml"
RENDERER="<marketplace>/plugins/document-co-author/skills/build-powerpoint/scripts/render_deck.py"

echo "Rendering..."
python3 "$RENDERER" "$SPEC"

if [ $? -eq 0 ]; then
    open "$SCRIPT_DIR/<name>.pptx"
else
    echo "✗ Render failed"
fi
```

Then make it executable:
```bash
chmod +x <name>.command
```

The file must be `chmod +x` or macOS will refuse to run it. The `.command` extension is what triggers Terminal to open it on double-click — `.sh` files do not behave this way by default.

## Deliverables

At the end of each run, the user has:

| File | Purpose |
|------|---------|
| `<name>.deck_spec.yaml` | Editable content source — prompt against this for all future changes. Named after the output artifact (e.g. `AXIS-Scoring-Criteria.deck_spec.yaml` produces `AXIS-Scoring-Criteria.pptx`). |
| `skills/build-powerpoint/scripts/render_deck.py` | Renderer in the skill dir — only changes when new slide types are needed; never copy alongside outputs. |
| `<name>.pptx` | Generated deck — share or present this; never edit directly. |

**Naming convention:** spec and output share a base name. `Foo.deck_spec.yaml` → `Foo.pptx`. This prevents collision when multiple decks live in the same folder.

## Common Iteration Requests and How to Handle Them

| User says | Claude does |
|-----------|------------|
| "Change the title on slide 2" | Edit `slides[1].title` in spec, re-render |
| "Add a bullet to the Tier 1 slide" | Edit `slides[1].criteria` or bullets in spec, re-render |
| "Move the scoring guide to its own slide" | Split `scoring_table_with_rubric` into two spec entries, re-render |
| "Add a new slide after the cover" | Insert new entry at `slides[1]` in spec, re-render |
| "Make the Tier 1 header dark navy instead of red" | Edit `TIER_COLORS[1]` in renderer, re-render |
| "Add a 'Thank You' slide at the end" | Add `type: thank_you_blue` entry at end of spec, re-render |
