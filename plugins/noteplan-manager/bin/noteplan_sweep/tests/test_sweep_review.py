"""
test_sweep_review.py — Regression tests for sweep_review.py (Python-side).

Run from the bin/ directory:
    cd plugins/noteplan-manager/bin
    python3 -m pytest noteplan_sweep/tests/test_sweep_review.py -v

Bug index (each test references its ID):
  SR-01  _decode_git_quoted_paths: octal emoji in +++ / --- lines not decoded
  SR-02  _decode_git_quoted_paths: diff --git a/... b/... lines decoded
  SR-03  _decode_git_quoted_paths: plain ASCII paths left unchanged
  SR-04  _extract_js_str: extracts DIFF_TEXT from snapshot HTML (JSONDecoder approach)
  SR-05  _extract_js_str: returns "" when var not present
  SR-06  _extract_js_str: handles huge string without catastrophic backtracking
  SR-07  _extract_js_val: extracts NARRATIVE array from snapshot HTML
  SR-08  _extract_js_val: returns [] when var not present
  SR-09  _extract_sweep_narrative: valid breadcrumb rows are returned
  SR-10  _extract_sweep_narrative: separator rows (---|---) are filtered out
  SR-11  _extract_sweep_narrative: header rows (non-date first col) are filtered out
  SR-12  _build_snapshot_html: embeds DIFF_TEXT as recoverable JSON string
  SR-13  _build_snapshot_html: embeds NARRATIVE as recoverable JSON array
  SR-14  _build_snapshot_html: DIFF_TEXT is decoded (no octal escapes remain)
  SR-15  compile round-trip: octal-encoded snapshot → compile → decoded DIFF_TEXT
"""

import json
import re
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BIN))

