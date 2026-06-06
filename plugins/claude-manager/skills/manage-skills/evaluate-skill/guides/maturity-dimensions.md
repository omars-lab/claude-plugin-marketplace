# Maturity Dimensions (qualitative)

The `evaluate-skill.py` scorer measures **structural** quality (9 mechanical dimensions). This guide covers a second, **qualitative** axis: how *mature* a skill/prompt is — whether it is self-aware, self-healing, metrics-driven, and improving over time. Use it for an optional deeper pass beyond the scorecard, or to decide whether to route a skill to `suggest-plugin-maturity` / `inject-prompt-metrics`.

Ask these questions about a skill. The more it answers "yes," the more mature it is.

## Self-healing
- Can it reference and update itself when given feedback during execution?
- Does it revise its approach mid-execution based on real-time corrections?
- Can it detect when it's going off-track and self-correct?
- Does it learn from execution failures and adjust strategy?

## Feedback loops
- Is there a mechanism to capture user feedback on effectiveness?
- Does it improve over time from previous interactions?
- Is feedback systematically analyzed and fed back into the skill?

## Metrics instrumentation
- Does it self-report usage metrics?
- Does it estimate time saved vs. doing the work manually?
- Does it collect quality self-assessments (confidence, revision counts)?
- Are metrics standardized so similar skills are comparable?
  → If a skill should be instrumented, route to `claude-manager:inject-prompt-metrics`.

## Clarity & intent
- Is the purpose crystal clear, with required inputs and expected outputs/format specified?
- Is "done" unambiguous? Does it give the model an adequate role/persona?

## Quality & documentation
- Positive and negative examples present? Edge cases / error scenarios handled?
- Reusable across contexts? Validation steps to verify output quality?

## Consistency
- Predictable, standardized outputs across runs, input variations, and users?

## Tool use & ambiguity
- Clear tool-selection criteria, fallbacks when tools fail, and validation of tool outputs?

## Maturity levels

Summarize the answers above into a level:

| Level | Description |
|---|---|
| **Experimental** | Basic functionality, minimal testing |
| **Developing** | Core features work, some edge cases handled |
| **Mature** | Well-tested, documented, examples + feedback loops |
| **Production** | Fully documented, self-healing, metrics-driven, continuously improved |

Report the level alongside the structural scorecard when doing a deep evaluation. Structural score answers "is it well-built?"; maturity level answers "does it improve itself over time?"
