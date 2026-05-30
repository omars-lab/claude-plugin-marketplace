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
  SR-16  _py_classify_all_rows: moved_lines and dest_lines populated for move row
  SR-17  _py_classify_all_rows: line_statuses maps each source line
  SR-18  _py_classify_all_rows: went_to_details for went-to rows
  SR-19  _py_classify_all_rows: inferred_section added when section header not in diff
  SR-20  _py_classify_all_rows: self_migration added when src == dest stem
  SR-21  _py_cross_row_issues: V-C2 detected when two rows claim same dest line
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
    _norm_line,
    _py_classify_all_rows,
    _py_cross_row_issues,
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


# ---------------------------------------------------------------------------
# Helpers for _py_classify_all_rows tests
# ---------------------------------------------------------------------------

def _py_make_diff(files: list[dict]) -> str:
    """Build a synthetic unified diff string for Python-level tests."""
    lines = []
    for f in files:
        p = f["path"]
        added   = f.get("added", [])
        removed = f.get("removed", [])
        lines.append(f"diff --git a/{p} b/{p}")
        lines.append("index 000000..abc123 100644")
        lines.append(f"--- a/{p}")
        lines.append(f"+++ b/{p}")
        lines.append(f"@@ -1,{len(removed)} +1,{len(added)} @@")
        for l in removed: lines.append(f"-{l}")
        for l in added:   lines.append(f"+{l}")
    return "\n".join(lines) + "\n"


def _run_classify(diff_text: str, narrative: list) -> list[dict]:
    """Run _py_classify_all_rows with a nonexistent root (no disk lookups)."""
    return _py_classify_all_rows(diff_text, narrative, Path("/nonexistent"))


# ---------------------------------------------------------------------------
# SR-16  _py_classify_all_rows: moved_lines and dest_lines populated for move
# ---------------------------------------------------------------------------

def test_sr16_py_classify_moved_lines():
    """SR-16: move rows include actual moved_lines + dest_lines line content."""
    task = "- [ ] Implement Bikar pattern system in Figma"
    diff = _py_make_diff([
        {"path": "Calendar/20260413.md", "removed": [task], "added": []},
        {"path": "Plans/Bikar.md",       "removed": [],     "added": [task]},
    ])
    narrative = [{"source_file": "Calendar/20260413.md", "section": "Design",
                  "destination": "[[Plans/Bikar]]", "date": "2026-04-13", "summary": ""}]
    results = _run_classify(diff, narrative)
    assert len(results) == 1
    r = results[0]
    assert r["type"] == "move", f"expected move, got {r['type']}"
    assert task in r["moved_lines"], f"moved_lines must contain source task: {r['moved_lines']}"
    assert task in r["dest_lines"],  f"dest_lines must contain matching addition: {r['dest_lines']}"


# ---------------------------------------------------------------------------
# SR-17  _py_classify_all_rows: line_statuses maps each source line
# ---------------------------------------------------------------------------

def test_sr17_py_classify_line_statuses():
    """SR-17: line_statuses maps normLine → 'move'|'absent' for each source line."""
    moved_task  = "- [ ] Implement Bikar pattern system in Figma"
    absent_task = "- [ ] Another task that went nowhere at all here"
    diff = _py_make_diff([
        # Section header ensures direct extraction (not inference) so absent_task is included
        {"path": "Calendar/20260413.md", "removed": ["## Design", moved_task, absent_task], "added": []},
        {"path": "Plans/Bikar.md",       "removed": [],   "added": [moved_task]},
    ])
    narrative = [{"source_file": "Calendar/20260413.md", "section": "Design",
                  "destination": "[[Plans/Bikar]]", "date": "2026-04-13", "summary": ""}]
    results = _run_classify(diff, narrative)
    assert len(results) == 1
    r = results[0]
    statuses = r["line_statuses"]
    moved_norm  = moved_task.strip().lower()
    absent_norm = absent_task.strip().lower()
    assert statuses.get(moved_norm)  == "move",   f"moved task must map to 'move': {statuses}"
    assert statuses.get(absent_norm) == "absent",  f"absent task must map to 'absent': {statuses}"


# ---------------------------------------------------------------------------
# SR-18  _py_classify_all_rows: went_to_details for went-to rows
# ---------------------------------------------------------------------------

