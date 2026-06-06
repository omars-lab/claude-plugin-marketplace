# Prompt Metrics Emission Spec

The authoritative standard for the metrics a prompt/skill emits after execution. The `inject-prompt-metrics` skill inserts a block conforming to this spec. Three tiers: **Core** (required fields + emission), **Analysis** (interpretation formulas), **Full** (improvement-over-time + usage patterns).

---

## Core — Required per-execution data

Every instrumented execution captures:

**Execution data**
- `promptName` — name/identifier of the prompt/skill
- `executionId` — unique id, format `exec_YYYYMMDD_HHMMSS_XXX`
- `startTimestamp` / `endTimestamp` — ISO 8601
- `duration` — seconds, start→end
- `user` — current user identifier (detect at runtime; do not hardcode)

**Performance metrics**
- `timeSavedEstimate` — int minutes saved vs. doing it manually (think-through + edits + research + review)
- `actualTimeSpent` — int minutes spent in the interaction
- `netTimeSavings` — `timeSavedEstimate - actualTimeSpent`
- `efficiencyRatio` — float, `timeSavedEstimate / actualTimeSpent`
- `confidenceLevel` — 1–10, AI confidence in output quality
- `revisionCount` — int revisions/corrections
- `toolConfusionIncidents` — int tool selection/usage confusions
- `feedbackIterations` — int feedback loops
- `userRating` — 1–10 or null
- `overallQuality` — 1–10 self-assessed

**Awareness requirements** — the injected block must state the prompt is being monitored, track end-to-end (first interaction → completion), stay time-conscious, and self-assess.

### JSON-LD structure (emit single-line)

```json
{"@context":"https://schema.org/","@type":"SoftwareApplication","name":"Prompt Execution Metrics","applicationCategory":"AI Prompt","dateCreated":"ISO8601","executionData":{"promptName":"string","executionId":"string","startTimestamp":"ISO8601","endTimestamp":"ISO8601","duration":0,"user":"string","metrics":{"timeSavedEstimate":0,"actualTimeSpent":0,"netTimeSavings":0,"efficiencyRatio":0,"confidenceLevel":0,"revisionCount":0,"toolConfusionIncidents":0,"feedbackIterations":0,"userRating":null,"overallQuality":0}}}
```

### Sink (configurable — NOT hardcoded)

The injecting skill asks the user where to write. Conventions:
- **Repo-local (default):** `.metrics/prompt-metrics-YYYY-Www.jsonld` in the current repo (e.g. `prompt-metrics-2026-W23.jsonld`).
- **Custom path:** a directory the user supplies (e.g. a NotePlan `📊 Metrics/` folder, or a shared store). Detect the user identifier at runtime rather than embedding a specific username.
- **Stdout only:** emit the record in the response, write nothing.
- **Format:** one JSON line per execution, append mode.

### Rules
- Collection runs after every execution; validate JSON before writing.
- Errors in metrics collection are logged but MUST NOT break prompt execution; use fallbacks (0 for counts, null for ratings).
- Use standardized field names/scales so records are comparable across prompts.

### Injected awareness + collection block (template)

```markdown
## Performance Monitoring & Self-Awareness

**IMPORTANT**: This prompt is monitored for effectiveness. Stay aware of your performance from first interaction to completion, and assess your impact.

### During execution
Track: start/end time, total duration, revisions, tool usage/confusion, feedback loops, quality checkpoints, time spent vs. estimated manual time.

### After execution — emit metrics
Collect the required fields above, compute net savings + efficiency ratio, generate an executionId, and write one single-line JSON-LD record to <CONFIGURED_SINK>. Confirm with a one-line summary. Never let metrics failures break the task.
```

---

## Analysis tier — interpretation formulas

Add when the consumer wants to interpret a single execution.

1. **Net Time Savings** = `timeSavedEstimate - actualTimeSpent` (positive = saving time).
2. **Efficiency Ratio** = `timeSavedEstimate / actualTimeSpent` (>2 highly efficient, 1–2 moderate, <1 inefficient).
3. **Quality vs Speed** = `overallQuality / (actualTimeSpent / 10)`.
4. **Iteration Efficiency** = `netTimeSavings / (1 + revisionCount + feedbackIterations)`.
5. **Tool Efficiency** = `netTimeSavings - (toolConfusionIncidents × 5)` (5 min penalty/incident).
6. **Satisfaction Efficiency** = `(userRating / 10) × efficiencyRatio`.
7. **Confidence Accuracy** = `|confidenceLevel - overallQuality|` (lower = better self-assessment).
8. **Performance Score** = `(efficiencyRatio × 0.4) + (overallQuality/10 × 0.3) + (userRating/10 × 0.2) + (confidenceAccuracy/10 × 0.1)`.

---

## Full tier — improvement & usage tracking

Add for prompts run frequently, to track trends across many executions.

**Improvement over time** (track ≥20 executions; rolling averages):
- Efficiency Trend = recent-5 avg − previous-5 avg
- Quality Consistency = `1 − stdev(overallQuality)`
- Learning Rate = recent vs. initial userRating avg
- Error Reduction = drop in `(toolConfusionIncidents + revisionCount)/executions`
- Speed Improvement = initial vs. recent avg time
- Overall Improvement Score = weighted blend (efficiency .3, consistency .2, learning .2, error-reduction .15, speed .1, satisfaction .05)
- Plateau Indicator = `stdev(recent-10 performance scores)` (<0.1 ≈ plateau)

Thresholds: >20% = significant, 10–20% = moderate, ±10% = stable, <−10% = degradation. Cadence: weekly basic, monthly comprehensive, quarterly long-term.

**Usage patterns** (track ≥30 days):
- Usage Frequency = executions / days (>1/day high, 0.2–1 regular, <0.2 infrequent)
- Usage Recency = `1/(days since last + 1)`; Abandonment Risk = `days since last / avg gap` (>2 at risk)
- Usage Burstiness = max-daily / avg-daily; Usage Concentration = unique task types / executions
- Classification: Power (>5/wk + high satisfaction) · Regular (1–5/wk) · Occasional (<1/wk) · Trial (<5 total) · Abandoned (30+ days idle)
- At-risk: idle 14+ days · Abandoned: idle 30+ days
