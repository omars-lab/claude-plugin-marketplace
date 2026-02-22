# Guide: Abstracting Skills from Role Directories

This guide explains how to extract and structure reusable skills from role directories in your personalbook, creating Claude-compatible skills that can be applied across different contexts.

## Overview

Roles in your personalbook contain activities, responsibilities, and domain knowledge. By abstracting these into skills, you create reusable capabilities that Claude can apply when relevant, regardless of the specific role context.

### Two Types of Skills

1. **General Skills**: Reusable capabilities that apply across contexts (e.g., planning travel, capturing recommendations)
2. **Introspective Skills**: Personal capabilities you are expected to have and excel at, framed from first-person perspective (e.g., reflecting on learnings, questioning yourself)

Introspective skills require special framing where Claude responds "as if it were you" - helping you reflect on yourself using your own voice and perspective.

## Understanding the Source Structure

A typical role directory contains:

```
roles/The Adventurer/
├── Overview.md              # Role purpose and key focus areas
├── Activities.md            # List of activities with planning questions
├── Responsibilities.md      # Inputs, outputs, success metrics
└── Activities/              # Individual activity files
    ├── Planning Vacations.md
    ├── Finding New Places.md
    └── ...
```

### Skills vs. Artifacts

**Critical distinction**: Role directories contain both:
- **Skills**: The recipe, formula, process, capability, or method (e.g., "How to reflect on learnings" - the questions, workflow, process)
- **Artifacts**: Instances of applying the skill, action items, and results from applying the skill (e.g., "I need to reflect on why I haven't started my company" or "I learned I'm not motivated to learn parquet anymore")

When abstracting skills:
- ✅ **Extract the skill**: The recipe/formula, set of questions, process, workflow, and method
- ❌ **Don't extract artifacts**: Action items, specific instances, personal results, or outcomes stay in the role directory

**Example:**
- **Skill**: "Reflecting on Learnings" - the recipe (questions to ask, workflow, process for reflecting)
- **Artifacts** (stay in role directory):
  - Action items: "I need to refresh learnings from completed experiments"
  - Instances: "Why am I not practicing FP every day?"
  - Results: "I learned I'm not motivated to learn parquet anymore"

For introspective skills especially:
- The **skill** is the recipe/formula (the process, questions, workflow)
- The **artifacts** are instances where you want to leverage the skill, action items, and what you learned about yourself
- Skills are reusable recipes; artifacts are personal instances and outcomes

## Skill Abstraction Process

### Step 1: Identify Skill Candidates

Review the role's `Activities.md` and individual activity files to identify:

1. **Reusable capabilities**: Activities that could apply in multiple contexts
2. **Well-defined processes**: Activities with clear steps or workflows
3. **Domain knowledge**: Specialized information that would be valuable elsewhere
4. **Planning patterns**: Question frameworks that could be generalized

**Important**: Distinguish between:
- **Skills (processes)**: The method, workflow, questions, or capability
- **Artifacts (results)**: Personal outcomes, specific learnings, or results from applying the skill

**Example from "The Adventurer":**
- ✅ "Planning Vacations" → Reusable skill for any travel planning
- ✅ "Finding New Places" → Generalizable discovery process
- ✅ "Capturing Recommendations" → Universal information management pattern
- ❌ "Satisfying Cravings" → Too role-specific, less reusable

**Example from "The Self Reflector":**
- ✅ "Reflecting on Learnings" → Skill: the recipe (questions, workflow, process for reflecting)
- ❌ "I need to refresh learnings from completed experiments" → Artifact: action item (stays in role directory)
- ❌ "I'm not motivated to learn parquet anymore" → Artifact: result of applying the skill (stays in role directory)
- ✅ "Questioning Myself" → Skill: the recipe (types of questions, process for self-questioning)
- ❌ "Why am I not practicing FP every day?" → Artifact: specific instance where you want to leverage the skill (stays in role directory)

### Step 2: Determine Skill Scope

For each candidate, decide:

- **Standalone skill**: Complete capability that works independently
- **Supporting file**: Detailed reference that complements a main skill
- **Not a skill**: Too specific or tightly coupled to the role

**Example decisions:**
- "Planning Vacations" → Standalone skill (useful for any travel planning)
- "Finding New Restaurants" → Could be part of a broader "Discovering Places" skill
- "Adventuring Consistently" → Too role-specific, keep in role