from noteplan_sweep.sweep_review import (
    _decode_git_quoted_paths,
    _extract_js_str,
    _extract_js_val,
    _build_snapshot_html,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COFFEE_RAW   = '"b/Notes/\\342\\230\\225\\357\\270\\217 NaqshCoffee/test.md"'
_COFFEE_PLAIN = 'b/Notes/☕️ NaqshCoffee/test.md'

_HOME_RAW   = '"b/Notes/\\360\\237\\217\\241 Personal/test.md"'
_HOME_PLAIN = 'b/Notes/🏡 Personal/test.md'


def _make_snapshot(diff_text: str, narrative: list, stat_text: str = "") -> str:
    """Build a minimal snapshot HTML string using the real builder."""
    return _build_snapshot_html(
        run_id="2026-04-21-01",
        date_str="2026-04-21",
        sha="abc1234",
        stat_text=stat_text or "1 file changed, 1 insertion(+)",
        diff_text=diff_text,
        seed_comments=[],
        narrative=narrative,
        changed_calendar_files=[],
    )


# ---------------------------------------------------------------------------
# SR-01 / SR-02 / SR-03  _decode_git_quoted_paths
# ---------------------------------------------------------------------------

class TestDecodeGitQuotedPaths:

    def test_sr01_plus_plus_plus_line_decoded(self):
        """SR-01: +++ "b/Notes/\\NNN..." → +++ b/Notes/emoji..."""
        line = f'+++ {_COFFEE_RAW}'
        result = _decode_git_quoted_paths(line)
        assert result == f'+++ {_COFFEE_PLAIN}', f"Got: {result!r}"

    def test_sr01_minus_minus_minus_line_decoded(self):
        """SR-01: --- "a/Notes/\\NNN..." → --- a/Notes/emoji..."""
        raw = _COFFEE_RAW.replace('"b/', '"a/')
        line = f'--- {raw}'
        result = _decode_git_quoted_paths(line)
        assert '☕️' in result
        assert '"' not in result

    def test_sr02_diff_git_line_decoded(self):
        """SR-02: diff --git "a/..." "b/..." both sides decoded."""
        line = f'diff --git {_COFFEE_RAW.replace("b/", "a/")} {_COFFEE_RAW}'
        result = _decode_git_quoted_paths(line)
        assert result.count('☕️') == 2
        assert '"' not in result

    def test_sr02_home_emoji(self):
        """SR-02: 🏡 personal path decoded correctly."""
        line = f'+++ {_HOME_RAW}'
        result = _decode_git_quoted_paths(line)
        assert result == f'+++ {_HOME_PLAIN}', f"Got: {result!r}"

    def test_sr03_plain_ascii_unchanged(self):
        """SR-03: ASCII-only paths pass through untouched."""
        line = '+++ b/Calendar/20260421.md'
        assert _decode_git_quoted_paths(line) == line

    def test_sr03_empty_string(self):
        """SR-03: Empty string is a no-op."""
        assert _decode_git_quoted_paths("") == ""

    def test_sr01_multiple_lines(self):
        """SR-01: Multi-line diff block decoded correctly."""
        block = (
            f'diff --git {_COFFEE_RAW.replace("b/","a/")} {_COFFEE_RAW}\n'
            f'--- {_COFFEE_RAW.replace("b/","a/")}\n'
            f'+++ {_COFFEE_RAW}\n'
            f'+some content\n'
        )
        result = _decode_git_quoted_paths(block)
        assert result.count('☕️') == 4   # diff --git (×2) + --- + +++
        assert '"' not in result


# ---------------------------------------------------------------------------
# SR-04 / SR-05 / SR-06  _extract_js_str
# ---------------------------------------------------------------------------

class TestExtractJsStr:

    def test_sr04_round_trips_simple_string(self):
        """SR-04: basic string value extracted correctly."""
        html = 'const DIFF_TEXT = "hello world";'
        assert _extract_js_str(html, "DIFF_TEXT") == "hello world"

    def test_sr04_round_trips_with_escapes(self):
        """SR-04: JSON escapes (\\n, \\t, emoji as \\uXXXX) survive round-trip."""
        original = "diff --git a/CLAUDE.md b/CLAUDE.md\nindex abc..def 100644\n"
        html = f'const DIFF_TEXT = {json.dumps(original)};'
        assert _extract_js_str(html, "DIFF_TEXT") == original

    def test_sr04_handles_unicode_emoji(self):
        """SR-04: Emoji in diff_text round-trips via json.dumps → extract."""
        original = "+++ b/Notes/☕️ NaqshCoffee/test.md\n+some content\n"
        html = f'const DIFF_TEXT = {json.dumps(original)};'
        assert _extract_js_str(html, "DIFF_TEXT") == original

    def test_sr05_missing_var_returns_empty(self):
        """SR-05: Missing variable returns empty string, not exception."""
        html = 'const OTHER = "value";'
        assert _extract_js_str(html, "DIFF_TEXT") == ""

    def test_sr05_wrong_type_returns_empty(self):
        """SR-05: Numeric value returns empty string (expects str)."""
        html = 'const DIFF_TEXT = 42;'
        assert _extract_js_str(html, "DIFF_TEXT") == ""

    def test_sr06_large_string_no_hang(self):
        """SR-06: 500 KB string extracts without catastrophic backtracking."""
        big = "x" * 500_000
        html = f'const DIFF_TEXT = {json.dumps(big)};'
        result = _extract_js_str(html, "DIFF_TEXT")
        assert result == big

    def test_sr04_extracts_correct_var_among_multiple(self):
        """SR-04: Picks the right variable when multiple are present."""
        html = (
            'const STAT_TEXT = "stat";\n'
            'const DIFF_TEXT = "diff";\n'
            'const OTHER = "other";\n'
        )
        assert _extract_js_str(html, "DIFF_TEXT") == "diff"
        assert _extract_js_str(html, "STAT_TEXT") == "stat"


# ---------------------------------------------------------------------------
# SR-07 / SR-08  _extract_js_val
# ---------------------------------------------------------------------------

class TestExtractJsVal:

    def test_sr07_extracts_narrative_array(self):
        """SR-07: NARRATIVE array of dicts round-trips correctly."""
        rows = [
            {"date": "2026-04-13", "source_file": "Calendar/20260413.md",
             "section": "I Owe", "summary": "IOUs (3 items)",
             "destination": "[[20260421]]"},
        ]
        html = f'const NARRATIVE = {json.dumps(rows)};'
        result = _extract_js_val(html, "NARRATIVE")
        assert result == rows

    def test_sr07_extracts_empty_array(self):
        """SR-07: Empty NARRATIVE array returns []."""
        html = 'const NARRATIVE = [];'
        assert _extract_js_val(html, "NARRATIVE") == []

    def test_sr08_missing_var_returns_empty_list(self):
        """SR-08: Missing variable returns [], not exception."""
        html = 'const OTHER = [];'
        assert _extract_js_val(html, "NARRATIVE") == []

    def test_sr08_string_type_returns_empty_list(self):
        """SR-08: String value for an array var returns [] (wrong type)."""
        html = 'const NARRATIVE = "not-an-array";'
        assert _extract_js_val(html, "NARRATIVE") == []


# ---------------------------------------------------------------------------
# SR-09 / SR-10 / SR-11  _extract_sweep_narrative (via table_re directly)
# ---------------------------------------------------------------------------

# We test the regex + filter logic in isolation (no git needed).

_TABLE_RE = re.compile(
    r'^\|\s*(?P<date>[\d-]+)\s*\|\s*(?P<section>[^|]+)\s*\|\s*(?P<summary>[^|]+)\s*\|\s*(?P<dest>[^|]+)\s*\|',
    re.MULTILINE
)
_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _parse_breadcrumb_table(markdown: str) -> list[dict]:
    """Replicate the filtering logic from _extract_sweep_narrative."""
    rows = []
    for m in _TABLE_RE.finditer(markdown):
        date_val = m.group("date").strip()
        if not _DATE_RE.match(date_val):
            continue
        rows.append({
            "date":        date_val,
            "section":     m.group("section").strip(),
            "summary":     m.group("summary").strip(),
            "destination": m.group("dest").strip(),
        })
    return rows


class TestExtractSweepNarrative:

    _VALID_TABLE = textwrap.dedent("""\
        | Date | Section | Summary | Destination |
        |---|---|---|---|
        | 2026-04-13 | I Owe | IOUs to Anna (3 items) | [[20260421]] |
        | 2026-04-13 | Config Agent ARB | ARB tasks | [[🏢260324🤖 Hardening A2A POC]] |
    """)

    _SEP_TABLE = textwrap.dedent("""\
        | Date | Section | Summary | Destination |
        |---|---|---|---|
        | ------- | ------- | ------- | ------------ |
        | 2026-04-13 | Real section | Real summary | [[20260421]] |
    """)

    _HEADER_ROW_TABLE = textwrap.dedent("""\
        | Date | Section | Summary | Destination |
        |---|---|---|---|
        | Date | Section | Summary | Destination |
        | 2026-04-13 | Real | Summary | [[20260421]] |
    """)

    def test_sr09_valid_rows_returned(self):
        """SR-09: Well-formed breadcrumb rows are parsed and returned."""
        rows = _parse_breadcrumb_table(self._VALID_TABLE)
        assert len(rows) == 2
        assert rows[0]["date"] == "2026-04-13"
        assert rows[0]["section"] == "I Owe"
        assert rows[0]["destination"] == "[[20260421]]"
        assert rows[1]["section"] == "Config Agent ARB"

    def test_sr10_separator_rows_filtered(self):
        """SR-10: |---|---|---|---|  and  |-------|-------|  rows are excluded."""
        rows = _parse_breadcrumb_table(self._SEP_TABLE)
        # Only the valid data row should survive
        assert len(rows) == 1
        assert rows[0]["section"] == "Real section"

    def test_sr11_header_rows_filtered(self):
        """SR-11: Header row ('Date | Section | ...') is excluded (not a YYYY-MM-DD date)."""
        rows = _parse_breadcrumb_table(self._HEADER_ROW_TABLE)
        assert len(rows) == 1
        assert rows[0]["section"] == "Real"

    def test_sr10_all_sep_table_returns_empty(self):
        """SR-10: Table with only separator rows returns empty list."""
        only_seps = textwrap.dedent("""\
            | Date | Section | Summary | Destination |
            |---|---|---|---|
            | ------- | ------- | ------- | ------------ |
        """)
        assert _parse_breadcrumb_table(only_seps) == []

    def test_sr09_partial_date_excluded(self):
        """SR-09: Partial date like '2026-04' is not a valid YYYY-MM-DD."""
        bad = "| 2026-04 | Section | Summary | [[dest]] |\n"
        assert _parse_breadcrumb_table(bad) == []


# ---------------------------------------------------------------------------
# SR-12 / SR-13 / SR-14  _build_snapshot_html
# ---------------------------------------------------------------------------

class TestBuildSnapshotHtml:

    _SAMPLE_DIFF = (
        "diff --git a/Calendar/20260413.md b/Calendar/20260413.md\n"
        "index abc..def 100644\n"
        "--- a/Calendar/20260413.md\n"
        "+++ b/Calendar/20260413.md\n"
        "@@ -1,3 +1,4 @@\n"
        " # 2026-04-13\n"
        "-old line\n"
        "+new line\n"
    )

    _SAMPLE_NARRATIVE = [
        {"date": "2026-04-13", "source_file": "Calendar/20260413.md",
         "section": "I Owe", "summary": "IOUs (3 items)",
         "destination": "[[20260421]]"},
    ]

    def test_sr12_diff_text_round_trips(self):
        """SR-12: DIFF_TEXT embedded in HTML can be re-extracted as original string."""
        html = _make_snapshot(self._SAMPLE_DIFF, [])
        extracted = _extract_js_str(html, "DIFF_TEXT")
        assert extracted == self._SAMPLE_DIFF

    def test_sr13_narrative_round_trips(self):
        """SR-13: NARRATIVE array embedded in HTML can be re-extracted intact."""
        html = _make_snapshot(self._SAMPLE_DIFF, self._SAMPLE_NARRATIVE)
        extracted = _extract_js_val(html, "NARRATIVE")
        assert extracted == self._SAMPLE_NARRATIVE

    def test_sr14_no_octal_escapes_in_diff_text(self):
        """SR-14: If diff_text has been decoded, DIFF_TEXT in HTML has no \\NNN octal."""
        decoded_diff = (
            "diff --git a/Notes/☕️ NaqshCoffee/test.md b/Notes/☕️ NaqshCoffee/test.md\n"
            "+++ b/Notes/☕️ NaqshCoffee/test.md\n"
            "+some content\n"
        )
        html = _make_snapshot(decoded_diff, [])
        extracted = _extract_js_str(html, "DIFF_TEXT")
        # Octal sequences like \342 must not appear in the extracted string
        assert not re.search(r'\\[0-3][0-7][0-7]', extracted), (
            "Octal escape sequences found in extracted DIFF_TEXT"
        )
        assert '☕️' in extracted

    def test_sr12_stat_text_round_trips(self):
        """SR-12: STAT_TEXT embedded and re-extracted correctly."""
        stat = " Calendar/20260413.md | 2 +-\n 1 file changed"
        html = _make_snapshot(self._SAMPLE_DIFF, [], stat_text=stat)
        assert _extract_js_str(html, "STAT_TEXT") == stat

    def test_html_structure(self):
        """Basic: output is well-formed HTML with required script block."""
        html = _make_snapshot(self._SAMPLE_DIFF, [])
        assert "<!DOCTYPE html>" in html or "<html" in html
        assert "const DIFF_TEXT = " in html
        assert "const NARRATIVE = " in html
        assert "function renderNarrative" in html


# ---------------------------------------------------------------------------
# SR-15  compile round-trip: octal snapshot → decode → extracted clean
# ---------------------------------------------------------------------------

class TestCompileRoundTrip:

    def test_sr15_compile_decodes_octal_paths(self):
        """SR-15: Snapshot with octal-encoded paths → _decode + embed → extracted clean."""
        # Simulate a snapshot that was generated before decoding was applied:
        # DIFF_TEXT contains raw octal-quoted paths as git would emit them.
        raw_diff = (
            'diff --git "a/Notes/\\342\\230\\225\\357\\270\\217 NaqshCoffee/test.md" '
            '"b/Notes/\\342\\230\\225\\357\\270\\217 NaqshCoffee/test.md"\n'
            '+++ "b/Notes/\\342\\230\\225\\357\\270\\217 NaqshCoffee/test.md"\n'
            '+content\n'
        )
        # Build snapshot with the raw (still-encoded) diff
        old_html = _make_snapshot(raw_diff, [])

        # Simulate what compile does: extract → decode → re-embed
        from noteplan_sweep.sweep_review import _decode_git_quoted_paths
        extracted = _extract_js_str(old_html, "DIFF_TEXT")
        decoded   = _decode_git_quoted_paths(extracted)
        new_html  = _make_snapshot(decoded, [])

        # The new HTML should have the emoji form, not octal
        final = _extract_js_str(new_html, "DIFF_TEXT")
        assert '☕️' in final, "Emoji not found after decode round-trip"
        assert '\\342' not in final, "Octal escape still present after decode"
        assert '"b/' not in final, "Git-quoted path still present after decode"
