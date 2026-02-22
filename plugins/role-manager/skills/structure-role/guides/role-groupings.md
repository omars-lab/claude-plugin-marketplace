# Role Groupings

This guide documents how roles are organized in the personalbook system. Roles are grouped by their **primary focus** and **shared knowledge base**.

## Organizing Principle: Development Focus

Roles are grouped by what they **develop** or **build**:

| Group | What It Develops | Shared Knowledge | Example Roles |
|-------|------------------|------------------|---------------|
| **Self-Development** | The person (you) | Psychology, habits, reflection, discipline | Self Reflector, Learner, Self Master |
| **Software-Development** | Software systems | Tech stacks, patterns, tools, architecttic | Developer, Architect, Data Engineer |
| **Business-Development** | Businesses/organizations | Markets, strategy, leadership, finance | CTO, Entrepreneur, Manager |
| **Life Roles** | Life experiences | Varies by role | Adventurer, Foodie, Entertainer |

## Role Categories

### roles-self-development/

Roles focused on **personal growth and self-improvement**.

**Characteristics:**
- Skills are introspective questions
- Habits are reflection practices
- Artifacts are personal insights and answers
- Cross-cutting: these skills apply across all other roles

**Roles:**
- The Self Reflector - Self-understanding, identity, meaning
- The Learner - Knowledge acquisition
- The Self Master - Discipline, habits, self-control
- The Philosopher - Deep understanding
- The Servant - Spiritual growth

### roles-software-development/

Roles focused on **building software systems**.

**Characteristics:**
- Skills are technical SOPs, patterns, techniques
- Knowledge is tech stacks, tools, frameworks
- Shared foundation: programming, systems thinking, debugging
- Roles often specialize in different layers or domains

**Roles:**
| Role | Focus Area |
|------|------------|
| The Architect | System design, structure |
| The Backend Developer | Server-side systems |
| The Frontend Developer | User interfaces |
| The Data Engineer | Data pipelines, storage |
| The Data Scientist | Analysis, ML models |
| The AI Engineer | AI/ML systems |
| The BI Engineer | Business intelligence |
| The AWS Engineer | Cloud infrastructure |
| The Performance Engineer | System optimization |
| The Automator | Automation, scripting |
| The Author of Scripts | Writing utility scripts |
| The Process Developer | Development workflows |
| The Master of Software | Meta-skills for software mastery |

### roles-business-development/

Roles focused on **building and running businesses**.

**Characteristics:**
- Skills include strategy, communication, leadership
- Knowledge is markets, finance, organizational dynamics
- Expectations are often external (investors, board, team)
- Many roles involve influencing others

**Roles:**
| Role | Focus Area |
|------|------------|
| **Leadership** | |
| The CTO | Technical strategy + business outcomes |
| The Manager | Team execution, operations |
| The Leader | Vision, influence, direction |
| The Decision Maker | Choices, trade-offs |
| The Treasurer | Finance, assets, money |
| **Business Functions** | |
| The Entrepreneur | Starting ventures |
| The Product Manager | Product strategy |
| The Businessman | General business operations |
| The Marketer | Marketing, positioning |
| The Salesman | Sales, closing deals |
| The Brand Ambassador | Brand representation |
| The Investor | Investment decisions |
| The Forecastor | Predictions, planning |
| **General** | |
| The Employee | Navigating employment |
| The Strategist | Strategic thinking |
| The Visionary | Long-term vision |

### roles/ (Life Roles)

General life roles that don't fit the "development" categories.

**Characteristics:**
- Often about experiences or activities
- May be personality aspects or hobbies
- Less structured than development roles

**Roles:**
- The Adventurer, Analyzer, Celebrator, Doer, Entertainer
- The Foodie, Lover, Maintainer, Motivator
- The Problem Solver, Questioner, Researcher
- The Role Player, Seller, Shopper, Traveler

### Specialized Categories

| Category | Focus | Example Roles |
|----------|-------|---------------|
| **roles-family/** | Family relationships | The Father, The Spouse, The Son |
| **roles-creative/** | Creative pursuits | The Writer, The Artist |
| **roles-spiritual/** | Spiritual practices | The Servant |
| **roles-societal/** | Societal contribution | The Citizen, The Volunteer |

## Cross-Category Roles

Some roles genuinely belong in multiple categories. Handle these with:

1. **Primary location** - Where the role's *outcome* is most focused
2. **Cross-reference** - Note in Overview.md of secondary category

**Example: The CTO**
- Primary: `roles-business-development/The CTO/` (outcome is business success)
- Cross-reference in `roles-software-development/Overview.md`:
  ```markdown
  ## Cross-Category Roles
  | Role | Primary Category | Why Cross-Listed |
  |------|-----------------|------------------|
  | [The CTO](../roles-business-development/The%20CTO/) | Business Development | Deep technical knowledge required |
  ```

## Deciding Where a Role Belongs

Ask these questions:

1. **What does this role primarily build/develop?**
   - Yourself → self-development
   - Software → software-development
   - Business/organization → business-development
   - Experiences → life roles

2. **What knowledge overlaps with other roles in that category?**
   - If a role shares 70%+ knowledge base with a category, it belongs there

3. **What is the primary outcome?**
   - Personal growth → self-development
   - Working software → software-development
   - Business success → business-development

4. **Who are the "stakeholders" or beneficiaries?**
   - Yourself → self-development
   - Users/systems → software-development
   - Organization/investors/customers → business-development

## Migration Notes

When reorganizing roles:

1. **Don't lose content** - Follow the Content Preservation Protocol in SKILL.md
2. **Update cross-references** - Search for `[[Role Name]]` links
3. **Document in Role Evolution** - Note previous locations in Overview.md
4. **Update this guide** - Keep role lists current
