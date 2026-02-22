# Guide: Organizing Personal Artifacts

This guide explains how to identify, move, and organize personal artifacts from role directories into the `artifacts/` directory, with examples of structuring artifacts by habits.

## TL;DR - Recommended Pattern

**Every artifact needs frontmatter** and should be **organized with habits as header sections**:

```markdown
---
intent: Captures personal reflections on whether my actions match my ambitions
habits:
  - daily-reflection
  - weekly-review
---

# Reflecting on Actions

## Daily Reflection
- Why am I not practicing FP every day? → I keep getting distracted by other projects
- Why have I not made my site yet? → I'm overthinking the design

## Weekly Review
- [Additional reflections with personal answers]
```

## Artifact Frontmatter

Every artifact MUST have frontmatter with:
- **intent**: What this artifact captures (the core purpose)
- **habits**: List of habits that create/update this artifact

## Questions: Skills vs Artifacts

| Question Type | Where It Belongs | Example |
|---------------|------------------|---------|
| **Questions to ask yourself** (no answer) | Skills or Habits | "Did I get better today?" |
| **Questions you attempted to answer** (with your answer) | Artifacts | "Why haven't I started my company? → I'm afraid of failure" |

**Rule**: Generic questions without answers → skills/habits. Personal questions with your answers/reflections → artifacts.

This pattern:
- Makes it clear which habit created each artifact
- Helps track progress across habits
- Keeps related artifacts grouped together
- Distinguishes recipe questions (skills) from personal answers (artifacts)

## Overview

Artifacts are personal outcomes created from engaging in habits. They contain action items, specific instances, personal learnings, and results - the concrete evidence of applying skills and habits.

### Artifacts vs. Skills vs. Habits

1. **Skills**: Reusable recipes/formulas, processes, workflows, and methods (e.g., "How to reflect on learnings" - the questions, workflow, process)
2. **Habits**: Regular practices that mix and match skills, with guidance on frequency, timing, and how to combine skills
3. **Artifacts**: Personal outcomes, action items, specific instances, and results created from engaging in habits (e.g., "I need to reflect on why I haven't started my company" or "I learned I'm not motivated to learn parquet anymore")

**Key distinctions:**
- **Skills** = The recipe/formula (how to do something)
- **Habits** = How you regularly apply skills (when, how often, which skills to combine)
- **Artifacts** = Personal results from applying habits (action items, learnings, outcomes)

## Identifying Artifacts

### What Should Be Moved to Artifacts

Artifacts contain personal, concrete content:

- ✅ **Action items**: Specific todo items with checkboxes `- [ ]` or `- [x]`
- ✅ **Personal learnings**: What you discovered about yourself (e.g., "I learned I'm not motivated to learn parquet anymore")
- ✅ **Specific instances**: Concrete examples or questions (e.g., "Why am I not practicing FP every day?")
- ✅ **Results**: Outcomes from applying habits (e.g., "I realized I should stop doing X")
- ✅ **Personal notes**: Observations, thoughts, and reflections about yourself
- ✅ **Personal preferences**: Decisions, choices, and preferences
- ✅ **Family and personal content**: Anything mentioning family members, children, or personal relationships
- ✅ **Completed items**: Items with @done markers or completion dates
- ✅ **Personal quotes**: Quotes that resonate with you personally
- ✅ **Date-stamped entries**: Personal entries with dates (e.g., `# >2019-11-23`)

### What Should NOT Be Moved to Artifacts

Keep these in the role directory or move to Activities.md:

- ❌ **Generic planning questions**: Questions that apply to anyone in the role (move to Activities.md)
- ❌ **Process descriptions**: How-to guides or workflows (these are skills)
- ❌ **Generic frameworks**: Reusable patterns or methodologies (these are skills)
- ❌ **Role definitions**: Generic definitions of the role (keep in role directory)

## Artifact Organization Patterns

### Pattern 1: Artifacts Organized by Habit (Recommended)

Organize artifacts with habits as header sections. This makes it easy to see what artifacts were created from each habit.

**Structure:**
```markdown
# [Artifact Type] Artifacts

## [Habit Name 1]
[Artifacts created from this habit]

## [Habit Name 2]
[Artifacts created from this habit]

## [Habit Name 3]
[Artifacts created from this habit]
```

