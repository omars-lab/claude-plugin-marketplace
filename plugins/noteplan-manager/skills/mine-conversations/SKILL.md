---
name: mine-conversations
description: Mine Claude conversation transcripts — cross-map sessions to plans, extract and dedup ideas from transcripts + NotePlan files, surface discovered_ideas.json for the dashboard. Incremental by default.
---

# Mine Conversations

Mine Claude conversation transcripts for this NotePlan project directory, cross-map sessions to plans, and surface ideas. Produces `dashboard/sessions.json`, `dashboard/plan-sessions.json`, `dashboard/ideas.json`, and `dashboard/discovered_ideas.json`.

---

## When to Invoke

Run this skill when the user asks to:
- "Mine my conversations"
- "Update idea dashboard"
- "What did I work on in my Claude sessions?"
- "Cross-map transcripts to plans"
- "Find ideas from my conversations"

This skill is also run automatically as a pre-step by `dashboard-generate` (pass `--skip-mine` to bypass).

---

## Environment

```bash
NOTEPLAN_ROOT="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
```

---

## Workflow

### Step 1 — Determine scope

Ask the user (or infer from context):
- **Full reindex?** Default: incremental (only new sessions since last run via cursor)
- **Since date?** Default: none (use cursor)
- **Specific project directories?** Default: this NotePlan repo's Claude project dir

### Step 2 — Run conversation-mine

```bash
noteplan-sweep conversation-mine
```

Flags:
- `--full` — ignore cursor, reprocess all sessions
- `--since YYYY-MM-DD` — only sessions on/after this date
- `--no-writeback` — skip any write-back to plan files (safe/read-only mode)

If the user wants to reprocess everything from scratch:
```bash
noteplan-sweep conversation-mine --full
```

### Step 3 — Report results

After the command completes, read `dashboard/mine-cursor.json` and report:
```bash
cat "$NOTEPLAN_ROOT/dashboard/mine-cursor.json"
```

Report:
- Total sessions processed
- Number of plans cross-mapped
- Number of new ideas discovered (transcript + notefile sources)
- Date range covered

### Step 4 — Surface insights (optional)

If the user wants to explore the results, read the output files:

```bash
# Top plans with most session activity
cat "$NOTEPLAN_ROOT/dashboard/plan-sessions.json" | python3 -c "
import json,sys
d=json.load(sys.stdin)
ranked = sorted(d.items(), key=lambda x: -len(x[1]))
for stem, sessions in ranked[:10]:
    print(f'{len(sessions):3d} sessions  {stem}')
"

# Recent ideas from transcripts
cat "$NOTEPLAN_ROOT/dashboard/discovered_ideas.json" | python3 -c "
import json,sys
ideas=json.load(sys.stdin)
transcript_ideas = [i for i in ideas if i.get('source_type') == 'transcript']
for i in sorted(transcript_ideas, key=lambda x: x.get('date',''), reverse=True)[:20]:
    print(f\"[{i['date']}] {i['text'][:80]}\")
"
```

---

## Output Files

| File | Contents |
|---|---|
| `dashboard/sessions.json` | All parsed sessions with signals (files_written, wikilinks, idea_lines) |
| `dashboard/plan-sessions.json` | `{plan_stem: [{session_id, date, files_written, wikilinks}]}` — rich cross-map |
| `dashboard/ideas.json` | Ideas surfaced from transcript idea_lines only |
| `dashboard/discovered_ideas.json` | Merged ideas from transcripts + NotePlan files, deduped by fingerprint, each with matched_plan |
| `dashboard/mine-cursor.json` | Incremental cursor — stores processed session IDs |

---

## Downstream: Graph Pipeline

After `conversation-mine`, optionally rebuild the conversation knowledge graph (weekly or after a significant batch of new sessions):

```bash
noteplan-sweep graph-extract    # build graph.json (Session/Plan/Repo/Skill/UseCase/App nodes)
noteplan-sweep graph-build      # validate + write embedding_meta
noteplan-sweep ai-usage-generate  # inject updated graph.json into D3 pane
```

Then for semantic search (requires LM Studio running at localhost:1234):
```bash
noteplan-sweep graph-embed           # embed all unembedded nodes
noteplan-sweep graph-query-vec "infrastructure planning sessions"
```

Text/Cypher search (no embedding required):
```bash
noteplan-sweep graph-query "config agent"
noteplan-sweep graph-query --cypher "MATCH (n:Plan) WHERE n.status contains 'active' RETURN n.label LIMIT 10"
noteplan-sweep graph-stats
```

---

## Troubleshooting

**"Could not locate Claude transcript directory"**
- Claude hasn't been used in this project directory before, or the key doesn't match
- Run `noteplan-sweep conversation-mine --projects auto` to let it search

**"0 new sessions" but transcripts exist**
- Run with `--full` to ignore the cursor and reprocess all sessions

**Ideas seem stale**
- Run `noteplan-sweep conversation-mine --full` to rebuild from scratch
- Then `noteplan-sweep dashboard-generate` to refresh the HTML dashboard

---

## Success Criteria

- [ ] `dashboard/sessions.json` updated with new sessions
- [ ] `dashboard/plan-sessions.json` shows plans with matched sessions
- [ ] `dashboard/discovered_ideas.json` merged and deduped
- [ ] Cursor updated so next run is incremental
