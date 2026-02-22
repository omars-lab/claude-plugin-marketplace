---
name: structure-role
description: Structures and refactors a specific role directory in the personalbook system, separating generic frameworks from personal action items and organizing skills, habits, artifacts, knowledge, and decisions. Use when refactoring a specific role, organizing a role directory, or structuring role content. Requires explicit role identification.
link: not
---

# Structuring a Role

## Triggering Criteria

Users can trigger this skill by saying things like:
- "Structure this role"
- "Refactor this role directory"
- "Organize this role"
- "Structure [Role Name]"
- Or using the slash command: `/role-manager:structure-role`

## Key Concepts

| Concept | What It Is | Example |
|---------|-----------|---------|
| **Skills** | The "how" - reusable recipes/processes, questions to ask | `/reflecting-on-learnings` |
| **Habits** | The "when" - regular practices combining skills | `daily-reflection` (daily, evening) |
| **Artifacts** | The "results" - personal outcomes, answers, learning plans | "I learned I'm not motivated to learn X" |
| **Knowledge** | The "what" - background understanding, domain mapping, concepts and how they relate | `knowledge/prioritization-factors.md` |
| **Decisions** | The "which" - major one-time decisions with options, criteria, reasoning | `decisions/grad-school/` |
| **Expectations** | The "should be" - standards/qualities someone in this role should embody | "CTOs should balance tech and people skills" |

### Skills = Verbs/Actions (CRITICAL)

**Skills are activities/actions you perform.** When restructuring a role, every verb in a file name or section header represents a potential skill.

**The Verb Test**: Look at file/folder names in the role. Each one starting with an action verb likely represents a skill:
- "Cataloging X" → skill for cataloging
- "Reflecting on X" → skill for reflecting
- "Prioritizing X" → skill for prioritizing
- "Identifying X" → skill for identifying

**Common mistake**: Converting action-oriented files into artifacts or knowledge only, losing the verb.

| Source | Wrong | Right |
|--------|-------|-------|
| `Cataloging Completed Projects/` | → `artifacts/accomplishments.md` only | → skill `tracking-accomplishments` + artifact `accomplishments.md` |
| `Prioritizing Projects.md` | → `knowledge/prioritization.md` | → skill `prioritizing` with questions |
| `Setting Deadlines.md` | → `knowledge/tips.md` | → skill section OR knowledge (if truly just tips) |

**Rule**: If content answers "How do I [verb]?" → it's a skill. If content answers "What is [noun]?" → it's knowledge.

**Verb Audit During Migration:**
Before deleting source files, list all verbs from file/folder names:
```
Source Files              Verb              Captured as Skill?
─────────────────────────────────────────────────────────────
Cataloging Projects/      catalog           ❌ Need to add
Reflecting on X.md        reflect           ✅ reflecting-on-X
Prioritizing Y.md         prioritize        ✅ prioritizing
Understanding Z.md        understand        → Knowledge (not action)
```

If a verb is NOT captured as a skill, either:
1. Create a new skill for it
2. Add it as a section in an existing related skill
3. Confirm it's truly just knowledge/reference (rare for action verbs)

**Every role should have a `habits/` directory** - habits are role-specific regular practices at various stages of development.

### Maturity Levels (Skills and Habits)

Both skills and habits have maturity levels tracked via frontmatter `status`:

| Level | Status | Skills | Habits |
|-------|--------|--------|--------|
| 0 | **ideating** | Considering whether to develop | Thinking about establishing |
| 1 | **establishing** | Actively developing the skill | Actively building the habit |
| 2 | **practicing** | Skill exists, strengthening | Habit exists, requires effort |
| 3 | **established** | Part of regular practice | Automatic/ingrained |
| - | **paused** | Temporarily not using | Temporarily not practicing |
| - | **retired** | No longer relevant | No longer needed |

**Frontmatter example:**
```yaml
---
name: weekly-reflection
status: establishing  # ideating | establishing | practicing | established | paused | retired
started_date: 2024-01-15
established_date: null  # filled when status becomes established
---
```

### Cross-Cutting Roles

Some roles are **cross-cutting** - their skills apply across many other roles. When structuring content, be aware of these roles to avoid misplacing skills.

| Cross-Cutting Role | What It Handles | Example Skills |
|--------------------|-----------------|----------------|
| **The Self Reflector** | Self-understanding, identity, meaning | `reflecting-on-purpose`, `reflecting-on-identity`, `reflecting-on-progress` |
| **The Self Master** | Discipline, habits, self-control | `training-mindset`, `controlling-desires` |
| **The Manager** | Execution, planning, prioritization | `prioritizing`, `planning`, `managing-tasks` |
| **The Learner** | Knowledge acquisition | `acquiring-knowledge`, `reflecting-on-learnings` |

**The Key Question**: When you have a "reflecting on X" skill, ask:

| If reflecting on... | Focus | Belongs In |
|---------------------|-------|------------|
| **What does X say about who I am?** | Self-understanding | The Self Reflector |
| **What X got done and what's next?** | Execution tracking | The domain role (e.g., The Manager) |
| **What did I learn from X?** | Knowledge extraction | The Learner OR domain role |

**Example - "Reflecting on Accomplishments":**
- "Am I living up to my potential?" → **Self Reflector** (`reflecting-on-progress`)
- "What projects completed? What to add to my record?" → **The Manager** (`reflecting-on-accomplishments`)

Both are valid - they serve different purposes. The Self Reflector asks "what does this mean for who I am?" while The Manager asks "what got done and what's next?"

**When in doubt**: If the reflection is about *identity/meaning/purpose*, it goes in The Self Reflector. If it's about *tracking/cataloging/planning*, it stays in the domain role.

### Skill Extension (extends)

Some skills **extend** foundational cross-cutting skills, adding domain-specific structure on top of them.

**Frontmatter syntax:**
```yaml
---
name: holding-retrospectives
extends: reflecting-on-progress  # Foundational skill from The Self Reflector
---
```

**What "extends" means:**
- The extending skill builds on the foundational skill's questions/framework
- The extending skill adds domain-specific structure, formats, or action items
- Users should be aware of the foundational skill when using the extending skill

**Example:**

| Foundational Skill | Extending Skill | What Extension Adds |
|--------------------|-----------------|---------------------|
| `reflecting-on-progress` (Self Reflector) | `holding-retrospectives` (Manager) | Structured retro formats (4Ls, Start/Stop/Continue), action items, team context |
| `reflecting-on-learnings` (Self Reflector) | `extracting-lessons` (Learner) | Specific frameworks for capturing and applying learnings |

**When to use extends:**
- The domain skill would be incomplete without the foundational skill's questions
- The domain skill adds structure/actionability to abstract reflection
- You want to avoid duplicating foundational questions across roles

**Pattern:**
```
Cross-Cutting Role (foundational)     Domain Role (extending)
─────────────────────────────────     ─────────────────────────
reflecting-on-progress          →     holding-retrospectives
  "Am I winning?"                       "What went well?"
  "Am I living up to potential?"        "What will we do differently?"
                                        "Action items: ..."
```

The foundational skill asks the deep questions; the extending skill makes them actionable.

### "Should I Develop X?" Questions

Questions about WHETHER to develop a skill or habit are **decisions**, not skill/habit content.

These belong in **The Self Reflector** role:
```
roles-self-development/The Self Reflector/decisions/developing-capabilities/
├── Overview.md           # Framework for deciding what skills AND habits to develop
├── planning-skills.md    # Should I get better at planning?
├── self-measurement.md   # Should I develop self-measurement practices?
├── habit-tracking.md     # Should I establish habit tracking?
└── ...
```

**Rationale:** Deciding what capabilities to develop is a self-reflective activity. Once decided, the actual skill/habit development happens in the appropriate role.

### Role Categories: Self-Development vs Technical

Roles fall into two broad categories with different organizational patterns:

| Aspect | Self-Development Roles | Technical/Development Roles |
|--------|------------------------|----------------------------|
| **Examples** | The Self Reflector, The Learner, The Self Master | The Automator, The Developer, The Process Developer |
| **Primary focus** | Reflection, growth, behavior change | Building, automating, implementing |
| **Skills are...** | Questions to ask yourself | SOPs, runbooks, techniques, mechanisms |
| **Habits are...** | Regular practices (daily reflection) | Processes (weekly backup, code review) |
| **Artifacts are...** | Personal answers, reflections | Implementation journals, TODOs, generated outputs |
| **Additional component** | — | **Initiatives** (projects applying skills) |

