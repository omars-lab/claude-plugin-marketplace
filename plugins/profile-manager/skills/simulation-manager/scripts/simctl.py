#!/usr/bin/env python3
"""simctl — mechanical helpers for simulation-manager workflow runs.

Reads a workflow transcript dir (journal.jsonl + agent-*.jsonl) and turns it into
something useful without spending agents:

  simctl.py latest                         print the newest workflow transcript dir
  simctl.py status  <wf_dir|latest>        per-run progress, failures, and why they failed
  simctl.py cost    <wf_dir|latest>        token usage per run and role (setup overhead vs output)
  simctl.py extract <wf_dir|latest> -o runs.json
                                           rebuild every run's transcript (partial runs too)
  simctl.py render  runs.json <sim_folder> [--leader Doug] [--ic IC]
                                           write "Run NN <Slug>.md" files from runs.json,
                                           with strategies taken from <sim_folder>/Gameplan.md

Labels follow the workflow script: "run NN <Slug> · <Leader> N", "· IC N", "· close", "write run NN".
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict

PROJECTS = os.path.expanduser("~/.claude/projects")
MIN_TEXT = 20  # shorter free-text fields are almost always placeholder output ("test")
LABEL = re.compile(r"^run (\d+) (\S+) · (.+?)(?: (\d+))?(?: · retry)?$")


# ---------- loading ----------

def resolve(wf):
    if wf != "latest":
        return wf
    dirs = glob.glob(os.path.join(PROJECTS, "*", "*", "subagents", "workflows", "wf_*"))
    if not dirs:
        sys.exit("no workflow transcript dirs found")
    return max(dirs, key=lambda d: os.path.getmtime(os.path.join(d, "journal.jsonl")) if os.path.exists(os.path.join(d, "journal.jsonl")) else 0)


def journal(wf):
    labels, results, failed = {}, {}, []
    with open(os.path.join(wf, "journal.jsonl")) as f:
        for line in f:
            d = json.loads(line)
            t, aid = d.get("type"), d.get("agentId")
            if t == "started":
                labels[aid] = d.get("label", "")
            elif t == "result":
                results[aid] = d.get("result")
            elif t == "failed":
                failed.append(aid)
    return labels, results, failed


def parse_label(label):
    m = LABEL.match(label or "")
    if not m:
        return None
    run_id, slug, role, turn = m.groups()
    return run_id, slug, role, int(turn) if turn else None


def agent_lines(wf, aid):
    p = os.path.join(wf, f"agent-{aid}.jsonl")
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return [json.loads(l) for l in f if l.strip()]


def last_error(wf, aid):
    for d in reversed(agent_lines(wf, aid)):
        r = d.get("toolUseResult")
        if isinstance(r, str) and r.startswith("Error"):
            return r[:200]
    return "unknown (no tool error in transcript)"


def usage(wf, aid):
    # streamed messages log several lines per message id; the last one carries final usage
    last = {}
    for d in agent_lines(wf, aid):
        msg = d.get("message") or {}
        if msg.get("usage"):
            last[msg.get("id")] = msg["usage"]
    tot = defaultdict(int)
    for u in last.values():
        for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"):
            tot[k] += u.get(k, 0) or 0
    return tot


# ---------- commands ----------

def cmd_latest(a):
    print(resolve("latest"))


def cmd_status(a):
    wf = resolve(a.wf)
    labels, results, failed = journal(wf)
    runs = defaultdict(lambda: {"done": 0, "close": False, "written": False, "failed": []})
    for aid, label in labels.items():
        if label.startswith("write run "):
            rid = label.split()[2]
            runs[rid]["written"] = aid in results
            continue
        p = parse_label(label)
        if not p:
            continue
        r = runs[p[0]]
        r["slug"] = p[1]
        if aid in results:
            r["done"] += 1
            r["close"] |= p[2] == "close"
        if aid in failed:
            r["failed"].append((label, last_error(wf, aid)))
        for k, v in (results.get(aid) or {}).items():
            if k not in ("trigger", "flight_risk") and isinstance(v, str) and len(v.strip()) < MIN_TEXT:
                r.setdefault("suspect", []).append(f"{label} · {k}={v!r}")
    ok = {(p[0], p[2], p[3]) for a_ in results if (p := parse_label(labels.get(a_, "")))}
    for r in runs.values():
        r["failed"] = [(l, e) for l, e in r["failed"] if (parse_label(l)[0], parse_label(l)[2], parse_label(l)[3]) not in ok]
    print(f"{wf}\n")
    print(f"{'run':<4} {'slug':<16} {'turns':>5}  close  file  status")
    for rid in sorted(runs):
        r = runs[rid]
        state = "FAILED" if r["failed"] else ("done" if r["written"] else "running")
        if r.get("suspect"):
            state += " · SUSPECT"
        print(f"{rid:<4} {r.get('slug', '?'):<16} {r['done']:>5}  {'yes' if r['close'] else '-':<5}  {'yes' if r['written'] else '-':<4}  {state}")
        for label, err in r["failed"]:
            print(f"       ✗ {label}: {err}")
        for x in r.get("suspect", []):
            print(f"       ? placeholder: {x}")
    other = [l for a_, l in labels.items() if not parse_label(l) and not l.startswith("write run ")]
    if other:
        print("\nother agents: " + ", ".join(f"{l} ({'done' if a_ in results else 'pending'})" for a_, l in labels.items() if l in other))


def cmd_cost(a):
    wf = resolve(a.wf)
    labels, _, _ = journal(wf)
    by_run, by_role, grand = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int)), defaultdict(int)
    n = 0
    for aid, label in labels.items():
        u = usage(wf, aid)
        if not u:
            continue
        n += 1
        p = parse_label(label)
        run = p[0] if p else ("write" if label.startswith("write run") else label)
        role = ((p[2] if p[2] in ("IC", "close", "IC prep", "IC debrief") else "leader") if p
                else "leader prep" if label.startswith("prep · ") else run)
        for k, v in u.items():
            by_run[run][k] += v
            by_role[role][k] += v
            grand[k] += v

    def row(name, u):
        inp = u["input_tokens"] + u["cache_creation_input_tokens"] + u["cache_read_input_tokens"]
        print(f"{name:<14} {inp:>11,} {u['cache_creation_input_tokens']:>11,} {u['cache_read_input_tokens']:>11,} {u['output_tokens']:>9,}")

    hdr = f"{'':<14} {'input(all)':>11} {'cache_new':>11} {'cache_read':>11} {'output':>9}"
    print(f"{wf}\n{n} agents\n\nby run\n{hdr}")
    for k in sorted(by_run):
        row(k, by_run[k])
    print(f"\nby role\n{hdr}")
    for k in sorted(by_role):
        row(k, by_role[k])
    print(f"\n{hdr}")
    row("TOTAL", grand)
    inp = grand["input_tokens"] + grand["cache_creation_input_tokens"] + grand["cache_read_input_tokens"]
    if n:
        print(f"\nper agent: ~{inp // n:,} input / ~{grand['output_tokens'] // n:,} output "
              f"→ {100 * inp / max(1, inp + grand['output_tokens']):.0f}% of tokens are context overhead")


def cmd_extract(a):
    wf = resolve(a.wf)
    labels, results, failed = journal(wf)
    runs = defaultdict(lambda: {"turns": defaultdict(dict), "close": None, "ic_prep": None, "debrief": None, "failed": []})
    leader_prep = next((results.get(a_) for a_, l in labels.items() if l.startswith("prep · ") and results.get(a_)), None)
    leader = None
    for aid, label in labels.items():
        p = parse_label(label)
        if not p:
            continue
        rid, slug, role, turn = p
        r = runs[rid]
        r["id"], r["slug"] = rid, slug
        if aid in failed:
            r["failed"].append(label)
        res = results.get(aid)
        if res is None:
            continue
        if role == "close":
            r["close"] = res
        elif role == "IC prep":
            r["ic_prep"] = res
        elif role == "IC debrief":
            r["debrief"] = res
        elif role == "IC":
            r["turns"][turn]["ic"] = res
        else:
            leader = role
            r["turns"][turn]["leader"] = res
    ok = {(p[0], p[2], p[3]) for a_ in results if (p := parse_label(labels.get(a_, "")))}
    out = []
    for rid in sorted(runs):
        r = runs[rid]
        r["failed"] = [l for l in r["failed"] if (lambda p: (p[0], p[2], p[3]) not in ok)(parse_label(l))]
        turns = [{"turn": k, **r["turns"][k]} for k in sorted(r["turns"])]
        score = sum((t.get("leader") or {}).get("impression_delta", 0) for t in turns if t["turn"] > 1)
        if r["close"]:
            score += r["close"].get("impression_delta", 0)
        out.append({"id": rid, "slug": r["slug"], "complete": bool(r["close"]) and not r["failed"],
                    "failed": r["failed"], "score": score, "ic_prep": r["ic_prep"], "turns": turns,
                    "close": r["close"], "debrief": r["debrief"]})
    data = {"workflow_dir": wf, "leader": leader, "leader_prep": leader_prep, "runs": out}
    if a.o:
        with open(a.o, "w") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        print(f"wrote {a.o}: {len(out)} runs ({sum(r['complete'] for r in out)} complete)")
    else:
        json.dump(data, sys.stdout, indent=1, ensure_ascii=False)


def strategies(folder):
    p = os.path.join(folder, "Gameplan.md")
    found = {}
    if os.path.exists(p):
        for line in open(p):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[0].isdigit():
                found[cells[0].zfill(2)] = cells[2]
    return found


def sign(n):
    return f"+{n}" if n >= 0 else str(n)


def scorecard(objs):
    icon = {"yes": "✅", "partly": "🟡", "no": "❌"}
    return [f"- {icon.get(o.get('met'), '?')} {o.get('objective')} — {o.get('evidence')}" for o in objs]


def render_run(r, leader, ic, strategy):
    c = r["close"] or {}
    lines = [f"# Run {r['id']} {r['slug']}", "", f"**Strategy:** {strategy}"]
    if c:
        lines += [f"**Outcome:** impression {sign(r['score'])} · sponsor: {'yes' if c.get('would_sponsor') else 'no'} · flight risk: {c.get('flight_risk')}",
                  f"**{leader}'s verdict:** {c.get('verdict')}"]
    else:
        state = f"failed at {', '.join(r['failed'])}" if r["failed"] else "in progress"
        lines += [f"**Outcome:** incomplete — {state} · impression so far {sign(r['score'])}"]
    P = r.get("ic_prep")
    if P:
        lines += ["", f"## {ic} Prep"] + [f"- **{k.replace('_', ' ').capitalize()}:** {'; '.join(v) if isinstance(v, list) else v}" for k, v in P.items()]
        lines.append(f"- {leader}'s prep: [[Prep {leader}]] (shared by all runs)")
    lines += ["", "## Conversation"]
    running = 0
    for t in r["turns"]:
        L, I = t.get("leader"), t.get("ic")
        lines += ["", f"### Turn {t['turn']}"]
        if L:
            lines += ["", f"**{leader}:** \"{L['spoken']}\"", f"> 💭 *{leader} thinks:* {L['private_thoughts']}"]
            if L.get("agenda_left"):
                lines.append(f"> 📋 *Agenda left:* {' · '.join(L['agenda_left'])}")
            if t["turn"] > 1:
                running += L.get("impression_delta", 0)
                lines.append(f"> Impression {sign(L.get('impression_delta', 0))} → {sign(running)} · trigger: {L.get('trigger', '')}")
        if I:
            lines += ["", f"**{ic}:** \"{I['spoken']}\"", f"> 💭 *{ic} thinks:* {I['private_thoughts']}"]
    if c:
        running += c.get("impression_delta", 0)
        lines += ["", "### Close", "", f"**{leader}:** \"{c['spoken']}\"", f"> 💭 *{leader} thinks:* {c['private_thoughts']}",
                  f"> Impression {sign(c.get('impression_delta', 0))} → {sign(running)} · trigger: {c.get('trigger', '')}",
                  "", "## Debriefs", "", f"### {leader}", f"- **Best moment:** {c.get('best_moment')}", f"- **Worst moment:** {c.get('worst_moment')}"]
        lines += scorecard(c.get("objectives_met") or []) + [f"- 🔎 {h}" for h in c.get("hypotheses_result") or []]
    D = r.get("debrief")
    if D:
        lines += ["", f"### {ic}", f"> 💭 {D.get('private_thoughts')}", f"- **Intent:** {D.get('intent')}",
                  f"- **Read of {leader}:** {D.get('read_of_leader')}"] + scorecard(D.get("objectives_met") or []) + [f"- **Would change:** {D.get('would_change')}"]
    return "\n".join(lines) + "\n"


def cmd_render(a):
    data = json.load(open(a.runs))
    leader = a.leader or data.get("leader") or "Leader"
    strat = strategies(a.folder)
    n = 0
    for r in data["runs"]:
        if not r["turns"] or (a.complete_only and not r["complete"]):
            continue
        path = os.path.join(a.folder, f"Run {r['id']} {r['slug']}.md")
        with open(path, "w") as f:
            f.write(render_run(r, leader, a.ic, strat.get(r["id"], "(see Gameplan)")))
        n += 1
        print(f"wrote {path}{'' if r['complete'] else '  (incomplete)'}")
    print(f"{n} run files")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("latest").set_defaults(fn=cmd_latest)
    for name, fn in (("status", cmd_status), ("cost", cmd_cost)):
        p = sp.add_parser(name)
        p.add_argument("wf")
        p.set_defaults(fn=fn)
    p = sp.add_parser("extract")
    p.add_argument("wf")
    p.add_argument("-o")
    p.set_defaults(fn=cmd_extract)
    p = sp.add_parser("render")
    p.add_argument("runs")
    p.add_argument("folder")
    p.add_argument("--leader")
    p.add_argument("--ic", default="IC")
    p.add_argument("--complete-only", action="store_true")
    p.set_defaults(fn=cmd_render)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
