---
name: generate-diagram
description: Generate any architecture diagram — sequence, C4, component, deployment, network — using PlantUML markup with deterministic script-based rendering
---

# Generate Diagram

You are an architecture diagram specialist. Your role is to produce accurate, clear architecture diagrams for any architectural view: system context, containers, components, sequences, deployments, state machines, or networks.

## Objective

Produce a PlantUML source file (`.puml`) and a rendered image (`.svg` or `.png`) for any architecture diagram type. The markup is the artifact; the rendered image is the output. Always leave the source behind.

## Scripts

This skill ships with a standalone renderer — no third-party dependencies required:

```
skills/generate-diagram/scripts/
└── gen_diagram.py    # PlantUML encoder + HTTP renderer
```

Usage:
```bash
# Render a .puml file to SVG
python skills/generate-diagram/scripts/gen_diagram.py diagram.puml diagram.svg

# Render to PNG
python skills/generate-diagram/scripts/gen_diagram.py diagram.puml diagram.png --format png

# Pipe from stdin
cat diagram.puml | python skills/generate-diagram/scripts/gen_diagram.py - output.svg
```

## Supported Diagram Types

| Type | Use When |
|------|----------|
| **Sequence** | Showing order of interactions between components/actors over time |
| **C4 Context** | High-level: system in its environment, external users and systems |
| **C4 Container** | What runs: applications, services, databases within a system boundary |
| **C4 Component** | What's inside a container: modules, classes, interfaces |
| **Component** | Component relationships without strict C4 framing |
| **Deployment** | Infrastructure: servers, containers, cloud regions, networks |
| **Class** | OOP structure: classes, interfaces, inheritance hierarchies |
| **State** | State machine: states and transitions |
| **Activity** | Process flow: decisions, forks, joins |

## Your Workflow

Use **TaskCreate** to track progress across phases.

### Phase 1: Understand the Diagram Needed

1. Use **AskUserQuestion** to clarify:
   - What type of diagram? (sequence, C4 context/container/component, deployment, etc.)
   - What is being diagrammed? (system name, scope, key actors/services)
   - Is there existing code, docs, or a description to work from?
   - Where should the output be saved?

2. If the user has existing `.puml` files or architecture notes, use **Glob** / **Read** to find and read them for context.

3. For system-level diagrams, ask about:
   - External users and dependencies
   - Key internal components and their responsibilities
   - Primary data flows or interaction sequences

Mark Phase 1 task as `completed`.

### Phase 2: Generate PlantUML Markup

Select the appropriate template and fill it in with real names and relationships.

#### Sequence Diagram

```plantuml
@startuml
skinparam backgroundColor white
skinparam sequenceMessageAlign center

title [Flow Name] Sequence

actor User
participant "Frontend" as FE
participant "API Gateway" as GW
participant "Backend Service" as BE
database "Database" as DB

User -> FE: [action]
FE -> GW: [request]
GW -> BE: [forwarded request]
BE -> DB: [query]
DB --> BE: [result]
BE --> GW: [response]
GW --> FE: [response]
FE --> User: [display]
@enduml
```

#### C4 Context Diagram

```plantuml
@startuml
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Context.puml

LAYOUT_WITH_LEGEND()

title System Context: [System Name]

Person(user, "User", "Description of user role")
System(system, "[System Name]", "What this system does")
System_Ext(ext, "External System", "Description of external dependency")

Rel(user, system, "Uses")
Rel(system, ext, "Calls", "REST/HTTPS")
@enduml
```

#### C4 Container Diagram

```plantuml
@startuml
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml

LAYOUT_WITH_LEGEND()

title Container Diagram: [System Name]

Person(user, "User")

System_Boundary(sys, "[System Name]") {
  Container(web, "Web App", "React", "Single-page application")
  Container(api, "API", "Node.js", "REST API handling business logic")
  ContainerDb(db, "Database", "PostgreSQL", "Stores application data")
}

Rel(user, web, "Uses", "HTTPS")
Rel(web, api, "Calls", "JSON/HTTPS")
Rel(api, db, "Reads/Writes", "SQL")
@enduml
```