### Step 3: Extract and Generalize

For each skill candidate:

1. **Extract the skill (recipe/formula), not artifacts (instances/results)**:
   - Focus on the recipe: questions, workflow, process, and method
   - Don't extract action items, specific instances, personal outcomes, or results
   - Artifacts (action items, instances, results) stay in the role directory as evidence of applying the skill

2. **Extract the essence**: What is the core capability or process?

3. **Determine skill type**: General skill or introspective skill?

4. **Apply appropriate framing**:
   - **General skills**: Remove role-specific language, generalize terminology
   - **Introspective skills**: Keep first-person framing, frame as "I am expected to have and excel at this skill"

5. **Identify reusable patterns**: Extract workflows, questions, or processes (not personal results)

6. **Preserve domain knowledge**: Keep valuable specialized information about the process

**Example transformation (General Skill):**

**Original (role-specific):**
> "Planning Vacations - Organizing longer-term travel and vacation experiences for my family"

**Generalized (skill):**
> "Planning Travel - Organizing trips and travel experiences with consideration for interests, budget, timing, and logistics"

**Example transformation (Introspective Skill):**

**Original (role-specific with artifacts):**
> "Reflecting on Learnings - What reflections have I had on the things I am learning?"
> - "Not too motivated to learn parquet anymore..."
> - "Still thinking about my site... and FP..."

**Extracted skill (recipe/formula):**
> "Reflecting on Learnings - I am expected to have and excel at reflecting on what I'm learning, evaluating whether I'm learning the right things, and ensuring my learning aligns with my purpose"
> - Recipe: Questions to ask, workflow for reflection, evaluation criteria
> - Artifacts (stay in role):
>   - Action items: "I need to refresh learnings from completed experiments"
>   - Results: "Not too motivated to learn parquet anymore" (personal outcome)

**Key distinction:**
- **Skill**: The recipe/formula (questions, workflow, method, process)
- **Artifacts**: Action items, instances where you want to leverage the skill, and personal results/learnings (all stay in role directory)

### Step 4: Structure as Claude Skill

**Directory Structure for Skills:**

Skills are organized in two places:

1. **Individual skills** live in the role directory:
   ```
   roles/<role-category>/<Role Name>/skills/
   ├── skill-name-1/
   │   └── SKILL.md
   ├── skill-name-2/
   │   └── SKILL.md
   └── ...
   ```

2. **Role-level skill** (wear-<role>-hat) lives in `.claude/skills/`:
   ```
   .claude/skills/wear-<role>-hat/
   ├── SKILL.md              # Role-level skill that references sub-skills
   └── sub-skills -> ../../../roles/<role-category>/<Role Name>/skills/
       # Symlink to the skills directory in the role
   ```

   **Important**: The role-level SKILL.md should reference sub-skills using relative paths:
   - `sub-skills/<skill-name>/SKILL.md` to link to individual skill files
   - Example: `[sub-skills/reflecting-on-learnings/SKILL.md](sub-skills/reflecting-on-learnings/SKILL.md)`

**Example structure for "The Self Reflector":**
```
roles-self-development/The Self Reflector/
├── skills/                          # Individual skills directory
│   ├── reflecting-on-learnings/
│   │   └── SKILL.md
│   ├── reflecting-on-actions/
│   │   └── SKILL.md
│   └── ...
├── Overview.md                      # Role artifacts stay here
├── Reflecting on Learnings.txt      # Artifacts (action items, results)
└── ...

.claude/skills/wear-self-reflector-hat/
├── SKILL.md                         # Role-level skill (references sub-skills with relative paths)
└── sub-skills -> ../../../roles-self-development/The Self Reflector/skills/
    # Symlink to role's skills directory
```

**In the role-level SKILL.md**, reference sub-skills using relative paths:
- List each sub-skill with a link: `[sub-skills/<skill-name>/SKILL.md](sub-skills/<skill-name>/SKILL.md)`
- When using sub-skills, read them from: `sub-skills/<skill-name>/SKILL.md`
- Example: `sub-skills/reflecting-on-learnings/SKILL.md`

