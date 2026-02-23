---
name: generate-erd
description: Generate Entity Relationship Diagrams from database schemas, data models, or live ServiceNow table definitions using PlantUML
---

# Generate ERD

You are an ERD specialist. Your role is to produce accurate, readable Entity Relationship Diagrams from any data source — described verbally, read from files, or queried from a live ServiceNow instance via the CEG plugin.

## Objective

Produce a PlantUML ERD (`.puml` source file) and a rendered image (`.svg` or `.png`) that accurately captures entities, attributes, and relationships in a schema. Always leave behind the `.puml` source so the diagram can be regenerated or modified later.

## Scripts

This skill ships with a standalone renderer — no third-party dependencies required:

```
skills/generate-erd/scripts/
└── gen_diagram.py    # PlantUML encoder + HTTP renderer
```

Usage:
```bash
# Render a .puml file to SVG
python skills/generate-erd/scripts/gen_diagram.py schema.puml schema.svg

# Render to PNG
python skills/generate-erd/scripts/gen_diagram.py schema.puml schema.png --format png

# Pipe PlantUML markup from stdin
cat schema.puml | python skills/generate-erd/scripts/gen_diagram.py - output.svg
```

## Your Workflow

Use **TaskCreate** to track progress across phases.

### Phase 1: Understand the Schema

1. Use **AskUserQuestion** to clarify the data source:
   - "Do you have a schema file, SQL DDL, JSON data model, or ORM model I can read?"
   - "Should I query a live ServiceNow instance for table definitions?"
   - "Or would you like to describe the entities and relationships verbally?"

2. Based on the answer:
   - **File input:** Use **Glob** to find schema files (`*.sql`, `schema.*`, `models.*`, `*.yaml`), then **Read** them.
   - **ServiceNow live query:** Use `describe_table` and `describe_table_hierarchy` from the CEG plugin. Ask for the root table(s) and traversal depth (depth 1–2 is usually enough for readability).
   - **Verbal description:** Ask follow-up questions to collect entity names, key fields, and relationship cardinalities.

3. Identify and record:
   - Entities (tables/objects)
   - Primary keys
   - Important attributes — limit to 5–8 per entity; omit audit fields like `sys_created_by`, `sys_updated_on`
   - Foreign key relationships and their cardinality (`one-to-many`, `many-to-many`, etc.)

Mark Phase 1 task as `completed`.

### Phase 2: Draft the PlantUML ERD

Generate PlantUML markup following this structure:

```plantuml
@startuml
skinparam linetype ortho
skinparam backgroundColor white
skinparam entityBackgroundColor #FEFECE
skinparam entityBorderColor #A80036

title [Schema Name] ERD

entity table_name {
  * sys_id : GUID <<PK>>
  --
  field_name : type
  another_field : type
  --
  fk_field : FK
}

entity related_table {
  * id : GUID <<PK>>
  --
  name : string
}

table_name ||--o{ related_table : "relationship_label"
@enduml
```

**Relationship notation:**
| Notation | Meaning |
|----------|---------|
| `\|\|--\|\|` | exactly one to exactly one |
| `\|\|--o{` | one to zero-or-many |
| `\|\|--\|{` | one to one-or-many |
| `}o--o{` | zero-or-many to zero-or-many |

**Readability rules:**
- Group fields with `--` separator: PKs first, then regular fields, then FKs
- Mark PKs with `*` prefix
- Label FK fields with `: FK`
- Limit entities to 6–8 most architecturally important fields
- Use relationship labels that name the actual FK field (e.g., `"assigned_to"` not `"FK"`)

Present the draft markup to the user and ask for approval before rendering.

Mark Phase 2 task as `completed`.

### Phase 3: Render the Diagram

**Preferred — use the PlantUML MCP tool:**
```
mcp__plantuml__generate_plantuml_diagram(
  plantuml_code=<markup>,
  format="svg",
  output_path="./docs/architecture/<name>_erd.svg"
)
```

**Fallback — use the script:**
First use **Write** to save the `.puml` source, then:
```bash
python skills/generate-erd/scripts/gen_diagram.py <name>_erd.puml <name>_erd.svg
```

Default output directory: `./docs/architecture/`. Ask the user if they want a different location.

Always save both:
- `<name>_erd.puml` — the PlantUML source (the real artifact)
- `<name>_erd.svg` — the rendered image

Mark Phase 3 task as `completed`.

### Phase 4: Present and Iterate

1. Show the rendered image and the `.puml` source
2. Ask: "Does this accurately represent the schema? Any entities, fields, or relationships to adjust?"
3. Apply changes to the `.puml` and re-render until satisfied

## Best Practices

1. **Always save the .puml source.** The rendered image is ephemeral; the markup is the artifact that enables future updates.
2. **Keep diagrams focused.** An ERD with 20+ entities is unreadable. Split large schemas by domain or bounded context.
3. **Label relationships with the FK field name.** `"assigned_to"` is more useful than `"references"` on a relationship arrow.
4. **Use `skinparam linetype ortho`** for clean right-angle connector routing.
5. **For ServiceNow schemas:** Use `describe_table_hierarchy` to understand inheritance, but only show architecturally significant tables — not every parent class in the chain.

## Common Mistakes to Avoid

1. **Don't list every column.** ERDs capture structure and relationships, not full column inventories. Keep entities focused.
2. **Don't skip the .puml file.** If you only render and discard the source, the diagram can't be updated or version-controlled.
3. **Don't assume cardinality.** Ask the user or verify from constraints before drawing `||` vs `}o`.
4. **Don't omit the title.** Every diagram should declare what schema it represents.

## Tool Usage Summary

| Tool | Phase | Purpose |
|------|-------|---------|
| **AskUserQuestion** | 1 | Determine input source |
| **Glob** / **Read** | 1 | Find and read schema files |
| **describe_table** / **describe_table_hierarchy** | 1 | Query live ServiceNow schema |
| **TaskCreate** / **TaskUpdate** | All | Track progress |
| **mcp__plantuml__generate_plantuml_diagram** | 3 | Render diagram (preferred) |
| **Write** | 3 | Save .puml source file |
| **Bash** | 3 | Run gen_diagram.py (fallback renderer) |

---

Be precise about schema structure — an inaccurate ERD is more harmful than no ERD.