**Key insight**: Technical roles are more "doing" than "reflecting". Their skills are procedural (how to do X) rather than introspective (what should I think about X).

### Technical Role Components

For technical/development roles (`roles-technical/`, `roles-development/`), use these adjusted definitions:

| Component | Technical Role Definition | Example |
|-----------|--------------------------|---------|
| **Skills** | SOPs, runbooks, techniques, mechanisms - procedural "how-to" guides | `skills/automating-with-shortcuts/SKILL.md` |
| **Processes** | Regular technical practices (replaces "habits") | `processes/weekly-backup/PROCESS.md`, `processes/code-review/PROCESS.md` |
| **Artifacts** | Implementation journals, TODOs, generated files, exploration notes | `artifacts/athan-automation.md`, `artifacts/explorations.md` |
| **Initiatives** | Projects/efforts that apply the role's skills | `initiatives/home-automation/`, `initiatives/automating-personal-tracking/` |
| **Knowledge** | Technical reference, tool documentation, gotchas | `knowledge/shortcuts-reference.md` |
| **Decisions** | Technology choices, architectural decisions | `decisions/choosing-automation-platform/` |

### Scripts and Outputs (Technical Roles)

**IMPORTANT**: Scripts AND their outputs live together in the external scripts repo. Roles only contain a reference artifact.

| Type | Location | Example |
|------|----------|---------|
| **Scripts** | `/scripts/[role]/[script]/` | `/scripts/automator/listing-experiments/generate.sh` |
| **Outputs** | `/scripts/[role]/[script]/outputs/` | `/scripts/automator/listing-experiments/outputs/Overview.md` |
| **Role reference** | `[role]/artifacts/related-scripts.md` | Links to scripts and their outputs |

**Why keep scripts + outputs together?**
- Scripts and outputs are tightly coupled - they belong together
- The scripts repo is self-contained and versioned independently
- Roles should **reference** scripts, not **contain** them or their outputs
- Avoids duplication and sync issues

**Script directory structure** (in external scripts repo):
```
scripts/                  # Symlink → ../workspace/scripts-role-management/
├── README.md             # Documents all scripts with descriptions
├── [role-name]/          # Scripts organized by role
│   └── [script-name]/
│       ├── script.sh     # The script implementation
│       ├── README.md     # Usage docs (optional)
│       ├── inputs/       # Input files/templates (if needed)
│       └── outputs/      # Generated outputs
└── shared/               # Scripts used across roles
```

**Role's related-scripts artifact** (in personalbook):
```markdown
# artifacts/related-scripts.md
---
intent: Reference to scripts related to this role
location: /scripts/[role-name]/
---

## Scripts

| Script | Purpose | Run | View Output |
|--------|---------|-----|-------------|
| script-name | Description | `./script.sh` | [outputs/](/scripts/role/script/outputs/) |
```

**Key principle**: Roles contain documentation and references. Scripts + outputs live externally in the scripts repo. Never put `.sh` files or generated outputs in role directories.

### Initiatives (Technical Roles)

**Initiatives** are projects or efforts that apply a technical role's skills. They track:
- What you're building/automating
- Progress and status
- Links to artifacts produced
- Decisions made along the way

**Initiative structure:**
```
initiatives/
└── home-automation/
    ├── Overview.md           # Goal, status, scope
    ├── progress.md           # Timeline, milestones achieved
    └── decisions.md          # Tech choices made for this initiative
```

**Example initiative:**
```markdown
# initiatives/home-automation/Overview.md
---
status: active
started: 2021-04
---

# Home Automation Initiative

## Goal
Automate recurring home tasks: athan notifications, lighting, temperature.

## Current Focus
- Athan automation via Mac Mini + catt

## Completed
- [x] Mac Mini setup for athan playback
- [x] Cron job for prayer times

## Artifacts Produced
- [Athan automation notes](../../artifacts/athan-automation.md) - implementation journal
- [Lessons learned](../../artifacts/home-automation-learnings.md) - wisdom from experience

## Skills Used
- [Automating with Shortcuts](../../skills/automating-with-shortcuts/SKILL.md)
- [Setting up Cron Jobs](../../skills/setting-up-cron/SKILL.md)

## Knowledge Referenced
- [Cron Syntax](../../knowledge/cron-reference.md) - prerequisite before setting up jobs
- [Shortcuts Actions](../../knowledge/shortcuts-reference.md) - prerequisite before building shortcuts
```

### Artifact: Learnings from Initiatives

When working on initiatives, capture experiential wisdom in artifacts:

```markdown
# artifacts/home-automation-learnings.md
---
intent: Lessons learned and observations from home automation work
initiative: home-automation
---

# Home Automation Learnings

## Gotchas Discovered
- Shortcuts has a 2-minute timeout - can't use for long-running tasks #gotcha
- HomePod disconnects from iPad on 5GHz network #gotcha
- Cron on Mac requires full disk access for some operations #gotcha

## Observations
- Cast-based solutions (catt) more reliable than AirPlay for scheduled audio
- Dedicated Mac Mini works better than relying on always-on iPad

## What Worked
- Using cron instead of Shortcuts for reliability
- Hardcoding IP addresses instead of relying on mDNS

## What Didn't Work
- Trying to use Shortcuts automation for time-based triggers
- Relying on iPad staying connected to HomePod
```

**This is the key pattern**: Knowledge contains prerequisite info (cron syntax), while artifacts contain experiential wisdom (cron requires full disk access on Mac).

### Habits (All Roles)

**Every role has a `habits/` directory.** Habits are regular practices with timing that combine one or more skills.

**Habit structure:**
```
[role]/habits/
└── [habit-name]/
    └── HABIT.md
```

**HABIT.md template:**
```markdown
# habits/weekly-reflection/HABIT.md
---
name: weekly-reflection
frequency: weekly
timing: Sunday evening
duration: 30 minutes
skills_used:
  - reflecting-on-progress
  - reflecting-on-priorities
status: establishing  # ideating | establishing | practicing | established | paused | retired
started_date: 2024-01-15
established_date: null
---

# Weekly Reflection

## Purpose
[Why this habit exists - what it helps me accomplish]

## When
- **Frequency**: Weekly
- **Day**: Sunday
- **Time**: Evening
- **Duration**: ~30 minutes

## Trigger
[What reminds me to do this? Calendar event, after another habit, etc.]

## Skills Exercised
- [reflecting-on-progress](../../skills/reflecting-on-progress/SKILL.md)
- [reflecting-on-priorities](../../skills/reflecting-on-priorities/SKILL.md)

## Checklist
- [ ] Review accomplishments from the week
- [ ] Review what didn't go well
- [ ] Review priorities for next week
- [ ] Update artifacts with insights

## Artifacts Updated
- [reflecting-on-progress.md](../../artifacts/reflecting-on-progress.md)

## Establishing This Habit
<!-- Remove this section once status is 'established' -->

### What "Established" Looks Like
- I do this automatically without reminders
- I feel uncomfortable if I skip it

### Current Blockers
- [What's preventing this from becoming automatic?]

### Experiments to Try
- [Ideas for making this stick]
```

**Habit frequencies:**
| Frequency | Examples |
|-----------|----------|
| Daily | morning-routine, daily-reflection, daily-prayer |
| Weekly | weekly-review, weekly-planning |
| Monthly | monthly-goals, monthly-budget-review |
| Quarterly | quarterly-review |
| Yearly | annual-reflection |

### Processes (Technical Roles)

In technical roles, **Processes** are the equivalent of **Habits** - regular technical workflows. They use the same maturity levels and similar structure.

**Process structure:**
```markdown
# processes/weekly-backup/PROCESS.md
---
name: weekly-backup
frequency: weekly
timing: Sunday evening
status: established
---

# Weekly Backup Process

## Purpose
Ensure all critical data is backed up and recoverable.

## Steps
1. Run Time Machine backup
2. Verify cloud sync status
3. Check NAS availability
4. Review backup logs for errors

## Checklist
- [ ] Time Machine completed successfully
- [ ] Dropbox fully synced
- [ ] NAS accessible and healthy
```

### Identifying Content Types (Self-Development Roles)

