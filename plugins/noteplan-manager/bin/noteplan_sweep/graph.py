"""
graph.py — Conversation graph pipeline for noteplan-sweep.

Builds a knowledge graph from Claude sessions, NotePlan plans, repos, and skills.
Supports extraction, querying (Cypher subset), and stats.

Commands:
  graph-extract    Build graph.json from dashboard/*.json + SKILL.md files
  graph-query      Search graph by text match or Cypher subset
  graph-stats      Node/edge counts, top plans/repos by activity
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

import noteplan_sweep.utils as utils
from noteplan_sweep.dashboard import parse_frontmatter, scan_plans

# ---------------------------------------------------------------------------
# Node + Edge types
# ---------------------------------------------------------------------------

NODE_TYPES = ("Session", "Plan", "Repo", "Skill", "UseCase", "App")
EDGE_TYPES = ("TOUCHES", "CLASSIFIED_AS", "IN_REPO", "DEFINED_IN", "BUILT", "IMPLEMENTS")

USE_CASES = ("Debug", "Code Gen", "Planning", "Research", "Docs", "Review", "Refactor", "General")

_PLUGIN_ROOT = Path(__file__).parent.parent.parent  # bin/../..  = plugins/noteplan-manager
_SKILLS_DIR = _PLUGIN_ROOT / "skills"


# ---------------------------------------------------------------------------
# Skill scanner (mirrors ai_usage._scan_skills)
# ---------------------------------------------------------------------------

def _scan_skills() -> list[dict]:
    skills = []
    if not _SKILLS_DIR.exists():
        return skills
    for skill_md in sorted(_SKILLS_DIR.rglob("SKILL.md")):
        rel = skill_md.relative_to(_SKILLS_DIR)
        parts = rel.parts
        name = parts[0] if parts else skill_md.stem
        group = parts[1] if len(parts) > 2 else ""
        try:
            content = skill_md.read_text(encoding="utf-8")[:2000]
        except Exception:
            content = ""
        skills.append({
            "id": f"skill:{name}",
            "name": name,
            "group": group,
            "path": str(skill_md),
            "content_preview": content[:300],
        })
    return skills


# ---------------------------------------------------------------------------
# App name extractor (CG-B)
# ---------------------------------------------------------------------------

_APP_TRIGGERS = re.compile(
    r'\b(?:build(?:ing)?|creat(?:e|ing)|implement(?:ing)?|develop(?:ing)?|ship(?:ping)?|launch(?:ing)?)\s+'
    r'((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}|[a-z][a-z0-9\-]+))',
    re.IGNORECASE,
)

def _extract_apps_from_text(text: str) -> list[str]:
    """Extract app/product names from free text using trigger patterns."""
    found = []
    for m in _APP_TRIGGERS.finditer(text):
        name = m.group(1).strip()
        if 3 <= len(name) <= 40 and not name.lower() in {
            "a", "an", "the", "this", "that", "it", "new", "feature",
            "test", "tests", "script", "file", "module", "function",
        }:
            found.append(name)
    return found


def _normalize_app_name(name: str) -> str:
    return re.sub(r'\s+', ' ', name.strip().lower())


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(dashboard_dir: Path, notes_root: Path | None = None) -> dict:
    """Build a graph dict {nodes, edges, stats} from dashboard data files."""
    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()

    def add_node(node_id: str, node_type: str, label: str, attrs: dict):
        if node_id not in node_ids:
            node_ids.add(node_id)
            nodes.append({"id": node_id, "type": node_type, "label": label, "attrs": attrs})

    def add_edge(source: str, target: str, rel: str, attrs: dict | None = None):
        edges.append({"source": source, "target": target, "rel": rel, "attrs": attrs or {}})

    # ── UseCase nodes (fixed set) ─────────────────────────────────────────
    for uc in USE_CASES:
        add_node(f"usecase:{uc}", "UseCase", uc, {})

    # ── Session + Plan nodes from ai-usage.json ───────────────────────────
    sessions_by_id: dict[str, dict] = {}
    ai_usage_path = dashboard_dir / "ai-usage.json"
    if ai_usage_path.exists():
        try:
            ai_data = json.loads(ai_usage_path.read_text(encoding="utf-8"))
            for s in ai_data.get("sessions", []):
                sid = s.get("session_id", "")
                if not sid:
                    continue
                node_id = f"session:{sid[:16]}"
                date = s.get("date", "")
                project = s.get("project_cwd", "").split("/")[-1]
                use_case = s.get("use_case", "General")
                add_node(node_id, "Session", f"{project} {date}", {
                    "date": date,
                    "project": project,
                    "project_cwd": s.get("project_cwd", ""),
                    "use_case": use_case,
                    "message_count": s.get("message_count", 0),
                    "files_written": s.get("files_written", []),
                    "automated": s.get("automated", False),
                })
                sessions_by_id[sid] = s
                # CLASSIFIED_AS edge
                uc_id = f"usecase:{use_case}"
                if uc_id in node_ids or use_case in USE_CASES:
                    add_node(uc_id, "UseCase", use_case, {})
                    add_edge(node_id, uc_id, "CLASSIFIED_AS")
        except Exception as e:
            utils.verbose(f"  [graph] Could not load ai-usage.json: {e}")

    # ── Plan nodes ────────────────────────────────────────────────────────
    if notes_root and notes_root.exists():
        plans = scan_plans(notes_root)
        for p in plans:
            pid = f"plan:{p['stem']}"
            add_node(pid, "Plan", p.get("title", p["stem"]), {
                "stem": p["stem"],
                "status": p.get("status", ""),
                "project": p.get("project", ""),
                "workstream": p.get("workstream", ""),
                "description": p.get("description", ""),
                "plantype": p.get("plantype", ""),
                "start_date": p.get("start_date", ""),
            })

    # ── TOUCHES edges from plan-sessions.json ────────────────────────────
    plan_sessions_path = dashboard_dir / "plan-sessions.json"
    if plan_sessions_path.exists():
        try:
            ps_data = json.loads(plan_sessions_path.read_text(encoding="utf-8"))
            for stem, session_list in ps_data.items():
                pid = f"plan:{stem}"
                # Ensure plan node exists (may not be in current index)
                if pid not in node_ids:
                    add_node(pid, "Plan", stem, {"stem": stem})
                for s in session_list:
                    sid_short = s.get("session_id", "")[:16]
                    snid = f"session:{sid_short}"
                    if snid in node_ids:
                        add_edge(snid, pid, "TOUCHES")
        except Exception as e:
            utils.verbose(f"  [graph] Could not load plan-sessions.json: {e}")

    # ── Repo nodes from repo-audit.json ──────────────────────────────────
    repo_audit_path = dashboard_dir / "repo-audit.json"
    repo_name_to_id: dict[str, str] = {}
    if repo_audit_path.exists():
        try:
            audit = json.loads(repo_audit_path.read_text(encoding="utf-8"))
            for r in audit.get("repos", []):
                name = r.get("name", "")
                if not name:
                    continue
                rid = f"repo:{name}"
                repo_name_to_id[name] = rid
                add_node(rid, "Repo", name, {
                    "domain": r.get("domain", ""),
                    "path": r.get("path", ""),
                    "ai_commit_count": r.get("ai_commits", 0),
                    "skill_count": r.get("skill_count", 0),
                    "has_claude_md": r.get("has_claude_md", False),
                })
        except Exception as e:
            utils.verbose(f"  [graph] Could not load repo-audit.json: {e}")

    # ── IN_REPO edges: Session → Repo by project_cwd ─────────────────────
    for node in nodes:
        if node["type"] != "Session":
            continue
        cwd = node["attrs"].get("project_cwd", "")
        if not cwd:
            continue
        # Match repo by path suffix
        for repo_name, rid in repo_name_to_id.items():
            if repo_name in cwd or cwd.endswith(repo_name):
                add_edge(node["id"], rid, "IN_REPO")
                break

    # ── Skill nodes + DEFINED_IN edges ───────────────────────────────────
    for skill in _scan_skills():
        sid = skill["id"]
        add_node(sid, "Skill", skill["name"], {
            "group": skill["group"],
            "path": skill["path"],
            "content_preview": skill["content_preview"],
        })
        # DEFINED_IN: skill → repo if skill path contains a known repo name
        skill_path = skill["path"]
        for repo_name, rid in repo_name_to_id.items():
            if repo_name in skill_path:
                add_edge(sid, rid, "DEFINED_IN")
                break

    # ── App nodes + BUILT edges (CG-B) ───────────────────────────────────
    app_names: dict[str, str] = {}  # normalized → node_id
    for node in nodes:
        if node["type"] not in ("Session", "Plan"):
            continue
        text = node["attrs"].get("description", "") + " " + node["label"]
        for raw_name in _extract_apps_from_text(text):
            norm = _normalize_app_name(raw_name)
            if norm not in app_names:
                app_id = f"app:{re.sub(r'[^a-z0-9]', '-', norm)}"
                app_names[norm] = app_id
                add_node(app_id, "App", raw_name, {"normalized": norm})
            app_id = app_names[norm]
            add_edge(node["id"], app_id, "BUILT")

    # ── Stats ─────────────────────────────────────────────────────────────
    type_counts: dict[str, int] = {}
    rel_counts: dict[str, int] = {}
    for n in nodes:
        type_counts[n["type"]] = type_counts.get(n["type"], 0) + 1
    for e in edges:
        rel_counts[e["rel"]] = rel_counts.get(e["rel"], 0) + 1

    # Top plans by TOUCHES in-degree
    touches_count: dict[str, int] = {}
    for e in edges:
        if e["rel"] == "TOUCHES":
            touches_count[e["target"]] = touches_count.get(e["target"], 0) + 1
    top_plans = sorted(touches_count.items(), key=lambda x: -x[1])[:10]

    stats = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "by_type": type_counts,
        "by_rel": rel_counts,
        "top_plans": [{"id": k, "touches": v} for k, v in top_plans],
    }

    return {"nodes": nodes, "edges": edges, "stats": stats}


# ---------------------------------------------------------------------------
# Command: graph-extract
# ---------------------------------------------------------------------------

def cmd_graph_extract(args):
    root = utils.noteplan_root()
    dash_dir = root / "dashboard"
    notes = root / "Notes"

    utils.verbose("Building conversation graph...")
    graph = build_graph(dash_dir, notes)

    if utils.DRY_RUN:
        s = graph["stats"]
        utils.log(f"[dry-run] graph: {s['node_count']} nodes, {s['edge_count']} edges")
        return

    out = dash_dir / "graph.json"
    out.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")

    s = graph["stats"]
    utils.log(f"graph-extract: wrote {out}")
    utils.log(f"  {s['node_count']} nodes  {s['edge_count']} edges")
    for t, c in sorted(s["by_type"].items()):
        utils.log(f"    {t}: {c}")
    if s["top_plans"]:
        utils.log(f"  Top plan by sessions: {s['top_plans'][0]['id']} ({s['top_plans'][0]['touches']} touches)")


# ---------------------------------------------------------------------------
# Command: graph-stats
# ---------------------------------------------------------------------------

def cmd_graph_stats(args):
    root = utils.noteplan_root()
    graph_path = root / "dashboard" / "graph.json"
    if not graph_path.exists():
        utils.err("dashboard/graph.json not found. Run graph-extract first.")
        sys.exit(utils.EXIT_NOT_FOUND)

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    s = graph["stats"]
    nodes = graph["nodes"]
    edges = graph["edges"]

    print(f"\n{'─'*50}")
    print(f"  Graph: {s['node_count']} nodes · {s['edge_count']} edges")
    print(f"{'─'*50}")

    print("\n  Nodes by type:")
    for t, c in sorted(s["by_type"].items(), key=lambda x: -x[1]):
        print(f"    {t:<14} {c:>4}")

    print("\n  Edges by relationship:")
    for r, c in sorted(s["by_rel"].items(), key=lambda x: -x[1]):
        print(f"    {r:<18} {c:>4}")

    if s.get("top_plans"):
        print("\n  Top plans by session count:")
        for entry in s["top_plans"][:5]:
            stem = entry["id"].replace("plan:", "")
            print(f"    {entry['touches']:>3}  {stem}")

    # Use case distribution from sessions
    uc_dist: dict[str, int] = {}
    for n in nodes:
        if n["type"] == "Session":
            uc = n["attrs"].get("use_case", "General")
            uc_dist[uc] = uc_dist.get(uc, 0) + 1
    if uc_dist:
        print("\n  Session use cases:")
        for uc, c in sorted(uc_dist.items(), key=lambda x: -x[1]):
            print(f"    {uc:<14} {c:>4}")

    print()


# ---------------------------------------------------------------------------
# Command: graph-query (Cypher subset + text match)
# ---------------------------------------------------------------------------

_CYPHER_MATCH_RE = re.compile(
    r'MATCH\s+\((\w+)(?::(\w+))?\)'
    r'(?:\s+WHERE\s+(.+?))?'
    r'\s+RETURN\s+(\S+(?:\s*,\s*\S+)*)'
    r'(?:\s+ORDER\s+BY\s+(\S+)(?:\s+(ASC|DESC))?)?'
    r'(?:\s+LIMIT\s+(\d+))?',
    re.IGNORECASE | re.DOTALL,
)


def _eval_where(node: dict, where_clause: str) -> bool:
    """Simple WHERE evaluator: supports n.attr = 'value', n.attr contains 'x', n.attr > N."""
    # n.attr = 'value' or n.attr = "value"
    m = re.match(r'(\w+)\.(\w+)\s*=\s*[\'"]([^\'"]*)[\'"]', where_clause.strip())
    if m:
        attr = m.group(2)
        val = m.group(3)
        return str(node["attrs"].get(attr, "") or node.get(attr, "")).lower() == val.lower()

    # n.attr contains 'value'
    m = re.match(r'(\w+)\.(\w+)\s+contains\s+[\'"]([^\'"]*)[\'"]', where_clause.strip(), re.IGNORECASE)
    if m:
        attr = m.group(2)
        val = m.group(3).lower()
        return val in str(node["attrs"].get(attr, "") or node.get(attr, "")).lower()

    # n.attr > N
    m = re.match(r'(\w+)\.(\w+)\s*([><=!]+)\s*(\d+)', where_clause.strip())
    if m:
        attr, op, val_s = m.group(2), m.group(3), int(m.group(4))
        actual = node["attrs"].get(attr, 0)
        try:
            actual = int(actual)
        except Exception:
            return False
        return eval(f"{actual} {op} {val_s}", {"__builtins__": {}})

    return True


def _get_field(node: dict, field: str) -> Any:
    """Get a field from node or attrs for RETURN/ORDER BY."""
    if "." in field:
        _, attr = field.split(".", 1)
    else:
        attr = field
    return node["attrs"].get(attr) or node.get(attr) or node.get("label", "")


def cmd_graph_query(args):
    root = utils.noteplan_root()
    graph_path = root / "dashboard" / "graph.json"
    if not graph_path.exists():
        utils.err("dashboard/graph.json not found. Run graph-extract first.")
        sys.exit(utils.EXIT_NOT_FOUND)

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = graph["nodes"]

    cypher = getattr(args, "cypher", None)
    text = getattr(args, "text", None)
    limit = getattr(args, "limit", 10)

    if cypher:
        m = _CYPHER_MATCH_RE.search(cypher)
        if not m:
            utils.err("Could not parse Cypher query. Supported: MATCH (n[:Type]) [WHERE n.attr op val] RETURN n.field [ORDER BY n.field [ASC|DESC]] [LIMIT N]")
            sys.exit(1)

        var, type_filter, where, return_fields, order_by, order_dir, lim = m.groups()
        results = nodes[:]

        # Filter by type
        if type_filter:
            results = [n for n in results if n["type"].lower() == type_filter.lower()]

        # Filter by WHERE
        if where:
            results = [n for n in results if _eval_where(n, where)]

        # ORDER BY
        if order_by:
            reverse = (order_dir or "ASC").upper() == "DESC"
            field = order_by.split(".", 1)[-1] if "." in order_by else order_by
            results = sorted(results, key=lambda n: n["attrs"].get(field, "") or "", reverse=reverse)

        # LIMIT
        cap = int(lim) if lim else (limit or 20)
        results = results[:cap]

        # RETURN
        fields = [f.strip() for f in return_fields.split(",")]
        print(f"\n{len(results)} results:\n")
        for node in results:
            vals = []
            for f in fields:
                vals.append(f"{f}={repr(_get_field(node, f))}")
            print(f"  [{node['type']}] {node['label']}  —  {', '.join(vals)}")
        print()

    elif text:
        # Text search across all node labels and attrs
        q = text.lower()
        results = [
            n for n in nodes
            if q in n["label"].lower()
            or any(q in str(v).lower() for v in n["attrs"].values())
        ]
        cap = limit or 10
        print(f"\n{len(results)} matches for '{text}':\n")
        for n in results[:cap]:
            print(f"  [{n['type']}] {n['label']}  ({n['id']})")
        if len(results) > cap:
            print(f"  … {len(results) - cap} more (use --limit or narrow query)")
        print()

    else:
        utils.err("Provide a search text or --cypher query.")
        sys.exit(1)