def test_sr18_py_classify_went_to_details():
    """SR-18: went-to rows include went_to_details mapping stem→source lines."""
    task = "- [ ] Setup Figma design system workspace for NaqshCoffee branding"
    diff = _py_make_diff([
        # Include section header so _extract_section_lines finds the "Design" section
        {"path": "Calendar/20260413.md", "removed": ["## Design", task], "added": []},
        {"path": "Plans/Breadcrumb.md",  "removed": [],     "added": ["status: done"]},
        {"path": "Plans/DesignSystem.md","removed": [],     "added": [task]},
    ])
    narrative = [{"source_file": "Calendar/20260413.md", "section": "Design",
                  "destination": "[[Plans/Breadcrumb]]", "date": "2026-04-13", "summary": ""}]
    results = _run_classify(diff, narrative)
    assert len(results) == 1
    r = results[0]
    assert r["type"] == "went-to", f"expected went-to, got {r['type']}"
    assert len(r["went_to_details"]) > 0, "went_to_details must be populated"
    all_lines = [l for lines in r["went_to_details"].values() for l in lines]
    assert task in all_lines, f"task must appear in went_to_details values: {r['went_to_details']}"
    norm_task = task.strip().lower()
    assert r["line_statuses"].get(norm_task) == "went-to", \
        f"line_statuses must map went-to task: {r['line_statuses']}"


# ---------------------------------------------------------------------------
# SR-19  _py_classify_all_rows: inferred_section in issues when section not in diff
# ---------------------------------------------------------------------------

def test_sr19_py_classify_inferred_section():
    """SR-19: 'inferred_section' appears in issues when the section header is absent from diff."""
    task = "- [ ] Design the onboarding flow wireframes"
    # No section header in removed lines — inference must be used
    diff = _py_make_diff([
        {"path": "Calendar/20260413.md", "removed": [task], "added": []},
        {"path": "Plans/Design.md",      "removed": [],     "added": [task]},
    ])
    narrative = [{"source_file": "Calendar/20260413.md", "section": "Design",
                  "destination": "[[Plans/Design]]", "date": "2026-04-13", "summary": ""}]
    results = _run_classify(diff, narrative)
    assert len(results) == 1
    r = results[0]
    assert "inferred_section" in r["issues"], \
        f"'inferred_section' must be in issues when section header absent: {r['issues']}"
    assert r["inferred"] is True, f"'inferred' flag must be True: {r}"


# ---------------------------------------------------------------------------
# SR-20  _py_classify_all_rows: self_migration when source and dest are same file
# ---------------------------------------------------------------------------

def test_sr20_py_classify_self_migration():
    """SR-20: 'self_migration' appears in issues when source_file stem == destination stem."""
    task = "- [ ] Refactor the planning section"
    diff = _py_make_diff([
        {"path": "Calendar/20260413.md", "removed": [task], "added": []},
        {"path": "Calendar/20260413.md", "removed": [],     "added": [task]},
    ])
    narrative = [{"source_file": "Calendar/20260413.md", "section": "Planning",
                  "destination": "[[Calendar/20260413]]", "date": "2026-04-13", "summary": ""}]
    results = _run_classify(diff, narrative)
    assert len(results) == 1
    r = results[0]
    assert "self_migration" in r["issues"], \
        f"'self_migration' must be in issues when src == dest: {r['issues']}"


# ---------------------------------------------------------------------------
# SR-21  _py_cross_row_issues: V-C2 when two rows claim the same dest line
# ---------------------------------------------------------------------------

def test_sr21_py_cross_row_issues_v_c2():
    """SR-21: _py_cross_row_issues returns V-C2 when same dest line is claimed by two
    move-rows targeting the same dest stem.
    """
    shared_line = "- [ ] Shared task moved to destination"
    common_stem = "plans/design"
    common_outcomes = [{"kind": "move", "dest": "Plans/Design",
                        "dest_stem": common_stem, "lines": [shared_line]}]
    pre_class = [
        {"idx": 0, "type": "move", "moved_lines": [shared_line],
         "dest_lines": [shared_line], "truly_lost_lines": [], "issues": [],
         "dest_stem": common_stem, "outcomes": common_outcomes},
        {"idx": 1, "type": "move", "moved_lines": [shared_line],
         "dest_lines": [shared_line], "truly_lost_lines": [], "issues": [],
         "dest_stem": common_stem, "outcomes": common_outcomes},
    ]
    issues = _py_cross_row_issues(pre_class)
    vc2 = [i for i in issues if i.startswith("V-C2")]
    assert len(vc2) >= 1, f"Expected at least one V-C2 issue, got: {issues}"
    assert "0" in vc2[0] and "1" in vc2[0], \
        f"V-C2 issue must reference both row indices: {vc2[0]}"


