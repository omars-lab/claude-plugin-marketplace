"""
test_invariants.py — Mental-model guardian tests (backlog #86).

Locks in the 9 structural invariants the portal's classification must satisfy.
Each invariant has:
  - a reusable `assert_*(results, ...)` helper
  - a focused test using a crafted diff that would *fail* the invariant if broken

A bundled `assert_all_invariants(results, diff_text)` runs all 9 helpers in one
shot — call it from any future SR-N test to guard against silent shape drift.

Run from the bin/ directory:
    cd plugins/noteplan-manager/bin
    python3 -m pytest noteplan_sweep/tests/test_invariants.py -v

Invariant index (each test references its number):
  INV-1  moved-line presence in diff: src has `-`, dest has `+`
  INV-2  lost-line absence in diff:   src has `-`, no `+` anywhere
  INV-3  inferred flag set when section header missing in diff
  INV-4  outcomes shape: kind ∈ enum, dest=None iff lost
  INV-5  outcomes ↔ legacy field count parity
  INV-6  dedupe non-duplication on (dest_stem, normLine) when ≥1 inferred
  INV-7  no phantom losses: dedupe_demoted line ∉ truly_lost / line_statuses
  INV-8  breadcrumb_idx == idx in 1:1 staged shape
  INV-9  V-C2/V-C3 issues include dest_stem context (stem-scoped)
"""

import sys
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BIN))

from noteplan_sweep.sweep_review import (
    _norm_line,
    _py_classify_all_rows,
    _py_cross_row_issues,
)

VALID_KINDS = {"move", "went-to", "lost", "anomaly", "empty"}


# ---------------------------------------------------------------------------
# Diff helpers — extract +/− line sets so we can verify against them
# ---------------------------------------------------------------------------

def _parse_diff_sides(diff_text: str) -> tuple[set[str], set[str]]:
    """Return (removed_lines, added_lines) sets across the whole diff.

    Tracks hunk state so content lines that themselves start with `-` (e.g.
    markdown tasks `- [ ] ...`) aren't confused with `---` file headers.
    File headers always appear before any `@@` hunk marker; once inside a
    hunk, any leading `-` or `+` is a content marker.
    """
    removed: set[str] = set()
    added: set[str] = set()
    in_hunk = False
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("diff --git") or line.startswith("index "):
            in_hunk = False
            continue
        if line.startswith("-"):
            removed.add(line[1:])
        elif line.startswith("+"):
            added.add(line[1:])
    return removed, added


def _make_diff(files: list[dict]) -> str:
    """Synthetic unified diff. Mirrors test_sweep_review._py_make_diff."""
    out: list[str] = []
    for f in files:
        p = f["path"]
        added = f.get("added", [])
        removed = f.get("removed", [])
        out.append(f"diff --git a/{p} b/{p}")
        out.append("index 000000..abc123 100644")
        out.append(f"--- a/{p}")
        out.append(f"+++ b/{p}")
        out.append(f"@@ -1,{len(removed)} +1,{len(added)} @@")
        for l in removed:
            out.append(f"-{l}")
        for l in added:
            out.append(f"+{l}")
    return "\n".join(out) + "\n"


def _classify(diff_text: str, narrative: list) -> list[dict]:
    return _py_classify_all_rows(diff_text, narrative, Path("/nonexistent"))


# ---------------------------------------------------------------------------
# Invariant assertion helpers (reusable across future SR-N tests)
# ---------------------------------------------------------------------------

def assert_moved_lines_in_diff(results: list[dict], diff_text: str) -> None:
    """INV-1: every moved_line appears in `-` AND `+` of the diff."""
    removed, added = _parse_diff_sides(diff_text)
    for r in results:
        for line in r.get("moved_lines", []):
            assert line in removed, (
                f"INV-1: moved line not in any `-` of diff (row idx={r.get('idx')}): "
                f"{line!r}"
            )
            assert line in added, (
                f"INV-1: moved line not in any `+` of diff (row idx={r.get('idx')}): "
                f"{line!r}"
            )


