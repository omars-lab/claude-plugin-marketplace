#!/usr/bin/env python3
"""Scope guard for a newcomer-review run: its diffs must be verdicts + reviewed pages only.

The rule the user set: *"when verdicts run, we should be on latest, and only tolerate diffs on
verdicts and accompanying wiki files (fixes, nothing else)."*

The naive reading — "refuse unless the working tree is clean" — is unusable in a NotePlan vault:
the app rewrites daily notes, table separators and image alt-text on its own schedule, so the
tree is almost never clean and the guard would block every run. That churn is not the review
run's doing and blocking on it protects nothing.

So the guard is **differential**. `--snapshot` records the paths already dirty *before* the
review starts; `--verify` re-reads the tree afterwards and fails only on paths that became dirty
*during* the run and are not a verdict or a reviewed article. Pre-existing churn is carried
through untouched; a stray edit the run made outside its scope is caught.

Usage:
  review_scope.py --snapshot <state.json>
  review_scope.py --verify <state.json> --page "<article path>" [--page ...]
  review_scope.py --selftest
Exit 0 = in scope, 1 = out of scope, 2 = usage/environment error. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

WIKI_REL = "Notes/📚 Wiki"
VERDICTS_REL = f"{WIKI_REL}/@References/@Verdicts/"


def dirty_paths(cwd: Path | None = None) -> set[str]:
    """Every path git reports as modified, staged, or untracked, repo-relative."""
    out = subprocess.run(
        ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
        cwd=cwd, capture_output=True, text=True, check=True).stdout
    paths: set[str] = set()
    fields = [f for f in out.split("\0") if f]
    i = 0
    while i < len(fields):
        entry = fields[i]
        status, _, path = entry[:2], entry[2:3], entry[3:]
        if status.startswith("R") or status.startswith("C"):
            i += 1  # a rename/copy is followed by its source path; both count
            if i < len(fields):
                paths.add(fields[i])
        paths.add(path)
        i += 1
    return paths


def in_scope(path: str, pages: list[str]) -> bool:
    """A verdict file, or one of the articles this run reviewed."""
    return path.startswith(VERDICTS_REL) or path in pages


def verify(state_file: Path, pages: list[str], cwd: Path | None = None) -> tuple[bool, list[str]]:
    before = set(json.loads(state_file.read_text(encoding="utf-8"))["dirty"])
    new = dirty_paths(cwd) - before
    out_of_scope = sorted(p for p in new if not in_scope(p, pages))
    return (not out_of_scope, out_of_scope)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot", metavar="STATE", help="record the pre-run dirty paths")
    ap.add_argument("--verify", metavar="STATE", help="check the post-run diff against STATE")
    ap.add_argument("--page", action="append", default=[],
                    help="a wiki article this run reviewed (repeatable); its own edits are in scope")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()
    if bool(args.snapshot) == bool(args.verify):
        ap.error("pass exactly one of --snapshot / --verify")

    try:
        if args.snapshot:
            state = Path(args.snapshot)
            state.parent.mkdir(parents=True, exist_ok=True)
            paths = sorted(dirty_paths())
            state.write_text(json.dumps({"dirty": paths}, indent=2, ensure_ascii=False),
                             encoding="utf-8")
            print(f"snapshot: {len(paths)} path(s) already dirty before the review "
                  f"— these are carried through untouched")
            return 0

        ok, bad = verify(Path(args.verify), args.page)
    except subprocess.CalledProcessError as e:
        print(f"git failed: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"{e}", file=sys.stderr)
        return 2

    if ok:
        print("scope: OK — this run touched only verdicts and the pages it reviewed")
        return 0
    print("scope: OUT OF SCOPE — this run changed paths that are neither a verdict nor a "
          "reviewed page. Revert them (by name) before committing:")
    for p in bad:
        print(f"   ✗ {p}")
    return 1


def _selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        repo = Path(d) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)

        art = repo / WIKI_REL / "📦 Past Work" / "Exp" / "q.md"
        churn = repo / "Calendar" / "20260916.md"
        for f in (art, churn):
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)

        # NotePlan churns a daily note BEFORE the review starts — must never block the run
        churn.write_text("app churn\n", encoding="utf-8")
        state = Path(d) / "state.json"  # kept OUTSIDE the repo, as the scratchpad is in real use
        state.write_text(json.dumps({"dirty": sorted(dirty_paths(repo))}), encoding="utf-8")
        assert "Calendar/20260916.md" in json.loads(state.read_text())["dirty"]

        pages = [f"{WIKI_REL}/📦 Past Work/Exp/q.md"]

        # the run edits the reviewed page and writes its verdict -> in scope
        art.write_text("fixed\n", encoding="utf-8")
        v = repo / VERDICTS_REL / "📦 Past Work" / "Exp" / "q.md"
        v.parent.mkdir(parents=True, exist_ok=True)
        v.write_text("---\npage_hash: abc\n---\n", encoding="utf-8")
        ok, bad = verify(state, pages, repo)
        assert ok, bad

        # the same daily note churning AGAIN mid-run is still the app, not the review
        churn.write_text("more app churn\n", encoding="utf-8")
        ok, bad = verify(state, pages, repo)
        assert ok, bad

        # but an edit to an unrelated note IS the run's doing -> out of scope
        stray = repo / "Notes" / "🏡 Personal" / "diary.md"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text("oops\n", encoding="utf-8")
        ok, bad = verify(state, pages, repo)
        assert not ok and bad == ["Notes/🏡 Personal/diary.md"], bad

        # a wiki page that was NOT reviewed is also out of scope
        stray.unlink()
        other = repo / WIKI_REL / "📦 Past Work" / "Exp" / "other.md"
        other.write_text("untouched?\n", encoding="utf-8")
        ok, bad = verify(state, pages, repo)
        assert not ok and bad == [f"{WIKI_REL}/📦 Past Work/Exp/other.md"], bad

        print("review_scope selftest: OK "
              "(pre-existing churn tolerated, in-run strays caught, verdicts + reviewed pages allowed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