# ---------------------------------------------------------------------------
# SR-24  V-C2 only fires when two MOVE-rows share the same dest stem
#        (different stems with same line content do NOT collide)
# ---------------------------------------------------------------------------

def test_sr25_outcomes_pure_move():
    """SR-25: pure-move breadcrumb produces outcomes=[{kind:'move', dest:<breadcrumb dest>}]."""
    task = "- [ ] Implement Bikar pattern system in Figma"
    diff = _py_make_diff([
        {"path": "Calendar/20260413.md", "removed": [task], "added": []},
        {"path": "Plans/Bikar.md",       "removed": [],     "added": [task]},
    ])
    narrative = [{"source_file": "Calendar/20260413.md", "section": "Design",
                  "destination": "[[Plans/Bikar]]", "date": "2026-04-13", "summary": ""}]
    results = _run_classify(diff, narrative)
    r = results[0]
    outcomes = r["outcomes"]
    assert len(outcomes) == 1, f"pure-move should have 1 outcome, got: {outcomes}"
    assert outcomes[0]["kind"] == "move"
    assert outcomes[0]["dest"] == "Plans/Bikar"
    assert task in outcomes[0]["lines"]
    assert outcomes[0]["dest_stem"] == "bikar"


def test_sr26_outcomes_pure_lost_has_no_destination():
    """SR-26: a row with truly-lost lines emits a 'lost' outcome with dest=None.
    Lost lines are destinationless by definition — the outcomes shape must reflect that.
    """
    lost_task = "- [ ] task that went nowhere at all in this diff"
    # Section header present, line removed from source, no matching dest add anywhere.
    diff = _py_make_diff([
        {"path": "Calendar/20260413.md", "removed": ["## Goals", lost_task], "added": []},
        {"path": "Plans/Bikar.md",       "removed": [],                      "added": ["## Goals", "- [ ] something else entirely"]},
    ])
    narrative = [{"source_file": "Calendar/20260413.md", "section": "Goals",
                  "destination": "[[Plans/Bikar]]", "date": "2026-04-13", "summary": ""}]
    results = _run_classify(diff, narrative)
    r = results[0]
    lost_outcomes = [o for o in r["outcomes"] if o["kind"] == "lost"]
    assert len(lost_outcomes) == 1, \
        f"row with truly-lost lines should emit a 'lost' outcome: {r['outcomes']}"
    lost_o = lost_outcomes[0]
    assert lost_o["dest"] is None, \
        f"lost outcome must have dest=None — lines have no destination: {lost_o}"
    assert lost_o["dest_stem"] is None, \
        f"lost outcome must have dest_stem=None: {lost_o}"
    assert lost_task in lost_o["lines"]


def test_sr27_outcomes_went_to_uses_actual_stem_not_breadcrumb():
    """SR-27: went-to outcome's `dest` is the file the line ACTUALLY went to,
    not the breadcrumb's claimed destination. Otherwise the row would lie about
    where content ended up.
    """
    task = "- [ ] Setup Figma design system workspace for NaqshCoffee branding"
    diff = _py_make_diff([
        {"path": "Calendar/20260413.md", "removed": ["## Design", task], "added": []},
        {"path": "Plans/Breadcrumb.md",  "removed": [],                  "added": ["status: done"]},
        {"path": "Plans/DesignSystem.md","removed": [],                  "added": [task]},
    ])
    narrative = [{"source_file": "Calendar/20260413.md", "section": "Design",
                  "destination": "[[Plans/Breadcrumb]]", "date": "2026-04-13", "summary": ""}]
    results = _run_classify(diff, narrative)
    r = results[0]
    went_to_outcomes = [o for o in r["outcomes"] if o["kind"] == "went-to"]
    assert len(went_to_outcomes) == 1, \
        f"row with went-to lines should emit a 'went-to' outcome: {r['outcomes']}"
    o = went_to_outcomes[0]
    assert "DesignSystem" in (o["dest"] or ""), \
        f"went-to outcome dest must be the actual file (DesignSystem), not the breadcrumb's claim (Breadcrumb): {o}"
    assert o["dest_stem"] == "designsystem"