| Content Type | Characteristics | Destination |
|--------------|-----------------|-------------|
| **Questions to ask yourself** (no answer) | Generic, reusable prompts | Skills |
| **Questions with personal answers** | Your reflection/response attached | Artifacts |
| **Domain concepts/frameworks** | Background info, how things relate, mental models | Knowledge |
| **Major life decisions** | Options, criteria, weighing pros/cons | Decisions |
| **Personal learning plans** | Your specific plan to acquire knowledge | Artifacts (learning-plans.md) |
| **Regular practices** | Timed activities (daily, weekly) | Habits |
| **Motivational content** | Quotes, affirmations, reminders | Artifacts (self-affirmations.md) or cross-role to The Motivator |
| **Personal resource collections** | Curated links, Etsy shops, video playlists | Artifacts or Knowledge (depending on personal vs reference) |
| **Spiritual/religious practices** | Prayer, Quran, Ramadan, religious routines | Cross-role to The Servant |
| **Dated personal entries** | Content with timestamps (>2019-10-12) | Artifacts (preserve dates!) |
| **Personal habit lists** | Specific habits you want to maintain | Artifacts (ideal-habits.md) |
| **Character traits/virtues** | "Be Confident", "Be Patient" type content | Artifacts (self-affirmations.md) |

### Identifying Content Types (Technical/Development Roles)

| Content Type | Characteristics | Destination |
|--------------|-----------------|-------------|
| **How-to procedures** | Step-by-step instructions, SOPs, runbooks | Skills |
| **Techniques/mechanisms** | Reusable patterns for accomplishing tasks | Skills |
| **Implementation notes** | Journal of building something, with dates/progress | Artifacts (e.g., `athan-automation.md`) |
| **Exploration/tinkering notes** | "Tinker with X", experiments, trials | Artifacts (`explorations.md`) |
| **TODOs and action items** | `[ ]` checkboxes, planned work | Artifacts |
| **Completed tasks** | `[x]` checkboxes, done items | Artifacts (preserve for reference) |
| **Generated/auto-created files** | Scripts, diagrams, outputs | Artifacts |
| **Regular technical workflows** | Weekly backups, code reviews, maintenance | Processes |
| **Prerequisite tool documentation** | How to use a tool BEFORE using it | Knowledge |
| **Links to external docs** | URLs to official docs, tutorials (prerequisite reading) | Knowledge |
| **Gotchas and lessons learned** | `#gotcha`, things that tripped you up | **Artifacts** (wisdom from experience!) |
| **Personal observations** | "I noticed that...", "This doesn't work when..." | **Artifacts** (experiential wisdom) |
| **Technology choices** | "Should I use X or Y?", weighing options | Decisions |
| **Project/effort tracking** | Ongoing work applying multiple skills | Initiatives |
| **Unorganized notes** | "Unorganized, X.md" files | Artifacts (`unorganized.md`) - preserve! |

**Key distinction for technical roles:**
- **Knowledge** = What you need to know BEFORE doing (tool syntax, API reference, framework concepts)
- **Artifacts** = What you learned FROM doing (gotchas, observations, lessons, insights, reflections)

### Cross-Role Content Destinations

**CRITICAL**: Some content belongs in a DIFFERENT role than the one being structured. Before deleting, check if content should go to:

| Content Type | Likely Destination Role |
|--------------|------------------------|
| Motivational quotes with `#id:motivational-quote-*` | `roles/The Motivator/` |
| Spiritual/religious content | `roles-self-development/The Servant/` |
| Career/vocation content | `roles-career/` |
| Learning/skills content | `roles-self-development/The Learner/` |
| Purpose/passion discovery | `roles-self-development/The Self Reflector/` |
| Character/discipline content | `roles-self-development/The Self Master/` |

**If content doesn't fit the current role, migrate it to the appropriate role instead of deleting.**

### Knowledge vs Skills vs Artifacts

**Knowledge** (foundational prerequisite information):
- Domain concepts and how they relate to each other
- Mental models and frameworks for understanding a space
- Definitions, terminology, principles
- Reference material you need BEFORE doing something
- Information that exists independent of your experience
- NOT questions to ask yourself (those belong in skills)
- NOT personal answers or TODOs (those belong in artifacts)
- NOT wisdom gained from experience (that belongs in artifacts)
- Example: "What are the different factors that affect prioritization?" → a knowledge file mapping the domain

**Skills** (questions to ask yourself):
- Prompts for reflection and decision-making
- "What should I prioritize?" "How should I allocate my time?"
- Reusable across situations
- The "action" you take when exercising a capability

**Artifacts** (personal content and experiential wisdom):
- Your answers to skill questions
- Personal TODOs and action items
- Dated entries and reflections
- Learning plans and progress tracking
- **Wisdom derived from experience** - lessons learned, observations, insights gained through doing
- Reflections and notes from initiatives/projects
- "What I learned from doing X" content

**Key Test**:
- "Is this something I'd ask myself?" → Skill
- "Is this foundational info I need BEFORE doing something?" → Knowledge
- "Is this wisdom I gained FROM doing something?" → Artifact
- "Is this my personal answer, plan, or TODO?" → Artifact

**Knowledge vs Artifact - The Experience Test**:
- **Knowledge** = Information that exists independent of your experience; prerequisite understanding
- **Artifact** = Wisdom derived through your experience; lessons learned, observations, insights

> **The simple pattern: Knowledge is what you read BEFORE doing. Artifacts are what you write AFTER doing.**

