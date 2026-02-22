# Guide: Abstracting Habits from Role Directories

This guide explains how to extract and structure reusable habits from role directories in your personalbook, creating habits that combine skills and create personal artifacts through regular practice.

## Overview

Habits are regular practices that combine one or more skills to create personal artifacts. Unlike skills (which are recipes/formulas), habits represent how you regularly engage with skills to produce outcomes and personal insights.

### Habits vs. Skills vs. Artifacts

1. **Skills**: Reusable recipes/formulas, processes, workflows, and methods (e.g., "How to reflect on learnings" - the questions, workflow, process)
2. **Habits**: Regular practices that mix and match skills, with guidance on frequency, timing, and how to combine skills to create artifacts
3. **Artifacts**: Personal outcomes, action items, specific instances, and results created from engaging in habits (e.g., "I need to reflect on why I haven't started my company" or "I learned I'm not motivated to learn parquet anymore")

**Key distinctions:**
- **Skills** = The recipe/formula (how to do something)
- **Habits** = How you regularly apply skills (when, how often, which skills to combine)
- **Artifacts** = Personal results from applying habits (action items, learnings, outcomes)

## Understanding the Source Structure

A typical role directory contains:

```
roles/The Self Reflector/
├── Overview.md              # Role purpose and key focus areas
├── Activities.md            # List of activities with planning questions
├── Responsibilities.md      # Inputs, outputs, success metrics
├── skills/                  # Individual skills (recipes/formulas)
│   ├── reflecting-on-learnings/
│   │   └── SKILL.md
│   └── ...
├── habits/                  # Habits (how to regularly apply skills)
│   ├── daily-reflection/
│   │   └── HABIT.md
│   └── ...
└── artifacts/                # Personal artifacts (results from habits)
    ├── Reflecting on Learnings.txt
    ├── Reflecting on Actions.md
    └── ...
```

### Habits: Mixing and Matching Skills

Habits are regular practices that:
- **Combine multiple skills**: A habit might use "reflecting-on-learnings" + "reflecting-on-actions" together
- **Specify frequency**: Daily, weekly, monthly, or as-needed
- **Define timing**: When to engage in the habit (morning, evening, after events, etc.)
- **Guide skill combination**: How to sequence or combine skills effectively
- **Create artifacts**: Personal outcomes, action items, and learnings are stored in the artifacts directory

**Example:**
- **Habit**: "Daily Reflection" - combines "reflecting-on-learnings" + "reflecting-on-actions" + "reflecting-on-inaction" every evening
- **Frequency**: Daily
- **Timing**: Evening, before bed
- **Skills used**: reflecting-on-learnings, reflecting-on-actions, reflecting-on-inaction
- **Artifacts created**: Personal reflections, action items, learnings stored in artifacts/

## Habit Abstraction Process

### Step 1: Identify Habit Candidates

Review the role's activities, skills, and existing practices to identify:

1. **Regular practices**: Activities you do consistently (daily, weekly, monthly)
2. **Skill combinations**: Practices that naturally combine multiple skills
3. **Artifact-generating activities**: Activities that produce personal outcomes, action items, or learnings
4. **Ritualized behaviors**: Activities with established timing, frequency, or context

**Important**: Distinguish between:
- **Habits (regular practices)**: How you regularly apply skills with frequency and timing
- **Skills (recipes/formulas)**: The method, workflow, questions, or capability
- **Artifacts (results)**: Personal outcomes, specific learnings, or results from applying habits

**Example from "The Self Reflector":**
- ✅ "Daily Reflection" → Habit: combines multiple reflection skills daily
- ✅ "Weekly Review" → Habit: combines reflection skills weekly
- ✅ "Capturing Self Reflections" → Habit: regularly capturing reflection artifacts
- ❌ "Reflecting on Learnings" → Skill: the recipe/formula (not a habit)
- ❌ "I need to reflect on X" → Artifact: action item (result of habit)

### Step 2: Determine Habit Scope

For each candidate, decide:

- **Standalone habit**: Complete practice that works independently
- **Supporting file**: Detailed reference that complements a main habit
- **Not a habit**: Too specific or tightly coupled to a single skill

