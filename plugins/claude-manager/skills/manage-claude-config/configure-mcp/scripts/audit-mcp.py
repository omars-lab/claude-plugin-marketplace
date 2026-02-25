#!/usr/bin/env python3
"""
audit-mcp.py — MCP configuration auditor for configure-mcp skill.

Parses ~/.claude.json and ~/.claude/settings.json, enumerates all MCP
servers, reports active vs disabled tool counts, and estimates token
context overhead.

Usage:
    python3 scripts/audit-mcp.py
    python3 scripts/audit-mcp.py --json      # machine-readable output
"""

import argparse
import json
import pathlib
import sys

# ---------------------------------------------------------------------------
# Known tool inventories (update as new servers are discovered)
# ---------------------------------------------------------------------------
KNOWN_TOOLS = {
    "MCP_DOCKER": [
        "code-mode",
        "get_timed_transcript",
        "get_transcript",
        "get_video_info",
        "mcp-add",
        "mcp-config-set",
        "mcp-exec",
        "mcp-find",
        "mcp-remove",
    ],
    "plantuml": [
        "generate_plantuml_diagram",
        "encode_plantuml",
        "decode_plantuml",
    ],
}

# Rough token cost per active tool (name + description + schema)
TOKENS_PER_TOOL = 120

COST_TIERS = [
    (0,  5,  "Negligible"),
    (6,  15, "Low"),
    (16, 30, "Medium"),
    (31, 999, "High ⚠"),
]


def cost_tier(n: int) -> str:
    for lo, hi, label in COST_TIERS:
        if lo <= n <= hi:
            return label
    return "Unknown"


def load_config(path: pathlib.Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"  ✗ JSON parse error in {path}: {e}", file=sys.stderr)
        return {}


def audit() -> list[dict]:
    sources = {
        "~/.claude.json": pathlib.Path("~/.claude.json").expanduser(),
        "~/.claude/settings.json": pathlib.Path("~/.claude/settings.json").expanduser(),
    }

    results = []

    for source_label, path in sources.items():
        config = load_config(path)
        servers = config.get("mcpServers", {})
        for name, entry in servers.items():
            disabled = entry.get("disabledTools", [])
            known = KNOWN_TOOLS.get(name)
            if known:
                total = len(known)
                active = [t for t in known if t not in disabled]
                active_count = len(active)
                unknown_tools = False
            else:
                total = None
                active_count = None
                active = []
                unknown_tools = True

            results.append({
                "name": name,
                "source": source_label,
                "command": entry.get("command", ""),
                "args": entry.get("args", []),
                "disabled_tools": disabled,
                "active_tools": active,
                "total_tools": total,
                "active_count": active_count,
                "unknown_tools": unknown_tools,
                "estimated_tokens": active_count * TOKENS_PER_TOOL if active_count is not None else None,
                "cost_tier": cost_tier(active_count) if active_count is not None else "Unknown",
            })

    return results


def print_dashboard(results: list[dict]) -> None:
    if not results:
        print("No MCP servers found in either config file.")
        return

    total_active = sum(r["active_count"] or 0 for r in results)
    total_tokens = sum(r["estimated_tokens"] or 0 for r in results)

    print()
    print("MCP Configuration Audit")
    print("─" * 72)
    print(f"  {'Server':<20} {'Source':<25} {'Tools':<8} {'Tier':<12} Notes")
    print(f"  {'──────':<20} {'──────':<25} {'─────':<8} {'────':<12} ─────")

    for r in results:
        if r["unknown_tools"]:
            tool_str = "?/?"
            notes = "tool inventory unknown"
        else:
            tool_str = f"{r['active_count']}/{r['total_tools']}"
            if r["disabled_tools"]:
                notes = f"{len(r['disabled_tools'])} tool(s) disabled"
            else:
                notes = "all tools active"

        print(f"  {r['name']:<20} {r['source']:<25} {tool_str:<8} {r['cost_tier']:<12} {notes}")

    print("─" * 72)
    print(f"  Total active tools: {total_active}  |  Estimated overhead: ~{total_tokens:,} tokens/session")
    print()

    # Recommendations
    high_cost = [r for r in results if r["active_count"] and r["active_count"] > 5]
    if high_cost:
        print("Recommendations:")
        for r in high_cost:
            known = KNOWN_TOOLS.get(r["name"])
            if known and r["active_count"] == r["total_tools"]:
                print(f"  • {r['name']}: {r['active_count']} tools all active — use disabledTools to restrict to what you need")
            elif r["active_count"] and r["active_count"] > 15:
                print(f"  • {r['name']}: {r['active_count']} active tools — consider moving to an opt-in alias")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit MCP server configuration")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    results = audit()

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_dashboard(results)


if __name__ == "__main__":
    main()
