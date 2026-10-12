#!/usr/bin/env python3
"""Content-preservation linter for the raw layer (git-backed).

The wiki's content-preservation invariant is non-negotiable: reorganizing the raw
inbox (moving a file, adding a header/frontmatter, splitting a multi-topic dump)
may ADD lines, but must never lose, reword, trim, or "clean up" an original source
line. `check_evidence.py` verifies the wiki→raw direction (facts are grounded);
this verifies the raw→raw direction (no source line vanished during reorganization).

Because the raw layer is a git repo, the check is well-defined and has NO expected
false positives: every non-trivial content line present in the raw tree at a BASELINE
commit must still exist verbatim (as a stripped line) SOMEWHERE in the raw tree of the
working copy. Splitting a note redistributes its lines across new files — that passes,
because the union of all current raw files still contains every original line. A line
that was deleted or reworded does NOT appear anywhere current → it is flagged.

What is compared:
  baseline = the raw tree as of <ref> (default HEAD), read from git.
  current  = the raw tree in the working copy right now (tracked + untracked .md).
Only DISAPPEARANCES are reported. Additions (new headers, frontmatter, `>` blockquote
annotations, whole new files) are the whole point of reorganizing and are
never flagged. Out-of-scope baseline lines are skipped because the invariant explicitly
permits restructuring them: blank lines and pure markdown punctuation (fences `---`, bare
bullets `-`, rules `***`, `>`), ATX headings (`#` — "add a `# Heading`"), and the leading
frontmatter block. Every remaining body line carrying a word or number is conserved.

If reorganization intentionally moves content OUT of the raw layer (e.g. into an
archive or a domain folder), pass that destination with --also so its lines count as
preserved; otherwise the moved lines are reported (surfacing "confirm this was
intentional", which is the safe default).

Usage:
  check_preservation.py --raw "Notes/🗑️ Unorganized"
  check_preservation.py --raw "Notes/🗑️ Unorganized" --since HEAD~1 --also "Notes/@Archive"
  check_preservation.py --raw <dir> --json
  check_preservation.py --selftest

Exit code is 1 whenever any original line is missing (this is data loss, and the check
has no expected false positives), 0 when the raw layer is fully preserved. Pass
--report-only to always exit 0. Standard library + git only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _has_content(line: str) -> bool:
    """A line is load-bearing content if it carries any letter or digit. Blank lines
    and pure-punctuation structure (`---`, `-`, `***`, `>`, `|`) are reflowable, not
    content — skipping them keeps the check free of structural false positives."""
    return any(ch.isalnum() for ch in line)


def _strip_frontmatter(text: str) -> str:
    """Drop a leading YAML frontmatter block. The invariant treats frontmatter as
    addable/restructurable metadata, not source prose, so it is out of scope."""
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            nl = text.find("\n", end + 1)
            return text[nl + 1:] if nl != -1 else ""
    return text


def _content_lines(text: str) -> list[str]:
    """The conserved source lines of a note: its body, minus blanks, pure-punctuation
    structure, and ATX headings (`#`). Headings and frontmatter are restructurable per
    the invariant ("add a `# Heading` / frontmatter", split a dump) — only the jotted
    body lines must survive verbatim somewhere in the raw layer."""
    out: list[str] = []
    for ln in _strip_frontmatter(text).splitlines():
        s = ln.strip()
        if not _has_content(s) or s.startswith("#"):
            continue
        out.append(s)
    return out


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    ).stdout


def _repo_root(start: Path) -> Path:
    top = _git(start if start.is_dir() else start.parent, "rev-parse", "--show-toplevel")
    return Path(top.strip())


def _baseline_files(repo: Path, ref: str, rel_dir: str) -> dict[str, str]:
    """{repo-relative path: content} for every tracked .md under rel_dir at <ref>.

    Uses `-z` so paths come back raw and NUL-separated — git otherwise octal-escapes
    and double-quotes any path with non-ASCII bytes (core.quotePath), which this vault's
    emoji folders all trip, breaking both the `.md` filter and the later `git show`."""
    listing = _git(repo, "ls-tree", "-r", "-z", "--name-only", ref, "--", rel_dir)
    out: dict[str, str] = {}
    for path in listing.split("\0"):
        if path.endswith(".md"):
            out[path] = _git(repo, "show", f"{ref}:{path}")
    return out


def _current_content_set(dirs: list[Path]) -> set[str]:
    lines: set[str] = set()
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.md")):
            if p.is_file():
                lines.update(_content_lines(p.read_text(encoding="utf-8", errors="ignore")))
    return lines


def check(raw_dir: Path, since: str = "HEAD", also: list[Path] | None = None) -> dict:
    repo = _repo_root(raw_dir)
    raw_rel = str(raw_dir.resolve().relative_to(repo))
    baseline = _baseline_files(repo, since, raw_rel)
    current = _current_content_set([raw_dir, *(also or [])])

    # Per baseline file, the distinct content lines that no longer exist anywhere current.
    lost: list[tuple[str, list[str]]] = []
    for path, text in sorted(baseline.items()):
        missing = [ln for ln in dict.fromkeys(_content_lines(text)) if ln not in current]
        if missing:
            lost.append((path, missing))

    return {
        "since": since,
        "baseline_files": len(baseline),
        "baseline_content_lines": sum(len(dict.fromkeys(_content_lines(t))) for t in baseline.values()),
        "current_content_lines": len(current),
        "lost_lines": lost,  # [(baseline_path, [missing line, ...]), ...]
        "lost_line_count": sum(len(m) for _, m in lost),
    }


def _print_report(r: dict) -> None:
    print(f"baseline: {r['baseline_files']} raw files @ {r['since']} "
          f"({r['baseline_content_lines']} distinct content lines)")
    print(f"current raw layer: {r['current_content_lines']} distinct content lines")
    print()
    print(f"Lost / reworded original lines (must be 0): {r['lost_line_count']}")
    if not r["lost_lines"]:
        print("   ✓ every original content line still exists verbatim in the raw layer")
        return
    for path, missing in r["lost_lines"]:
        print(f"   ✗ {path} — {len(missing)} line(s) no longer found anywhere in raw:")
        for ln in missing:
            shown = ln if len(ln) <= 100 else ln[:97] + "..."
            print(f"       · {shown}")


def _selftest() -> int:
    import tempfile

    if not _have_git():
        print("check_preservation selftest: SKIPPED (git not available)")
        return 0

    with tempfile.TemporaryDirectory() as d:
        repo = Path(d)
        _git(repo, "init", "-q")
        _git(repo, "config", "user.email", "t@t")
        _git(repo, "config", "user.name", "t")
        raw = repo / "raw"
        raw.mkdir()
        (raw / "bundle.md").write_text(
            "# Bundle\n\n"
            "Call the plumber on 2026-03-01.\n"
            "Renew the passport before the trip.\n"
            "---\n"
            "Buy 3 bags of Yemeni beans from the souk.\n",
            encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "baseline")

        # Reorganize: SPLIT bundle into two topic files + add headers/frontmatter.
        # All three original content lines are preserved (redistributed).
        (raw / "bundle.md").unlink()
        (raw / "errands").mkdir()
        (raw / "errands" / "Home errands.md").write_text(
            "---\ntopic: errands\n---\n# Home errands\n"
            "> Filed from the inbox bundle.\n\n"
            "Call the plumber on 2026-03-01.\n"
            "Renew the passport before the trip.\n",
            encoding="utf-8")
        # A non-ASCII dir name (git quotes these) guards the -z path handling.
        (raw / "☕️ coffee").mkdir()
        (raw / "☕️ coffee" / "Bean sourcing.md").write_text(
            "# Bean sourcing\n\nBuy 3 bags of Yemeni beans from the souk.\n",
            encoding="utf-8")
        r = check(raw, since="HEAD")
        assert r["lost_line_count"] == 0, r["lost_lines"]

        # Now DROP a line (simulate a careless "clean up") — must be flagged.
        (raw / "☕️ coffee" / "Bean sourcing.md").write_text(
            "# Bean sourcing\n\n(removed the beans line)\n", encoding="utf-8")
        r = check(raw, since="HEAD")
        assert r["lost_line_count"] == 1, r["lost_lines"]
        assert any("Yemeni beans" in ln for _, miss in r["lost_lines"] for ln in miss), r["lost_lines"]

        # REWORD a line (forbidden) — the original wording is gone → flagged.
        (raw / "☕️ coffee" / "Bean sourcing.md").write_text(
            "# Bean sourcing\n\nBuy three bags of Yemeni beans from the souk.\n", encoding="utf-8")
        r = check(raw, since="HEAD")
        assert any("Buy 3 bags" in ln for _, miss in r["lost_lines"] for ln in miss), r["lost_lines"]

        # Restore the exact line but via --also (content moved OUT of raw into archive).
        (raw / "☕️ coffee" / "Bean sourcing.md").write_text("# Bean sourcing\n", encoding="utf-8")
        arch = repo / "archive"
        arch.mkdir()
        (arch / "old.md").write_text("Buy 3 bags of Yemeni beans from the souk.\n", encoding="utf-8")
        r_no_also = check(raw, since="HEAD")
        assert r_no_also["lost_line_count"] >= 1, r_no_also["lost_lines"]
        r_also = check(raw, since="HEAD", also=[arch])
        assert not any("Yemeni beans" in ln for _, miss in r_also["lost_lines"] for ln in miss), r_also["lost_lines"]

    print("check_preservation selftest: OK")
    return 0


def _have_git() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", help="raw sources directory (Notes/🗑️ Unorganized)")
    ap.add_argument("--since", default="HEAD",
                    help="baseline git ref to compare against (default HEAD)")
    ap.add_argument("--also", action="append", default=[],
                    help="extra directory whose lines also count as preserved "
                         "(for content intentionally moved out of raw; repeatable)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a report")
    ap.add_argument("--report-only", action="store_true",
                    help="always exit 0, even when lines are lost")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()
    if not args.raw:
        ap.error("--raw is required (or use --selftest)")

    try:
        r = check(Path(args.raw), since=args.since, also=[Path(a) for a in args.also])
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"git error: {e.stderr or e}\n")
        return 2
    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        _print_report(r)
    if r["lost_line_count"] and not args.report_only:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