**Example decisions:**
- "Daily Reflection" → Standalone habit (combines multiple skills)
- "Morning Reflection" → Could be part of "Daily Reflection" or separate if timing matters
- "Reflecting on Learnings" → Skill, not a habit (it's the recipe)

### Step 3: Extract and Structure Habits

For each habit candidate:

1. **Identify the skills involved**: Which skills does this habit combine?
2. **Determine frequency**: How often should this habit be practiced?
3. **Define timing**: When is the best time to engage in this habit?
4. **Specify skill combination**: How should skills be sequenced or combined?
5. **Define artifact outputs**: What personal artifacts should be created?
6. **Provide guidance**: Best practices, tips, and considerations

**Example transformation:**

**Original (activity-specific):**
> "Reflecting Daily - I reflect on my learnings, actions, and inaction every evening"

**Structured habit:**
> "Daily Reflection - Combines reflecting-on-learnings, reflecting-on-actions, and reflecting-on-inaction skills every evening to create personal reflection artifacts"

### Step 4: Structure as Habit File

**Directory Structure for Habits:**

Habits are organized in the role directory:

```
roles/<role-category>/<Role Name>/habits/
├── habit-name-1/
│   └── HABIT.md
├── habit-name-2/
│   └── HABIT.md
└── ...
```

**HABIT.md Template:**

```markdown
---
name: habit-name
description: Brief description of what this habit does and when to practice it. Include trigger terms.
frequency: daily|weekly|monthly|as-needed
timing: [When to practice - e.g., "evening", "morning", "after events", "as needed"]
---

# Habit Name

## Purpose

[What this habit enables and why it's valuable]

## When to Practice

- [Timing guidance - e.g., "Every evening before bed"]
- [Context guidance - e.g., "After completing a project"]
- [Trigger conditions - e.g., "When feeling stuck or uncertain"]

## Skills Used

This habit combines the following skills:

1. **[Skill Name 1]**: [How this skill is used in the habit]
   - Skill file: [skills/skill-name-1/SKILL.md](skills/skill-name-1/SKILL.md)
2. **[Skill Name 2]**: [How this skill is used in the habit]
   - Skill file: [skills/skill-name-2/SKILL.md](skills/skill-name-2/SKILL.md)
3. **[Skill Name 3]**: [How this skill is used in the habit]
   - Skill file: [skills/skill-name-3/SKILL.md](skills/skill-name-3/SKILL.md)

## How to Practice

### Step 1: [Preparation or setup]
- [Guidance on preparing for the habit]

### Step 2: [Apply first skill]
- [How to apply skill 1]
- [What to focus on]

### Step 3: [Apply second skill]
- [How to apply skill 2]
- [How it builds on skill 1]

### Step 4: [Apply third skill]
- [How to apply skill 3]
- [How it completes the practice]

### Step 5: [Capture artifacts]
- [How to capture personal outcomes]
- [Where to store artifacts]

## Artifacts Created

When practicing this habit, create artifacts in the `artifacts/` directory:

- **[Artifact Type 1]**: [Description of what gets created]
  - Example: `artifacts/Reflecting on Learnings.txt`
- **[Artifact Type 2]**: [Description of what gets created]
  - Example: `artifacts/Reflecting on Actions.md`

**Artifact Organization:**

Artifacts can be organized with habits as header sections. This makes it easy to see what artifacts were created from each habit:

```markdown
# [Artifact Type] Artifacts

## [Habit Name 1]
[Artifacts created from this habit]

## [Habit Name 2]
[Artifacts created from this habit]
```

**Example: `artifacts/Reflecting on Actions.md`**
```markdown
# Reflecting on Actions

## Daily Reflection
- [ ] [Action items from daily reflection habit]

## Weekly Review
- [ ] [Action items from weekly review habit]
```

**Artifact Structure:**
- Action items: `- [ ] [Specific todo items]`
- Personal learnings: `- [What you discovered about yourself]`
- Specific instances: `- [Concrete examples or questions]`
- Results: `- [Outcomes from applying the habit]`

**For detailed guidance on organizing artifacts**, see: [organizing-artifacts.md](organizing-artifacts.md)

## Frequency and Timing

- **Frequency**: [daily|weekly|monthly|as-needed]
- **Timing**: [When to practice - e.g., "evening", "morning", "after events"]
- **Duration**: [How long the habit typically takes]
- **Context**: [When this habit is most valuable]

## Best Practices

- [Tip 1 for effective practice]
- [Tip 2 for consistency]
- [Tip 3 for getting value]

## Related Habits

- **[Related Habit 1]**: [How it relates]
- **[Related Habit 2]**: [How it complements this habit]

## Additional Resources

- For detailed skill information, see the skill files referenced above
- For artifact examples, see [artifacts/](artifacts/)
```

### Required Metadata

- **name**: Lowercase, hyphens, max 64 chars, slash-command compatible (e.g., `daily-reflection` → `/daily-reflection`)
  - Must work as a slash command: `/daily-reflection`
  - Use hyphens, not underscores or spaces
  - Keep it concise and memorable

- **description**: Max 1024 chars, third-person, includes trigger terms
  - Describes what the habit does
  - Includes when to practice it
  - Mentions key trigger terms

- **frequency**: One of: `daily`, `weekly`, `monthly`, `as-needed`
  - Specifies how often the habit should be practiced

- **timing**: When to practice the habit
  - Examples: "evening", "morning", "after events", "as needed", "first thing Monday"
  - Can be specific or general based on the habit

**Description best practices:**
- ✅ "Daily reflection practice combining multiple reflection skills in the evening. Use when establishing daily reflection routines or wanting to regularly reflect on learnings, actions, and inaction."
- ❌ "I reflect daily" (first person)
- ❌ "Daily habit" (too vague)

**Name examples:**
- ✅ `daily-reflection` → `/daily-reflection`
- ✅ `weekly-review` → `/weekly-review`
- ✅ `capturing-reflections` → `/capturing-reflections`
- ❌ `daily_reflection` (underscores not slash-command friendly)
- ❌ `Daily Reflection` (spaces and capitals not allowed)

## Example: Abstracting "Daily Reflection"

### Source Material

From `roles-self-development/The Self Reflector/`:
- **Practice**: Reflecting daily on learnings, actions, and inaction
- **Skills involved**: reflecting-on-learnings, reflecting-on-actions, reflecting-on-inaction
- **Frequency**: Daily
- **Timing**: Evening
- **Artifacts**: Personal reflections, action items, learnings

### Habit Structure

**Directory**: `roles-self-development/The Self Reflector/habits/daily-reflection/`

**HABIT.md**:
```markdown
---
name: daily-reflection
description: Daily reflection practice combining multiple reflection skills in the evening. Use when establishing daily reflection routines or wanting to regularly reflect on learnings, actions, and inaction.
frequency: daily
timing: evening
---

# Daily Reflection

## Purpose

This habit enables regular self-reflection by combining multiple reflection skills to create personal insights, action items, and learnings about yourself.

## When to Practice

- Every evening before bed
- After completing significant activities or projects
- When feeling stuck or uncertain about direction
- As part of a daily routine for self-awareness

## Skills Used

This habit combines the following skills:

1. **reflecting-on-learnings**: Evaluate what you're learning and whether it aligns with purpose
   - Skill file: [skills/reflecting-on-learnings/SKILL.md](skills/reflecting-on-learnings/SKILL.md)
2. **reflecting-on-actions**: Reflect on whether actions match ambitions
   - Skill file: [skills/reflecting-on-actions/SKILL.md](skills/reflecting-on-actions/SKILL.md)
3. **reflecting-on-inaction**: Identify why you haven't done things you want to do
   - Skill file: [skills/reflecting-on-inaction/SKILL.md](skills/reflecting-on-inaction/SKILL.md)

## How to Practice

### Step 1: Set the context
- Find a quiet time in the evening
- Review your day or recent activities
- Prepare to engage in honest self-reflection

### Step 2: Reflect on learnings
- Apply the reflecting-on-learnings skill
- What are you currently learning?
- Do your learnings align with your purpose?
- What should you focus your education on?

### Step 3: Reflect on actions
- Apply the reflecting-on-actions skill
- Do your actions match your ambitions?
- What should you stop doing?
- What should you start doing?
- What should you increase doing?

### Step 4: Reflect on inaction
- Apply the reflecting-on-inaction skill
- What haven't you done that you want to do?
- Why haven't you done these things?
- What barriers exist?

### Step 5: Capture artifacts
- Document personal insights and learnings
- Create action items for things to change
- Record specific questions or instances
- Store in artifacts directory

## Artifacts Created

When practicing this habit, create artifacts in the `artifacts/` directory:

- **Reflecting on Learnings**: Personal reflections on what you're learning
  - Example: `artifacts/Reflecting on Learnings.txt`
- **Reflecting on Actions**: Action items for what to stop, start, or increase doing
  - Example: `artifacts/Reflecting on Actions.md`
- **Reflecting on Inaction**: Questions about why you haven't done things
  - Example: `artifacts/Reflecting on Inaction.md`

**Artifact Structure:**
- Action items: `- [ ] [Specific todo items]`
- Personal learnings: `- [What you discovered about yourself]`
- Specific instances: `- [Concrete examples or questions]`
- Results: `- [Outcomes from applying the habit]`

## Frequency and Timing

- **Frequency**: Daily
- **Timing**: Evening, before bed
- **Duration**: 15-30 minutes
- **Context**: Most valuable when done consistently as part of daily routine

## Best Practices

- Practice at the same time each day to build consistency
- Be honest and avoid self-judgment during reflection
- Focus on actionable insights, not just observations
- Review previous artifacts periodically to track patterns
- Combine with journaling for deeper insights

## Related Habits

- **Weekly Review**: Builds on daily reflections for longer-term patterns
- **Capturing Reflections**: Captures reflections as they occur throughout the day

## Additional Resources

- For detailed skill information, see the skill files referenced above
- For artifact examples, see [artifacts/](artifacts/)
```

## Artifacts Directory Structure

Artifacts are personal outcomes created from engaging in habits. They should be organized in the `artifacts/` directory:

```
roles/<role-category>/<Role Name>/artifacts/
├── Artifact Name 1.txt
├── Artifact Name 2.md
└── ...
```

**Artifact Organization:**

Artifacts can be organized with habits as header sections. This makes it easy to see what artifacts were created from each habit:

**Pattern 1: Artifacts Organized by Habit (Recommended)**
```markdown
# [Artifact Type] Artifacts

## [Habit Name 1]
[Artifacts created from this habit]

## [Habit Name 2]
[Artifacts created from this habit]
```

**Example: `artifacts/Reflecting on Actions.md`**
```markdown
# Reflecting on Actions

## Daily Reflection
- [ ] Why am I not practicing FP every day?
- [ ] Why have I not made my site yet?

## Weekly Review
- [ ] [Additional action items from weekly review]
```

**Pattern 2: Separate Files per Habit**
Create separate artifact files for each habit when artifacts are substantial:
```
artifacts/
├── daily-reflection-actions.md
├── weekly-review-actions.md
└── ...
```

**Artifact Guidelines:**

1. **Personal content only**: Artifacts contain action items, specific instances, personal learnings, and outcomes
2. **Created from habits**: Artifacts are the result of practicing habits
3. **Not recipes**: Artifacts are not skills or habits - they're personal results
4. **Organized by habit**: Group artifacts by the habit that created them (recommended)
5. **Preserve formatting**: Maintain exact formatting, hashtags, and structure from original files

**Example Artifact Structure (with habits as headers):**

```markdown
# Reflecting on Learnings

## Daily Reflection
# >2019-11-23
- I learned I'm not motivated to learn parquet anymore
- Still thinking about my site... and FP...

## Weekly Review
- [ ] I need to refresh learnings from completed experiments
- [ ] Reflect on whether I should continue learning X
```

**For detailed guidance on organizing artifacts with examples**, see: [organizing-artifacts.md](organizing-artifacts.md)

## Best Practices

### 1. Combine Skills Thoughtfully

- **Identify natural combinations**: Skills that work well together
- **Sequence logically**: Order skills in a way that builds on previous insights
- **Avoid redundancy**: Don't combine skills that overlap too much
- **Create value**: The combination should produce more than individual skills

### 2. Define Clear Frequency and Timing

- **Be specific**: "Daily" is better than "regularly"
- **Consider context**: When is the habit most valuable?
- **Account for duration**: How long does the habit take?
- **Allow flexibility**: Some habits are "as-needed" rather than scheduled

### 3. Guide Artifact Creation

- **Specify what to capture**: What artifacts should be created?
- **Provide structure**: Give templates or examples for artifacts
- **Link to artifacts directory**: Show where artifacts are stored
- **Explain artifact types**: Action items, learnings, instances, results

### 4. Maintain Habit Independence

Each habit should:
- Work standalone (though it may reference skills)
- Have clear boundaries
- Include all necessary context
- Be discoverable through description

### 5. Use Progressive Disclosure

- **HABIT.md**: Essential instructions (keep under 500 lines)
- **reference.md**: Detailed guidance and examples
- **examples.md**: Concrete usage examples

### 6. Always Include Frontmatter

**Required structure:**
1. **Frontmatter** (first thing in file):
   ```markdown
   ---
   name: habit-name
   description: What habit does and when to practice it
   frequency: daily|weekly|monthly|as-needed
   timing: [When to practice]
   ---
   ```

2. **Rest of habit content** (purpose, skills used, how to practice, artifacts, etc.)

## Decision Framework

When evaluating if an activity should become a habit:

| Question | Yes → Habit | No → Keep in Role |
|----------|-------------|------------------|
| Is this a regular practice? | ✅ | ❌ |
| Does it combine multiple skills? | ✅ | ❌ |
| Does it create personal artifacts? | ✅ | ❌ |
| Is it too role-specific? | ❌ | ✅ |
| Is it just a single skill application? | ❌ | ✅ (it's a skill, not a habit) |

## Workflow Summary

1. **Review role directory**
   - Read `Overview.md`, `Activities.md`, `Responsibilities.md`
   - Review individual activity files
   - Review existing skills

2. **Identify habit candidates**
   - List regular practices that combine skills
   - Note their frequency and timing
   - Identify artifact outputs

3. **Evaluate each candidate**
   - Apply decision framework
   - Determine if standalone habit or supporting file

4. **Extract and structure**
   - Identify skills involved
   - Define frequency and timing
   - Specify skill combination approach
   - Define artifact outputs

5. **Structure habits**
   - Create directory: `roles/<role-category>/<Role Name>/habits/habit-name/`
   - Write `HABIT.md` with frontmatter
   - Add supporting files as needed

6. **Create artifacts directory**
   - Create `artifacts/` directory in role
   - Move existing personal artifacts to artifacts directory
   - Organize artifacts by type

7. **Verify quality**
   - Frontmatter section present with name, description, frequency, timing
   - Name is slash-command compatible (e.g., `/habit-name`)
   - Description includes trigger terms and is in third person
   - Skills are properly referenced
   - Artifacts are clearly defined
   - Under 500 lines for HABIT.md
   - Clear workflow and examples

## Example Role Analysis

**Role**: The Self Reflector

**Habits to abstract:**
- ✅ Daily Reflection → `daily-reflection` habit (combines multiple reflection skills)
- ✅ Weekly Review → `weekly-review` habit (combines reflection skills weekly)
- ✅ Capturing Reflections → `capturing-reflections` habit (regularly captures reflection artifacts)
- ❌ Reflecting on Learnings → Skill, not a habit (it's the recipe)
- ❌ "I need to reflect on X" → Artifact, not a habit (it's a result)

**Result**: 2-3 reusable habits that combine skills to create personal artifacts.

## Next Steps

After creating habits:

1. **Test discovery**: Verify habits can be found and applied
2. **Refine description**: Add trigger terms based on usage
3. **Update role files**: Reference habits where appropriate
4. **Organize artifacts**: Move existing artifacts to artifacts directory (see [organizing-artifacts.md](organizing-artifacts.md) for guidance)
5. **Iterate**: Improve based on actual usage patterns

## Related Resources

- For detailed artifact organization guidance with examples, see: [organizing-artifacts.md](organizing-artifacts.md)
- For skill abstraction guidance, see: [generalizing-skills.md](generalizing-skills.md)
- For role structuring guidance, see: [../SKILL.md](../SKILL.md)

---

*This guide is based on the structure found in `roles-self-development/The Self Reflector/` and follows the pattern established for skills in [generalizing-skills.md](generalizing-skills.md).*
