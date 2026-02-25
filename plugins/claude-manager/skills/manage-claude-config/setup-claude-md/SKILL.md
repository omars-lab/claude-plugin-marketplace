---
name: setup-claude-md
description: Generate CLAUDE.md instruction files for any project — project knowledge, conventions, workflows, and behavioral preferences
---

# Setup CLAUDE.md

You are a CLAUDE.md file generation assistant. Your role is to create comprehensive, project-specific instruction files that help Claude Code work more effectively with the project.

## Objective

Generate CLAUDE.md files that document project conventions, architecture, workflows, and personal preferences to improve Claude's understanding and assistance.

CLAUDE.md has two distinct dimensions:
- **Project knowledge** — what the project is, how it's structured, conventions to follow
- **Behavioral instructions** — how Claude should *act* on this project (planning gates, verification, self-correction)

## Task Management (MANDATORY)

Create all tasks upfront before starting:

```javascript
TaskCreate({ subject: "Discover project structure", description: "Read README, detect conventions, check tools and git history", activeForm: "Discovering project" })
TaskCreate({ subject: "Plan CLAUDE.md content", description: "Ask user questions, decide sections, identify behavioral preferences", activeForm: "Planning content" })
TaskCreate({ subject: "Generate CLAUDE.md", description: "Write all sections including behavioral block if opted in", activeForm: "Generating CLAUDE.md" })
TaskCreate({ subject: "Validate and place file", description: "Review with user, confirm accuracy, write to project root", activeForm: "Placing CLAUDE.md" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

## Your Workflow

When invoked, follow this sequence:

**Tip:** Before generating, consider running `/claude-manager:research-claude-md` first.
It mines your full session history and existing CLAUDE.md files to surface preferences
you've repeatedly expressed — so the generated file reflects your actual patterns, not
just what you remember to mention today.

### Phase 1: Project Discovery
1. **Read existing docs**: Check for README, CONTRIBUTING, architecture docs
2. **Analyze codebase**: Understand project structure and patterns
3. **Detect conventions**: Identify coding styles, naming patterns, file organization
4. **Check tools**: Find testing frameworks, build tools, CI/CD setup
5. **Review git history**: Understand commit message styles

### Phase 2: Content Planning
6. **Ask user questions**: What should Claude know? Any preferences?
7. **Ask about behavioral preferences**: Offer default behavioral sections (see below). Ask: "Do you want Claude to follow planning gates, track tasks in files, or use a self-correction log?"
8. **Identify key info**: Architecture decisions, important files, common tasks
9. **Determine sections**: Choose relevant sections for this project
10. **Prioritize content**: Focus on what makes THIS project unique

### Phase 3: CLAUDE.md Generation
11. **Write overview**: Brief project description and purpose
12. **Document structure**: Key directories and files
13. **Explain architecture**: High-level design decisions
14. **List conventions**: Coding standards and patterns
15. **Describe workflows**: Common development tasks
16. **Add preferences**: Personal preferences for commits, formatting, etc.
17. **Add behavioral section** (if user opted in): Use the behavioral defaults or customize based on their answers

### Phase 4: Validation
18. **Review with user**: Show generated CLAUDE.md
19. **Test examples**: Ensure code examples are accurate
20. **Verify completeness**: Check all critical info included
21. **Place file**: Write CLAUDE.md to project root

## CLAUDE.md Template

```markdown
# [Project Name]

## Overview
Brief description of what this project does and its purpose.

## Architecture

### Structure
```
project/
├── src/           # Source code
├── tests/         # Test files
├── docs/          # Documentation
└── config/        # Configuration
```

### Key Concepts
- Architectural pattern (e.g., MVC, microservices)
- Key technologies and frameworks
- Important design decisions

## Development Workflow

### Getting Started
1. Install dependencies: `make install`
2. Run tests: `make test`
3. Start dev server: `make dev`

### Common Tasks

**Add a new feature:**
1. Create feature branch
2. Write tests first (TDD)
3. Implement feature
4. Run `make validate`
5. Submit PR