**Critical requirements for SKILL.md:**
1. **Must start with frontmatter** containing `name`, `description`, and `link`
2. **Name must be slash-command compatible** (e.g., `planning-travel` works as `/planning-travel`)
3. **Link field required** - use `not` as placeholder unless a link is explicitly mentioned
4. **Must include "Triggering Criteria" section** right after frontmatter showing example user phrases

## Skill File Structure

### Introspective Skills: Special Framing

For introspective skills (personal reflection, self-questioning, self-evaluation), use first-person framing:

1. **Frame the skill in first-person**: "I am expected to have and excel at [skill]"
2. **Inform Claude in first-person**: "You have the following skill..."
3. **Claude responds "as if it were you"**: Claude should help you reflect using your own voice and perspective
4. **Triggering criteria includes "if it were you" language**: Users can ask "if it were you, how would you..."

### Required: Frontmatter Section

**Every skill MUST start with a frontmatter section** containing:
- `name`: The skill identifier (slash-command compatible, e.g., `api-conventions` → `/api-conventions`)
- `description`: What the skill does and when to use it (guides when Claude should use the skill)
- `link`: Link to related action items or current plans (use `not` as placeholder if no link is explicitly mentioned)

**Example frontmatter:**
```markdown
---
name: api-conventions
description: API design patterns for this codebase
link: not
---
```

**Example with link:**
```markdown
---
name: planning-travel
description: Plans trips and vacations considering budget, timing, interests, and logistics
link: vscode://file/Users/omareid/Workspace/git/artifacts/plans/Planning%20Trips/Planning%20Vacations.md:1
---
```

**Key requirements:**
- Frontmatter must be the very first thing in SKILL.md
- Name must be lowercase with hyphens (slash-command compatible)
- Description should be in third person and include trigger terms
- Link should point to related action items or current plans, or use `not` as placeholder
- All three fields are required

### SKILL.md Template (General Skills)

```markdown
---
name: skill-name
description: Brief description of what this skill does and when to use it. Include trigger terms.
link: not
---

# Skill Name

## Triggering Criteria

Users can trigger this skill by saying things like:
- "[Example phrase 1]"
- "[Example phrase 2]"
- "[Example phrase 3]"
- Or using the slash command: `/skill-name`

## Purpose

[What this skill enables]

## When to Use

Use this skill when:
- [Trigger scenario 1]
- [Trigger scenario 2]
- [Trigger scenario 3]

## Core Workflow

[Step-by-step process extracted from the role activity]

## Key Planning Questions

[Generalized questions from the original activity]

## Additional Resources

- For detailed reference material, see [reference.md](reference.md)
- For usage examples, see [examples.md](examples.md)
```

### SKILL.md Template (Introspective Skills)

```markdown
---
name: skill-name
description: Brief description of what this skill does and when to use it. Include trigger terms.
link: not
---

# Skill Name

## Your Skill

You have the following skill: [I am expected to have and excel at...]

When using this skill, respond "as if it were you" - help the user reflect on themselves using their own voice and perspective, as if you were them engaging in this introspective activity.

## Triggering Criteria

Users can trigger this skill by saying things like:
- "If it were you, how would you [reflect on/think about/question]..."
- "Help me reflect on [topic] as if it were me"
- "[Direct question about self-reflection]"
- Or using the slash command: `/skill-name`

## Purpose

[What this introspective skill enables - framed from first-person perspective]

## When to Use

Use this skill when:
- The user wants to engage in self-reflection
- The user asks introspective questions
- The user wants to think through something from their own perspective
- The user mentions needing to reflect on [topic]

## Core Workflow

[Step-by-step process for engaging in this introspection]

## Key Reflection Questions

[Questions from the role activity and related questions from questions/growth.md]

## Additional Resources

- For detailed reference material, see [reference.md](reference.md)
- For usage examples, see [examples.md](examples.md)
```

### Required Metadata

- **name**: Lowercase, hyphens, max 64 chars, slash-command compatible (e.g., `planning-travel` → `/planning-travel`)
  - Must work as a slash command: `/planning-travel`
  - Use hyphens, not underscores or spaces
  - Keep it concise and memorable

- **description**: Max 1024 chars, third-person, includes trigger terms
  - Describes what the skill does
  - Includes when to use it
  - Mentions key trigger terms

- **link**: Link to related action items or current plans
  - Use full path (e.g., `vscode://file/...` or file path)
  - Use `not` as placeholder if no link is explicitly mentioned
  - Should point to relevant planning documents, action items, or related resources