**Example: `artifacts/Reflecting on Actions.md`**
```markdown
# Reflecting on Actions

## Daily Reflection
> Do your actions match your ambitions?! >2019-04-06 #Quote
- [x] I need to capture these reflections! #SelfReflection

### Stop Doing ...
The following thoughts indicate that I should probably stop doing something ...
- Why do I have to ...

### Start Doing ...
- [ ] Why am I not practicing FP every day?
- [ ] Why have I not made my site yet?
- [ ] Why have I not made my first app yet?
- [ ] Why don't I make a mobile app out of the geometric patterns?!
- [ ] Why cant I brew install my mac libraries?!

### Increase Doing
- [ ] I need to do more reading! #SelfReflection

## Weekly Review
[Additional artifacts from weekly review habit]

## Capturing Reflections
[Artifacts captured throughout the day]
```

**Example: `artifacts/Reflecting on Learnings.txt`**
```markdown
# Reflecting on Learnings

## Daily Reflection
# >2019-11-23
- Not too motivated to learn parquet anymore …
- Not too motivated to dig into performance engineering …
- Still thinking about my site … and FP …
- Thinking about big data as well …
- I am a fan of abstract math!

## Weekly Review
[Additional learnings from weekly review]
```

### Pattern 2: Separate Files per Habit

Create separate artifact files for each habit. Use this when artifacts are substantial or when habits produce very different types of artifacts.

**Structure:**
```
artifacts/
├── daily-reflection-actions.md
├── daily-reflection-learnings.txt
├── weekly-review-actions.md
└── capturing-reflections.md
```

**Example: `artifacts/daily-reflection-actions.md`**
```markdown
# Daily Reflection - Actions

## Stop Doing
- [ ] [Specific action item to stop]

## Start Doing
- [ ] [Specific action item to start]

## Increase Doing
- [ ] [Specific action item to increase]
```

### Pattern 3: Chronological Organization

Organize artifacts chronologically when temporal context is important.

**Structure:**
```markdown
# [Artifact Type] Artifacts

## 2024-01
[Artifacts from January 2024]

## 2024-02
[Artifacts from February 2024]
```

## Artifact File Structure

### Basic Structure

```markdown
# [Artifact Type Name]

## [Habit Name or Category]
[Artifacts organized by habit or category]

### [Sub-category if needed]
- [ ] [Action item with exact formatting preserved]
- [Personal learning or observation]
- [Specific instance or question]
```

### Preserving Formatting

**CRITICAL**: When moving content to artifacts, preserve exact formatting:

- ✅ All hashtags (e.g., `#SelfReflection`, `#Daily`)
- ✅ All references and links
- ✅ Exact indentation levels for sub-tasks
- ✅ All formatting and special characters
- ✅ Checkbox states (`[ ]` vs `[x]`)
- ✅ Completion markers (`@done`, dates like `>2019-04-06`)
- ✅ Quotes and blockquotes
- ✅ Date stamps (e.g., `# >2019-11-23`)

## Examples: Moving Content to Artifacts

### Example 1: Moving Action Items

**Original file: `Reflecting on Actions.md`**
```markdown
# Retrospecting Actions
> Do you actions match your ambitions?! >2019-04-06 #Quote
- [x] I need to capture these reflections! #SelfReflection

## Stop Doing ...
The following thoughts indicate that I should probably stop doing something ...
	- Why do I have to ...

## Start Doing ...
- *The following are all powerful in deterring what to do:*
	- Why haven't I ...
	- Why cant I ...
	- Why don't I ...
	- Why amn't I ...

- [ ] Why am I not practicing FP every day?
- [ ] Why have I not made my site yet?
- [ ] Why have I not made my first app yet?
- [ ] Why don't I make a mobile app out of the geometric patterns?!
- [ ] Why cant I brew install my mac libraries?!

# Increase Doing
- [ ] I need to do more reading! #SelfReflection
```