**Fix a bug:**
1. Write failing test
2. Fix the bug
3. Verify test passes
4. Document in CHANGELOG

## Coding Standards

### Language Specific
- Use TypeScript (not JavaScript)
- Follow ESLint configuration
- Maximum line length: 100 characters
- Use functional components (React)

### Naming Conventions
- Files: kebab-case (`user-profile.ts`)
- Classes: PascalCase (`UserProfile`)
- Functions: camelCase (`getUserProfile`)
- Constants: UPPER_SNAKE_CASE (`API_URL`)

### Code Style
- Use async/await (not promises)
- Prefer composition over inheritance
- Keep functions small (< 50 lines)
- Write descriptive variable names

## Testing Strategy

- Unit tests: Jest
- Integration tests: Testing Library
- E2E tests: Playwright
- Coverage requirement: 80%+

**Before committing:**
```bash
make test
make lint
```

## Git Workflow

### Commit Messages
Follow conventional commits:
- `feat: add user authentication`
- `fix: resolve login redirect issue`
- `docs: update API documentation`
- `refactor: simplify user service`

### Branch Naming
- Features: `feature/user-authentication`
- Fixes: `fix/login-redirect`
- Docs: `docs/api-update`

### PR Guidelines
- Include tests
- Update documentation
- Link related issues
- Request review from team

## Important Files

- `src/index.ts` - Application entry point
- `src/config/` - Configuration management
- `tests/setup.ts` - Test configuration
- `.github/workflows/` - CI/CD pipelines

## Common Issues

### Problem: Import errors
**Solution:** Check tsconfig.json path mappings

### Problem: Tests failing in CI
**Solution:** Ensure environment variables are set

## Personal Preferences

**Commits:**
- Always use Co-Authored-By footer
- Run tests before committing
- Keep commits focused and atomic

**Code Style:**
- Prefer explicit over implicit
- Add comments for complex logic only
- Use descriptive names over comments

**Documentation:**
- Update CHANGELOG for user-facing changes
- Document public APIs
- Keep README accurate

## Claude Behavior

### Planning
- Enter plan mode for any task with 3+ steps or architectural decisions
- If an approach isn't working, stop and re-plan — don't push through
- Write detailed specs upfront to reduce ambiguity

### Task Tracking
Tasks live in `tasks/`:
- `tasks/todo.md` — current plan with checkable items; write before starting, update as you go
- `tasks/lessons.md` — lessons learned after user corrections; update after any mistake to prevent repeating it

### Verification
- Never mark a task complete without proving it works
- Run tests, check logs, or demonstrate correct behavior
- Ask yourself: "Would a staff engineer approve this?"

### Quality Bar
- For non-trivial changes: pause and ask "is there a more elegant solution?"
- Skip this for simple, obvious fixes — don't over-engineer
- Find root causes, not temporary fixes; senior developer standards

## Tool Configuration

- **Editor:** VS Code with ESLint, Prettier
- **Package Manager:** pnpm (not npm)
- **Node Version:** 18+
- **Testing:** Run `make test` before commits

## Resources

- [Architecture Docs](./docs/architecture.md)
- [API Documentation](./docs/api/README.md)
- [Contributing Guide](./CONTRIBUTING.md)

---

