"""Tests for sweep_executor finalize path: validation, breadcrumbs, clear-source,
commit — exercised against a real temporary git repo."""

import subprocess
from pathlib import Path

import pytest

import noteplan_sweep.sweep_executor as ex
import noteplan_sweep.sweep_manifest as sm
import noteplan_sweep.sweep_session as ss


def _git(args, root):
    return subprocess.run(["git"] + args, cwd=str(root),
                          capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """A git repo with a Calendar note + a Plan note committed at base."""
    root = tmp_path
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@t"], root)
    _git(["config", "user.name", "t"], root)
    (root / "Calendar").mkdir()
    (root / "Notes").mkdir()
    (root / "sweeps").mkdir()
    (root / "Calendar" / "20260709.md").write_text(
        "# Work\n- [ ] alpha\n- [ ] beta\n- [ ] keepme\n- [x] done already\n",
        encoding="utf-8")
    (root / "Notes" / "Plan.md").write_text(
        "# Plan\n\n# Next Steps\n- [ ] existing\n", encoding="utf-8")
    _git(["add", "-A"], root)
    _git(["commit", "-q", "-m", "base"], root)
    base = _git(["rev-parse", "HEAD"], root).stdout.strip()
    return root, base


def _manifest(base, moves):
    return {
        "schema_version": sm.SCHEMA_VERSION,
        "run_id": "2026-07-09-01",
        "base_sha": base,
        "created_at": "2026-07-09T00:00:00Z",
        "mode": "work",
        "source_files": [{"file": "Calendar/20260709.md",
                          "cleanup": {"clear_source": True, "keep_completed": True}}],
        "moves": moves,
    }


def _move(mid, start, texts, section="# Next Steps", dst="Notes/Plan.md",
          content=None, breadcrumb=None):
    content = content or [sm.content_line(t, "verbatim", source_n=start + i)
                          for i, t in enumerate(texts)]
    return sm.build_move(mid, "Calendar/20260709.md", "# Work", start,
                         list(texts), dst, section, content,
                         breadcrumb=breadcrumb or {"section": "Work",
                                                   "summary": "moved",
                                                   "destination": "[[Plan]]"})


def test_finalize_happy_path_commits(repo):
    root, base = repo
    mv = _move("a", 2, ["- [ ] alpha", "- [ ] beta"])
    mf = _manifest(base, [mv])

    res = ex.apply_move(root, mv)
    assert res.ok

    # fold state: mark 'a' applied, and 'keepme' would be a separate kept move
    journal = [{"seq": 1, "type": "apply_done", "move_id": "a",
                "dst_file": "Notes/Plan.md", "inserted": res.inserted,
                "removed": res.removed, "anchor": res.anchor}]
    state = ss.fold_state(mf, journal)

    out = ex.finalize(root, mf, state, sweep_date="2026-07-09")
    assert out["ok"], out
    # committed
    log = _git(["log", "--oneline"], root).stdout
    assert "sweep(2026-07-09)" in log
    # destination got the lines; source cleared open tasks but kept [x] + breadcrumb
    plan = (root / "Notes/Plan.md").read_text()
    assert "- [ ] alpha" in plan and "- [ ] beta" in plan
    cal = (root / "Calendar/20260709.md").read_text()
    assert "- [x] done already" in cal          # completed kept
    assert "| Swept |" in cal                    # breadcrumb table added
    assert "- [ ] keepme" not in cal             # open task cleared (not kept/moved)


def test_finalize_keeps_user_kept_lines(repo):
    root, base = repo
    mv = _move("a", 2, ["- [ ] alpha"])
    keep_mv = _move("k", 4, ["- [ ] keepme"])
    mf = _manifest(base, [mv, keep_mv])
    ex.apply_move(root, mv)
    journal = [
        {"seq": 1, "type": "apply_done", "move_id": "a", "dst_file": "Notes/Plan.md"},
        {"seq": 2, "type": "decision", "move_id": "k", "action": "keep"},
    ]
    state = ss.fold_state(mf, journal)
    out = ex.finalize(root, mf, state, sweep_date="2026-07-09")
    assert out["ok"], out
    cal = (root / "Calendar/20260709.md").read_text()
    assert "- [ ] keepme" in cal   # kept in source survives clear-source


def test_validation_flags_invented_line(repo):
    root, base = repo
    mv = _move("a", 2, ["- [ ] alpha"])
    mf = _manifest(base, [mv])
    ex.apply_move(root, mv)
    # Sneak an unexplained line into the destination directly
    plan = root / "Notes/Plan.md"
    plan.write_text(plan.read_text() + "- [ ] INVENTED not in any move\n", encoding="utf-8")
    journal = [{"seq": 1, "type": "apply_done", "move_id": "a",
                "dst_file": "Notes/Plan.md"}]
    state = ss.fold_state(mf, journal)
    out = ex.finalize(root, mf, state, sweep_date="2026-07-09")
    assert not out["ok"]
    assert any("unexplained new line" in e for e in out["report"]["errors"])
    # not committed
    assert "sweep(" not in _git(["log", "--oneline"], root).stdout


def test_validation_flags_lost_line_when_no_clear_source(repo):
    root, base = repo
    mv = _move("a", 2, ["- [ ] alpha"])
    mf = _manifest(base, [mv])
    mf["source_files"][0]["cleanup"]["clear_source"] = False  # no clearing allowed
    ex.apply_move(root, mv)
    # Delete an unrelated source line by hand → lost content
    cal = root / "Calendar/20260709.md"
    cal.write_text(cal.read_text().replace("- [ ] keepme\n", ""), encoding="utf-8")
    journal = [{"seq": 1, "type": "apply_done", "move_id": "a",
                "dst_file": "Notes/Plan.md"}]
    state = ss.fold_state(mf, journal)
    out = ex.finalize(root, mf, state, sweep_date="2026-07-09")
    assert not out["ok"]
    assert any("content lost" in e for e in out["report"]["errors"])


def test_abort_restores_files(repo):
    root, base = repo
    mv = _move("a", 2, ["- [ ] alpha"])
    new_dst = _move("b", 3, ["- [ ] beta"], dst="Notes/Brand New.md",
                    section="# Next Steps")
    new_dst["destination"]["exists"] = False
    new_dst["destination"]["create"] = {"kind": "plan", "frontmatter": {"doctype": "plan"},
                                        "h1": "# 🏢 Brand New", "boilerplate_lines": []}
    mf = _manifest(base, [mv, new_dst])
    ex.apply_move(root, mv)
    ex.apply_move(root, new_dst)
    assert (root / "Notes/Brand New.md").exists()
    journal = [
        {"seq": 1, "type": "apply_done", "move_id": "a", "dst_file": "Notes/Plan.md"},
        {"seq": 2, "type": "apply_done", "move_id": "b", "dst_file": "Notes/Brand New.md"},
    ]
    state = ss.fold_state(mf, journal)
    out = ex.abort(root, mf, state)
    assert out["ok"]
    # tracked files restored to base content
    assert (root / "Calendar/20260709.md").read_text().count("- [ ] alpha") == 1
    assert "- [ ] alpha" not in (root / "Notes/Plan.md").read_text()
    # newly-created file removed
    assert not (root / "Notes/Brand New.md").exists()
