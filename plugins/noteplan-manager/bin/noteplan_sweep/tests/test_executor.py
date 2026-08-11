"""Tests for sweep_executor: find_anchor relocation matrix + apply_move E2E."""

from pathlib import Path

import noteplan_sweep.sweep_executor as ex
import noteplan_sweep.sweep_manifest as sm


# ---------------------------------------------------------------------------
# find_anchor matrix
# ---------------------------------------------------------------------------

def _lines(*ls):
    return list(ls)


def test_anchor_fast_path():
    cur = _lines("a", "b", "c", "d", "")
    r = ex.find_anchor(cur, ["b", "c"], 1)
    assert isinstance(r, ex.Anchor) and r.pos == 1 and r.kind == "exact"


def test_anchor_relocated_after_earlier_deletion():
    # expected at 3 but an earlier move removed 2 lines → now at 1
    cur = _lines("x", "target1", "target2", "y", "")
    r = ex.find_anchor(cur, ["target1", "target2"], 3)
    assert isinstance(r, ex.Anchor) and r.pos == 1 and r.kind == "relocated"


def test_anchor_cosmetic_drift_refreshable():
    cur = _lines("intro", "- [ ] task >2026-07-20", "outro", "")
    # manifest had it without the date tag
    r = ex.find_anchor(cur, ["- [ ] task"], 1)
    assert isinstance(r, ex.Stale) and r.reason == "cosmetic_drift"
    assert r.refreshable and r.pos == 1
    assert r.current_texts == ["- [ ] task >2026-07-20"]


def test_anchor_content_drift():
    cur = _lines("totally", "different", "content", "")
    r = ex.find_anchor(cur, ["- [ ] gone"], 0)
    assert isinstance(r, ex.Stale) and r.reason == "content_drift"


def test_anchor_ambiguous_duplicates():
    cur = _lines("dup", "x", "dup", "")  # two identical single-line runs
    r = ex.find_anchor(cur, ["dup"], 5)  # expected far away → no clear nearest? equidistant-ish
    # pos 0 dist 5, pos 2 dist 3 → 2 is strictly nearer, so it resolves
    assert isinstance(r, ex.Anchor) and r.pos == 2


def test_anchor_ambiguous_equidistant():
    cur = _lines("dup", "x", "dup", "")
    r = ex.find_anchor(cur, ["dup"], 1)  # dist 1 to both → ambiguous
    assert isinstance(r, ex.Stale) and r.reason == "ambiguous"


# ---------------------------------------------------------------------------
# apply_move E2E
# ---------------------------------------------------------------------------

def _move(src_file, start, texts, dst_file, section, *, content=None,
          create=None, dst_exists=True):
    content = content or [sm.content_line(t, "verbatim", source_n=start + i)
                          for i, t in enumerate(texts)]
    return sm.build_move("mv-1", src_file, "# Work", start, list(texts),
                         dst_file, section, content,
                         dst_exists=dst_exists, create=create)


def test_apply_moves_and_removes(tmp_path):
    src = tmp_path / "Calendar" / "20260709.md"
    dst = tmp_path / "Notes" / "Plan.md"
    src.parent.mkdir(parents=True)
    dst.parent.mkdir(parents=True)
    src.write_text("# Work\n- [ ] alpha\n- [ ] beta\n- [ ] gamma\n", encoding="utf-8")
    dst.write_text("# Plan\n\n# Next Steps\n- [ ] existing\n", encoding="utf-8")

    mv = _move("Calendar/20260709.md", 2, ["- [ ] alpha", "- [ ] beta"],
               "Notes/Plan.md", "# Next Steps")
    res = ex.apply_move(tmp_path, mv)
    assert res.ok and res.anchor == 1
    src_after = src.read_text()
    dst_after = dst.read_text()
    assert "alpha" not in src_after and "beta" not in src_after
    assert "gamma" in src_after
    assert "- [ ] alpha" in dst_after and "- [ ] beta" in dst_after


def test_apply_relocates_after_shift(tmp_path):
    src = tmp_path / "Calendar" / "20260709.md"
    dst = tmp_path / "Notes" / "Plan.md"
    src.parent.mkdir(parents=True)
    dst.parent.mkdir(parents=True)
    # manifest recorded beta at lines 4-4, but alpha/x already removed → beta moved up
    src.write_text("# Work\n- [ ] beta\n", encoding="utf-8")
    dst.write_text("# Plan\n\n# Next Steps\n", encoding="utf-8")
    mv = _move("Calendar/20260709.md", 4, ["- [ ] beta"], "Notes/Plan.md", "# Next Steps")
    res = ex.apply_move(tmp_path, mv)
    assert res.ok and res.anchor == 1
    assert "beta" not in src.read_text()
    assert "- [ ] beta" in dst.read_text()