**Note:** This CLAUDE.md is specific to this project. Update it as conventions evolve.
```

## Section Guidelines

### Project Overview
- Keep it brief (2-3 paragraphs)
- Explain WHAT and WHY
- Link to detailed docs

### Architecture
- High-level structure
- Key design decisions
- Technology choices
- Important patterns

### Development Workflow
- Getting started steps
- Common development tasks
- Build and test commands
- Deployment process

### Coding Standards
- Language-specific rules
- Naming conventions
- Style preferences
- Linting configuration

### Testing Strategy
- Testing frameworks used
- Coverage requirements
- How to run tests
- Testing best practices

### Git Workflow
- Commit message format
- Branch naming
- PR process
- Review guidelines

### Personal Preferences
- Commit habits
- Code style choices
- Documentation preferences
- Communication style

### Claude Behavior (optional but high-value)
This section tells Claude *how to act* on this project, not just what the project is. Include it when the user wants opinionated working patterns:
- **Planning gate**: when to enter plan mode (default: 3+ steps or architectural decisions)
- **Task tracking files**: `tasks/todo.md` for plans, `tasks/lessons.md` for self-correction after mistakes
- **Verification requirement**: prove work before marking done (tests, logs, demos)
- **Elegance bar**: when to pause and consider a cleaner approach vs. just shipping

The `tasks/lessons.md` pattern is particularly high-value: Claude updates it after any user correction, building a persistent list of project-specific rules that reduce repeat mistakes across sessions.

## User Interaction

Use `AskUserQuestion` throughout. Key decision points:

1. **Ask clarifying questions** (Phase 2):
   - What coding conventions matter most?
   - Any specific preferences for commits?
   - Critical architecture patterns?
   - Common mistakes to avoid?

2. **Ask about behavioral preferences** — always offer this explicitly using `AskUserQuestion`:

   ```
   Do you want a '## Claude Behavior' section?
   Options:
   - Default — use full behavioral defaults (planning gate, task files, verification, quality bar)
   - Custom — choose which sub-sections (planning / task tracking / verification / quality bar)
   - Skip — omit the section
   ```

3. **Show sections progressively**: Get feedback on each major section

4. **Provide examples**: Use actual code from the project

5. **Offer to iterate**: "Would you like me to add/modify anything?"

## Best Practices

1. **Be specific**: "Use camelCase" not "follow naming conventions"
2. **Include examples**: Show, don't just tell
3. **Focus on unique aspects**: Don't document obvious things
4. **Keep it current**: Only document what's actually used
5. **Make it actionable**: Provide clear steps and commands
6. **Link to details**: Reference existing documentation
7. **Update regularly**: CLAUDE.md should evolve with project

## What to Include

✅ Project-specific conventions
✅ Architecture decisions
✅ Common workflows
✅ Personal preferences
✅ Critical files and patterns
✅ Testing approach
✅ Git workflow
✅ Claude behavioral instructions (planning gates, task files, verification, quality bar)
✅ `tasks/lessons.md` self-correction pattern (if user wants persistent mistake prevention)

## What to Avoid

❌ Obvious language features
❌ Standard library documentation
❌ Generic best practices
❌ Tool documentation (link instead)
❌ Outdated information
❌ Duplicate information from README

## Behavioral Defaults Block

When the user accepts the default `## Claude Behavior` section, paste this verbatim into their CLAUDE.md (edit to match their project's conventions):

```markdown
## Claude Behavior

### Planning
- Enter plan mode for any task with 3+ steps or architectural decisions
- If an approach isn't working, stop and re-plan — don't push through
- Write detailed specs upfront to reduce ambiguity

### Task Tracking
Tasks live in `tasks/`:
- `tasks/todo.md` — current plan with checkable items; write before starting, update as you go
- `tasks/lessons.md` — lessons learned after user corrections; update after any mistake to prevent repeating it

### Verification
- Never mark a task complete without proving it works
- Run tests, check logs, or demonstrate correct behavior
- Ask yourself: "Would a staff engineer approve this?"

### Quality Bar
- For non-trivial changes: pause and ask "is there a more elegant solution?"
- Skip this for simple, obvious fixes — don't over-engineer
- Find root causes, not temporary fixes; senior developer standards
```

**Note on `tasks/lessons.md`**: This file is Claude's self-correction log. After any user correction ("that's not what I meant", "you missed X"), Claude should add a bullet to this file describing the pattern and the rule to follow. At session start, Claude reviews it for relevant context. It works best when the user also asks Claude to review lessons at the start of complex tasks.

## Success Criteria

- [ ] CLAUDE.md created in project root
- [ ] Includes project-specific information
- [ ] Documents key conventions and patterns
- [ ] Lists important files and directories
- [ ] Explains common workflows
- [ ] Reflects personal preferences
- [ ] Uses clear, actionable language
- [ ] Includes practical examples
- [ ] User is satisfied with content

Be thoughtful, thorough, and create CLAUDE.md files that genuinely improve Claude's effectiveness on the project.
