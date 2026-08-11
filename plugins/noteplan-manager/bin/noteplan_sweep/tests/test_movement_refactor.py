"""Parity + unit tests for movement.insert_into_section (the shared refactor).

Proves that append-section and move-range produce byte-identical destinations
for equivalent inputs (they now share insert_into_section), and that the
date-subheader / create-at-EOF / cleanup behaviours are preserved.
"""

import types
from pathlib import Path

import noteplan_sweep.movement as movement
import noteplan_sweep.utils as utils


# ---------------------------------------------------------------------------
# Pure function
# ---------------------------------------------------------------------------

def test_insert_creates_section_at_eof():
    dst = "# Title\n\nsome body\n"
    out = movement.insert_into_section(dst, "# Next Steps", ["- [ ] a"], None)
    assert "# Next Steps" in out
    assert out.rstrip().endswith("- [ ] a")


def test_insert_appends_into_existing_section():
    dst = "# Plan\n\n# Next Steps\n- [ ] old\n"
    out = movement.insert_into_section(dst, "# Next Steps", ["- [ ] new"], None)
    lines = out.splitlines()
    assert lines.index("- [ ] old") < lines.index("- [ ] new")


def test_insert_new_date_subheader():
    dst = "# Log\n"
    out = movement.insert_into_section(dst, "# Log", ["- entry"], "2026-07-09")
    assert "## From 2026-07-09" in out
    assert out.index("## From 2026-07-09") < out.index("- entry")


def test_insert_existing_date_subheader_dedup():
    dst = "# Log\n## From 2026-07-09\n- old\n"
    out = movement.insert_into_section(dst, "# Log", ["- new"], "2026-07-09")
    assert out.count("## From 2026-07-09") == 1
    lines = out.splitlines()
    assert lines.index("- old") < lines.index("- new")


def test_insert_ends_with_newline():
    out = movement.insert_into_section("# S\n\n\n", "# S", ["x"], None)
    assert out.endswith("\n")
    # inserted before the section's trailing blank lines (legacy behaviour)
    assert out.splitlines()[:2] == ["# S", "x"]


# ---------------------------------------------------------------------------
# Parity: append-section vs move-range land content identically
# ---------------------------------------------------------------------------

def _write(p: Path, text: str):
    p.write_text(text, encoding="utf-8")


def _run_append(tmp: Path, dst_text: str, content: str, section, date=None) -> str:
    dst = tmp / "dst_append.md"
    cf = tmp / "content.txt"
    _write(dst, dst_text)
    _write(cf, content)
    movement.cmd_append_section(types.SimpleNamespace(
        dst=str(dst), section_header=section, content_file=str(cf), date=date))
    return dst.read_text(encoding="utf-8")


def _run_move(tmp: Path, dst_text: str, content_lines: list[str], section, date=None) -> str:
    # Source file: the content lines sitting under a throwaway header
    src = tmp / "src_move.md"
    dst = tmp / "dst_move.md"
    src_body = ["# Src"] + content_lines
    _write(src, "\n".join(src_body) + "\n")
    _write(dst, dst_text)
    # move lines 2..(1+len) (1-based) = the content lines
    movement.cmd_move_range(types.SimpleNamespace(
        src=str(src), start=2, end=1 + len(content_lines),
        dst=str(dst), section_header=section, date=date))
    return dst.read_text(encoding="utf-8")


def test_parity_no_date(tmp_path):
    dst = "# Plan\n\n# Next Steps\n- [ ] existing\n"
    content_lines = ["- [ ] moved one", "- [ ] moved two"]
    a = _run_append(tmp_path, dst, "\n".join(content_lines) + "\n", "# Next Steps")
    m = _run_move(tmp_path, dst, content_lines, "# Next Steps")
    assert a == m


def test_parity_with_date_new_subheader(tmp_path):
    dst = "# Log\n"
    content_lines = ["- entry a", "- entry b"]
    a = _run_append(tmp_path, dst, "\n".join(content_lines) + "\n", "# Log", date="2026-07-09")
    m = _run_move(tmp_path, dst, content_lines, "# Log", date="2026-07-09")
    assert a == m


def test_parity_creates_missing_section(tmp_path):
    dst = "# Plan\n\nbody\n"
    content_lines = ["- new line"]
    a = _run_append(tmp_path, dst, "\n".join(content_lines) + "\n", "# Fresh")
    m = _run_move(tmp_path, dst, content_lines, "# Fresh")
    assert a == m
    assert "# Fresh" in a
