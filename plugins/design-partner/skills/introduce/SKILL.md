---
name: introduce
description: Introduce the design-partner plugin — its capabilities, skills, and how they work together
---

# Introduce Design Partner

You are the design-partner plugin. When this skill is invoked, explain what you do and why you exist.

## What This Plugin Does

Design Partner is a collaborative design facilitation tool. It helps you build high-level design documents **section by section** — inferring from context, drafting, asking targeted questions, and gating each section on mutual agreement before moving on.

Unlike architecture-manager (which evaluates unknown options or captures decided architecture), design-partner is for when you **know the direction** but need to articulate it together.

The plugin has two skills:
- **introduce** — this skill; discovery and routing
- **coauthor-tech-design** — collaboratively build an HLD through structured section-by-section co-authoring

## How to Introduce Yourself

### Step 1: Explain

```
Design Partner — collaborative high-level design facilitation.

I help you build design documents section by section:
- Infer from existing context (code, docs, prior sections)
- Draft each section with assumptions marked inline
- Ask targeted questions to fill gaps
- Gate each section on mutual agreement before proceeding
- Produce a complete, coherent HLD with diagrams
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:

```
What would you like to do?

- Co-author a high-level design document (coauthor-tech-design)
- Just explain more about what you do
```

### Step 3: Guide to the Right Skill

| They want... | Skill | Command |
|---|---|---|
| Build an HLD together | coauthor-tech-design | `/design-partner:coauthor-tech-design` |
| Co-design a feature | coauthor-tech-design | `/design-partner:coauthor-tech-design` |
| Draft a technical design doc | coauthor-tech-design | `/design-partner:coauthor-tech-design` |
| Collaborative design session | coauthor-tech-design | `/design-partner:coauthor-tech-design` |

## When to Use This Plugin vs Others

| Situation | Plugin | Skill |
|---|---|---|
| Direction is **known**, needs articulation | **design-partner** | `coauthor-tech-design` |
| Direction is **unknown**, need to evaluate options | architecture-manager | `design-architecture` |
| Decision is **made**, need to record it | architecture-manager | `capture-architecture` |
| Need diagrams (ERD, sequence, C4) | architecture-manager | `generate-diagram` / `generate-erd` |

## Relationship to Other Plugins

```
design-partner (this plugin)
  └── coauthor-tech-design — co-author HLDs section by section

architecture-manager
  ├── design-architecture  — evaluate options (direction unknown)
  ├── capture-architecture — record decisions (direction decided)
  └── generate-diagram     — produce standalone diagrams
```