def assert_lost_lines_absent_from_added(results: list[dict], diff_text: str) -> None:
    """INV-2: every truly_lost_line appears in `-` but NOT in any `+`.

    If a line classified as lost actually appears in some `+`, it should have
    been classified as `went-to`, not lost.
    """
    removed, added = _parse_diff_sides(diff_text)
    added_norms = {_norm_line(a) for a in added}
    for r in results:
        for line in r.get("truly_lost_lines", []):
            assert line in removed, (
                f"INV-2: lost line not in any `-` of diff (row idx={r.get('idx')}): "
                f"{line!r}"
            )
            assert _norm_line(line) not in added_norms, (
                f"INV-2: lost line ALSO appears in `+` — should be went-to, not lost "
                f"(row idx={r.get('idx')}): {line!r}"
            )


def assert_inferred_flag(results: list[dict], diff_text: str) -> None:
    """INV-3: when a row's section header is not present in the diff, inferred=True."""
    for r in results:
        section = (r.get("section") or "").strip()
        if not section:
            continue
        # Header tokens we look for — match _py_classify_all_rows' header detection
        hdr_tokens = (f"## {section}", f"### {section}", f"#### {section}",
                      f"# {section}")
        # The diff contains both the source `-## Section` (when removed) and possibly
        # a dest `+## Section` add. INV-3 asks: was the source header found in source `-` lines?
        # Approximation: if no header token is in the diff at all (either side), inferred should be True.
        header_in_diff = any(t in diff_text for t in hdr_tokens)
        if not header_in_diff:
            assert r.get("inferred") is True, (
                f"INV-3: section header '{section}' not in diff but inferred=False "
                f"(row idx={r.get('idx')})"
            )


def assert_outcomes_shape(results: list[dict]) -> None:
    """INV-4: every result has a non-empty outcomes list with valid shape.

    - outcomes is a list of dicts
    - each entry has keys: kind, dest, dest_stem, lines
    - kind ∈ {move, went-to, lost, anomaly, empty}
    - lost outcomes have dest=None AND dest_stem=None
    - non-lost outcomes have dest_stem != None (move/anomaly/empty/went-to)
    """
    for r in results:
        outcomes = r.get("outcomes")
        assert isinstance(outcomes, list) and len(outcomes) > 0, (
            f"INV-4: outcomes must be a non-empty list (row idx={r.get('idx')}): "
            f"{outcomes!r}"
        )
        for o in outcomes:
            assert isinstance(o, dict), f"INV-4: outcome must be dict: {o!r}"
            for key in ("kind", "dest", "dest_stem", "lines"):
                assert key in o, (
                    f"INV-4: outcome missing key {key!r} "
                    f"(row idx={r.get('idx')}): {o!r}"
                )
            assert o["kind"] in VALID_KINDS, (
                f"INV-4: invalid outcome kind {o['kind']!r} "
                f"(row idx={r.get('idx')})"
            )
            assert isinstance(o["lines"], list), (
                f"INV-4: outcome.lines must be a list "
                f"(row idx={r.get('idx')}): {o!r}"
            )
            if o["kind"] == "lost":
                assert o["dest"] is None, (
                    f"INV-4: lost outcome must have dest=None — lost lines "
                    f"have no destination (row idx={r.get('idx')}): {o!r}"
                )
                assert o["dest_stem"] is None, (
                    f"INV-4: lost outcome must have dest_stem=None "
                    f"(row idx={r.get('idx')}): {o!r}"
                )
            else:
                assert o["dest_stem"] is not None, (
                    f"INV-4: non-lost outcome must have dest_stem != None "
                    f"(row idx={r.get('idx')}): {o!r}"
                )


