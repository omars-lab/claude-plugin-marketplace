"""Tests for sweep_manifest (schema/validation/fold) + sweep_session (journal/fold)."""

import copy

import pytest

import noteplan_sweep.sweep_manifest as sm
import noteplan_sweep.sweep_session as ss


def _move(mid="mv-1", src="Calendar/20260709.md", start=10,
          texts=("- [ ] task one", "- [ ] task two"),
          dst="Notes/Plan.md", section="# Next Steps"):
    content = [sm.content_line(t, "verbatim", source_n=start + i)
               for i, t in enumerate(texts)]
    return sm.build_move(mid, src, "# Work", start, list(texts),
                         dst, section, content, rationale="because")


def _manifest(moves, run_id="2026-07-09-01", mode="both"):
    return {
        "schema_version": sm.SCHEMA_VERSION,
        "run_id": run_id,
        "base_sha": "deadbeef",
        "created_at": "2026-07-09T00:00:00Z",
        "mode": mode,
        "source_files": [{"file": "Calendar/20260709.md",
                          "cleanup": {"clear_source": True, "keep_completed": True}}],
        "moves": moves,
    }


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def test_line_hash_is_raw_and_stable():
    assert sm.line_hash("- [ ] task one") == sm.line_hash("- [ ] task one")
    # trailing date tag changes the raw hash (guards deletion)
    assert sm.line_hash("- [ ] task") != sm.line_hash("- [ ] task >2026-07-14")
    assert len(sm.line_hash("x")) == 16


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_valid_manifest_passes():
    assert sm.validate_manifest(_manifest([_move()])) == []


def test_bad_schema_version_flagged():
    m = _manifest([_move()])
    m["schema_version"] = 99
    errs = sm.validate_manifest(m)
    assert any("schema_version" in e for e in errs)


def test_overlapping_ranges_rejected():
    a = _move("a", start=10, texts=("l10", "l11", "l12"))
    b = _move("b", start=12, texts=("l12", "l13"))  # overlaps at 12
    errs = sm.validate_manifest(_manifest([a, b]))
    assert any("overlapping" in e for e in errs)


def test_adjacent_ranges_ok():
    a = _move("a", start=10, texts=("l10", "l11"))
    b = _move("b", start=12, texts=("l12", "l13"))
    assert sm.validate_manifest(_manifest([a, b])) == []


def test_hash_mismatch_detected():
    m = _manifest([_move()])
    m["moves"][0]["source"]["lines"][0]["h"] = "0000000000000000"
    errs = sm.validate_manifest(m)
    assert any("hash mismatch" in e for e in errs)


def test_transformed_line_requires_original():
    mv = _move()
    mv["content"]["lines"][0] = sm.content_line(
        "- [ ] task one >2026-07-14", "transformed", source_n=10)  # no original
    errs = sm.validate_manifest(_manifest([mv]))
    assert any("missing 'original'" in e for e in errs)


def test_new_file_requires_create_block():
    mv = _move()
    mv["destination"]["exists"] = False
    mv["destination"]["create"] = None
    errs = sm.validate_manifest(_manifest([mv]))
    assert any("create block" in e for e in errs)


def test_duplicate_move_ids_rejected():
    errs = sm.validate_manifest(_manifest([_move("dup"), _move("dup")]))
    assert any("duplicate move id" in e for e in errs)


def test_line_count_mismatch_flagged():
    mv = _move()
    mv["source"]["line_end"] = 99  # doesn't match 2 lines
    errs = sm.validate_manifest(_manifest([mv]))
    assert any("line range spans" in e for e in errs)


# ---------------------------------------------------------------------------
# Effective move folding
# ---------------------------------------------------------------------------

def test_reroute_amendment_changes_destination():
    mv = _move()
    eff = sm.effective_move(mv, [{"action": "reroute",
                                  "dest": {"file": "Notes/Other.md",
                                           "section_header": "# Inbox"}}])
    assert eff["destination"]["file"] == "Notes/Other.md"
    assert eff["destination"]["section_header"] == "# Inbox"
    # original untouched
    assert mv["destination"]["file"] == "Notes/Plan.md"


def test_edit_amendment_replaces_content():
    mv = _move()
    new = [sm.content_line("- [ ] edited", "transformed",
                           source_n=10, original="- [ ] task one")]
    eff = sm.effective_move(mv, [{"action": "edit", "content_lines": new}])
    assert sm.content_texts(eff) == ["- [ ] edited"]


def test_refresh_amendment_rebases_source():
    mv = _move()
    new_lines = sm.build_source_lines(20, ["- [ ] task one", "- [ ] task two"])
    eff = sm.effective_move(mv, [{"action": "refresh", "lines": new_lines}])
    assert eff["source"]["line_start"] == 20
    assert eff["source"]["line_end"] == 21


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------

def test_split_partitions_lines_and_content():
    mv = _move(texts=("l10", "l11", "l12"), start=10)
    parts = [
        {"line_idxs": [0, 1]},                                   # keep original dest
        {"line_idxs": [2], "dest": {"file": "Notes/Home.md",
                                    "section_header": "# Errands"}},
    ]
    children = sm.split_move(mv, parts)
    assert len(children) == 2
    assert sm.source_texts(children[0]) == ["l10", "l11"]
    assert children[0]["destination"]["file"] == "Notes/Plan.md"
    assert sm.source_texts(children[1]) == ["l12"]
    assert children[1]["destination"]["file"] == "Notes/Home.md"
    # content lines follow their source_n
    assert sm.content_texts(children[0]) == ["l10", "l11"]
    assert sm.content_texts(children[1]) == ["l12"]