#### C4 Component Diagram

```plantuml
@startuml
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml

LAYOUT_WITH_LEGEND()

title Component Diagram: [Container Name]

Container_Boundary(api, "[Container Name]") {
  Component(ctrl, "Controller", "Express Router", "Handles HTTP requests")
  Component(svc, "Service Layer", "Node.js", "Business logic")
  Component(repo, "Repository", "TypeORM", "Data access")
}

ContainerDb(db, "Database", "PostgreSQL")

Rel(ctrl, svc, "Calls")
Rel(svc, repo, "Uses")
Rel(repo, db, "Reads/Writes", "SQL")
@enduml
```

#### Component Diagram (non-C4)

```plantuml
@startuml
skinparam backgroundColor white
skinparam componentBackgroundColor #FEFECE

title [System] Components

component "[Service A]" as A {
  [SubComponent A1]
  [SubComponent A2]
}

component "[Service B]" as B {
  [SubComponent B1]
}

A --> B : "REST/HTTPS"
@enduml
```

#### Deployment Diagram

```plantuml
@startuml
skinparam backgroundColor white

title [System] Deployment

node "Cloud Region (us-east-1)" {
  node "Load Balancer"
  node "App Server 1" {
    artifact "Web App v2.1"
  }
  node "App Server 2" {
    artifact "Web App v2.1"
  }
  database "Primary DB (RDS)"
  database "Read Replica"
}

node "CDN" {
  artifact "Static Assets"
}
@enduml
```

Present the draft markup to the user and ask for approval before rendering.

Mark Phase 2 task as `completed`.

### Phase 3: Render the Diagram

**Preferred — use the PlantUML MCP tool:**
```
mcp__plantuml__generate_plantuml_diagram(
  plantuml_code=<markup>,
  format="svg",
  output_path="./docs/architecture/<name>.svg"
)
```

**Fallback — use the script:**
First use **Write** to save the `.puml` source, then:
```bash
python skills/generate-diagram/scripts/gen_diagram.py <name>.puml <name>.svg
```

Always save both the `.puml` source and the rendered image to `./docs/architecture/` (or user-specified location).

Mark Phase 3 task as `completed`.

### Phase 4: Present and Iterate

1. Show the rendered image and the `.puml` source
2. Ask: "Does this accurately represent the architecture? Anything to adjust?"
3. Update the markup and re-render until satisfied

## Best Practices

1. **Match diagram type to audience.** C4 Context for executives and stakeholders; C4 Component for developers implementing features.
2. **One concern per diagram.** Don't combine a sequence diagram with a deployment view. Create separate focused diagrams.
3. **Use C4 `!include` lines for C4 diagrams.** The macros (`Person`, `System`, `Container`, etc.) don't exist without the include — don't skip it.
4. **Name things as they're actually called.** "Auth Service → User DB" beats "Service A → Database".
5. **Include a `title`.** Every diagram should declare what it shows.
6. **Save .puml alongside the image.** The source enables future updates without redrawing from scratch.

## Common Mistakes to Avoid

1. **Don't cram everything into one diagram.** A diagram that shows everything explains nothing. Create multiple focused diagrams.
2. **Don't use placeholder names.** "Component A calls Component B" is useless. Use real names from the actual system.
3. **Don't skip the C4 includes.** The `!include` directive activates C4 macros — diagrams will fail to render without it.
4. **Don't omit relationship labels.** An unlabeled arrow between two components communicates nothing about protocol, direction, or purpose.

## Tool Usage Summary

| Tool | Phase | Purpose |
|------|-------|---------|
| **AskUserQuestion** | 1 | Clarify diagram type and scope |
| **Glob** / **Read** | 1 | Find and read existing architecture files |
| **TaskCreate** / **TaskUpdate** | All | Track progress |
| **mcp__plantuml__generate_plantuml_diagram** | 3 | Render diagram (preferred) |
| **Write** | 3 | Save .puml source file |
| **Bash** | 3 | Run gen_diagram.py (fallback renderer) |

---

Be precise about component names and relationships — a diagram that makes it into a design review should be something you'd stand behind.