def test_sr28_breadcrumb_idx_matches_idx_in_one_to_one_world():
    """SR-28: in the staged shape (1 result row per narrative breadcrumb), every result has
    breadcrumb_idx == idx. This guarantees existing JS lookups via idx still work and gives
    us a forward-compatible field for future per-outcome row emission.
    """
    diff = _py_make_diff([
        {"path": "Calendar/20260413.md", "removed": ["- [ ] alpha"], "added": []},
        {"path": "Calendar/20260414.md", "removed": ["- [ ] beta"],  "added": []},
        {"path": "Plans/Bikar.md",       "removed": [],              "added": ["- [ ] alpha", "- [ ] beta"]},
    ])
    narrative = [
        {"source_file": "Calendar/20260413.md", "section": "Design",
         "destination": "[[Plans/Bikar]]", "date": "2026-04-13", "summary": ""},
        {"source_file": "Calendar/20260414.md", "section": "Design",
         "destination": "[[Plans/Bikar]]", "date": "2026-04-14", "summary": ""},
    ]
    results = _run_classify(diff, narrative)
    assert len(results) == 2
    for r in results:
        assert r["breadcrumb_idx"] == r["idx"], \
            f"breadcrumb_idx must equal idx in the staged 1:1 shape: {r}"


def test_sr29_outcomes_for_mixed_breadcrumb():
    """SR-29: a breadcrumb with both moved AND went-to content emits multiple outcomes
    in a single result dict (one per kind). Foundation for splitting them into separate
    visual rows in the table later.
    """
    moved_task   = "- [ ] task that moves to breadcrumb dest properly here"
    went_to_task = "- [ ] task that ends up at a different destination here"
    diff = _py_make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["## Mixed", moved_task, went_to_task], "added": []},
        {"path": "Plans/Breadcrumb.md",
         "removed": [],                                     "added": [moved_task]},
        {"path": "Plans/Elsewhere.md",
         "removed": [],                                     "added": [went_to_task]},
    ])
    narrative = [{"source_file": "Calendar/20260413.md", "section": "Mixed",
                  "destination": "[[Plans/Breadcrumb]]", "date": "2026-04-13", "summary": ""}]
    results = _run_classify(diff, narrative)
    r = results[0]
    kinds = sorted(o["kind"] for o in r["outcomes"])
    assert "move" in kinds, f"mixed row must have a move outcome: {r['outcomes']}"
    assert "went-to" in kinds, f"mixed row must have a went-to outcome: {r['outcomes']}"
    move_o = next(o for o in r["outcomes"] if o["kind"] == "move")
    wt_o   = next(o for o in r["outcomes"] if o["kind"] == "went-to")
    assert moved_task in move_o["lines"]
    assert went_to_task in wt_o["lines"]
    # Critical mental-model assertion: the went-to outcome's dest must NOT be the
    # breadcrumb's claimed destination.
    assert "Elsewhere" in (wt_o["dest"] or ""), \
        f"went-to outcome dest is the actual file, not the breadcrumb's claim: {wt_o}"
    assert wt_o["dest"] != move_o["dest"], \
        f"different outcomes for the same breadcrumb must have different destinations: {r['outcomes']}"


def test_sr24_v_c2_scoped_to_dest_stem():
    """SR-24: identical content under different destinations no longer cross-fires V-C2.
    Pre-#95 V-C2 keyed on normLine alone, flagging shared frontmatter across files as
    a 'collision'. Now scoped on (dest_stem, normLine) — different stems are independent.
    """
    shared_line = "doctype: 📆"  # frontmatter line common to many plan files
    pre_class = [
        {"idx": 0, "type": "anomaly", "moved_lines": [], "dest_lines": [shared_line],
         "truly_lost_lines": [], "issues": [],
         "dest_stem": "plan_a",
         "outcomes": [{"kind": "anomaly", "dest": "Plan A",
                       "dest_stem": "plan_a", "lines": [shared_line]}]},
        {"idx": 1, "type": "anomaly", "moved_lines": [], "dest_lines": [shared_line],
         "truly_lost_lines": [], "issues": [],
         "dest_stem": "plan_b",
         "outcomes": [{"kind": "anomaly", "dest": "Plan B",
                       "dest_stem": "plan_b", "lines": [shared_line]}]},
    ]
    issues = _py_cross_row_issues(pre_class)
    vc2 = [i for i in issues if i.startswith("V-C2")]
    assert len(vc2) == 0, \
        f"V-C2 must NOT fire when stems differ — different files can have identical " \
        f"content (e.g. frontmatter) without it being a collision: {issues}"


# ---------------------------------------------------------------------------
# SR-22  Dedupe: two inferred rows competing for same dest line — winner only
# ---------------------------------------------------------------------------

