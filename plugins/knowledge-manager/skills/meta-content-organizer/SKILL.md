---
name: meta-content-organizer
description: "Meta-prompt generator that analyzes a target directory (structure, existing templates, naming patterns) and generates a custom, self-healing content-organizer prompt tailored to that directory. Use when asked to generate a content organizer, build a custom organization prompt for a directory, create a meta-prompt for filing content, or design self-healing routing rules for a folder (e.g. a NotePlan notes vault, a research archive, a projects directory)."
---

# Meta Content Organizer

You are a meta-prompt generator. Your role is to analyze a target directory the user supplies — its structure, existing templates, and naming patterns — and produce a single, ready-to-use content-organizer prompt tailored to that directory. The generated prompt teaches a future assistant how to file new content into the right place, in the right format, with self-healing rules that adapt as the directory evolves.

## Objective

Given a target directory, content domain, and organization goals, output a custom organizer prompt that contains: a domain-specific introduction, a complete content index, template integration, smart routing rules, cross-directory pattern mapping, and a self-healing execution protocol — all derived from the actual directory, with zero hardcoded paths beyond the ones the user provides.

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Gather target inputs", description: "Get target directory, content domain, organization goals, template location", activeForm: "Gathering inputs" })
TaskCreate({ subject: "Analyze directory structure", description: "Scan tree, file types, counts, naming patterns, existing organization and inconsistencies", activeForm: "Analyzing structure" })
TaskCreate({ subject: "Discover templates and patterns", description: "Find templates, infer variables, recognize content categories and cross-directory relationships", activeForm: "Discovering templates" })
TaskCreate({ subject: "Generate organizer prompt", description: "Assemble custom self-healing organizer from guides/generated-prompt-template.md", activeForm: "Generating organizer" })
TaskCreate({ subject: "Validate and deliver", description: "Confirm index covers all content, routing covers all types, no hardcoded paths leaked; write output", activeForm: "Validating and delivering" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
TaskUpdate({ taskId: "5", addBlockedBy: ["4"] })
```

Set each task to `in_progress` when starting and `completed` when done.

## Git Safety (MANDATORY — this skill writes files)

This skill writes a generated organizer prompt file. If it lands in a git repo: run `git status`; if dirty, offer to commit a baseline. Record the current commit as `CHECKPOINT`. After writing, run `git diff CHECKPOINT` and confirm only the generated prompt file was added. If unexpected changes appear, stop and report before committing.

## Your Workflow

### Phase 1: Gather Target Inputs

Collect the three things you cannot infer. If the user already supplied them, skip the question.

```javascript
AskUserQuestion({
  questions: [
    {
      question: "What directory should the organizer manage?",
      header: "Target dir",
      options: [
        { label: "Provide a path now", description: "I'll give the absolute path to the folder to organize" },
        { label: "Use current directory", description: "Organize the directory we're working in" }
      ],
      multiSelect: false
    },
    {
      question: "Where do reusable templates live, if anywhere?",
      header: "Templates",
      options: [
        { label: "A template folder", description: "Point me at a folder of templates (e.g. a NotePlan @Templates folder, a _templates dir)" },
        { label: "No templates yet", description: "There are no templates; suggest where they'd help" }
      ],
      multiSelect: false
    },
    {
      question: "What is the content domain and primary goal?",
      header: "Domain/goal",
      options: [
        { label: "Describe it", description: "e.g. research archive, personal projects, work notes — and what good organization looks like" }
      ],
      multiSelect: false
    }
  ]
})
```

Record: target directory (absolute path), content domain, organization goals, and template location (or note its absence).

Mark Task 1 `completed`.

### Phase 2: Analyze Directory Structure

Scan the target directory and all subdirectories. Capture:

- **Tree and file types** — directory layout, file extensions, what kind of content each area holds
- **Counts and distribution** — files per directory; where content concentrates vs. where it is sparse
- **Naming patterns** — date prefixes, kebab/snake/camel case, tag conventions, ID schemes
- **Existing organization** — implicit themes, workstreams, or categories already in use
- **Inconsistencies** — misfiled content, competing conventions, duplicate-purpose folders

Use shell listing and a recursive scan. Do not read every file — sample representative files per directory to infer purpose.

Mark Task 2 `completed`.

### Phase 3: Discover Templates and Patterns

1. **Template discovery** — if a template location was given, scan it. For each template, infer its variables and the content type it serves. Match templates to the content categories found in Phase 2. Flag recurring content patterns that have no template yet as template-creation opportunities.
2. **Pattern recognition** — name the content categories, recurring themes, and workstreams. Map relationships between directories (which areas feed which, which are siblings).
3. **Self-healing design** — decide the smart routing rules (content signal -> destination), the theme/workstream mapping, the detection triggers for new content, and the classification logic that will let the generated prompt evolve itself.

Mark Task 3 `completed`.

### Phase 4: Generate the Organizer Prompt

Assemble the custom organizer using the structure in `guides/generated-prompt-template.md`. Fill every section with findings from Phases 2-3 — the generated prompt must reflect *this* directory, not a generic example. The output is a self-contained prompt the user can run on its own.

Mark Task 4 `completed`.

### Phase 5: Validate and Deliver

Run the validation checks (see Success Criteria), fix anything that fails, then confirm where to write the output.

```javascript
AskUserQuestion({
  questions: [{
    question: "Where should I save the generated organizer prompt?",
    header: "Output",
    options: [
      { label: "Inside the target directory", description: "Save as organize-<domain>.md within the folder being organized" },
      { label: "Specify a path", description: "I'll give a different location for the prompt file" },
      { label: "Display only", description: "Show it in the conversation; I'll save it myself" }
    ],
    multiSelect: false
  }]
})
```

Write the file (naming convention: `organize-<domain>.md`, kebab-case domain), then present a short summary: directories indexed, templates integrated, routing rules created, and any template-creation opportunities flagged.

Mark Task 5 `completed`.

## Success Criteria

- [ ] Target directory, domain, and goals captured from the user (never assumed)
- [ ] Full directory tree analyzed with file counts and naming patterns recorded
- [ ] Every existing template discovered, with inferred variables and matched content types
- [ ] Generated prompt includes all six components: domain intro, content index, template integration, smart routing, pattern mapping, self-healing execution
- [ ] Routing rules cover every content type found; the index covers every directory
- [ ] Output contains only paths the user supplied — no hardcoded or personal paths leaked
- [ ] Output written to the agreed location with a delivery summary

## Common Mistakes to Avoid

1. **Generating a generic template** — the whole point is a *tailored* prompt; every section must cite real directories, counts, and patterns from the analysis
2. **Leaking hardcoded paths** — never bake in absolute paths, app-specific containers, or personal folder names; use only the directory the user provides
3. **Skipping template discovery** — if a template folder exists and you ignore it, the organizer won't route content into the right format
4. **Routing gaps** — content types found in analysis but absent from the routing rules will be misfiled; audit coverage before delivering
5. **Omitting self-healing** — without detection triggers and an evolution protocol, the organizer goes stale the moment the directory changes
6. **Reading every file** — sample to infer purpose; exhaustive reading wastes the budget without improving the index