def assert_outcomes_legacy_parity(results: list[dict]) -> None:
    """INV-5: outcome line counts agree with legacy fields per row.

    Per result:
      sum(len(o.lines) for o.kind=='move')      == len(moved_lines)
      sum(len(o.lines) for o.kind=='went-to')   == sum(len(v) for v in went_to_details.values())
      sum(len(o.lines) for o.kind=='lost')      == len(truly_lost_lines)

    Outcomes truncate to 20 / 10 lines (display safety) — only assert parity
    when the legacy field is at or below the truncation cap.
    """
    for r in results:
        outcomes = r.get("outcomes") or []
        moved_legacy = len(r.get("moved_lines") or [])
        wt_legacy = sum(len(v) for v in (r.get("went_to_details") or {}).values())
        lost_legacy = len(r.get("truly_lost_lines") or [])

        moved_outcomes = sum(len(o["lines"]) for o in outcomes if o["kind"] == "move")
        wt_outcomes = sum(len(o["lines"]) for o in outcomes if o["kind"] == "went-to")
        lost_outcomes = sum(len(o["lines"]) for o in outcomes if o["kind"] == "lost")

        if moved_legacy <= 20:
            assert moved_outcomes == moved_legacy, (
                f"INV-5: move parity (row idx={r.get('idx')}): "
                f"outcomes={moved_outcomes}, legacy={moved_legacy}"
            )
        if wt_legacy <= 10:
            assert wt_outcomes == wt_legacy, (
                f"INV-5: went-to parity (row idx={r.get('idx')}): "
                f"outcomes={wt_outcomes}, legacy={wt_legacy}"
            )
        if lost_legacy <= 20:
            assert lost_outcomes == lost_legacy, (
                f"INV-5: lost parity (row idx={r.get('idx')}): "
                f"outcomes={lost_outcomes}, legacy={lost_legacy}"
            )


def assert_dedupe_non_duplication(results: list[dict]) -> None:
    """INV-6: across all results, no (dest_stem, normLine) collides between two
    distinct *move* outcomes when at least one row has inferred=True. Dedupe
    must have demoted the loser. (Real-header rows can still collide and emit
    V-C2 — that's intentional, no demotion.)
    """
    # (dest_stem, norm) -> list of (idx, inferred)
    owners: dict[tuple[str, str], list[tuple[int, bool]]] = {}
    for r in results:
        idx = r.get("idx")
        inferred = bool(r.get("inferred"))
        for o in (r.get("outcomes") or []):
            if o.get("kind") != "move":
                continue
            stem = o.get("dest_stem")
            if not stem:
                continue
            for line in o.get("lines", []):
                key = (stem, _norm_line(line))
                owners.setdefault(key, []).append((idx, inferred))

    for (stem, n), entries in owners.items():
        if len(entries) <= 1:
            continue
        any_inferred = any(inferred for _, inferred in entries)
        if any_inferred:
            distinct_idxs = sorted({idx for idx, _ in entries})
            raise AssertionError(
                f"INV-6: dedupe missed: rows {distinct_idxs} all claim "
                f"line at stem={stem!r}: {n!r} — at least one is inferred, "
                f"loser should have been demoted"
            )


def assert_no_phantom_losses(results: list[dict]) -> None:
    """INV-7: regression for #96. When a row has dedupe_demoted in issues,
    the line that was demoted must NOT appear in truly_lost_lines or
    line_statuses for that row. The demoted line was misattributed by
    inference; from the loser's perspective it was never theirs at all.

    We don't track per-line which one was demoted, so the rule is stronger:
    a row tagged dedupe_demoted whose claim was a single misattribution
    must have lost_count == 0 (no phantom losses introduced by dedupe).
    Also: line_statuses must not list a line claimed as 'lost' by a demoted row.
    """
    for r in results:
        if "dedupe_demoted" not in (r.get("issues") or []):
            continue
        # The dedupe pass removes the demoted line entirely — it shouldn't
        # appear in truly_lost. But the row may still have OTHER truly-lost
        # lines that were lost on their own merits (not from dedupe). The
        # invariant we can assert is about line_statuses: no entry in
        # line_statuses should claim 'lost' for a line not also in truly_lost_lines.
        truly_lost_norms = {_norm_line(l) for l in (r.get("truly_lost_lines") or [])}
        for norm, status in (r.get("line_statuses") or {}).items():
            if status == "lost":
                assert norm in truly_lost_norms, (
                    f"INV-7: line_statuses claims 'lost' for a line not in "
                    f"truly_lost_lines (row idx={r.get('idx')}, demoted): "
                    f"{norm!r} — phantom loss from dedupe"
                )


