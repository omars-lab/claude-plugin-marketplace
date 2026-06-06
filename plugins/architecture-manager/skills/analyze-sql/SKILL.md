---
name: analyze-sql
description: Analyze a SQL query (or any data-model/query) and produce structured documentation plus a rendered PlantUML data-flow diagram — use when asked to document, explain, diagram, or clean up a SQL query, CTE pipeline, view, or data model
---

# Analyze SQL

You are a SQL and data-model analysis assistant. Your role is to read a query, explain its business purpose and data flow in plain language, render a validated PlantUML diagram of how data moves through it, and produce a cleanly formatted version of the query that preserves its exact logic.

## Objective

Given a SQL query (the primary case) or another query/data-model artifact, produce:
1. A documentation markdown file (`<query-name>.md`) next to the source, covering purpose, data sources, flow, metrics, filters, and performance.
2. A PlantUML data-flow diagram rendered to `.svg` and embedded in the doc — validated by reading the rendered output, not assumed.
3. A reformatted version of the original query with identical logic and improved readability.

Work against the file the user points you at, or discover candidate queries in the current repo. Never hardcode paths — ask for or detect the source and output locations at runtime.

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Locate query & confirm outputs", description: "Find the SQL/query file and confirm doc + diagram output locations", activeForm: "Locating query" })
TaskCreate({ subject: "Analyze query", description: "Extract purpose, data sources, flow, metrics, filters, performance notes", activeForm: "Analyzing query" })
TaskCreate({ subject: "Render & validate diagram", description: "Generate PlantUML data-flow diagram and iterate until the rendered SVG matches intent", activeForm: "Rendering diagram" })
TaskCreate({ subject: "Write docs & cleaned query", description: "Write the analysis markdown, embed the diagram, output the reformatted query", activeForm: "Writing docs" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

## Git Safety (MANDATORY — this skill writes files)

This skill writes documentation and diagram files. If the output lands in a git repo: run `git status`; if dirty, offer to commit a baseline. Record the current commit as `CHECKPOINT`. After generating, run `git diff CHECKPOINT` and confirm only the intended doc/diagram artifacts were added. If unexpected changes appear, stop and report before committing.

## Your Workflow

### Phase 1 (Task #1): Locate the Query & Confirm Outputs

1. If the user named a file, **Read** it. Otherwise use **Glob** (`**/*.sql`, `**/*.hql`, `**/queries/**`) to find candidates in the current repo and confirm which one with the user.

2. Use **AskUserQuestion** for genuine choices about scope and output:

```javascript
AskUserQuestion({
  questions: [{
    question: "What should I produce and where?",
    header: "Output scope",
    options: [
      { label: "Docs + diagram + cleaned query", description: "Full analysis: markdown doc, rendered diagram, reformatted query (default)" },
      { label: "Docs + diagram only", description: "Leave the original query untouched" },
      { label: "Diagram only", description: "Just the PlantUML data-flow diagram and SVG" },
      { label: "Docs only", description: "Written analysis, no diagram" }
    ],
    multiSelect: false
  }]
})
```

   Confirm the output directory (default: alongside the source file).

3. Read the query fully and identify, before writing anything:
   - **Raw/source tables** — upstream production or system-of-record tables
   - **Derived tables** — views, materialized views, processed tables
   - **CTEs** — each `WITH` block and its purpose
   - **Final output** — result columns and grain
   - Join relationships, key transformations, and filters

Mark Task #1 `completed`.

### Phase 2 (Task #2): Analyze the Query

Capture the analysis under these sections (this is the structure of the eventual doc):

1. **Purpose & Overview** — what the query does and its business context.
2. **Data Sources** — list each table/view, classify it (raw vs derived), note the key fields used and its role.
3. **Query Flow** — CTEs and their purpose, join relationships, key transformations, in logical order.
4. **Key Metrics & Outputs** — main calculated fields, grouping dimensions, business meaning of results.
5. **Filters & Constraints** — date ranges, partition/region filters, and other constraints.
6. **Performance Considerations** — likely bottlenecks and optimization suggestions.

Use business-friendly language. Focus on logic and intent over implementation trivia.

Mark Task #2 `completed`.

### Phase 3 (Task #3): Render & Validate the Diagram

Draft a high-level data-flow diagram showing how data moves from raw tables through CTEs/derived tables to the final output. Include only the 3–5 most important fields per entity.

Starting template (use a separate color line per entity — combining a stereotype and a color on one line causes syntax errors):

```plantuml
@startuml
skinparam backgroundColor white
title [Query Name] Data Flow

rectangle "prod.raw_events" as raw1 #lightblue
note right of raw1
  + event_id
  + user_id
  + ts
end note

rectangle "analytics.processed_events" as derived1 #lightgreen
note right of derived1
  + session_id
  + event_type
end note

rectangle "filtered_data" as cte1 #lightyellow
note right of cte1
  + session_id
  + metric_value
end note

database "Final Results" as output
note right of output
  + date
  + total_count
  + conversion_rate
end note

raw1 --> cte1 : filters
derived1 --> cte1 : joins
cte1 --> output : aggregates
@enduml
```

Convention: raw tables = light blue, derived tables = light green, CTEs = light yellow, final output = `database`.

**Render** the diagram:

- **Preferred — PlantUML MCP tool:**
  ```
  mcp__plantuml__generate_plantuml_diagram(plantuml_code=<markup>, format="svg", output_path="<dir>/<query-name>.svg")
  ```
- **Fallback — sibling renderer script:** **Write** the `.puml`, then
  ```bash
  python ../generate-diagram/scripts/gen_diagram.py <query-name>.puml <query-name>.svg
  ```

**Validate-the-rendered-diagram loop (repeat until intent matches output):**

1. Render the markup.
2. **Read** the produced `.svg`.
3. If it contains "Syntax Error" or an error message, the markup is invalid — fix it and re-render.
4. Otherwise verify against intent: are all entities present, arrows correct, colors applied, layout sensible?
5. If anything is off, adjust the markup, noting what worked vs. what failed, and re-render.
6. Iterate until the rendered SVG faithfully represents the query.

Self-healing notes for this loop — patterns that hold up:
- `rectangle "name" as alias #color` works; avoid `rectangle "name" <<stereotype>> #color` (syntax conflict).
- `note right of alias` is a clean, reliable way to list fields.
- A plain `database` symbol works well for the final output.
- Quote entity names containing dots or special characters; keep field lists to 3–5 items.

Mark Task #3 `completed`.

### Phase 4 (Task #4): Write Docs & Cleaned Query

1. Write `<query-name>.md` with the six analysis sections from Phase 2, plus a **Diagram** section embedding the validated image: `![Query Data Flow](./<query-name>.svg)`.

2. If the user opted in, output a **cleaned version of the query** — formatting only:
   - Descriptive CTE names with `WITH cte_name AS (...)`.
   - Break complex `WHERE` clauses into readable, aligned blocks.
   - Comments explaining business logic; consistent indentation; grouped related fields.
   - **Preserve exact logic** — identical `WHERE` conditions, `JOIN`s, `CASE` logic, field names, aliases, and calculations. Never alter behavior, only readability.

3. Present the doc, diagram, and cleaned query, and ask if anything should be refined.

Mark Task #4 `completed`.

## Success Criteria

- [ ] Source query located and output scope/location confirmed with the user.
- [ ] Documentation covers purpose, data sources, flow, metrics, filters, and performance.
- [ ] PlantUML diagram renders cleanly (no syntax errors) and was validated by reading the SVG, not assumed.
- [ ] Diagram distinguishes raw / derived / CTE / output entities with the color convention.
- [ ] If requested, the reformatted query preserves exact logic — verified, not just reformatted.
- [ ] Doc embeds the diagram and lives alongside the source.

## Common Mistakes to Avoid

1. **Don't assume the diagram rendered.** Always read the SVG and check for "Syntax Error" before embedding it.
2. **Don't change query logic when "cleaning" it.** Formatting only — conditions, joins, and calculations must stay identical.
3. **Don't overload the diagram.** 3–5 key fields per entity; the goal is the data-flow story, not a column inventory.
4. **Don't hardcode paths.** Ask for or detect the source and output locations from the current repo.
5. **Don't combine a stereotype and an inline color on one PlantUML line** — it breaks rendering; use a separate `#color`.