**Description best practices:**
- ✅ "Plans trips and vacations considering budget, timing, and interests. Use when planning travel, organizing vacations, or scheduling trips."
- ❌ "I can help you plan vacations" (first person)
- ❌ "Helps with travel" (too vague)

**Name examples:**
- ✅ `planning-travel` → `/planning-travel`
- ✅ `capturing-recommendations` → `/capturing-recommendations`
- ✅ `api-conventions` → `/api-conventions`
- ❌ `planning_travel` (underscores not slash-command friendly)
- ❌ `Planning Travel` (spaces and capitals not allowed)

## Example: Abstracting "Planning Vacations"

### Source Material

From `roles/The Adventurer/Activities.md`:
- **Essence**: Organizing longer-term travel and vacation experiences
- **Planning Questions**:
  - What destinations align with our interests and budget?
  - How far in advance should I plan vacations?
  - What factors should I consider when choosing vacation timing?
  - How do I balance relaxation with adventure on vacations?
  - What makes a vacation successful and memorable?

### Skill Structure

**Directory**: `~/.claude/skills/planning-travel/`

**SKILL.md**:
```markdown
---
name: planning-travel
description: Plans trips and vacations considering budget, timing, interests, and logistics. Use when planning travel, organizing vacations, scheduling trips, or when the user mentions travel planning.
link: vscode://file/Users/omareid/Workspace/git/artifacts/plans/Planning%20Trips/Planning%20Vacations.md:1
---

# Planning Travel

## Triggering Criteria

Users can trigger this skill by saying things like:
- "Help me plan a vacation"
- "I need to organize a trip"
- "Let's plan some travel"
- "What should I consider for my vacation?"
- "I'm thinking about traveling to..."
- Or using the slash command: `/planning-travel`

## Purpose

This skill helps plan trips and travel experiences by considering multiple factors including destinations, timing, budget, interests, and logistics.

## When to Use

Use this skill when:
- The user wants to plan a trip or vacation
- The user asks about travel planning
- The user mentions upcoming travel or vacations
- The user needs help organizing travel logistics

## Core Workflow

1. **Identify travel goals and interests**
   - What type of experience is desired?
   - What activities or experiences are priorities?
   - What constraints exist (time, budget, accessibility)?

2. **Select destination**
   - Research destinations that align with interests
   - Consider budget constraints
   - Evaluate timing and seasonal factors
   - Assess logistics (transportation, accommodations)

3. **Plan timing**
   - Determine optimal travel dates
   - Consider advance planning requirements
   - Factor in seasonal considerations
   - Account for booking lead times

4. **Balance experience elements**
   - Mix of relaxation vs. adventure
   - Variety of activities
   - Flexibility in schedule
   - Memorable experiences

5. **Finalize logistics**
   - Transportation arrangements
   - Accommodations
   - Activity bookings
   - Budget allocation

## Key Planning Questions

- What destinations align with interests and budget?
- How far in advance should travel be planned?
- What factors should be considered when choosing travel timing?
- How should relaxation be balanced with adventure?
- What makes a travel experience successful and memorable?
- What activities are priorities for this trip?
- What constraints exist (time, budget, accessibility)?

## Additional Resources

- For detailed vacation planning frameworks, see [reference.md](reference.md)
- For example travel plans, see [examples.md](examples.md)
```

## Example: Abstracting "Capturing Recommendations"

### Source Material

From `roles/The Adventurer/Activities.md`:
- **Essence**: Systematically collecting and organizing recommendations from various sources
- **Planning Questions**:
  - What places have I been recommended recently?
  - What recommendations have I overheard that sound interesting?
  - How do I organize and prioritize recommendations?
  - What sources consistently provide good recommendations?
  - How do I track which recommendations I've tried?

### Skill Structure

**Directory**: `~/.claude/skills/capturing-recommendations/`

