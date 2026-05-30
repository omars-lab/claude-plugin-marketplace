"""
test_smoke.py — pytest smoke suite for noteplan-sweep Python modules.

Run from the bin/ directory:
    cd plugins/noteplan-manager/bin
    python3 -m pytest noteplan_sweep/tests/test_smoke.py -v

These tests cover Python-level concerns not reachable by test_smoke.sh:
  - COMMANDS index alignment (drift detection)
  - All modules import without error
  - switch-plan-org dry-run on a known plan stem
  - build_work_board_html produces valid HTML
  - config.plantype_names returns live filesystem entries
  - build_contributions_html produces valid HTML
"""

import re
import sys
import os
from pathlib import Path

import pytest

# Add bin/ to sys.path so imports work regardless of where pytest is invoked from
_BIN = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BIN))

NOTEPLAN_ROOT = Path(
    "~/Library/Containers/co.noteplan.NotePlan3/Data/Library/"
    "Application Support/co.noteplan.NotePlan3"
).expanduser()

DISPATCHER = _BIN / "noteplan-sweep"


# ---------------------------------------------------------------------------
# 1. COMMANDS index alignment — catches any future drift
# ---------------------------------------------------------------------------

def _parse_commands_list(content: str) -> list[str]:
    """Extract command names from the COMMANDS[] list at the top of the dispatcher."""
    return re.findall(r'^\s+\("([^"]+)"', content, re.M)


def _parse_parser_refs(content: str) -> list[tuple[int, str, int]]:
    """Return (lineno, cmd_name, commands_index) for every add_parser() call."""
    refs = []
    for i, line in enumerate(content.split("\n"), start=1):
        m = re.search(r'add_parser\("([^"]+)",\s*help=COMMANDS\[(\d+)\]', line)
        if m:
            refs.append((i, m.group(1), int(m.group(2))))
    return refs


def test_commands_index_alignment():
    """Every add_parser('cmd', help=COMMANDS[N]) must have COMMANDS[N][0] == 'cmd'."""
    content = DISPATCHER.read_text()
    cmds = _parse_commands_list(content)
    refs = _parse_parser_refs(content)

    assert cmds, "COMMANDS[] list is empty — check dispatcher format"
    assert refs, "No add_parser(COMMANDS[N]) calls found — check dispatcher format"

    mismatches = []
    for lineno, name, idx in refs:
        if idx >= len(cmds):
            mismatches.append(f"  Line {lineno}: COMMANDS[{idx}] out of range ({len(cmds)} entries)")
        elif cmds[idx] != name:
            mismatches.append(
                f"  Line {lineno}: add_parser({name!r}) uses COMMANDS[{idx}]={cmds[idx]!r}"
            )

    assert not mismatches, "COMMANDS index drift detected:\n" + "\n".join(mismatches)


def test_commands_count():
    """Sanity-check: dispatcher should have exactly 62 commands."""
    content = DISPATCHER.read_text()
    cmds = _parse_commands_list(content)
    assert len(cmds) == 62, f"Expected 62 commands, got {len(cmds)}: {cmds}"


# ---------------------------------------------------------------------------
# 2. All modules import cleanly
# ---------------------------------------------------------------------------

_MODULES = [
    "noteplan_sweep.backlinks",
    "noteplan_sweep.config",
    "noteplan_sweep.contributions",
    "noteplan_sweep.conversation_mine",
    "noteplan_sweep.dashboard",
    "noteplan_sweep.discovery",
    "noteplan_sweep.graph",
    "noteplan_sweep.graph_embed",
    "noteplan_sweep.link_repair",
    "noteplan_sweep.movement",
    "noteplan_sweep.nav",
    "noteplan_sweep.server",
    "noteplan_sweep.source",
    "noteplan_sweep.sweep_review",
    "noteplan_sweep.url_enrichment",
    "noteplan_sweep.utils",
    "noteplan_sweep.validation",
    "noteplan_sweep.work_board",
]


