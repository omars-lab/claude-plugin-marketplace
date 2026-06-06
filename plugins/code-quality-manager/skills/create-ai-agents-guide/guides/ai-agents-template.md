# AI-AGENTS.md Template (13 Sections)

This is the canonical structure for an `AI-AGENTS.md` governance guide — a file that
tells AI agents how to safely modify a repository. Populate every section with
**real, repo-specific facts** discovered by analyzing the codebase. Omit sections that
genuinely do not apply (e.g. "Design System" for a backend-only library) rather than
emitting empty placeholders.

Replace every `[bracketed placeholder]` with actual values. Never ship brackets.

---

## 1. Repository Overview

```markdown
# AI Agents Guide for [Repository Name]

## Repository Overview
- Purpose: [what this repo does and who it serves]
- Key technologies: [languages, frameworks, runtimes — from manifests]
- Main components/modules: [top-level building blocks]
- Architecture pattern: [monolith / service / library / CLI / monorepo, if applicable]
```

## 2. Architecture & Key Components

```markdown
## Architecture & Key Components

### Core System Components
- [component] — [responsibility]; relationship to [other component]
- Critical systems that must not be modified casually: [list]

### State Management
- [How state is managed — Redux/Context/local/DB/none] and key state and flow

### Data Flow
- [How data moves through the system, key data structures, APIs/data sources]
```

## 3. Design System & Styling

(Include only for UI-bearing repos.)

```markdown
## Design System & Styling

### Color Scheme
[Exact tokens/values pulled from the theme/config]

### Layout Principles
- [Grid/layout system, spacing scale, breakpoints, typography]

### Component Styling Patterns
- [Common classes, animation/transition conventions, interaction states]
```

## 4. File Structure & Responsibilities

```markdown
## File Structure & Responsibilities

### Core Files
- `[path]` — [responsibility]

### Configuration Files
- `[manifest/config path]` — [purpose]

### Documentation Files
- `README.md` — [purpose]
- `AI-AGENTS.md` — this file
```

## 5. Development Guidelines

```markdown
## Development Guidelines

### When Making Changes
- [What to preserve, patterns to maintain, scenarios to test — per change type:
  component/module modifications, styling changes, content/data updates]
```

## 6. Common Patterns & Examples

```markdown
## Common Patterns

### Adding New [Components/Features/Modules]
[Real code snippet from this repo showing the established pattern]

### [Styling / Data Structure / Other recurring task]
[Real example following repo conventions]
```

## 7. Critical Rules & Constraints

```markdown
## Critical Rules & Constraints

### DO NOT
- Remove [critical functionality]
- Break [specific feature / responsive design / accessibility]
- Change [design system / state structure / public API] without strong reason

### ALWAYS
- Test changes in [specific scenarios]
- Maintain [consistency / accessibility / responsiveness]
- Update documentation when adding features
- Follow [framework] best practices and [naming] conventions
```

## 8. Development Workflow

```markdown
## Development Workflow

### Before Making Changes
1. Read current code to understand structure
2. Check existing docs in [files]
3. Understand [key systems] and component interactions
4. Plan changes to minimize breakage

### During Development
1. Make incremental changes — don't rewrite whole components
2. Test frequently against [scenarios]
3. Follow established patterns
4. Preserve existing functionality

### After Making Changes
1. Test [scenarios]
2. Check [responsive design / edge cases]
3. Verify [accessibility / correctness]
4. Update docs if behavior changed
```

## 9. Troubleshooting Common Issues

```markdown
## Troubleshooting Common Issues

### [Common Issue]
- Symptoms: [what to look for]
- Solutions: [how to fix]
```

## 10. Key Dependencies & Technologies

```markdown
## Key Dependencies

### [Framework/Library]
[Import/usage example and why it's used]

### [Platform features used]
- [e.g. CSS Grid, async runtime, ORM, build tooling]
```

## 11. Best Practices for AI Agents

```markdown
## Best Practices for AI Agents

### Code Quality
- Write clean, readable code; clear names; comment complex logic
- Follow [framework] patterns; match existing style

### User Experience / Behavior
- Preserve [interactions / performance / established flows]
- Maintain [accessibility / API contracts]

### Documentation
- Update README and relevant docs; document new components
```

## 12. Testing Checklist

```markdown
## Testing Checklist

Before considering changes complete:
- [ ] [Core functionality] works
- [ ] [Key features] behave as expected
- [ ] [Navigation/interactions] function
- [ ] Responsive design works (if UI)
- [ ] No console/build errors
- [ ] [Accessibility] preserved (if UI)
- [ ] Tests pass: `[test command]`
- [ ] Documentation updated if needed
```

## 13. Support & Resources

```markdown
## Support & Resources

### Key Files for Reference
- `[file]` — [purpose]

### Common Commands
```bash
[build/test/run commands actually used in this repo]
```

---

**Remember**: This [repo type] exists to [purpose]. All changes must maintain the
[quality standards] and [requirements] that reflect the project's goals.
```