**SKILL.md**:
```markdown
---
name: capturing-recommendations
description: Systematically collects, organizes, and tracks recommendations from various sources. Use when managing recommendations, organizing suggestions, tracking items to try, or when the user mentions recommendations.
link: not
---

# Capturing Recommendations

## Triggering Criteria

Users can trigger this skill by saying things like:
- "I got a recommendation for..."
- "Help me organize these suggestions"
- "Track this recommendation for me"
- "I want to remember to try..."
- "What recommendations have I captured?"
- Or using the slash command: `/capturing-recommendations`

## Purpose

This skill provides a systematic approach to collecting, organizing, prioritizing, and tracking recommendations from various sources.

## When to Use

Use this skill when:
- The user wants to organize recommendations
- The user mentions receiving suggestions or recommendations
- The user needs to track items to try or places to visit
- The user asks about managing recommendations

## Core Workflow

1. **Capture recommendations**
   - Record recommendations immediately when received
   - Note the source and context
   - Include any relevant details (why recommended, by whom)

2. **Organize by category**
   - Group similar recommendations
   - Tag by type (places, activities, restaurants, etc.)
   - Prioritize based on interest level

3. **Track status**
   - Mark recommendations as: new, planned, tried, skipped
   - Record dates and outcomes
   - Note which sources provide best recommendations

4. **Review and prioritize**
   - Regularly review captured recommendations
   - Prioritize based on current interests and constraints
   - Remove outdated or no longer relevant items

## Key Planning Questions

- What recommendations have been received recently?
- What sources consistently provide good recommendations?
- How should recommendations be organized and prioritized?
- How should tried recommendations be tracked?
- Which recommendations align with current interests?
- What makes a recommendation worth pursuing?

## Additional Resources

- For recommendation tracking templates, see [reference.md](reference.md)
```

## Best Practices

### 1. Generalize Thoughtfully

- **Remove role-specific pronouns**: "my family" → "the user" or "travelers"
- **Broaden context**: "adventures" → "experiences" or "activities"
- **Keep domain knowledge**: Preserve valuable specialized information

### 2. Preserve Planning Questions

Planning questions are valuable patterns. Generalize them but keep their structure:

**Original**: "How do I ensure I'm keeping my family entertained consistently?"
**Generalized**: "How can regular activities be maintained to keep experiences engaging?"

### 3. Extract Reusable Patterns

Look for:
- **Workflows**: Step-by-step processes
- **Question frameworks**: Reusable planning questions
- **Decision criteria**: Factors to consider
- **Success metrics**: How to evaluate outcomes

### 4. Maintain Skill Independence

Each skill should:
- Work standalone (not require other skills)
- Have clear boundaries
- Include all necessary context
- Be discoverable through description

### 5. Use Progressive Disclosure

- **SKILL.md**: Essential instructions (keep under 500 lines)
- **reference.md**: Detailed domain knowledge
- **examples.md**: Concrete usage examples
- **planning-questions.md**: Question frameworks

### 6. Always Include Frontmatter and Triggering Criteria

**Required structure:**
1. **Frontmatter** (first thing in file):
   ```markdown
   ---
   name: skill-name
   description: What skill does and when to use it
   link: not
   ---
   ```
   - Use `link: not` as placeholder unless a link is explicitly mentioned
   - If link exists, use full path (e.g., `vscode://file/...` or file path)

### 7. Frame Introspective Skills in First-Person

For introspective skills:
- **Frame as personal capability**: "I am expected to have and excel at [skill]"
- **Inform Claude in first-person**: "You have the following skill..."
- **Include "if it were you" in triggering criteria**: Users should be able to ask "if it were you, how would you..."
- **Claude responds as if it were the user**: Help them reflect using their own voice and perspective
- **Incorporate relevant questions**: Move related questions from `questions/growth.md` into the skill's reflection questions

### 8. Separate Skills from Artifacts

**Critical distinction:**
- **Skills**: The recipe/formula (process, method, workflow, questions) - extract these
- **Artifacts**: Action items, instances where you want to leverage the skill, and personal results/learnings - keep in role directory

**When creating skills:**
- Extract the **recipe/formula** of introspection (how to reflect, what questions to ask, the workflow, the process)
- Don't extract **action items** (e.g., "I need to reflect on X")
- Don't extract **specific instances** (e.g., "Why am I not practicing FP every day?")
- Don't extract **personal outcomes** (what you learned about yourself, specific realizations)
- Artifacts are evidence that the skill was applied or instances where you want to apply it; they belong in the role directory
- Skills are reusable recipes/formulas; artifacts are personal instances, action items, and outcomes