def test_split_keep_in_source_drops_lines():
    mv = _move(texts=("l10", "l11", "l12"), start=10)
    children = sm.split_move(mv, [
        {"line_idxs": [0, 2]},
        {"line_idxs": [1], "keep_in_source": True},
    ])
    assert len(children) == 1
    assert sm.source_texts(children[0]) == ["l10", "l12"]


def test_split_rejects_overlapping_parts():
    mv = _move(texts=("l10", "l11"), start=10)
    with pytest.raises(sm.ManifestError):
        sm.split_move(mv, [{"line_idxs": [0]}, {"line_idxs": [0, 1]}])


# ---------------------------------------------------------------------------
# Session journal + fold
# ---------------------------------------------------------------------------

def test_journal_append_assigns_seq(tmp_path):
    root = tmp_path
    (root / "sweeps").mkdir()
    run = "2026-07-09-01"
    e1 = ss.append_event(root, run, {"type": "session_created", "run_id": run})
    e2 = ss.append_event(root, run, {"type": "decision", "move_id": "mv-1",
                                     "action": "skip"})
    assert e1["seq"] == 1 and e2["seq"] == 2
    assert ss.current_seq(root, run) == 2


def test_fold_status_transitions():
    mf = _manifest([_move("a"), _move("b", start=20), _move("c", start=30)])
    journal = [
        {"seq": 1, "type": "session_created"},
        {"seq": 2, "type": "decision", "move_id": "a", "action": "skip"},
        {"seq": 3, "type": "apply_started", "move_id": "b"},
        {"seq": 4, "type": "apply_done", "move_id": "b",
         "dst_file": "Notes/Plan.md", "inserted": ["x"], "removed": ["y"], "anchor": 19},
    ]
    st = ss.fold_state(mf, journal)
    by_id = {m["id"]: m for m in st["moves"]}
    assert by_id["a"]["status"] == ss.STATUS_SKIPPED
    assert by_id["b"]["status"] == ss.STATUS_APPLIED
    assert by_id["b"]["applied_detail"]["anchor"] == 19
    assert by_id["c"]["status"] == ss.STATUS_PENDING
    assert st["counts"]["total"] == 3
    assert st["counts"]["resolved"] == 2  # skipped + applied
    assert st["can_finalize"] is False    # c still pending


def test_fold_apply_failed_marks_stale():
    mf = _manifest([_move("a")])
    journal = [{"seq": 1, "type": "apply_failed", "move_id": "a",
                "reason": "content_drift", "detail": {}}]
    st = ss.fold_state(mf, journal)
    assert st["moves"][0]["status"] == ss.STATUS_STALE


def test_fold_reroute_sets_flag_and_effective_dest():
    mf = _manifest([_move("a")])
    journal = [{"seq": 1, "type": "decision", "move_id": "a", "action": "reroute",
                "payload": {"dest": {"file": "Notes/Other.md",
                                     "section_header": "# Inbox"}}}]
    st = ss.fold_state(mf, journal)
    m = st["moves"][0]
    assert m["rerouted"] is True
    assert m["destination"]["file"] == "Notes/Other.md"


def test_fold_split_supersedes_parent_adds_children():
    mv = _move("a", texts=("l10", "l11", "l12"), start=10)
    mf = _manifest([mv])
    children = sm.split_move(mv, [
        {"line_idxs": [0, 1]},
        {"line_idxs": [2], "dest": {"file": "Notes/Home.md",
                                    "section_header": "# Errands"}},
    ])
    journal = [{"seq": 1, "type": "split", "parent_id": "a", "children": children}]
    st = ss.fold_state(mf, journal)
    by_id = {m["id"]: m for m in st["moves"]}
    assert by_id["a"]["status"] == ss.STATUS_SUPERSEDED
    assert st["counts"]["total"] == 2  # superseded excluded
    assert len([m for m in st["moves"] if m["status"] == ss.STATUS_PENDING]) == 2


def test_fold_finalized_state():
    mf = _manifest([_move("a")])
    journal = [
        {"seq": 1, "type": "decision", "move_id": "a", "action": "skip"},
        {"seq": 2, "type": "finalize_started"},
        {"seq": 3, "type": "finalize_done", "commit_sha": "abc1234"},
    ]
    st = ss.fold_state(mf, journal)
    assert st["state"] == "finalized"
    assert st["commit_sha"] == "abc1234"


def test_fold_finalize_failed_stays_open():
    mf = _manifest([_move("a")])
    journal = [
        {"seq": 1, "type": "decision", "move_id": "a", "action": "skip"},
        {"seq": 2, "type": "finalize_started"},
        {"seq": 3, "type": "finalize_failed", "report": {"errors": ["boom"]}},
    ]
    st = ss.fold_state(mf, journal)
    assert st["state"] == "open"
    assert st["finalize_error"]["errors"] == ["boom"]


def test_can_finalize_when_all_resolved():
    mf = _manifest([_move("a"), _move("b", start=20)])
    journal = [
        {"seq": 1, "type": "decision", "move_id": "a", "action": "skip"},
        {"seq": 2, "type": "apply_done", "move_id": "b", "dst_file": "x"},
    ]
    st = ss.fold_state(mf, journal)
    assert st["can_finalize"] is True