| Content | Knowledge or Artifact? | Why |
|---------|----------------------|-----|
| "Cron syntax reference" | Knowledge | Prerequisite info before setting up cron |
| "Cron has a 2-minute timeout on Mac" | Artifact | Learned through experience (#gotcha) |
| "What is a process?" | Knowledge | Foundational concept |
| "My process for X doesn't work because..." | Artifact | Personal observation from doing |
| "RICE scoring framework" | Knowledge | External framework to learn |
| "RICE doesn't work well for my projects because..." | Artifact | Personal insight from applying it |

```markdown
# Example: knowledge/prioritization-factors.md
---
topic: Prioritization Factors
status: reference
---

# Prioritization Factors

## Impact Dimensions
- Business value - revenue, cost savings
- User value - satisfaction, retention
- Strategic alignment - fits roadmap, enables future work

## Effort Considerations
- Development time
- Dependencies on other work
- Risk and uncertainty

## Frameworks
- RICE scoring (Reach, Impact, Confidence, Effort)
- MoSCoW (Must, Should, Could, Won't)
- Value vs Effort matrix
```

```markdown
# Example: skills/prioritizing/SKILL.md (questions)
## Questions to Ask Yourself
- What should I prioritize right now?
- What factors am I weighing in this decision?
- What am I deprioritizing and why?
```

```markdown
# Example: artifacts/priorities.md (personal answers)
## Current Priorities
1. Ship feature X by Friday
2. Hire senior engineer

## Why These?
- Feature X has deadline commitment
- Team is understaffed
```

**Learning Plans** (personal, artifact):
- Your specific plan to learn certain knowledge topics
- Progress tracking, priorities, timeline
- Example: "My plan: Learn Spring by March, then Kubernetes"

```markdown
# Example: artifacts/learning-plans.md
---
intent: Personal plans for acquiring role knowledge
habits: [weekly-review]
---

## Current Focus: Design Patterns
- Priority: High
- Timeline: Complete by February
- Progress: Read 5/23 patterns
- Next: Study Observer pattern this week

## Queued: Concurrency
- Will start after Design Patterns
- Reason: Need for current project
```

### Questions: Skills vs Artifacts

| Question Type | Where It Belongs | Example |
|---------------|------------------|---------|
| **Questions to ask yourself** (no answer) | Skills or Habits | "Did I get better today?" |
| **Questions you attempted to answer** (with personal answer/reflection) | Artifacts | "Why haven't I started my company? → Because I'm afraid of failure" |

**Rule**: If it's a question template/recipe → skill. If it's a personal instance with your answer → artifact.

### Decisions: Structure and Content

Decisions are **major one-time choices** that require exploration, weighing options, and reasoning. They differ from skills (recurring processes) and artifacts (personal answers).

**Characteristics of decision content:**
- Exploring options (grad school vs self-study)
- Weighing criteria (cost, time, outcomes)
- Reasoning through trade-offs
- Personal thoughts on what to choose
- NOT recurring - once decided, it's done

**Decision directory structure:**
```
decisions/
└── pursuing-grad-degree/
    ├── Overview.md           # The decision context and current status
    ├── options.md            # Options being considered
    ├── criteria.md           # What matters in making this decision
    ├── exploration.md        # Research, questions, considerations
    └── resolution.md         # Final decision and reasoning (when decided)
```

**Example decision content:**
```markdown
# decisions/pursuing-grad-degree/Overview.md

## The Decision
Should I pursue a graduate degree?

## Status
Exploring - not yet decided

## Key Questions
- What do I want to gain from a degree?
- Will it help my purpose?
- What field aligns with my interests?

## Related Decisions
- Committing to a field of study
- Choosing between programs
```

### Expectations: Standards for the Role

**Expectations** are standards, qualities, or demands placed on someone playing a role - from external stakeholders OR from your own definition of what excellence looks like.

| Role Type | Expectation Source | Example |
|-----------|-------------------|---------|
| **Career roles** | Industry, employers, investors, team | "CTOs should balance tech and people" |
| **Self-development roles** | Your ideal self, role models, personal standards | "A Self Reflector challenges their assumptions" |
| **Family roles** | Family members, cultural norms, your values | "A good father is present and engaged" |
| **Community roles** | Community, organization, cultural norms | "A good leader empowers others" |

**Expectations vs Similar Concepts:**

| Concept | Question Answered | Example (CTO Role) |
|---------|-------------------|---------------------|
| **Responsibilities** | What does this role DO/produce? | "Produce technical strategy" |
| **Success Metrics** | How do I know I'm good at this? | "Team ships on time" |
| **Expectations** | What should someone in this role BE like? | "Balance tech and people skills" |
| **Skills** | How do I DO things? | "Addressing investor concerns" |

**Key distinction:**
- **Responsibilities** = outputs and activities (what you produce)
- **Success Metrics** = measurable indicators (how you know you're succeeding)
- **Expectations** = character traits, behaviors, qualities, or standards (what you should embody)

**Expectations directory structure:**
```
expectations/
├── Overview.md           # "What do we expect of someone playing this role?"
└── [expectation].md      # Specific expectation with observations
```

**Expectation file template:**
```markdown
---
source: [Who expects this - stakeholders, industry, self, role models]
observed: [Date you noticed/documented this]
---

# [Expectation Name]

[Description of the expectation - use "A good X does/has Y" or "A good X does NOT do Y" framing]

## Observations
- [Notes, examples, quotes from others about this expectation]

## Role Models
- [People who exemplify this expectation and what you've learned from them]

## Related Skills
- [Skills that help meet this expectation]
```

**Role Models section guidance:**
The Role Models section captures people who exemplify this expectation. Include:
- Their name and context (colleague, public figure, historical, etc.)
- What specifically they do/did that demonstrates this expectation
- Lessons or quotes from observing them

Example:
```markdown
## Role Models
- **Russ** - AI Visionary who combined technical depth with political savvy
  - Blend of technical vision + influence/clout
  - Observed: 2020-05-21
- **[Public Figure]** - Known for X approach to leadership
  - Key lesson: ...
```

**Framing expectations - "A good X..." pattern:**

Use this pattern to frame expectations clearly:
- **Positive**: "A good CTO balances technical depth with people skills"
- **Negative (anti-pattern)**: "A good CTO does NOT get lost in technical details at the expense of strategy"

Both framings are valuable:
| Framing | Purpose | Example |
|---------|---------|---------|
| **"A good X has/does Y"** | What to aspire to | "A good Self Reflector is honest with themselves" |
| **"A good X does NOT do Y"** | What to avoid | "A good Self Reflector does NOT rationalize their failures" |

**For self-development roles**, expectations might capture:
- Traits you aspire to embody ("A good Self Master has discipline")
- Anti-patterns to avoid ("A good Self Master does NOT give in to impulses")
- Observations from role models
- Quotes/insights about what excellence looks like

**Example expectations:**
```markdown
# expectations/breaking-molds.md
---
source: industry, role models
observed: 2020-05-20
---

# Breaking Molds / Thinking Outside the Box

A good CTO thinks beyond conventional boundaries and challenges assumptions.

A good CTO does NOT accept "we can't do that because there's no data" without exploring alternatives.

## Observations
- "You have to start where there is data" - but what valuable use cases are ignored because there's no data? What data could we create?

## Role Models
- **Russ** - AI Visionary who combined technical depth with political savvy
  - Blend of technical vision + influence/clout that got things moving
  - Observed: 2020-05-21

## Related Skills
- [Setting a Development Strategy](skills/setting-a-development-strategy/SKILL.md)
```

### Consolidating Questions from `/questions` Directory

The `/questions` directory contains raw question collections organized by theme (purpose.md, growth.md, life.md, etc.). When structuring a role, **move relevant questions into appropriate skills**.

**The Key Test**: For each question, ask: **"Would I ask myself this question when exercising this particular skill?"**

- "What is my purpose?" → Yes, when `/reflecting-on-purpose`
- "What are my priorities?" → Yes, when `/reflecting-on-priorities`
- "What gives me meaning?" → Yes, when `/reflecting-on-purpose`

If the answer is yes, the question belongs in that skill. If no existing skill fits, consider creating a new one.

**Question Voice**: Questions may be in 1st person ("What are my values?") or 3rd person ("What are your values?"). Both are equivalent self-reflective questions - the voice doesn't determine where it belongs.

**Process:**
1. Read ALL files in `/questions` directory relevant to the role (don't process piecemeal)
2. For each question, apply the test: "Would I ask this when exercising skill X?"
3. Add questions to appropriate skill under a section like `### From [source].md`
4. If questions don't fit existing skills, consider creating new skills
5. Remove the moved questions from the source file in `/questions`

**Example skill section:**
```markdown
### From growth.md
- What areas in your life can you improve?
- How should I grow?
- What are my gaps?
```

**Why consolidate?** Questions scattered across `/questions` are harder to use during reflection. Moving them into skills makes them actionable during habits.

### Skill Scope Definition

Every skill should have a clear **scope** that defines its boundaries. This prevents questions from being missed or misplaced.

**Required in each skill:**

1. **Frontmatter `scope` field** - A concise one-liner of what the skill covers:
```yaml
---
name: reflecting-on-priorities
scope: Goals, plans, task prioritization, time allocation, weekly planning
---
```

2. **Scope section after Purpose** - Explicit boundaries:
```markdown
## Scope

This skill covers questions about:
- Goals and plans
- Task prioritization and tracking
- Time allocation and scheduling
- Weekly/daily planning rituals

This skill does NOT cover:
- Project-specific estimation (see planning questions)
- Learning priorities (see reflecting-on-learnings)
```

**Why scope matters**: Without explicit boundaries, questions like "What are your plans?" might not be recognized as belonging to `reflecting-on-priorities`. The scope makes this obvious.

### Breaking Down Large Skills

When a skill grows beyond ~100-150 lines or covers multiple distinct domains, consider breaking it into sub-skills.

**Signs a skill needs breakdown:**
- The skill has 5+ distinct section headers that could stand alone
- Different sections would be invoked at different times
- The skill covers multiple domains (e.g., "motivation" AND "overcoming obstacles" AND "starting actions")
- Reading the whole skill is overwhelming when you just need one part

**Sub-skill structure:**
```
skills/
└── parent-skill/
    ├── SKILL.md              # Overview that references sub-skills
    └── sub-skills/
        ├── sub-skill-1/
        │   └── SKILL.md
        └── sub-skill-2/
            └── SKILL.md
```

**Parent SKILL.md template:**
```markdown
---
name: parent-skill
scope: [Overall scope covering all sub-skills]
---

# Parent Skill Name

## Purpose
[What this skill family helps you accomplish]

## Sub-Skills

| Sub-Skill | Focus | When to Use |
|-----------|-------|-------------|
| [sub-skill-1](sub-skills/sub-skill-1/SKILL.md) | [Focus area] | [When you'd invoke it] |
| [sub-skill-2](sub-skills/sub-skill-2/SKILL.md) | [Focus area] | [When you'd invoke it] |

## Core Questions
[A few essential questions that span all sub-skills - keep this brief]
```

**When NOT to break down:**
- The skill is under 100 lines
- All sections are tightly related and used together
- Breaking it would create artificial separation
- The sections are just different angles on the same question

**Example breakdown:**
A 350-line `training-mindset` skill covering motivation, overcoming obstacles, starting actions, and failure mindset could become:
- `training-mindset/SKILL.md` - Overview with core mindset questions
- `training-mindset/sub-skills/motivating-yourself/SKILL.md` - How to get motivated
- `training-mindset/sub-skills/overcoming-obstacles/SKILL.md` - How to push through blocks
- `training-mindset/sub-skills/starting-actions/SKILL.md` - How to begin things
- `training-mindset/sub-skills/embracing-failure/SKILL.md` - How to reframe failure

## Content Preservation Protocol

**CRITICAL**: Before deleting ANY source file, you MUST verify all content has been migrated. This section establishes the protocol for ensuring no content is lost.

### The #1 Rule: When In Doubt, Keep It

**If you're unsure where content belongs, DO NOT DELETE IT.** Options:
1. Create a `holding/` directory for ambiguous content
2. Ask the user where it should go
3. Add it to an artifact with a `## Unsorted` section
4. Migrate it to a related role that might use it

**Never assume content is "not needed" or "outdated."** Personal notes, dated entries, and resource links often have sentimental or practical value that isn't obvious.

### Pre-Migration: Content Audit

Before restructuring, create a **written** inventory (not mental):

1. **List all files** with their line counts
2. **Categorize each file's content** by destination:
   - Same role: skill / artifact / knowledge / decision / habit
   - Different role: specify which role
   - Unsure: mark for user decision
3. **Flag high-risk content types** that are often lost:
   - [ ] Links and URLs
   - [ ] Motivational quotes (especially with `#id:` markers)
   - [ ] Dated entries (>YYYY-MM-DD)
   - [ ] TODO items ([ ])
   - [ ] Personal lists (habits, resources, books)
   - [ ] Religious/spiritual content
4. **Calculate expected line count** for destination

### During Migration: Track Everything

For each source file being processed:

1. **Read the ENTIRE file** before making any changes
2. **Process ALL content** - don't stop after finding "enough" for one skill
3. **Use source attribution**: Add `### From [Source File/Role]` headers when migrating
4. **Handle every item**: Each question, link, note must go somewhere or be explicitly marked as duplicate

### Post-Migration: Verification Checklist (MANDATORY STOP GATE)

**⛔ DO NOT DELETE ANY SOURCE FILES UNTIL ALL BOXES ARE CHECKED ⛔**

Before deleting any source file, complete this checklist:

- [ ] **Re-read the ENTIRE source file** line by line after migration
- [ ] **For EACH item**, explicitly state: "This was migrated to [destination]" or "This is duplicate of [existing content]"
- [ ] **Run line count verification**:
  ```bash
  # Count non-blank lines in source
  cat "source-file.md" | grep -v '^[[:space:]]*$' | wc -l
  # Compare to destination additions
  ```
- [ ] **Spot-check 5+ specific items** by searching for unique phrases in destinations
- [ ] **Check for orphaned content**:
  - [ ] All URLs/links accounted for?
  - [ ] All `#id:` tagged items accounted for?
  - [ ] All dated entries (>YYYY) accounted for?
  - [ ] All TODO items ([ ]) accounted for?
- [ ] **Cross-role check**: Did any content belong in a different role? If so, migrate there first.
- [ ] **User confirmation**: For large deletions (>50 lines), show user what will be deleted and get explicit approval

### Content Types That Are Often Missed

Be especially careful with:
- **Links and resources** (URLs, book references, video links, Etsy shops, YouTube timestamps)
- **Personal notes** (thoughts, reflections inline with questions)
- **TODO items** (action items marked with [ ])
- **Dated entries** (content with timestamps like >2019-10-12)
- **Hashtags and special markers** (#want, #need, #habit, #goal, #id:motivational-quote-*)
- **Code snippets and examples**
- **Nested content** (indented items under main points)
- **Motivational quotes and affirmations** (especially numbered/tagged ones)
- **Personal habit lists** (daily routines, morning/evening practices)
- **Spiritual/religious content** (prayers, Quran notes, Ramadan prep)
- **Character trait content** ("Be Confident", "Be Patient" style files)
- **Curated resource collections** (book lists, course lists, expert lists)

### Special Markers to Search For Before Deleting

Run these searches on source files before deleting:

```bash
# Find all tagged content
grep -E "#id:|#want|#need|#habit|#goal|#THOUGHT|#Realization" source-file.md

# Find all links
grep -E "https?://|www\." source-file.md

# Find all dated entries
grep -E ">[0-9]{4}-[0-9]{2}-[0-9]{2}|@[0-9]{4}-[0-9]{2}-[0-9]{2}" source-file.md

# Find all TODO items
grep -E "^\s*-?\s*\[ \]" source-file.md
```

If any of these return results, verify each item was migrated.

### When Merging Roles: Extended Protocol

When merging one role into another:

1. **Create COMPREHENSIVE content mapping table** before starting:
   ```
   | Source File | Content Type | Line Count | Destination | Cross-Role? | Status |
   |-------------|--------------|------------|-------------|-------------|--------|
   | growth.md | questions | 45 | reflecting-on-growth skill | No | Pending |
   | Be Patient.md | affirmations + quotes | 40 | self-affirmations artifact | No | Pending |
   | Ramadan.md | personal planning | 161 | The Servant | YES | Pending |
   | motivational-quotes | quotes (#id:35-87) | 78 | The Motivator | YES | Pending |
   ```

2. **Identify ALL cross-role destinations** - content that belongs in a different role entirely
3. **Present mapping to user** for approval before executing - especially cross-role migrations
4. **Migrate cross-role content FIRST** - before deleting source role
5. **Update mapping status** as you migrate each piece
6. **Run line count verification** after migration:
   ```bash
   git diff --stat HEAD -- "source-role/" "dest-role1/" "dest-role2/" | tail -1
   # Insertions should be >= deletions (accounting for structural overhead)
   ```
7. **Final verification**: Show user what was migrated where, with line counts

### The "Will Any Content Be Lost?" Test

Before any deletion, you should be able to answer:
- "Where did [specific item X] go?" → [Exact file and section]
- "What happened to [source file Y]?" → [List of all destinations]
- "Is anything being deleted without migration?" → Only true duplicates

**If you cannot answer these questions, DO NOT delete the source files yet.**

### Role Deletion Safety Protocol

**⛔ NEVER delete an entire role directory without this protocol ⛔**

When deleting a role (after merging or restructuring):

1. **List ALL files in the role**:
   ```bash
   find "role-directory/" -type f -name "*.md" -o -name "*.txt"
   ```

2. **For EACH file**, document:
   - File name and line count
   - Where content was migrated (file path + section)
   - If cross-role: which role received it
   - If not migrated: why (duplicate, empty, etc.)

3. **Run pre-deletion verification**:
   ```bash
   # Count what you're about to delete
   find "role-directory/" -type f \( -name "*.md" -o -name "*.txt" \) -exec cat {} \; | grep -v '^[[:space:]]*$' | wc -l

   # This number should be accounted for in your migration mapping
   ```

4. **Search for high-value content markers**:
   ```bash
   grep -r "#id:\|https://\|>20[0-9][0-9]\|\[ \]" "role-directory/"
   ```
   Each result must have a documented destination.

5. **Get user confirmation** before `rm -rf`:
   - Show the file list
   - Show where each file's content went
   - Show the line count balance (deleted vs added)

6. **Use git, not rm**: Prefer `git rm -r` so content can be recovered if needed

### Post-Verification Recovery Protocol

When verification reveals content was lost, use git to recover and properly migrate:

**Recovery Steps**:

1. **Restore from git history**:
   ```bash
   git checkout <baseline-commit> -- path/to/deleted/directory/
   ```

2. **Read each restored file and merge into proper location**:
   - Initiative content → `initiatives/[name]/Overview.md`
   - Exploration/tinkering notes → `artifacts/explorations.md`
   - Unorganized content → `artifacts/unorganized.md`
   - Gotchas/learnings → `artifacts/learnings.md`
   - Generated files → `artifacts/generated/`
   - Reference material → `knowledge/`

3. **Verify specific items migrated** (search for unique phrases):
   ```bash
   grep "unique phrase from source" destination-file.md
   ```

4. **Cleanup restored files after migration**:
   ```bash
   git reset HEAD
   rm -rf path/to/restored/directory/
   ```

5. **Final verification**:
   ```bash
   git status --short
   # Should only show M (modified) and ?? (new) files
   ```

**Key Principle**: Don't create intermediate directories like `source-content/`. Instead, properly merge content into the established structure (artifacts/, initiatives/, knowledge/, etc.).

## Role Identification

**CRITICAL**: Before proceeding, identify the specific role to structure.

If not provided, ask: "Which role would you like me to structure? (e.g., roles-self-development/The Self Reflector)"
Ask this question using the AskUserQuestion tool.

Common paths: `roles-self-development/`, `roles-software-development/`, `roles-business-development/`, `roles-family/`, `roles-creative/`, `roles/`

## Quick Assessment

### Minimum Structure (All Roles)
- [ ] **Overview.md** - Role description, philosophy, skills/habits/knowledge tables
- [ ] **Responsibilities.md** - Inputs, outputs, success metrics

### Optional Components

#### For Self-Development Roles

| Component | Create If... |
|-----------|-------------|
| **skills/** | Role has reusable processes worth extracting |
| **habits/** | **ALWAYS** - every role has habits (even if only ideating status) |
| **expectations/** | Role has standards/qualities to embody (especially career, family, community roles) |
| **artifacts/** | Role has personal action items, learnings, or learning plans to track |
| **knowledge/** | Role requires mastering topics, has learning material, reference content |
| **decisions/** | Role involves major one-time life decisions to explore |
| **Activities.md** | Role has FEW or NO skills (otherwise incorporate into Overview.md) |

**Note on Habits**: Every role should have a `habits/` directory. If no habits are currently practiced, create habits with `status: ideating` for regular practices you WANT to establish. This makes implicit desires explicit and connects to The Self Reflector's `decisions/developing-capabilities/` for tracking which capabilities to develop.

#### For Technical/Development Roles

| Component | Create If... |
|-----------|-------------|
| **skills/** | Role has SOPs, runbooks, techniques, or mechanisms to document |
| **processes/** | Role has regular technical workflows (weekly backups, code reviews) |
| **expectations/** | Role has professional standards to embody (especially leadership/senior roles) |
| **artifacts/** | Role has implementation journals, TODOs, generated outputs, exploration notes |
| **initiatives/** | Role has ongoing projects/efforts that apply its skills |
| **knowledge/** | Role has technical reference, tool docs, gotchas to document |
| **decisions/** | Role involves technology choices or architectural decisions |

### Avoiding Redundancy: Activities.md vs Overview.md

**Don't create separate Activities.md if role has skills** - the skills already contain planning questions.

**When role has skills, use this Overview.md structure:**
```markdown
## Skills
| Skill | Essence | Invoke |
|-------|---------|--------|
| [Skill Name](skills/skill-name/SKILL.md) | Brief description | `/skill-name` |

## Habits
| Habit | Frequency | Timing | Skills Combined |
|-------|-----------|--------|-----------------|
| [Habit Name](habits/habit-name/HABIT.md) | Daily | Evening | skill-1, skill-2 |

## Expectations
| Expectation | Essence | Source |
|-------------|---------|--------|
| [Breaking Molds](expectations/breaking-molds.md) | Think beyond conventional boundaries | Industry, role models |

## Knowledge Areas
| Topic | Description | Status |
|-------|-------------|--------|
| [Design Patterns](knowledge/design-patterns.md) | Core OOP patterns | Learning |
| [Concurrency](knowledge/concurrency.md) | Threading, async | Queued |

## Decisions
| Decision | Status | Link |
|----------|--------|------|
| [Pursuing Grad Degree](decisions/pursuing-grad-degree/) | Exploring | Overview |

## Other Activities
Minor activities without dedicated skills:
- **Activity Name**: Key planning questions
```

## Migration Checklist

### Phase 0: Pre-Migration Inventory (MANDATORY)
- [ ] **List ALL files** with line counts: `find role/ -type f \( -name "*.md" -o -name "*.txt" \) -exec wc -l {} \;`
- [ ] **Calculate total non-blank lines**: `find role/ -type f \( -name "*.md" -o -name "*.txt" \) -exec cat {} \; | grep -v '^[[:space:]]*$' | wc -l`
- [ ] **Search for high-value markers**: `grep -r "#id:\|https://\|>20[0-9][0-9]\|\[ \]" role/`
- [ ] **Create written content mapping table** with columns: Source File | Content Type | Lines | Destination | Cross-Role? | Status
- [ ] **Identify cross-role content** that belongs in different roles (spiritual → Servant, quotes → Motivator, etc.)
- [ ] **Present mapping to user** for approval before proceeding

### Phase 1: Discovery
- [ ] Read ALL files to understand full scope (don't skim)
- [ ] Identify content types: skills, artifacts, knowledge, decisions, **cross-role**
- [ ] Identify: planning questions vs personal content
- [ ] Identify: which activities → skills, which → "Other Activities"
- [ ] Check `/questions` directory for relevant questions to consolidate
- [ ] **Update content mapping** with any new discoveries

### Phase 2: Core Structure
- [ ] **Overview.md**: Role description, philosophy, focus areas, component tables
- [ ] **Responsibilities.md**: Inputs, outputs, success metrics
- [ ] Handle special directories if present (Background/, Learning Topics/, Mindset/, Definitions/)

### Phase 3: Skills, Habits, Artifacts
- [ ] **Verb Audit**: List all verbs from source file/folder names - each verb is a potential skill
- [ ] **skills/**: Extract reusable processes → See [guides/generalizing-skills.md](guides/generalizing-skills.md)
- [ ] **habits/**: Extract regular practices → See [guides/generalizing-habits.md](guides/generalizing-habits.md)
- [ ] **artifacts/**: Move personal content → See [guides/organizing-artifacts.md](guides/organizing-artifacts.md)
- [ ] **Verify verbs captured**: For each verb identified, confirm it's captured as a skill (not just artifact/knowledge)
- [ ] **artifacts/learning-plans.md**: Create if role has personal learning goals
- [ ] **Consolidate questions**: Move relevant questions from `/questions` → skills
- [ ] **Define skill scopes**: Add `scope` to frontmatter and Scope section to each skill
- [ ] **Source attribution**: Add `### From [Source]` headers for migrated content

### Phase 3.5: Skill Gap Analysis (⚠️ USER CONFIRMATION REQUIRED)

After organizing existing content into skills, **proactively identify missing skills or question sets** that would make the role more complete.

**Process:**
1. Review the skills you've created from existing content
2. Ask: "What other questions would someone in this role ask themselves?"
3. Consider common skill gaps:
   - If role has "doing" skills, does it have corresponding "reflecting" skills?
   - If role has "planning" skills, does it have "evaluating outcomes" skills?
   - Are there industry-standard frameworks or questions missing?
4. **Present recommendations to user** with clear rationale
5. **Get explicit confirmation** before adding new skills

**Recommendation Format:**
```
## Recommended Additional Skills

Based on the existing content, I recommend adding these skills:

| Skill | Rationale | Key Questions It Would Cover |
|-------|-----------|------------------------------|
| [skill-name] | [Why this skill is valuable for the role] | [2-3 example questions] |

Would you like me to create any of these skills?
```

**Examples of skill gaps to look for:**

| Role Type | Existing Skills | Likely Missing |
|-----------|-----------------|----------------|
| Decision-making role | making-decisions | reflecting-on-decisions, evaluating-options |
| Learning role | acquiring-knowledge | reflecting-on-learnings, applying-knowledge |
| Management role | planning, prioritizing | retrospectives, assessing-outcomes |
| Creative role | creating, ideating | critiquing, iterating |
| Relationship role | communicating | reflecting-on-relationships |

**Cross-role skill connections:**
- If a role has "doing" skills, check if The Self Reflector has corresponding reflection skills
- If a role has "planning" skills, check if it connects to The Manager's planning framework
- If a role involves decisions, ensure connection to The Decision Maker skills

**IMPORTANT**: Do NOT skip this phase. Always present skill gap recommendations to the user, even if you think the existing skills are sufficient. The user may have domain knowledge you don't.

### Phase 4: Knowledge & Decisions (if applicable)
- [ ] **knowledge/**: Organize domain concepts, mental models, reference material (NOT questions - those go in skills)
- [ ] **decisions/**: Structure major life decisions with options, criteria, exploration
- [ ] Link knowledge topics to learning plans in artifacts

### Phase 5: Cross-Role Migration (if applicable)
- [ ] **Migrate spiritual content** to The Servant (if any)
- [ ] **Migrate motivational quotes** to The Motivator (if any `#id:motivational-quote-*`)
- [ ] **Migrate learning content** to The Learner (if any)
- [ ] **Migrate purpose/passion content** to The Self Reflector (if any)
- [ ] **Migrate discipline/habit content** to The Self Master (if any)
- [ ] **Verify cross-role migrations** before proceeding to cleanup

### Phase 6: Verification & Cleanup (⛔ STOP GATE)
- [ ] **Re-read ALL source files** line by line after migration
- [ ] **Verify each item** was migrated or is duplicate - document where
- [ ] **Spot-check 5+ specific items** in their destinations
- [ ] **Run line count verification**:
  ```bash
  git diff --stat HEAD -- "affected-directories/" | tail -1
  # Insertions should be close to deletions
  ```
- [ ] **Search for orphaned high-value content**:
  ```bash
  # In source files, find anything not yet migrated
  grep -r "#id:\|https://\|>20[0-9][0-9]\|\[ \]" "source-role/"
  ```
- [ ] **User approval**: Show user what will be deleted and get explicit "yes"
- [ ] Remove redundant files using `git rm` (ONLY after all above checked)
- [ ] Final structure validation

### Phase 7: Post-Commit High-Level Verification

**IMPORTANT**: After committing, run a high-level check across the entire migration period. This catches content lost across MULTIPLE commits that per-commit checks miss.

```bash
# Find the commit before migrations started
git log --oneline -20

# Run high-level diff from before migrations to now
git diff --stat <baseline-commit>..HEAD -- roles-self-development/ roles/ | tail -1

# Check: Insertions should be >= Deletions (or close, with documented reasons for gap)
```

**High-value marker verification:**
```bash
# Count specific markers before and after
echo "Motivational quotes deleted vs current:"
echo "  Deleted: $(git diff <baseline>..HEAD | grep "^-" | grep -c "#id:motivational-quote")"
echo "  Current: $(grep -r "#id:motivational-quote" --include="*.md" | wc -l)"

echo "URLs deleted vs added:"
echo "  Deleted: $(git diff <baseline>..HEAD -- roles-self-development/ roles/ | grep "^-" | grep -cE "https?://")"
echo "  Added: $(git diff <baseline>..HEAD -- roles-self-development/ roles/ | grep "^+" | grep -cE "https?://")"
```

**Why both per-commit AND high-level checks?**
- Per-commit catches issues immediately during migration
- High-level catches cumulative loss across multiple commits
- High-level catches content moved externally (blog, other repos) that wasn't flagged

## Key Principles

1. **Preserve formatting**: Never alter hashtags, indentation, or special characters
2. **Preserve references**: Never discard links or tidbits
3. **Skills = recipes + questions**: Extract processes and questions to ask (not answers)
4. **Artifacts = personal answers + learning plans**: Questions with your answers, action items, learnings
5. **Knowledge = what to learn**: Topics, concepts, resources for role mastery
6. **Decisions = choices to make**: Major one-time decisions with exploration
7. **Habits as headers**: Organize artifacts by the habit that created them
8. **Frontmatter on everything**: Every skill, artifact, knowledge file needs frontmatter
9. **Source attribution**: Always note where migrated content came from
10. **Verify before delete**: Never delete source files without verification
11. **Cross-role awareness**: Content may belong in a different role - migrate there, don't delete
12. **When in doubt, keep it**: Create a holding area for ambiguous content rather than deleting

## Common Pitfalls (Things That Cause Content Loss)

### ❌ Pitfall 1: Assuming Content Doesn't Fit
**Wrong**: "This motivational quote doesn't fit in The Learner, so I'll skip it"
**Right**: "This quote belongs in The Motivator - I'll migrate it there"

### ❌ Pitfall 2: Only Migrating Questions
**Wrong**: Migrating questions but leaving behind the personal notes, links, and reflections
**Right**: Migrate EVERYTHING - questions, notes, links, dated entries, TODO items

### ❌ Pitfall 3: Treating Numbered/Tagged Content as Generic
**Wrong**: "These are just motivational quotes, they're probably duplicates"
**Right**: `#id:motivational-quote-67` is a specific, tracked item - verify it exists somewhere

### ❌ Pitfall 4: Skipping "Unorganized" Files
**Wrong**: "This file is called 'Unorganized, Ramadan.md' - probably not important"
**Right**: "Unorganized" files often contain the most personal, valuable content - read every line

### ❌ Pitfall 5: Deleting Without Line Count Check
**Wrong**: Delete source files after "feeling like" everything was migrated
**Right**: Run `git diff --stat` - if deletions >> insertions, content was lost

### ❌ Pitfall 6: Ignoring Nested Content
**Wrong**: Migrating top-level bullets but missing indented sub-items
**Right**: Preserve the ENTIRE hierarchy including all nested content

### ❌ Pitfall 7: Not Checking Cross-Role Destinations
**Wrong**: Deleting a role and assuming all content belonged in the merge target
**Right**: Content from "The Developer of My Inner Self" might go to 4+ different roles

## File Naming Conventions

### Prefer Markdown (.md) Over Text (.txt)

**Always use `.md` extension** for all content files. Markdown provides:
- Consistent rendering across tools
- Frontmatter support for metadata
- Better formatting options
- Syntax highlighting in editors

**When encountering .txt files:**
1. Rename to `.md` extension
2. Add frontmatter if missing
3. Verify content renders correctly

### Naming Convention: kebab-case

Use lowercase kebab-case for all file and directory names:

| Bad | Good |
|-----|------|
| `Reflecting on Value.md` | `reflecting-on-value.md` |
| `Identifying Interests.txt` | `identifying-interests.md` |
| `My Learning Plans.md` | `learning-plans.md` |
| `PURPOSE DISCOVERY.md` | `purpose-discovery.md` |

**Why kebab-case?**
- Consistent with skill/habit directory naming
- No quoting needed in terminal commands
- Works across all operating systems
- Matches URL-friendly conventions

## Role Naming & Merging

When restructuring, renaming, or merging roles, follow these guidelines to preserve history and prevent confusion.

### Capturing Role History in Overview.md

Every role's Overview.md should include a **Role Evolution** section that documents:

```markdown
## Role Evolution

- **Previous Names**: [List all previous names this role was known by]
- **Merged Roles**: [List roles that were merged into this one, with brief note on what was absorbed]
- **Related Concepts**: [Alternative terms for this role's focus]
```

**Example:**
```markdown
## Role Evolution

- **Previous Names**: The Self Discipliner, The Conductor, The Controller
- **Merged Roles**:
  - The Striver (partial - desires content absorbed into controlling-desires skill)
  - The Thinker (partial - mindset content absorbed into training-mindset skill)
- **Related Concepts**: Self-control, self-regulation, discipline
```

### When Merging Roles

1. **Identify overlap**: Determine which content is redundant vs. unique
2. **Create content mapping table**: Show source → destination for ALL content
3. **Present mapping to user**: Get approval before executing
4. **Migrate content**: Move questions/content to appropriate destinations, noting source with `### From [Role Name]`
5. **Update receiving role's Overview**: Add merged role to "Merged Roles" list
6. **Verify migration**: Re-read source files, confirm all content migrated
7. **Delete source role**: ONLY after verification complete

### When Renaming Roles

1. **Rename directory**: `mv "Old Name" "New Name"`
2. **Update Overview.md**: Change title and add old name to "Previous Names"
3. **Update references**: Search codebase for `[[Old Name]]` links and update them

### When Repurposing Roles

If a role has valuable content but significant overlap, consider repurposing rather than deleting:

1. **Migrate overlapping content** to the better-suited role
2. **Keep unique content** that serves a distinct purpose
3. **Rename if needed** to better reflect the focused scope
4. **Update Overview** to document what was migrated out and why

**Example**: The Thinker → The Philosopher
- Mindset content migrated to The Self Master
- Reflection content migrated to The Self Reflector
- Philosophical understanding content kept and role renamed to reflect focused scope

## Artifact Structure

Every artifact file should have frontmatter:
```markdown
---
intent: [What this artifact captures - the core purpose]
habits: [List of habits that update this artifact]
---

# Artifact Name

## [Habit Name]
[Personal content: questions with your answers, action items, learnings]
```

**Artifact contains**: Questions you've attempted to answer (with your reflection/answer), action items, personal learnings, specific instances, learning plans.

**Artifact does NOT contain**: Generic questions without answers (those go in skills/habits).

### Learning Plans Artifact

For roles with knowledge to acquire, create a learning plans artifact:

```markdown
---
intent: Personal plans and progress for acquiring role knowledge
habits: [weekly-review, quarterly-planning]
---

# Learning Plans

## Current Focus
### [Topic Name]
- **Priority**: High/Medium/Low
- **Timeline**: Target completion date
- **Progress**: Current status
- **Resources**: What you're using to learn
- **Next Steps**: Immediate actions

## Queued Topics
- [Topic 2] - Will start after [Topic 1]
- [Topic 3] - Low priority, someday

## Completed
- [Topic X] - Completed [date], key learnings: ...
```

## Knowledge Structure

Knowledge files contain **foundational prerequisite information** - things you need to understand BEFORE doing something. They are **not** wisdom gained from experience (that goes in artifacts).

Every knowledge file should have frontmatter:
```markdown
---
topic: [Topic name]
status: reference
---

# Topic Name

## Overview
[What this domain/concept is about]

## Key Concepts
[Core ideas and how they relate to each other]

## Frameworks/Models
[Mental models for thinking about this space]

## Terminology
[Important terms and definitions]

## Resources (optional)
- Books: [List]
- Articles: [List]
```

**Knowledge contains**:
- Domain concepts and how they interconnect
- Mental models and frameworks for understanding
- Definitions and terminology
- Reference material you'd look up BEFORE doing something
- Principles and guidelines from external sources
- Prerequisite information needed to exercise a skill

**Knowledge does NOT contain**:
- Questions to ask yourself (those go in **skills**)
- Your personal learning plan (that's an **artifact**)
- Your personal answers/reflections (those are **artifacts**)
- TODO items or action items (those are **artifacts**)
- **Lessons learned from experience** (those are **artifacts**)
- **Gotchas you discovered** (those are **artifacts**)
- **Personal observations/insights** (those are **artifacts**)

**The Key Test**:
- Knowledge answers "What do I need to know BEFORE doing this?"
- Artifacts answer "What did I learn FROM doing this?"

**Examples**:
| Content | Type | Reasoning |
|---------|------|-----------|
| "Shortcuts has actions for X, Y, Z" | Knowledge | Prerequisite reference |
| "Shortcuts has a 2-minute timeout #gotcha" | Artifact | Learned through experience |
| "What is process meshing?" | Knowledge | Foundational concept |
| "Process meshing failed for me when..." | Artifact | Personal experience |

## Expected Outcome

### Self-Development Role Structure

```
roles-self-development/<Role Name>/
├── Overview.md          # With Skills/Habits/Expectations/Knowledge/Decisions tables
├── Responsibilities.md  # Inputs, outputs, success metrics
├── skills/              # Reusable processes, questions to ask
│   └── skill-name/
│       └── SKILL.md     # With status: ideating|establishing|practicing|established
├── habits/              # Regular practices with timing (EVERY ROLE)
│   └── habit-name/
│       └── HABIT.md     # With status: ideating|establishing|practicing|established
├── expectations/        # Standards/qualities to embody
│   ├── Overview.md      # "What do we expect of someone playing this role?"
│   └── [expectation].md # Specific expectation with observations
├── artifacts/           # Personal outcomes, answers, learnings
│   ├── [Artifact].md    # With frontmatter, contains personal answers
│   └── learning-plans.md # Personal plans for knowledge acquisition
├── knowledge/           # If applicable - prerequisite info
│   └── [topic].md       # Topics to learn, reference material
└── decisions/           # If applicable - major one-time choices
    └── [decision-name]/
        ├── Overview.md  # Decision context and status
        └── ...          # Options, criteria, exploration
```

### Business-Development Role Structure

```
roles-business-development/<Role Name>/
├── Overview.md          # With Skills/Habits/Expectations/Knowledge/Decisions tables
├── Responsibilities.md  # Inputs, outputs, success metrics
├── skills/              # How to do things in this role
│   └── skill-name/
│       └── SKILL.md     # With status: ideating|establishing|practicing|established
├── habits/              # Regular practices with timing
│   └── habit-name/
│       └── HABIT.md     # With status: ideating|establishing|practicing|established
├── expectations/        # What stakeholders/industry expect of this role
│   ├── Overview.md      # "What do we expect of someone playing this role?"
│   └── [expectation].md # Specific expectation (e.g., breaking-molds.md)
├── artifacts/           # Personal notes, learnings, observations
│   └── [Artifact].md    # With frontmatter
├── knowledge/           # Domain knowledge for the role
│   └── [topic].md       # Topics to learn, reference material
└── decisions/           # Career decisions
    └── [decision-name]/
        ├── Overview.md  # Decision context and status
        └── ...          # Options, criteria, exploration
```

### Technical/Development Role Structure

```
roles-software-development/<Role Name>/
├── Overview.md          # With Skills/Processes/Expectations/Initiatives/Knowledge/Decisions tables
├── Responsibilities.md  # Inputs, outputs, success metrics
├── skills/              # SOPs, runbooks, techniques
│   └── skill-name/
│       └── SKILL.md     # With status: ideating|establishing|practicing|established
├── processes/           # Regular technical workflows (equivalent of habits/)
│   └── process-name/
│       └── PROCESS.md   # With status: ideating|establishing|practicing|established
├── expectations/        # Professional standards (especially for leadership roles)
│   ├── Overview.md      # "What do we expect of someone playing this role?"
│   └── [expectation].md # Specific expectation
├── initiatives/         # Ongoing projects applying skills
│   └── initiative-name/
│       ├── Overview.md  # Goal, status, scope
│       └── progress.md  # Timeline, milestones
├── artifacts/           # Implementation journals, TODOs, generated files
│   ├── [project]-notes.md    # Implementation journal
│   ├── explorations.md       # Tinkering and experimentation notes
│   └── unorganized.md        # Holding area for unsorted content
├── knowledge/           # Technical reference (prerequisite info)
│   └── [topic].md       # Tool docs, reference material
└── decisions/           # Technology choices
    └── [decision-name]/
        ├── Overview.md  # Decision context and status
        └── options.md   # Technologies/approaches being considered
```

## Incremental Migration: Small Commits, Frequent Verification

**CRITICAL**: Never do a large migration in a single commit. Break it into small, verifiable steps.

### Why Incremental Migration?

| Approach | Risk | Recovery Difficulty |
|----------|------|---------------------|
| Single large commit | High - hard to spot what's missing | Hard - must review entire diff |
| Small incremental commits | Low - easy to verify each step | Easy - can revert specific commit |

### Recommended Commit Cadence

1. **Commit after each file migration** (or small group of related files)
2. **Run verification after EACH commit** - don't batch
3. **Commit message should document what was migrated where**

**Example commit sequence:**
```
git commit -m "Migrate growth questions to reflecting-on-growth skill"
git commit -m "Migrate purpose questions to reflecting-on-purpose skill"
git commit -m "Migrate Be Patient.md to self-affirmations artifact"
git commit -m "Cross-role: Migrate Ramadan.md to The Servant"
git commit -m "Delete empty source files after verification"
```

### Verification After Each Commit

```bash
# After EACH commit, run quick verification
git diff --stat HEAD~1 | tail -1
# Should show reasonable balance for that specific migration
```

### Benefits of Small Commits

1. **Easy rollback**: If you notice loss, `git revert` one commit
2. **Clear audit trail**: Commit history shows exactly what went where
3. **Catch issues early**: Don't accumulate problems across large changes
4. **User can review**: Each commit is small enough to review quickly

## Recovery Protocol: When Content Loss is Detected

If verification reveals content loss after commits have been made:

### Step 1: Don't Panic - Git Has Everything

```bash
# Find the commit before the problem
git log --oneline -20

# View any file at any point in history
git show <commit>:"path/to/file.md"
```

### Step 2: Identify What's Missing

```bash
# Compare current state to before migration
git diff <baseline>..HEAD | grep "^-" | grep -v "^---" | head -100

# Filter for high-value content
git diff <baseline>..HEAD | grep "^-" | grep -E "#id:|https://|>20[0-9]"
```

### Step 3: Recover to Appropriate Location

```bash
# Extract file content to recover
git show <baseline>:"path/to/lost/file.md" > /tmp/recovered.md

# Review and migrate to correct destination
```

### Step 4: Document the Recovery

Add to migration audit:
- What was lost
- When it was lost (which commit)
- Where it was recovered to
- Root cause (why it was missed)

## Pre-Flight Checklist: Before Starting ANY Migration

Run this checklist BEFORE starting migration work:

- [ ] **Noted baseline commit**: Record the commit hash before any changes (this is your recovery point)
- [ ] **Inventoried all files**: Listed all files with line counts
- [ ] **Identified high-value markers**: Searched for `#id:`, URLs, dates, TODOs
- [ ] **Created content mapping table**: Documented where each file will go
- [ ] **Identified cross-role content**: Flagged content for other roles
- [ ] **User approved mapping**: Got explicit approval before proceeding
- [ ] **Cleared schedule**: Have uninterrupted time to complete with verification

## Detailed Guides

For step-by-step instructions on specific components:
- **Role Groupings**: [guides/role-groupings.md](guides/role-groupings.md) - How roles are organized (self-development, software-development, business-development, etc.)
- **Skills**: [guides/generalizing-skills.md](guides/generalizing-skills.md)
- **Habits**: [guides/generalizing-habits.md](guides/generalizing-habits.md)
- **Artifacts**: [guides/organizing-artifacts.md](guides/organizing-artifacts.md)
- **Content Verification**: [guides/verifying-content-preservation.md](guides/verifying-content-preservation.md) - Using git diff line counts to verify no content was lost during migrations