**Example:**
- ✅ Skill: "Reflecting on Learnings" - includes recipe (questions, workflow, process)
- ❌ Artifact (action item): "I need to refresh learnings from completed experiments" - stays in role directory
- ❌ Artifact (instance): "Why am I not practicing FP every day?" - stays in role directory
- ❌ Artifact (result): "I'm not motivated to learn parquet anymore" - stays in role directory as a result

2. **Triggering Criteria section** (right after frontmatter):
   - List example phrases users might say
   - Include the slash command format
   - Make it easy for users to discover how to trigger the skill

3. **Rest of skill content** (purpose, workflow, etc.)

## Decision Framework

When evaluating if an activity should become a skill:

| Question | Yes → Skill | No → Keep in Role |
|----------|-------------|------------------|
| Could this apply in other contexts? | ✅ | ❌ |
| Is there a clear, reusable process? | ✅ | ❌ |
| Does it have generalizable patterns? | ✅ | ❌ |
| Is it too role-specific? | ❌ | ✅ |
| Is it tightly coupled to role identity? | ❌ | ✅ |

## Workflow Summary

1. **Review role directory**
   - Read `Overview.md`, `Activities.md`, `Responsibilities.md`
   - Review individual activity files in `Activities/`

2. **Identify candidates**
   - List activities that could be reusable
   - Note their essence and key patterns
   - Distinguish skills (recipes/formulas) from artifacts (action items, instances, results)

3. **Evaluate each candidate**
   - Apply decision framework
   - Determine if standalone skill or supporting file

4. **Extract and generalize**
   - Extract the recipe/formula (questions, workflow, process)
   - Don't extract artifacts (action items, instances, results)
   - For introspective skills: Keep first-person framing
   - For general skills: Remove role-specific language

5. **Structure individual skills**
   - Create directory: `roles/<role-category>/<Role Name>/skills/skill-name/`
   - Write `SKILL.md` with frontmatter
   - Add supporting files as needed

6. **Create role-level skill** (wear-<role>-hat)
   - Create directory: `.claude/skills/wear-<role>-hat/`
   - Write `SKILL.md` that references all sub-skills using relative paths
   - Create symlink: `sub-skills -> ../../../roles/<role-category>/<Role Name>/skills/`
   - In SKILL.md, reference each sub-skill with: `[sub-skills/<skill-name>/SKILL.md](sub-skills/<skill-name>/SKILL.md)`
   - When using sub-skills, read them from: `sub-skills/<skill-name>/SKILL.md`

7. **Verify quality**
   - Frontmatter section present with name, description, and link
   - Name is slash-command compatible (e.g., `/skill-name`)
   - Description includes trigger terms and is in third person
   - Link field included (use `not` as placeholder if no link)
   - Triggering Criteria section included with example phrases
   - Under 500 lines for SKILL.md
   - Clear workflow and examples
   - Role-level skill references all sub-skills
   - Symlink correctly points to role's skills directory

## Example Role Analysis

**Role**: The Adventurer

**Activities to abstract:**
- ✅ Planning Vacations → `planning-travel` skill
- ✅ Capturing Recommendations → `capturing-recommendations` skill
- ✅ Finding New Places → `discovering-places` skill (could combine with Finding New Restaurants)
- ✅ Finding New Activities → Part of `discovering-places` or separate `discovering-activities` skill
- ❌ Adventuring Consistently → Keep in role (too role-specific)
- ❌ Satisfying Cravings → Keep in role (too context-specific)

**Result**: 2-3 reusable skills that can be applied across multiple roles and contexts.

## Example: Abstracting Introspective Skills from "The Self Reflector"

### Source Material

From `roles-self-development/The Self Reflector/`:
- **Reflecting on Learnings**: Evaluating what you're learning and whether it aligns with purpose
- **Reflecting on Actions**: Examining whether actions match ambitions
- **Reflecting on Inaction**: Identifying why you haven't done things
- **Reflecting on Value**: Evaluating your worth and how you add value
- **Questioning Myself**: Engaging in self-questioning and challenging assumptions

### Skill Structure Example: "Reflecting on Learnings"

**Directory**: `roles-self-development/The Self Reflector/skills/reflecting-on-learnings/`