**After moving to artifacts: `artifacts/Reflecting on Actions.md`**
```markdown
# Reflecting on Actions

## Daily Reflection
> Do your actions match your ambitions?! >2019-04-06 #Quote
- [x] I need to capture these reflections! #SelfReflection

### Stop Doing ...
The following thoughts indicate that I should probably stop doing something ...
	- Why do I have to ...

### Start Doing ...
- *The following are all powerful in deterring what to do:*
	- Why haven't I ...
	- Why cant I ...
	- Why don't I ...
	- Why amn't I ...

- [ ] Why am I not practicing FP every day?
- [ ] Why have I not made my site yet?
- [ ] Why have I not made my first app yet?
- [ ] Why don't I make a mobile app out of the geometric patterns?!
- [ ] Why cant I brew install my mac libraries?!

### Increase Doing
- [ ] I need to do more reading! #SelfReflection
```

**Key changes:**
- Added "Daily Reflection" header section (the habit that created these artifacts)
- Preserved all formatting, hashtags, indentation, and special characters
- Kept the quote, date stamp, and checkbox states exactly as they were

### Example 2: Moving Personal Learnings

**Original file: `Reflecting on Learnings.txt`**
```markdown
# Reflecting on Learnings

- What reflections have I had on the things I am learning?
- What did I want to learn at different points in time?
- Am I learning the right things?
	- Do the things I am learning align to [[What is my purpose?]]
	- How do I ensure I am learning things that fulfill [[What do I want to become?]]

# >2019-11-23
* Not too motivated to learn parquet anymore …
* Not too motivated to dig into performance engineering …
* Still thinking about my site … and FP …
* Thinking about big data as well …
* I am a fan of abstract math!
```

**After moving to artifacts: `artifacts/Reflecting on Learnings.txt`**
```markdown
# Reflecting on Learnings

## Daily Reflection
# >2019-11-23
* Not too motivated to learn parquet anymore …
* Not too motivated to dig into performance engineering …
* Still thinking about my site … and FP …
* Thinking about big data as well …
* I am a fan of abstract math!

## Weekly Review
[Additional learnings from weekly review habit]
```

**Key changes:**
- Moved personal learnings (the dated entries) to artifacts
- Added "Daily Reflection" header section
- Removed generic planning questions (these should go to Activities.md)
- Preserved date stamp and formatting exactly

### Example 3: Moving Daily Reflection Artifacts

**Original file: `Reflecting Daily.md`**
```markdown
# Reflecting Daily
#Daily #Activity

* [ ] What do I need to ask myself everyday?

* [ ] Did I get a little bit better today? 1% better?
* [ ] Did I learn today?
* [ ] Did I hurt anyone today?
* [ ] Did I worship sincerely today?
* [ ] Did show my loved ones affection today?
* [ ] Did I repent today?
* [ ] Did I pray for my teachers/ loved ones today?
* [ ] Did I get closer to God today?
```

**After moving to artifacts: `artifacts/Daily Reflection.md`**
```markdown
# Daily Reflection

## Daily Reflection Habit
#Daily #Activity

* [ ] What do I need to ask myself everyday?

* [ ] Did I get a little bit better today? 1% better?
* [ ] Did I learn today?
* [ ] Did I hurt anyone today?
* [ ] Did I worship sincerely today?
* [ ] Did show my loved ones affection today?
* [ ] Did I repent today?
* [ ] Did I pray for my teachers/ loved ones today?
* [ ] Did I get closer to God today?
```

**Key changes:**
- Added "Daily Reflection Habit" header section
- Preserved all checkboxes, hashtags, and formatting
- This is a personal checklist artifact, not a generic planning question

## Artifact Types

### 1. Action Items Artifacts

Contain specific todo items and tasks:

```markdown
# [Artifact Type] - Action Items

## [Habit Name]
- [ ] [Specific action item]
- [x] [Completed action item]
- [ ] [Another action item with hashtags] #tag1 #tag2
```

### 2. Personal Learnings Artifacts

Contain insights and discoveries about yourself:

```markdown
# [Artifact Type] - Learnings

## [Habit Name]
# >2024-01-15
- I learned that I'm not motivated to learn X anymore
- I discovered that I really enjoy Y
- I realized I should focus more on Z
```

### 3. Specific Instances Artifacts

Contain concrete examples or questions:

```markdown
# [Artifact Type] - Instances

## [Habit Name]
- Why am I not practicing FP every day?
- Why have I not made my site yet?
- What should I focus my education on?
```