@pytest.mark.parametrize("module", _MODULES)
def test_module_imports(module):
    """Each module must import without raising at module level."""
    import importlib
    importlib.import_module(module)


# ---------------------------------------------------------------------------
# 3. switch-plan-org dry-run — no crash, no file writes
# ---------------------------------------------------------------------------

def test_switch_plan_org_dry_run(tmp_path):
    """
    switch-plan-org --dry-run on a known personal plan should print a plan and
    exit 0 without moving any files.
    """
    from noteplan_sweep import discovery

    # Pick a plan known to exist in the personal development folder
    known_stem = "🏡260409👨🏻‍💻 Developing Sweep Notes CLI"

    plan_path = None
    if NOTEPLAN_ROOT.exists():
        plan_path = discovery._find_plan_by_stem(known_stem)

    if plan_path is None:
        pytest.skip(f"Plan not found (NotePlan root unavailable or plan removed): {known_stem!r}")

    mtime_before = plan_path.stat().st_mtime

    # Build minimal args namespace
    import types
    args = types.SimpleNamespace(
        stem=known_stem,
        to="work",
        workstream=None,
        dry_run=True,
    )

    # Should not raise; may call sys.exit(0)
    with pytest.raises(SystemExit) as exc_info:
        discovery.cmd_switch_plan_org(args)

    assert exc_info.value.code == 0, f"Unexpected exit code: {exc_info.value.code}"

    # File must not have moved
    assert plan_path.exists(), "Plan file was moved despite --dry-run"
    assert plan_path.stat().st_mtime == mtime_before, "Plan file was modified despite --dry-run"


# ---------------------------------------------------------------------------
# 4. build_work_board_html — produces non-empty HTML string
# ---------------------------------------------------------------------------

def test_build_work_board_html():
    from noteplan_sweep.work_board import build_work_board_html

    html = build_work_board_html(
        plans=[], tasks=[], ideas=[], brag=[], observations=[],
        gaps=[], superpowers=[], impact=[], ai_summary=None,
        generated_at="2026-04-21T00:00:00",
        active_plan_count=0,
        last_brag_date="",
        ai_sessions_month=0,
        days_since_commit=-1,
    )

    assert isinstance(html, str), "build_work_board_html should return a str"
    assert "<!DOCTYPE html>" in html or "<html" in html, "Output is not HTML"
    assert len(html) > 1000, f"HTML suspiciously short: {len(html)} chars"


# ---------------------------------------------------------------------------
# 5. config.plantype_names — live filesystem scan returns >= 5 entries
# ---------------------------------------------------------------------------

def test_plantype_names_live():
    if not NOTEPLAN_ROOT.exists():
        pytest.skip("NotePlan root not available in this environment")

    from noteplan_sweep.config import plantype_names

    names = plantype_names(NOTEPLAN_ROOT)
    assert isinstance(names, dict), "plantype_names should return a dict"
    assert len(names) >= 5, (
        f"Expected >= 5 plantype entries from live filesystem, got {len(names)}: {names}"
    )


def test_plantype_names_keys_are_emojis():
    if not NOTEPLAN_ROOT.exists():
        pytest.skip("NotePlan root not available in this environment")

    from noteplan_sweep.config import plantype_names

    names = plantype_names(NOTEPLAN_ROOT)
    for key in names:
        assert key.strip(), f"Empty key in plantype_names: {names}"


# ---------------------------------------------------------------------------
# 6. build_contributions_html — produces non-empty HTML string
# ---------------------------------------------------------------------------

def test_build_contributions_html():
    from noteplan_sweep.contributions import build_contributions_html

    data = {
        "heatmap": [],
        "work_logs": [],
        "shipped": [],
        "repos": [],
        "summary": {"total_commits": 0, "repos_active": 0},
        "generated_at": "2026-04-21T00:00:00",
    }

    html = build_contributions_html(data)

    assert isinstance(html, str), "build_contributions_html should return a str"
    assert "<!DOCTYPE html>" in html or "<html" in html, "Output is not HTML"
    assert len(html) > 1000, f"HTML suspiciously short: {len(html)} chars"