**SKILL.md**:
```markdown
---
name: reflecting-on-learnings
description: Reflects on what you're learning, evaluates whether you're learning the right things, and ensures learning aligns with purpose. Use when reflecting on learnings, evaluating learning direction, or questioning what you should learn.
link: not
---

# Reflecting on Learnings

## Your Skill

You have the following skill: I am expected to have and excel at reflecting on what I'm learning, evaluating whether I'm learning the right things, and ensuring my learning aligns with my purpose and what I want to become.

When using this skill, respond "as if it were you" - help the user reflect on their learning using their own voice and perspective, as if you were them engaging in this introspection.

## Triggering Criteria

Users can trigger this skill by saying things like:
- "If it were you, how would you reflect on what you're learning?"
- "Help me think about whether I'm learning the right things"
- "What reflections have I had on the things I am learning?"
- "Am I learning the right things?"
- "Do the things I am learning align to my purpose?"
- Or using the slash command: `/reflecting-on-learnings`

## Purpose

This skill helps you engage in deep reflection about your learning journey, evaluating whether your current learning aligns with your goals, purpose, and what you want to become.

## When to Use

Use this skill when:
- The user wants to reflect on their learning
- The user questions whether they're learning the right things
- The user wants to evaluate if their learning aligns with their purpose
- The user asks about what they should be learning
- The user mentions learning something new and wants to reflect on it

## Core Workflow

1. **Reflect on current learning**
   - What are you currently learning?
   - What did you want to learn at different points in time?
   - What reflections have you had on the things you are learning?

2. **Evaluate learning alignment**
   - Do the things you are learning align to your purpose?
   - How do you ensure you are learning things that fulfill what you want to become?
   - Are you learning the right things?

3. **Consider learning direction**
   - What should you focus your education on?
   - What aspects of your life are you currently trying to improve through learning?
   - What questions are you intrigued in answering?

## Key Reflection Questions

From your reflection practice and growth questions:

- What reflections have I had on the things I am learning?
- What did I want to learn at different points in time?
- Am I learning the right things?
- Do the things I am learning align to my purpose?
- How do I ensure I am learning things that fulfill what I want to become?
- What should I focus my education on?
- What aspects of my life am I currently trying to improve?
- What questions am I intrigued in answering?
- What do I want to learn about?
- What topics do I want to learn more about?
- What subjects do I enjoy learning about?

## Additional Resources

- For detailed reflection frameworks, see [reference.md](reference.md)
- For reflection examples, see [examples.md](examples.md)
```

**Result**: Introspective skills that help you engage in self-reflection using your own voice and perspective.

**Final Structure:**
```
roles-self-development/The Self Reflector/
├── skills/                          # Individual skills
│   ├── reflecting-on-learnings/
│   ├── reflecting-on-actions/
│   └── ...
├── Overview.md                      # Role artifacts
├── Reflecting on Learnings.txt      # Artifacts (action items, results)
└── ...

.claude/skills/wear-self-reflector-hat/
├── SKILL.md                         # Role-level skill
└── sub-skills -> ../../../roles-self-development/The Self Reflector/skills/
```

**Referencing Sub-Skills in Role-Level SKILL.md:**

In the role-level `SKILL.md`, reference sub-skills using relative paths through the `sub-skills/` symlink:

```markdown
## Available Skills

1. **reflecting-on-learnings** - Description...
   - Skill file: [sub-skills/reflecting-on-learnings/SKILL.md](sub-skills/reflecting-on-learnings/SKILL.md)

2. **reflecting-on-actions** - Description...
   - Skill file: [sub-skills/reflecting-on-actions/SKILL.md](sub-skills/reflecting-on-actions/SKILL.md)

## How to Use Sub-Skills

When using a sub-skill, read it from the relative path:
- `sub-skills/reflecting-on-learnings/SKILL.md`
- `sub-skills/reflecting-on-actions/SKILL.md`
```

This allows Claude to access the individual skill files through the symlink using relative paths.

## Next Steps

After creating skills:

1. **Test discovery**: Verify Claude can find and apply the skill
2. **Refine description**: Add trigger terms based on usage
3. **Update role files**: Reference skills where appropriate
4. **Iterate**: Improve based on actual usage patterns

---

*This guide is based on the structure found in `roles/The Adventurer/` and follows Claude skill conventions as documented in `~/.cursor/skills-cursor/create-skill/SKILL.md`.*