def test_sr22_dedupe_inferred_rows():
    """SR-22: when two inferred rows claim the same dest line, only the lowest-idx row keeps it.
    The losing row's source line is REMOVED from its accounting entirely (not added to
    truly_lost). The line was misattributed by inference; it actually belongs to the winner
    row and is safely on disk at the destination — falsely reporting it as lost would mislead.
    """
    task = "- [ ] Implement Bikar pattern system in Figma"
    # No section headers in source — both rows fall into inference mode.
    diff = _py_make_diff([
        {"path": "Calendar/20260413.md", "removed": [task], "added": []},
        {"path": "Plans/Design.md",      "removed": [],     "added": [task]},
    ])
    narrative = [
        {"source_file": "Calendar/20260413.md", "section": "Section A",
         "destination": "[[Plans/Design]]", "date": "2026-04-13", "summary": ""},
        {"source_file": "Calendar/20260413.md", "section": "Section B",
         "destination": "[[Plans/Design]]", "date": "2026-04-13", "summary": ""},
    ]
    results = _run_classify(diff, narrative)
    assert len(results) == 2

    winner, loser = results[0], results[1]
    assert winner["inferred"] is True, "winner row should be inferred"
    assert loser["inferred"] is True,  "loser row should be inferred"

    assert task in winner["moved_lines"], f"winner must keep the line: {winner}"
    assert task in winner["dest_lines"],  f"winner must keep dest line: {winner}"

    assert task not in loser["moved_lines"], f"loser must not keep moved line: {loser}"
    assert task not in loser["dest_lines"],  f"loser must drop dest line: {loser}"
    assert task not in loser["truly_lost_lines"], \
        f"loser must NOT report the line as truly_lost — it's misattribution, not loss: {loser}"
    assert "dedupe_demoted" in loser["issues"], \
        f"loser must be tagged dedupe_demoted: {loser['issues']}"
    assert loser["moved_count"] == 0
    assert loser["lost_count"] == 0, \
        f"loser must not gain a phantom lost count from dedupe: {loser}"
    assert loser["type"] == "empty", \
        f"loser drops to empty when its only claim was a misattribution: {loser['type']}"
    # line_statuses for the demoted line must be cleared
    assert _norm_line(task) not in (loser.get("line_statuses") or {}), \
        f"loser's line_statuses must drop the demoted line: {loser.get('line_statuses')}"


# ---------------------------------------------------------------------------
# SR-23  Dedupe skipped: two real-header rows — V-C2 reported, no demotion
# ---------------------------------------------------------------------------

def test_sr23_dedupe_real_header_collisions_auto_resolve():
    """SR-23 (rev v3.116.0): real-header cross-row collisions auto-resolve to
    one canonical winner — a line can only exist once in the destination, so
    showing it in N rows misrepresents the move count. Lowest-idx row wins,
    others get `dedupe_demoted` and drop the line entirely.

    The user's authoring intent (multiple sections claiming the same content)
    is preserved via the `dedupe_demoted` audit tag on losers, but the portal
    no longer visually inflates the move count.
    """
    task = "- [ ] shared planning task across both sections"
    diff = _py_make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["## Section A", task, "## Section B", task], "added": []},
        {"path": "Plans/Design.md",
         "removed": [], "added": [task]},
    ])
    narrative = [
        {"source_file": "Calendar/20260413.md", "section": "Section A",
         "destination": "[[Plans/Design]]", "date": "2026-04-13", "summary": ""},
        {"source_file": "Calendar/20260413.md", "section": "Section B",
         "destination": "[[Plans/Design]]", "date": "2026-04-13", "summary": ""},
    ]
    results = _run_classify(diff, narrative)
    assert len(results) == 2
    winner, loser = results[0], results[1]

    assert winner["inferred"] is False, "winner has real header"
    assert loser["inferred"]  is False, "loser also has real header"

    # Winner keeps the line; loser drops it (auto-resolved).
    assert task in winner["moved_lines"], f"winner keeps line: {winner}"
    assert task not in loser["moved_lines"], f"loser drops line: {loser}"
    assert "dedupe_demoted" in loser.get("issues", []), \
        f"loser must be tagged dedupe_demoted for audit: {loser['issues']}"
    assert task not in loser.get("truly_lost_lines", []), \
        f"loser must NOT report the line as lost — it's at the dest, just not " \
        f"attributed to this row anymore: {loser}"

    # V-C2 no longer fires — the collision was auto-resolved.
    issues = _py_cross_row_issues(results)
    vc2 = [i for i in issues if i.startswith("V-C2")]
    assert len(vc2) == 0, \
        f"V-C2 must NOT fire after auto-resolution — only one row claims the line now: {issues}"