def assert_breadcrumb_idx_eq_idx(results: list[dict]) -> None:
    """INV-8: in the staged 1:1 shape, every result has breadcrumb_idx == idx.
    Breaks loudly if/when results start emitting multiple rows per breadcrumb
    (so we know to update JS lookups too).
    """
    for r in results:
        assert "breadcrumb_idx" in r, (
            f"INV-8: result missing breadcrumb_idx field (row idx={r.get('idx')})"
        )
        assert r["breadcrumb_idx"] == r["idx"], (
            f"INV-8: breadcrumb_idx != idx in 1:1 shape "
            f"(row idx={r.get('idx')}): breadcrumb_idx={r['breadcrumb_idx']}"
        )


def assert_vc_issues_include_dest_stem(issues: list[str]) -> None:
    """INV-9: V-C2/V-C3 issue strings always include 'at <stem>:' or 'to <stem>:'
    so the human reader can scope the collision to a specific destination.
    The format string was changed in #95 task 4 to include the stem.
    """
    for issue in issues:
        if issue.startswith("V-C2"):
            assert " at " in issue, (
                f"INV-9: V-C2 issue must include 'at <stem>': {issue!r}"
            )
        elif issue.startswith("V-C3"):
            assert " to " in issue, (
                f"INV-9: V-C3 issue must include 'to <stem>': {issue!r}"
            )


def assert_all_invariants(results: list[dict], diff_text: str) -> None:
    """Bundle: run every guardian helper. Future SR-N tests can call this to
    opt in to drift protection in one line."""
    assert_moved_lines_in_diff(results, diff_text)
    assert_lost_lines_absent_from_added(results, diff_text)
    assert_inferred_flag(results, diff_text)
    assert_outcomes_shape(results)
    assert_outcomes_legacy_parity(results)
    assert_dedupe_non_duplication(results)
    assert_no_phantom_losses(results)
    assert_breadcrumb_idx_eq_idx(results)
    issues = _py_cross_row_issues(results)
    assert_vc_issues_include_dest_stem(issues)


# ---------------------------------------------------------------------------
# Focused tests — one per invariant, using a crafted diff that exercises it
# ---------------------------------------------------------------------------

def test_inv1_moved_lines_must_appear_in_both_sides_of_diff():
    """INV-1: a moved line must be present as `-` in source AND `+` in dest."""
    task = "- [ ] write the design system docs"
    diff = _make_diff([
        {"path": "Calendar/20260413.md", "removed": [task], "added": []},
        {"path": "Plans/Bikar.md",       "removed": [],     "added": [task]},
    ])
    narrative = [{"source_file": "Calendar/20260413.md", "section": "Design",
                  "destination": "[[Plans/Bikar]]", "date": "2026-04-13",
                  "summary": ""}]
    results = _classify(diff, narrative)
    assert_moved_lines_in_diff(results, diff)


def test_inv2_lost_lines_must_not_appear_in_any_added_line():
    """INV-2: a lost line is in `-` but not in any `+`. If it's in `+` somewhere,
    it should have been classified as went-to, not lost.
    """
    lost = "- [ ] truly orphaned task that ends up nowhere"
    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["## Goals", lost], "added": []},
        {"path": "Plans/Bikar.md",
         "removed": [], "added": ["## Goals", "- [ ] something else"]},
    ])
    narrative = [{"source_file": "Calendar/20260413.md", "section": "Goals",
                  "destination": "[[Plans/Bikar]]", "date": "2026-04-13",
                  "summary": ""}]
    results = _classify(diff, narrative)
    assert_lost_lines_absent_from_added(results, diff)


def test_inv3_inferred_flag_when_section_header_absent_from_diff():
    """INV-3: when the source section header isn't in the diff, the row must be
    flagged inferred so consumers know the classification used fuzzy fallback.
    """
    task = "- [ ] orphaned task with no header context"
    # No `## Section` line in the diff at all — extraction must infer.
    diff = _make_diff([
        {"path": "Calendar/20260413.md", "removed": [task], "added": []},
        {"path": "Plans/Bikar.md",       "removed": [],     "added": [task]},
    ])
    narrative = [{"source_file": "Calendar/20260413.md",
                  "section": "Section That Does Not Exist",
                  "destination": "[[Plans/Bikar]]",
                  "date": "2026-04-13", "summary": ""}]
    results = _classify(diff, narrative)
    assert_inferred_flag(results, diff)


