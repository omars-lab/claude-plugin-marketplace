# Profile Manager

Manage your profiles — both your shell environment (browser automation, aliases, setup across machines) and your professional profile (resume mission statement, bullet points, leadership-meeting simulators).

## Getting Started

```bash
# Install
/plugin install profile-manager@oeid-claude-plugins

# Learn what this plugin can do
/profile-manager:introduce
```

## Skills (8)

| Skill | What it does |
|---|---|
| `introduce` | Introduce the profile-manager plugin and available skills |
| `setup-chrome-integration` | Configure Chrome for Testing auto-start, remote debugging, and `claude-chrome` alias in your shell profile |
| `refine-mission-statement` | Iteratively refine a resume/personal-brand mission statement, saving each version with a Good/Bad/Enhancement critique |
| `refactor-resume-bullets` | Refactor resume bullet points into action-led, quantified statements, tracking each bullet's revisions with critiques |
| `vp-simulator` | Role-play a VP/skip-level who booked a meeting with you — motivations, likely questions, what impresses them, and a branching ideal-scenario conversation |
| `ic-simulator` | Role-play an IC meeting a leader — motivations, doubts, questions, what wins them over, and a branching ideal-scenario conversation |
| `simulate-conversation` | **Start here** to simulate an upcoming conversation. It interviews you (who, what about, each side's goals and knowledge, length, depth), builds private pre-briefs, and runs the cheapest engine that fits (operator for 1–3 runs, workflow for more) |
| `simulation-manager` | Run N simulated leader ↔ IC conversations (separate agents, leader's private thoughts + impression deltas per turn), one file per run, then a Recap of what impressed vs hurt and where runs diverged |

## Agents (3)

| Agent | What it does |
|---|---|
| `vp-simulator` | Subagent version of the `vp-simulator` skill — writes the leader-view prep brief to today's NotePlan note |
| `ic-simulator` | Subagent version of the `ic-simulator` skill — writes the IC-view brief to today's NotePlan note |
| `sim-recap` | Analyzes a simulation folder's run files and writes Recap.md — leaderboard, impressed/hurt, divergence points, top 5 questions to prep, composite script |

---

**Part of**: [OEID Claude Plugin Marketplace](../../README.md)