### 4. Results Artifacts

Contain outcomes from applying habits:

```markdown
# [Artifact Type] - Results

## [Habit Name]
- I realized I should stop doing X
- I decided to start doing Y
- I'm going to increase doing Z
```

## Workflow: Moving Content to Artifacts

### Step 1: Identify Artifact Candidates

Review role directory files to identify:
- Personal action items with checkboxes
- Personal learnings and insights
- Specific instances or questions
- Results and outcomes
- Date-stamped personal entries

### Step 2: Determine Organization Pattern

Choose the organization pattern:
- **By habit** (recommended): Organize artifacts with habits as header sections
- **Separate files**: Create separate files per habit if artifacts are substantial
- **Chronological**: Organize by date when temporal context matters

### Step 3: Create Artifacts Directory

Create the `artifacts/` directory in the role:
```
roles/<role-category>/<Role Name>/artifacts/
```

### Step 4: Move and Organize Content

For each artifact candidate:
1. **Preserve exact formatting**: Copy content exactly as written
2. **Add habit header**: Add the habit name as a header section
3. **Organize by type**: Group similar artifacts together
4. **Maintain structure**: Keep original structure and organization

### Step 5: Update Original Files

After moving artifacts:
- Remove personal content from original files
- Keep generic planning questions in Activities.md
- Keep process descriptions in skills
- Reference artifacts directory where appropriate

## Best Practices

### 1. Preserve Formatting Exactly

- Never alter original formatting, hashtags, or indentation
- Maintain checkbox states and completion markers
- Keep date stamps and special characters

### 2. Use Habits as Headers

- Organize artifacts by the habit that created them
- Makes it easy to see what artifacts came from which habit
- Helps track progress and patterns

### 3. Group Similar Artifacts

- Group action items together
- Group learnings together
- Group instances together
- Makes artifacts easier to navigate

### 4. Maintain Chronological Context

- Preserve date stamps when present
- Add dates when creating new artifacts
- Helps track evolution over time

### 5. Link from Habits

- Habits should reference where artifacts are stored
- Makes it easy to find artifacts created by a habit
- Example: "Artifacts are stored in `artifacts/Reflecting on Actions.md`"

## Example: Complete Artifact Organization

**Role structure:**
```
roles-self-development/The Self Reflector/
├── artifacts/
│   ├── Reflecting on Actions.md
│   ├── Reflecting on Learnings.txt
│   ├── Reflecting on Inaction.md
│   ├── Reflecting on Value.md
│   ├── Daily Reflection.md
│   └── Identifying Interests.txt
├── habits/
│   ├── daily-reflection/
│   │   └── HABIT.md
│   └── weekly-review/
│       └── HABIT.md
└── skills/
    └── ...
```

**Example artifact file: `artifacts/Reflecting on Actions.md`**
```markdown
# Reflecting on Actions

## Daily Reflection
> Do your actions match your ambitions?! >2019-04-06 #Quote
- [x] I need to capture these reflections! #SelfReflection

### Stop Doing ...
The following thoughts indicate that I should probably stop doing something ...
	- Why do I have to ...

### Start Doing ...
- *The following are all powerful in deterring what to do:*
	- Why haven't I ...
	- Why cant I ...
	- Why don't I ...
	- Why amn't I ...

- [ ] Why am I not practicing FP every day?
- [ ] Why have I not made my site yet?
- [ ] Why have I not made my first app yet?
- [ ] Why don't I make a mobile app out of the geometric patterns?!
- [ ] Why cant I brew install my mac libraries?!

### Increase Doing
- [ ] I need to do more reading! #SelfReflection

## Weekly Review
[Additional artifacts from weekly review habit]

## Capturing Reflections
[Artifacts captured throughout the day]
```

## Related Resources

- For habit abstraction guidance, see: [generalizing-habits.md](generalizing-habits.md)
- For skill abstraction guidance, see: [generalizing-skills.md](generalizing-skills.md)
- For role structuring guidance, see: [../SKILL.md](../SKILL.md)

---

*This guide is based on the structure found in `roles-self-development/The Self Reflector/` and follows the pattern established for organizing artifacts with habits as header sections.*