def test_inv4_outcomes_shape_valid_across_all_kinds():
    """INV-4: outcomes carry valid shape for every kind. Mix one move + one lost
    in a single test to cover the dest=None branch and the dest_stem!=None branch.
    """
    moved = "- [ ] task that gets moved properly here in this diff"
    lost  = "- [ ] task that has nowhere to go in this run"
    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["## Goals", moved, lost], "added": []},
        {"path": "Plans/Bikar.md",
         "removed": [], "added": ["## Goals", moved]},
    ])
    narrative = [{"source_file": "Calendar/20260413.md", "section": "Goals",
                  "destination": "[[Plans/Bikar]]", "date": "2026-04-13",
                  "summary": ""}]
    results = _classify(diff, narrative)
    assert_outcomes_shape(results)


def test_inv5_outcomes_legacy_parity_for_mixed_row():
    """INV-5: per-outcome line counts must agree with legacy field counts."""
    moved = "- [ ] move this task to dest correctly please"
    wt    = "- [ ] this task ends up in elsewhere instead of breadcrumb"
    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["## Mixed", moved, wt], "added": []},
        {"path": "Plans/Breadcrumb.md",
         "removed": [], "added": [moved]},
        {"path": "Plans/Elsewhere.md",
         "removed": [], "added": [wt]},
    ])
    narrative = [{"source_file": "Calendar/20260413.md", "section": "Mixed",
                  "destination": "[[Plans/Breadcrumb]]", "date": "2026-04-13",
                  "summary": ""}]
    results = _classify(diff, narrative)
    assert_outcomes_legacy_parity(results)


def test_inv6_dedupe_non_duplication_when_one_row_inferred():
    """INV-6: when two rows claim the same dest line and at least one is inferred,
    dedupe must demote the loser. No (dest_stem, normLine) collision should
    survive across move-outcomes.
    """
    task = "- [ ] shared inference target task here"
    # Both narrative rows have section names not in the diff — so both inferred.
    diff = _make_diff([
        {"path": "Calendar/20260413.md", "removed": [task], "added": []},
        {"path": "Plans/Design.md",      "removed": [],     "added": [task]},
    ])
    narrative = [
        {"source_file": "Calendar/20260413.md", "section": "Section A",
         "destination": "[[Plans/Design]]", "date": "2026-04-13", "summary": ""},
        {"source_file": "Calendar/20260413.md", "section": "Section B",
         "destination": "[[Plans/Design]]", "date": "2026-04-13", "summary": ""},
    ]
    results = _classify(diff, narrative)
    assert_dedupe_non_duplication(results)


def test_inv7_no_phantom_losses_after_dedupe_demotion():
    """INV-7: after dedupe (regression for #96), the demoted row's line_statuses
    must not contain a 'lost' status for a line not in truly_lost_lines.
    """
    task = "- [ ] inferred shared task that dedupe will demote"
    diff = _make_diff([
        {"path": "Calendar/20260413.md", "removed": [task], "added": []},
        {"path": "Plans/Design.md",      "removed": [],     "added": [task]},
    ])
    narrative = [
        {"source_file": "Calendar/20260413.md", "section": "Section A",
         "destination": "[[Plans/Design]]", "date": "2026-04-13", "summary": ""},
        {"source_file": "Calendar/20260413.md", "section": "Section B",
         "destination": "[[Plans/Design]]", "date": "2026-04-13", "summary": ""},
    ]
    results = _classify(diff, narrative)
    # Sanity: the demotion happened
    assert any("dedupe_demoted" in (r.get("issues") or []) for r in results), \
        "test setup failure: expected at least one row to be dedupe_demoted"
    assert_no_phantom_losses(results)