def test_apply_stale_does_not_write(tmp_path):
    src = tmp_path / "Calendar" / "20260709.md"
    dst = tmp_path / "Notes" / "Plan.md"
    src.parent.mkdir(parents=True)
    dst.parent.mkdir(parents=True)
    src.write_text("# Work\n- [ ] wholly different\n", encoding="utf-8")
    dst.write_text("# Plan\n\n# Next Steps\n", encoding="utf-8")
    before_src, before_dst = src.read_text(), dst.read_text()
    mv = _move("Calendar/20260709.md", 2, ["- [ ] gone"], "Notes/Plan.md", "# Next Steps")
    res = ex.apply_move(tmp_path, mv)
    assert not res.ok and res.stale["reason"] == "content_drift"
    assert src.read_text() == before_src and dst.read_text() == before_dst


def test_apply_creates_new_file(tmp_path):
    src = tmp_path / "Calendar" / "20260709.md"
    src.parent.mkdir(parents=True)
    src.write_text("# Work\n- [ ] seed task\n", encoding="utf-8")
    create = {"kind": "plan",
              "frontmatter": {"doctype": "plan", "status": "🔵"},
              "h1": "# 🏢 New Plan",
              "boilerplate_lines": ["", "# Next Steps"]}
    mv = _move("Calendar/20260709.md", 2, ["- [ ] seed task"],
               "Notes/Plans/🏢 New Plan.md", "# Next Steps",
               create=create, dst_exists=False)
    res = ex.apply_move(tmp_path, mv)
    assert res.ok and res.created_file
    new = (tmp_path / "Notes/Plans/🏢 New Plan.md").read_text()
    assert new.startswith("---\ndoctype: plan\nstatus: 🔵\n---\n# 🏢 New Plan")
    assert "- [ ] seed task" in new


def test_apply_idempotent_on_disk(tmp_path):
    src = tmp_path / "Calendar" / "20260709.md"
    dst = tmp_path / "Notes" / "Plan.md"
    src.parent.mkdir(parents=True)
    dst.parent.mkdir(parents=True)
    src.write_text("# Work\n- [ ] alpha\n", encoding="utf-8")
    dst.write_text("# Plan\n\n# Next Steps\n", encoding="utf-8")
    mv = _move("Calendar/20260709.md", 2, ["- [ ] alpha"], "Notes/Plan.md", "# Next Steps")
    r1 = ex.apply_move(tmp_path, mv)
    assert r1.ok and not r1.already_applied
    # second apply: source no longer has it, dst has it → detected as applied
    r2 = ex.apply_move(tmp_path, mv)
    assert r2.ok and r2.already_applied
    # dst not double-inserted
    assert dst.read_text().count("- [ ] alpha") == 1


def test_refresh_rebases_cosmetic_drift(tmp_path):
    src = tmp_path / "Calendar" / "20260709.md"
    src.parent.mkdir(parents=True)
    src.write_text("# Work\n- [ ] task >2026-07-20\n", encoding="utf-8")
    mv = _move("Calendar/20260709.md", 2, ["- [ ] task"], "Notes/Plan.md", "# Next Steps")
    new_lines = ex.refresh_move_lines(tmp_path, mv)
    assert new_lines is not None
    assert new_lines[0]["text"] == "- [ ] task >2026-07-20"
    assert new_lines[0]["h"] == sm.line_hash("- [ ] task >2026-07-20")


def test_dest_existence_issues(tmp_path):
    (tmp_path / "Notes").mkdir()
    (tmp_path / "Notes" / "Exists.md").write_text("# x\n", encoding="utf-8")
    manifest = {"moves": [
        # claims new but exists → error
        {"id": "a", "destination": {"file": "Notes/Exists.md", "exists": False,
                                    "create": {"kind": "list", "h1": "# x"}}},
        # claims existing but missing → warning
        {"id": "b", "destination": {"file": "Notes/Missing.md", "exists": True}},
        # correct new file → nothing
        {"id": "c", "destination": {"file": "Notes/Fresh.md", "exists": False,
                                    "create": {"kind": "list", "h1": "# f"}}},
    ]}
    errors, warnings = ex.dest_existence_issues(tmp_path, manifest)
    assert any("already exists on disk" in e and e.startswith("a") for e in errors)
    assert any("not found" in w and w.startswith("b") for w in warnings)
    assert not any(x.startswith("c") for x in errors + warnings)


def test_atomic_write_roundtrip(tmp_path):
    p = tmp_path / "sub" / "f.md"
    ex.atomic_write(p, "hello\n")
    assert p.read_text() == "hello\n"
    ex.atomic_write(p, "world\n")
    assert p.read_text() == "world\n"