def test_inv8_breadcrumb_idx_equals_idx_in_one_to_one_shape():
    """INV-8: every result has breadcrumb_idx == idx in the staged 1:1 shape."""
    diff = _make_diff([
        {"path": "Calendar/20260413.md", "removed": ["- [ ] alpha"], "added": []},
        {"path": "Calendar/20260414.md", "removed": ["- [ ] beta"],  "added": []},
        {"path": "Plans/Bikar.md", "removed": [],
         "added": ["- [ ] alpha", "- [ ] beta"]},
    ])
    narrative = [
        {"source_file": "Calendar/20260413.md", "section": "Design",
         "destination": "[[Plans/Bikar]]", "date": "2026-04-13", "summary": ""},
        {"source_file": "Calendar/20260414.md", "section": "Design",
         "destination": "[[Plans/Bikar]]", "date": "2026-04-14", "summary": ""},
    ]
    results = _classify(diff, narrative)
    assert_breadcrumb_idx_eq_idx(results)


def test_inv9_vc_issues_carry_dest_stem_context():
    """INV-9: V-C2/V-C3 issue strings must include the dest stem so a human
    investigator can locate the collision quickly. Two real-header rows
    claiming the same line will fire V-C2.
    """
    task = "- [ ] shared real-header task here for V-C2"
    diff = _make_diff([
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
    results = _classify(diff, narrative)
    issues = _py_cross_row_issues(results)
    assert any(i.startswith("V-C2") for i in issues), \
        "test setup failure: expected V-C2 to fire on real-header collision"
    assert_vc_issues_include_dest_stem(issues)


# ---------------------------------------------------------------------------
# Bundled smoke test: run all 9 invariants against a multi-row mixed diff.
# This is the test that future SR-N additions should pattern-match — call
# `assert_all_invariants(results, diff)` once and you're protected.
# ---------------------------------------------------------------------------

def test_all_invariants_hold_on_realistic_mixed_scenario():
    """Bundle: a multi-row diff exercising move + went-to + lost + inferred.
    Passing this test means the entire mental model is intact end-to-end.
    """
    moved   = "- [ ] task that lands at the breadcrumb dest cleanly"
    wt      = "- [ ] task that ends up at a different file via went-to"
    lost    = "- [ ] task that has nowhere on this run"
    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["## Mixed", moved, wt, lost], "added": []},
        {"path": "Plans/Breadcrumb.md",
         "removed": [], "added": [moved]},
        {"path": "Plans/Elsewhere.md",
         "removed": [], "added": [wt]},
    ])
    narrative = [{"source_file": "Calendar/20260413.md", "section": "Mixed",
                  "destination": "[[Plans/Breadcrumb]]", "date": "2026-04-13",
                  "summary": ""}]
    results = _classify(diff, narrative)
    assert_all_invariants(results, diff)


# ---------------------------------------------------------------------------
# Negative tests: confirm helpers actually FAIL when the invariant is broken.
# Without these, a bug in a helper (e.g. always returning early) wouldn't
# surface — the helper would silently pass on every run.
# ---------------------------------------------------------------------------

def test_inv4_helper_catches_invalid_kind():
    """Negative: a synthetic row with kind='wat' must trip the shape helper."""
    bad = [{"idx": 0, "outcomes": [
        {"kind": "wat", "dest": "X", "dest_stem": "x", "lines": []}
    ]}]
    with pytest.raises(AssertionError, match="INV-4"):
        assert_outcomes_shape(bad)


def test_inv4_helper_catches_lost_with_dest():
    """Negative: a lost outcome with a non-None dest must trip the helper."""
    bad = [{"idx": 0, "outcomes": [
        {"kind": "lost", "dest": "Plans/X", "dest_stem": "x", "lines": []}
    ]}]
    with pytest.raises(AssertionError, match="INV-4"):
        assert_outcomes_shape(bad)


def test_inv8_helper_catches_breadcrumb_idx_mismatch():
    """Negative: breadcrumb_idx != idx must trip the helper."""
    bad = [{"idx": 0, "breadcrumb_idx": 5,
            "outcomes": [{"kind": "empty", "dest": "x", "dest_stem": "x",
                          "lines": []}]}]
    with pytest.raises(AssertionError, match="INV-8"):
        assert_breadcrumb_idx_eq_idx(bad)


def test_inv9_helper_catches_vc2_without_stem():
    """Negative: a V-C2 issue without 'at <stem>' context must trip the helper."""
    with pytest.raises(AssertionError, match="INV-9"):
        assert_vc_issues_include_dest_stem(["V-C2: dest line claimed by rows [0,1]: foo"])
