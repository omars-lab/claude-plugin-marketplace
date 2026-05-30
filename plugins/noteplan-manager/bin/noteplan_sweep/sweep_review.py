"""
sweep_review.py — Sweep commit + HTML review commands.

Commands:
  sweep-commit             Stage modified .md files and create a structured sweep commit
  sweep-review-generate    Generate immutable snapshot HTML from sweep commit diff
  sweep-review-compile     Merge snapshot + comment rounds → review.html
  sweep-review-squash      Squash all rN comment files for a run into r1
  sweep-review-list        List all runs grouped by date
  sweep-review-open        Open compiled review (or snapshot) in browser
"""

import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import noteplan_sweep.utils as utils


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _git(args: list, cwd: Path, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, timeout=timeout,
        cwd=str(cwd)
    )


def _np_root() -> Path:
    return utils.noteplan_root()


def _sweeps_dir(root: Path) -> Path:
    d = root / "sweeps"
    d.mkdir(exist_ok=True)
    return d


def _run_counter(sweeps: Path, date_str: str) -> int:
    """Return next available run counter NN for the given date."""
    existing = sorted(sweeps.glob(f"{date_str}-*.snapshot.html"))
    if not existing:
        return 1
    last = existing[-1].stem  # e.g. "2026-04-20-03.snapshot"
    m = re.search(r'-(\d+)\.snapshot$', last)
    return int(m.group(1)) + 1 if m else 1


def _latest_run(sweeps: Path, date_str: str | None = None) -> tuple[str | None, int | None]:
    """Return (date_str, run_N) of the most recent snapshot, or (None, None)."""
    pattern = f"{date_str}-*.snapshot.html" if date_str else "*.snapshot.html"
    snapshots = sorted(sweeps.glob(pattern))
    if not snapshots:
        return None, None
    stem = snapshots[-1].stem  # e.g. "2026-04-20-02.snapshot"
    m = re.match(r'(\d{4}-\d{2}-\d{2})-(\d+)\.snapshot', stem)
    if not m:
        return None, None
    return m.group(1), int(m.group(2))


# ---------------------------------------------------------------------------
# sweep-start  (called at Phase 2 before any sweep commits)
# ---------------------------------------------------------------------------

def cmd_sweep_start(args):
    """Record the current HEAD as the sweep base and assign a sweep ID.

    Writes two files to sweeps/:
      .sweep-base   — current HEAD SHA (used as diff base by sweep-review-generate)
      .sweep-id     — human-readable ID like "2026-04-21-01"
    """
    root = _np_root()
    sweeps = _sweeps_dir(root)

    date_str = args.date or date.today().strftime("%Y-%m-%d")
    run_n = _run_counter(sweeps, date_str)
    sweep_id = f"{date_str}-{run_n:02d}"

    head_r = _git(["rev-parse", "HEAD"], cwd=root)
    if head_r.returncode != 0:
        utils.err("Could not determine HEAD SHA.")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)
    base_sha = head_r.stdout.strip()

    base_file = sweeps / ".sweep-base"
    id_file   = sweeps / ".sweep-id"
    base_file.write_text(base_sha + "\n", encoding="utf-8")
    id_file.write_text(sweep_id + "\n", encoding="utf-8")

    utils.log(f"sweep-start: sweep ID = {sweep_id} | base = {base_sha[:7]}")


# ---------------------------------------------------------------------------
# sweep-commit
# ---------------------------------------------------------------------------

def cmd_sweep_commit(args):
    root = _np_root()
    # Use -z for NUL-terminated output: paths are unquoted (no octal escaping)
    r = subprocess.run(
        ["git", "status", "--porcelain", "-z"],
        capture_output=True, timeout=30, cwd=str(root)
    )
    if r.returncode != 0:
        utils.err(f"git status failed: {r.stderr.decode(errors='replace').strip()}")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    modified_md = []
    untracked_md = []
    # -z output: each entry is "XY PATH\0" (renames: "XY FROM\0TO\0")
    entries = r.stdout.decode("utf-8", errors="replace").split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        xy = entry[:2]
        path_str = entry[3:]
        # Renames have a second NUL-terminated path (TO) already consumed above
        if xy[0] in ("R", "C"):
            i += 1  # skip the "from" path
        if not path_str.endswith(".md"):
            continue
        if xy == "??":
            untracked_md.append(path_str)
        else:
            modified_md.append(path_str)

    all_md = modified_md + untracked_md

    if not all_md:
        utils.log("Nothing to commit — working tree is clean.")
        return

    today = date.today().strftime("%Y-%m-%d")

    # Compute stats
    calendar_files = [p for p in all_md if p.startswith("Calendar/")]
    plan_files = [p for p in all_md if "Plans/" in p or "Lists/" in p]
    other_files = [p for p in all_md if p not in calendar_files and p not in plan_files]

    # Count task lines moved (rough heuristic: [x] lines in calendar files)
    task_count = 0
    for rel in calendar_files:
        abs_path = root / rel
        try:
            content = abs_path.read_text(encoding="utf-8")
            task_count += content.count("- [x]")
        except Exception:
            pass

    n_files = len(all_md)
    stats_line = f"{n_files} file{'s' if n_files != 1 else ''} changed"
    if task_count:
        stats_line += f", {task_count} task{'s' if task_count != 1 else ''} completed"

    subject = f"sweep({today}): {stats_line}"

    body_lines = []
    if calendar_files:
        body_lines.append("Sources swept:")
        for p in sorted(calendar_files):
            body_lines.append(f"  {p}")
    if plan_files:
        body_lines.append("Plans/lists touched:")
        for p in sorted(plan_files):
            body_lines.append(f"  {p}")
    if other_files:
        body_lines.append("Other files:")
        for p in sorted(other_files):
            body_lines.append(f"  {p}")

    commit_msg = subject + "\n\n" + "\n".join(body_lines)

    if args.dry_run:
        utils.log(f"[dry-run] Would stage {n_files} .md files and commit:")
        utils.log(f"  {subject}")
        for line in body_lines:
            utils.log(f"  {line}")
        return

    # Stage via --pathspec-from-file with NUL separators to handle emoji/space paths
    nul_paths = "\0".join(all_md).encode("utf-8")
    stage_result = subprocess.run(
        ["git", "add", "--pathspec-from-file=-", "--pathspec-file-nul"],
        input=nul_paths, capture_output=True, timeout=30, cwd=str(root)
    )
    if stage_result.returncode != 0:
        utils.err(f"git add failed: {stage_result.stderr.decode(errors='replace').strip()}")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    commit_result = _git(["commit", "-m", commit_msg], cwd=root)
    if commit_result.returncode != 0:
        utils.err(f"git commit failed: {commit_result.stderr.strip()}")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    # Extract commit SHA
    sha_r = _git(["rev-parse", "--short", "HEAD"], cwd=root)
    sha = sha_r.stdout.strip() if sha_r.returncode == 0 else "?"

    utils.log(f"sweep-commit: {sha} — {subject}")


# ---------------------------------------------------------------------------
# sweep-review-generate
# ---------------------------------------------------------------------------

def cmd_sweep_review_generate(args):
    root = _np_root()
    sweeps = _sweeps_dir(root)

    date_str = args.date or date.today().strftime("%Y-%m-%d")

    # Determine the base commit for the diff range.
    # Priority: --base-commit arg > .sweep-base file > auto-detect first sweep commit today
    base_commit = getattr(args, "base_commit", None)
    sweep_id = None

    base_file = sweeps / ".sweep-base"
    id_file   = sweeps / ".sweep-id"

    if base_commit:
        # Validate it exists
        check = _git(["rev-parse", "--verify", base_commit], cwd=root)
        if check.returncode != 0:
            utils.err(f"Base commit not found: {base_commit}")
            sys.exit(utils.EXIT_NOT_FOUND)
        base_commit = check.stdout.strip()
    elif base_file.exists():
        # Use sweep-start recorded base
        base_commit = base_file.read_text(encoding="utf-8").strip()
        sweep_id = id_file.read_text(encoding="utf-8").strip() if id_file.exists() else None
    else:
        # Fall back: parent of first sweep-related commit today
        log_r = _git(
            ["log", "--oneline", "--after", f"{date_str} 00:00:00",
             "--before", f"{date_str} 23:59:59",
             "--extended-regexp", "--grep",
             r"^(sweep|chore|reflect|fix|feat)\("],
            cwd=root
        )
        sweep_commits = []
        if log_r.returncode == 0 and log_r.stdout.strip():
            sweep_commits = [line.split()[0] for line in log_r.stdout.strip().splitlines()]

        if not sweep_commits:
            utils.err(f"No sweep commits found for {date_str}. Run 'sweep-start' at Phase 2 or pass --base-commit.")
            sys.exit(utils.EXIT_NOT_FOUND)

        earliest_sweep = sweep_commits[-1]
        parent_r = _git(["rev-parse", f"{earliest_sweep}^"], cwd=root)
        if parent_r.returncode != 0:
            utils.err(f"Could not find parent of {earliest_sweep}")
            sys.exit(utils.EXIT_VALIDATION_FAILURE)
        base_commit = parent_r.stdout.strip()

    head_sha = _git(["rev-parse", "HEAD"], cwd=root).stdout.strip()
    sweep_sha = (sweep_id or head_sha[:7])  # display label

    run_n = _run_counter(sweeps, date_str)
    run_id = f"{date_str}-{run_n:02d}"

    # Get diff stat + unified diff for the full range base..HEAD
    stat_r = _git(["diff", "--stat", f"{base_commit}..HEAD"], cwd=root)
    stat_text = stat_r.stdout if stat_r.returncode == 0 else ""

    diff_r = _git(["diff", "--unified=3", f"{base_commit}..HEAD"], cwd=root)
    diff_text = diff_r.stdout if diff_r.returncode == 0 else ""

    if not diff_text:
        utils.err(f"Could not get diff for range {base_commit[:7]}..HEAD")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    # Decode git-quoted octal paths so emoji filenames are readable
    diff_text = _decode_git_quoted_paths(diff_text)
    stat_text = _decode_git_quoted_paths(stat_text)

    # Extract sweep narrative from breadcrumb tables in swept Calendar files
    narrative_data = _extract_sweep_narrative(root, base_commit)
    narrative = narrative_data["rows"]
    changed_calendar_files = narrative_data["changed_calendar_files"]

    # Check for existing comments file to carry forward
    existing_comments: list = []
    comments_files = sorted(sweeps.glob(f"{run_id}-r*.comments.jsonl"))
    for cf in comments_files:
        try:
            for line in cf.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    existing_comments.append(json.loads(line))
        except Exception:
            pass

    # Deduplicate: latest entry per anchor wins
    by_anchor: dict = {}
    for entry in existing_comments:
        anchor = entry.get("anchor", "")
        if anchor:
            by_anchor[anchor] = entry
    seed_comments = list(by_anchor.values())

    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would write {sweeps / (run_id + '.snapshot.html')}")
        return

    html = _build_snapshot_html(run_id, date_str, sweep_sha, stat_text, diff_text, seed_comments, narrative, changed_calendar_files)
    out_path = sweeps / f"{run_id}.snapshot.html"
    out_path.write_text(html, encoding="utf-8")
    utils.log(f"sweep-review-generate: wrote {out_path}")


def _decode_git_quoted_paths(text: str) -> str:
    """Replace git-quoted octal paths with decoded UTF-8 filenames.

    Git wraps paths containing non-ASCII chars in double quotes and encodes
    each byte as \\NNN (octal). This function decodes them so emoji filenames
    are human-readable in the HTML diff view.

    Examples:
      +++ "b/Notes/\\360\\237\\217\\242 ServiceNow/..."
      → +++ b/Notes/🏢 ServiceNow/...
    """
    import re as _re

    def _unescape(m: "_re.Match") -> str:
        quoted = m.group(1)  # content between the outer quotes
        # Decode C-style octal escapes (\NNN) to bytes, then UTF-8
        byte_parts = []
        i = 0
        while i < len(quoted):
            if quoted[i] == '\\' and i + 1 < len(quoted):
                # Could be \NNN (octal) or other escape
                if quoted[i+1].isdigit():
                    byte_parts.append(int(quoted[i+1:i+4], 8))
                    i += 4
                else:
                    # Other escape: keep as-is
                    byte_parts.append(ord(quoted[i+1]))
                    i += 2
            else:
                byte_parts.append(ord(quoted[i]))
                i += 1
        try:
            decoded = bytes(byte_parts).decode("utf-8", errors="replace")
        except Exception:
            decoded = quoted
        return decoded  # Return without surrounding quotes

    # Match lines like `+++ "b/..."` or `--- "a/..."` or `diff --git "a/..." "b/..."`
    # Also handles rename lines and stat lines with quoted paths.
    # Pattern: a double-quoted string that starts with a/ or b/
    pattern = _re.compile(r'"((?:[ab])/(?:[^"\\]|\\.)*)\"')

    def _replace(m: "_re.Match") -> str:
        inner = m.group(1)  # e.g. "b/Notes/\360..."
        prefix = inner[:2]  # "b/" or "a/"
        rest = inner[2:]
        decoded = _unescape(_re.match(r'(.*)', rest))
        return prefix + decoded

    # Replace all quoted path instances
    result = pattern.sub(lambda m: _replace(m), text)
    return result


def _extract_sweep_narrative(root: "Path", base_commit: str) -> list:
    """Parse breadcrumb tables from swept Calendar files and return narrative rows.

    Returns a list of dicts:
      { date, source_file, section, summary, destination }
    """
    import re as _re

    # Find Calendar/*.md files that changed since base_commit
    diff_r = _git(
        ["diff", "--name-only", f"{base_commit}..HEAD", "--", "Calendar/*.md"],
        cwd=root
    )
    changed_files: list[str] = []
    if diff_r.returncode == 0:
        changed_files = [l.strip() for l in diff_r.stdout.strip().splitlines() if l.strip()]

    rows = []
    table_re = _re.compile(
        r'^\|\s*(?P<date>[\d-]+)\s*\|\s*(?P<section>[^|]+)\s*\|\s*(?P<summary>[^|]+)\s*\|\s*(?P<dest>[^|]+)\s*\|',
        _re.MULTILINE
    )

    for rel in changed_files:
        abs_path = root / rel
        try:
            content = abs_path.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in table_re.finditer(content):
            date_val = m.group("date").strip()
            section  = m.group("section").strip()
            summary  = m.group("summary").strip()
            dest     = m.group("dest").strip()
            # Only accept rows with a valid YYYY-MM-DD date (skips headers + separator rows)
            if not _re.match(r'^\d{4}-\d{2}-\d{2}$', date_val):
                continue
            rows.append({
                "date":        date_val,
                "source_file": rel,
                "section":     section,
                "summary":     summary,
                "destination": dest,
            })

    rows.sort(key=lambda r: (r["date"], r["source_file"]))
    return {"rows": rows, "changed_calendar_files": changed_files}


def _build_snapshot_html(
    run_id: str, date_str: str, sha: str,
    stat_text: str, diff_text: str,
    seed_comments: list,
    narrative: list | None = None,
    changed_calendar_files: list | None = None,
) -> str:
    seed_json = json.dumps(seed_comments, indent=2)
    narrative_json = json.dumps(narrative or [], indent=2)
    changed_cal_json = json.dumps(changed_calendar_files or [], indent=2)
    # Build dest-file grep map: destStem → [normLine, ...] from actual files on disk
    # Used by JS classifyRow to confirm "lost" lines are truly absent (not already in dest)
    dest_file_lines: dict[str, list[str]] = {}
    _notes_root = Path("~/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes").expanduser()
    if narrative and _notes_root.exists():
        dest_stems = set()
        for r in narrative:
            d = re.sub(r'\[\[([^\]]+)\]\]', r'\1', r.get('destination', '')).strip()
            d = re.sub(r'\.md$', '', d).strip()
            if d: dest_stems.add(d)
        for stem in dest_stems:
            p = _find_dest_on_disk(_notes_root.parent, stem)
            if p:
                lines = [_norm_line(l) for l in p.read_text(errors='replace').splitlines()]
                dest_file_lines[stem.lower()] = [l for l in lines if len(l) > 4]
    dest_file_lines_json = json.dumps(dest_file_lines)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Sweep Review — {run_id}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px;background:#0d1117;color:#e6edf3;display:flex;flex-direction:column;height:100vh}}
#hdr{{background:#161b22;border-bottom:1px solid #30363d;padding:10px 20px;display:flex;align-items:center;gap:16px;position:sticky;top:0;z-index:100}}
#hdr h1{{font-size:15px;font-weight:600;color:#58a6ff}}
.stat{{font-size:12px;color:#8b949e}}
.tabs{{display:flex;gap:4px;margin-left:auto}}
.tab{{padding:4px 12px;border-radius:4px;cursor:pointer;font-size:12px;background:transparent;color:#8b949e;border:1px solid transparent}}
.tab.active{{background:#21262d;color:#e6edf3;border-color:#30363d}}
#filter-bar{{background:#161b22;border-bottom:1px solid #30363d;padding:6px 20px;display:flex;align-items:center;gap:8px;flex-shrink:0}}
.domain-chip,.type-chip{{padding:3px 10px;border-radius:12px;cursor:pointer;font-size:12px;background:#21262d;color:#8b949e;border:1px solid #30363d}}
.domain-chip.active{{background:#1a3a28;color:#3fb950;border-color:#3fb950}}
.type-chip.active{{background:#1c2128;color:#e6edf3;border-color:#58a6ff}}
.filter-sep{{color:#30363d;font-size:14px;margin:0 2px}}
.copy-btn{{margin-left:auto;padding:3px 10px;border-radius:4px;cursor:pointer;font-size:12px;background:#21262d;color:#8b949e;border:1px solid #30363d}}
.copy-btn:hover{{color:#e6edf3}}
.orphaned-block{{margin-top:16px;padding:12px 16px;border:1px solid #4a2f10;border-radius:8px;background:#1a1200}}
.orphaned-hdr{{font-size:12px;color:#d29922;margin-bottom:6px;font-weight:600}}
.orphaned-block ul{{list-style:none;padding:0}}
.orphaned-block li{{font-size:11.5px;color:#8b949e;font-family:'SF Mono','Fira Code',monospace;padding:2px 0}}
.dest-link{{color:#79c0ff;text-decoration:none;font-family:'SF Mono','Fira Code',monospace;font-size:11px}}
.dest-link:hover{{text-decoration:underline;color:#a5d6ff}}
.view-btn{{padding:1px 6px;border-radius:3px;cursor:pointer;font-size:11px;background:#21262d;color:#8b949e;border:1px solid #30363d}}
.view-btn:hover{{color:#e6edf3;border-color:#8b949e}}
#modal-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:1000;align-items:center;justify-content:center}}
#modal-overlay.open{{display:flex}}
.modal{{background:#161b22;border:1px solid #30363d;border-radius:10px;width:92vw;max-width:1400px;max-height:88vh;display:flex;flex-direction:column;overflow:hidden}}
.modal-hdr{{padding:10px 20px;border-bottom:1px solid #30363d;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;gap:12px}}
.modal-title{{font-size:13px;font-weight:600;color:#e6edf3;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.modal-close{{background:none;border:none;color:#8b949e;cursor:pointer;font-size:18px;line-height:1;padding:0 2px;flex-shrink:0}}
.modal-close:hover{{color:#e6edf3}}
.modal-body{{flex:1;min-height:0;padding:16px;display:grid;grid-template-columns:1fr 1fr;gap:16px;overflow:hidden}}
.modal-body>div{{min-width:0;overflow-y:auto;overflow-x:hidden;display:flex;flex-direction:column}}
.modal-panel-hdr{{font-size:11px;font-weight:600;color:#8b949e;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #30363d}}
.modal-empty{{color:#484f58;font-size:12px;padding:16px;text-align:center}}
.diff-lines{{font-family:'SF Mono','Fira Code',monospace;font-size:11.5px;line-height:18px;overflow-x:auto;flex:1}}
.diff-line{{padding:1px 8px;white-space:pre}}
.diff-line.removed{{background:#4a0f1a;color:#ffdcd7}}
.diff-line.added{{background:#0e4429;color:#aff5b4}}
.diff-line.new-content{{background:#1f1200;color:#e3b341}}
.diff-line.cross-moved{{background:#0d1b2a;color:#79c0ff}}
.modal-panel-tabs{{display:flex;gap:4px;margin-bottom:8px}}
.mpanel-tab{{padding:2px 10px;border-radius:4px;cursor:pointer;font-size:11px;background:#21262d;color:#8b949e;border:1px solid #30363d}}
.mpanel-tab.active{{background:#1a3a28;color:#3fb950;border-color:#3fb950}}
.mpanel-tab.new-tab.active{{background:#2d1f00;color:#e3b341;border-color:#e3b341}}
.mpanel-tab.cross-tab.active{{background:#0d1b2a;color:#79c0ff;border-color:#79c0ff}}
#layout{{display:flex;flex:1;min-height:0}}
#sidebar{{width:260px;min-width:160px;background:#161b22;border-right:1px solid #30363d;overflow-y:auto;flex-shrink:0;padding:8px 0}}
.fi{{padding:5px 12px;cursor:pointer;display:flex;align-items:center;gap:8px;border-left:3px solid transparent;font-size:12px}}
.fi:hover{{background:#21262d}}
.fi.active{{background:#21262d;border-left-color:#58a6ff}}
.fi .name{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}}
.badge{{font-size:10px;font-weight:700;padding:1px 5px;border-radius:3px;flex-shrink:0}}
.ba{{background:#1f4a2a;color:#3fb950}}.bd{{background:#4a1f2a;color:#f85149}}.bm{{background:#1f2d4a;color:#79c0ff}}
#main{{flex:1;overflow-y:auto;padding:16px}}
/* ── Diff panel ── */
.fd{{margin-bottom:20px;border:1px solid #30363d;border-radius:8px;overflow:hidden}}
.fdh{{background:#161b22;padding:7px 14px;font-size:12px;color:#8b949e;border-bottom:1px solid #30363d;display:flex;justify-content:space-between}}
.fdh .fn{{color:#e6edf3;font-weight:600;font-family:'SF Mono','Fira Code',monospace}}
.sbs{{display:grid;grid-template-columns:1fr 1fr;font-family:'SF Mono','Fira Code',monospace;font-size:11.5px}}
.sbs-col{{overflow:hidden;border-right:1px solid #30363d}}
.sbs-col:last-child{{border-right:none}}
.sbs-col .col-hdr{{background:#1c2128;padding:3px 8px;font-size:11px;color:#8b949e;border-bottom:1px solid #30363d}}
.row{{display:flex;min-height:18px}}
.ln{{width:36px;text-align:right;padding:0 6px;color:#484f58;user-select:none;border-right:1px solid #30363d;flex-shrink:0;line-height:18px}}
.lc{{flex:1;padding:0 6px;white-space:pre;overflow:hidden;line-height:18px}}
.row.add{{background:#0e4429}}.row.add .ln{{background:#0a3320;color:#3fb950}}.row.add .lc{{color:#aff5b4}}
.row.del{{background:#1a0a0f}}.row.del .ln{{background:#120508;color:#6e3a44}}.row.del .lc{{color:#6b7280}}
.row.ctx{{background:#0d1117}}
.row.hdr{{background:#1c2128}}.row.hdr .lc{{color:#8b949e}}
.diff-ctx-hdr{{font-family:'SF Mono','Fira Code',monospace;font-size:11px;padding:4px 8px 2px;color:#58a6ff;font-weight:600;background:#0d1117;border-top:1px solid #21262d;margin-top:6px}}
.diff-ctx-skip{{font-family:'SF Mono','Fira Code',monospace;font-size:11px;padding:0 8px 4px;color:#484f58;background:#0d1117}}
.line-no{{color:#484f58;font-size:10px;min-width:30px;display:inline-block;text-align:right;padding-right:8px;user-select:none;flex-shrink:0}}
.pair-highlight{{background:rgba(255,255,255,0.06)!important;outline:1px solid rgba(255,255,255,0.15);z-index:1;position:relative}}
[data-pair-id]{{cursor:pointer}}
.move-badge{{margin-left:6px;padding:0 5px;border-radius:3px;font-size:10px;background:#1a3a28;color:#3fb950;border:1px solid #3fb950;text-decoration:none;white-space:nowrap;flex-shrink:0}}
.move-badge:hover{{background:#204830}}
.lost-badge{{margin-left:6px;padding:0 5px;border-radius:3px;font-size:10px;background:#2d0a0a;color:#f85149;border:1px solid #f85149;white-space:nowrap;flex-shrink:0}}
.row.add .lc{{color:#aff5b4}}.row.del .lc{{color:#ffdcd7}}
/* ── Narrative panel ── */
#narrative{{padding:16px}}
.day-block{{margin-bottom:24px}}
.day-hdr{{font-size:14px;font-weight:600;color:#58a6ff;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #30363d}}
.nav-tbl{{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed}}
.nav-tbl th{{background:#161b22;padding:6px 10px;text-align:left;color:#8b949e;font-weight:500;border-bottom:2px solid #30363d;position:sticky;top:0;z-index:1}}
.nav-tbl th:nth-child(1){{width:28px}}.nav-tbl th:nth-child(2){{width:50px}}.nav-tbl th:nth-child(3){{width:18%}}.nav-tbl th:nth-child(4){{width:22%}}.nav-tbl th:nth-child(5){{width:88px}}.nav-tbl th:nth-child(6){{width:auto}}.nav-tbl th:nth-child(7){{width:44px}}
.src-col{{color:#58a6ff;font-family:monospace;font-size:11px;white-space:nowrap}}
.row-badge{{display:inline-block;font-size:11px;min-width:16px;text-align:center;border-radius:3px;padding:1px 4px;font-weight:600}}
.rb-move{{background:#1a3a28;color:#3fb950}}.rb-lost{{background:#2d0a0a;color:#f85149}}.rb-anomaly{{background:#1a1a00;color:#e3b341}}.rb-empty{{background:#1c2128;color:#484f58}}.rb-pending{{color:#484f58}}.rb-mixed{{background:#2d1f00;color:#e3b341;border:1px solid #e3b341}}
.mixed-lost-sub-row td{{background:#1a0a0a;border-left:2px solid #f85149;padding-left:10px!important;color:#8b949e;font-size:11px;cursor:pointer}}
.mixed-lost-sub-row:hover td{{background:#251010}}
.mixed-lost-sub-row .row-badge{{vertical-align:middle}}
.nav-tbl td{{padding:5px 10px;border-bottom:1px solid #21262d;vertical-align:middle;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.nav-tbl tr:hover td{{background:#161b22}}
.nav-tbl .section-col{{color:#e6edf3;font-weight:500}}
.nav-tbl .summary-col{{color:#8b949e}}
.day-sep-row td{{background:#0d1117;padding:14px 10px 5px;font-size:13px;font-weight:600;color:#58a6ff;border-bottom:1px solid #30363d;white-space:normal;overflow:visible}}
.src-sep-row td{{background:#0a0f1a;padding:4px 10px 3px;font-size:10px;font-weight:500;color:#3d6a9e;border-bottom:1px solid #1c2128;font-family:monospace;white-space:nowrap;overflow:visible}}
.item-row td{{background:#0a0d12;padding:3px 10px;border-bottom:1px solid #161b22;font-size:11px}}
.item-row:hover td{{background:#0d1117}}
.item-row .item-text{{color:#c9d1d9;font-family:'SF Mono','Fira Code',monospace;padding-left:20px}}
.sec-toggle{{padding:0 5px 0 0;background:none;border:none;color:#484f58;cursor:pointer;font-size:9px;vertical-align:middle}}
.sec-toggle:hover{{color:#8b949e}}
.empty{{color:#484f58;padding:24px;text-align:center}}
/* ── Validation ── */
.row-warn{{display:inline-block;font-size:10px;margin-left:4px;color:#e3b341;cursor:help;vertical-align:middle}}
#validation-banner{{padding:6px 16px;font-size:12px;border-bottom:1px solid #30363d;display:none}}
#validation-banner.ok{{background:#0e2a14;color:#3fb950;display:block}}
#validation-banner.warn{{background:#2d1f00;color:#e3b341;display:block}}
</style>
</head>
<body>
<div id="hdr">
  <h1>Sweep Review — {run_id}</h1>
  <span class="stat" id="stat-line"></span>
  <span class="stat" id="date-range" style="color:#484f58"></span>
  <span class="stat" style="color:#484f58">base {sha}</span>
  <div class="tabs">
    <button class="tab active" onclick="showTab('narrative')">📋 Narrative</button>
    <button class="tab" onclick="showTab('diff')">🔀 Diff</button>
  </div>
</div>
<div id="filter-bar">
  <span style="font-size:11px;color:#484f58;margin-right:2px">Domain:</span>
  <button class="domain-chip active" data-domain="all" onclick="setDomain('all')">All</button>
  <button class="domain-chip" data-domain="work" onclick="setDomain('work')">🏢 Work</button>
  <button class="domain-chip" data-domain="personal" onclick="setDomain('personal')">🏡 Personal</button>
  <button class="domain-chip" data-domain="earlbear" onclick="setDomain('earlbear')">👥 EarlBear</button>
  <button class="domain-chip" data-domain="coffee" onclick="setDomain('coffee')">☕️ Naqsh</button>
  <span class="filter-sep">|</span>
  <span style="font-size:11px;color:#484f58;margin-right:2px">Type:</span>
  <button class="type-chip active" data-type="all" onclick="setType('all')" title="Show all rows">All</button>
  <button class="type-chip" data-type="move" onclick="setType('move')" title="Move — all source lines confirmed at destination">→ Move</button>
  <button class="type-chip" data-type="lost" onclick="setType('lost')" title="Lost — one or more source lines did not arrive">✗ Lost</button>
  <button class="type-chip" data-type="mixed" onclick="setType('mixed')" title="Mixed — some lines moved, some lost; needs split">⚡ Mixed</button>
  <button class="type-chip" data-type="anomaly" onclick="setType('anomaly')" title="Anomaly — destination has additions with no matching source">+ Anomaly</button>
  <button class="type-chip" data-type="empty" onclick="setType('empty')" title="Empty — no source content found or destination file is empty">· Empty</button>
  <button class="copy-btn" id="copy-btn" onclick="copyNarrative()">📋 Copy</button>
</div>
<div id="layout">
  <nav id="sidebar" style="display:none"></nav>
  <main id="main">
    <div id="validation-banner"></div>
    <div id="narrative"></div>
    <div id="diff" style="display:none"></div>
  </main>
</div>

<script>
const RUN_ID = {json.dumps(run_id)};
const DIFF_TEXT = {json.dumps(diff_text)};
const STAT_TEXT = {json.dumps(stat_text)};
const SEED_COMMENTS = {seed_json};
const NARRATIVE = {narrative_json};
const CHANGED_CALENDAR_FILES = {changed_cal_json};
// destStem.lower() → [normLine, ...] — full file content at generate time, for lost-line verification
const DEST_FILE_LINES = {dest_file_lines_json};

let allParsedFiles = [];
const MODAL_ROWS = [];

// ── xcallback links ────────────────────────────────────────────────────────
function xcallbackUrl(dest) {{
  let raw = dest.replace(/\\[\\[([^\\]]+)\\]\\]/g, '$1').trim().replace(/\\.md$/, '');
  if (/^\\d{{8}}$/.test(raw)) {{
    return 'noteplan://x-callback-url/openNote?filename=' + raw;
  }}
  return 'noteplan://x-callback-url/openNote?noteTitle=' + encodeURIComponent(raw);
}}

// ── Section diff modal ─────────────────────────────────────────────────────
// ── Expandable section rows ────────────────────────────────────────────────
function toggleSectionItems(rowIdx, btn) {{
  const existing = document.querySelectorAll(`tr.item-row[data-parent="${{rowIdx}}"]`);
  if (existing.length) {{
    existing.forEach(r => r.remove());
    btn.textContent = '▶';
    return;
  }}
  const row = MODAL_ROWS[rowIdx];
  if (!row) return;
  const result = extractSectionLines(row.source_file, row.section, '-');
  const lines = result.lines.filter(l => l.trim() && !isNoiseLine(l));
  if (!lines.length) {{ btn.textContent = '○'; return; }}
  btn.textContent = '▼';
  // Classify each line as moved or lost using dest diff + dest file on disk
  const destRawE = row.destination.replace(/\\[\\[([^\\]]+)\\]\\]/g, '$1').trim().replace(/\\.md$/, '');
  const sectionNameE = row.section.replace(/^#+\\s*/, '').trim();
  const _destSecE = extractSectionLines(destRawE + '.md', sectionNameE, '+');
  const addedLines = _destSecE.lines.length > 0
    ? _destSecE.lines
    : extractSectionLines(destRawE + '.md', null, '+').lines;
  const {{ moved: movedSet, movedPairs }} = classifyDestLines(lines, addedLines);
  const movedSrcSet = new Set([...movedPairs.values()]);
  const parentRow = document.querySelector(`tr[data-row-idx="${{rowIdx}}"]`);
  if (!parentRow) return;
  // Insert after the mixed-lost sub-row if present, otherwise after parent
  let insertAfter = parentRow.nextSibling?.dataset?.mixedLostFor === String(rowIdx)
    ? parentRow.nextSibling : parentRow;
  for (const line of lines) {{
    const tr = document.createElement('tr');
    tr.className = 'item-row';
    tr.dataset.parent = rowIdx;
    const clean = line.replace(/^-\\s*\\[[x ]\\]\\s*/i, '').replace(/^-\\s+/, '').trim();
    if (!clean) continue;
    const inDest = movedSrcSet.has(line) || isLineInDestFile(line, destRawE);
    const badge = inDest
      ? `<span style="color:#3fb950;font-size:9px;margin-right:4px">→</span>`
      : `<span style="color:#f85149;font-size:9px;margin-right:4px">✗</span>`;
    const color = inDest ? '' : 'color:#f85149;opacity:0.8;';
    tr.innerHTML = `<td class="sec-toggle" style="color:#30363d;text-align:right">↳</td><td></td><td class="item-text" colspan="3" style="${{color}}">${{badge}}${{esc(clean)}}</td><td></td><td></td>`;
    insertAfter.insertAdjacentElement('afterend', tr);
    insertAfter = tr;
  }}
}}

function closeModal() {{
  document.getElementById('modal-overlay').classList.remove('open');
}}

document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeModal(); }});

// Extract only the + or - lines for a section from DIFF_TEXT.
// Normalize for fuzzy section matching: strip leading #s, collapse special chars to spaces
function normSectionStr(s) {{
  return s.replace(/^#+\\s*/, '').replace(/[/\\-+()|]/g, ' ').replace(/\\s+/g, ' ').trim().toLowerCase();
}}

function sectionHeaderMatches(content, nameLower) {{
  const stripped = normSectionStr(content);
  if (!stripped) return false;
  // Exact match or query is a prefix of header (header is MORE specific — ok)
  if (stripped === nameLower) return true;
  if (stripped.startsWith(nameLower + ' ') || stripped.startsWith(nameLower + ':')) return true;
  // Reject: header is a strict prefix of query → parent section, not this row's section
  if (nameLower.startsWith(stripped + ' ') || nameLower.startsWith(stripped + ':')) return false;
  // Last-token check: query's last significant word (≥3 chars) matched as whole word in header
  // e.g. "Config Agent ARB" → last token "arb" → matches "## ARB & Governance"
  const qToks = nameLower.split(' ').filter(w => w.length >= 3);
  const lastTok = qToks[qToks.length - 1];
  if (lastTok && lastTok.length >= 3) {{
    const safe = lastTok.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
    if (new RegExp(`\\\\b${{safe}}\\\\b`).test(stripped)) return true;
  }}
  // Word-overlap fallback: 60%+ of significant words (len>3) from query must appear in header
  const words = nameLower.split(' ').filter(w => w.length > 3);
  if (!words.length) return stripped.includes(nameLower);
  const hits = words.filter(w => stripped.includes(w)).length;
  return hits >= Math.max(1, Math.ceil(words.length * 0.6));
}}

// V-47a: score a candidate header against the query nameLower for fuzzy section matching.
// Uses existing sectionHeaderMatches as a first pass, then token-level prefix overlap.
// Returns a numeric score — accept the best header if score >= 0.5.
function v47aScore(hdr, nameLower) {{
  if (sectionHeaderMatches(hdr, nameLower)) return 999;
  const hdrNorm = normSectionStr(hdr);
  const qToks = nameLower.split(/[\\s\\/\\-,\\.]+/).filter(w => w.length >= 3);
  const hToks = hdrNorm.split(/[\\s\\/\\-,\\.]+/).filter(w => w.length >= 3);
  if (!qToks.length || !hToks.length) return 0;
  let score = 0;
  for (const qt of qToks) {{
    // Strip trailing 's' for de-plural stem comparison ("refs" → "ref")
    const qtS = qt.length > 3 && qt.endsWith('s') ? qt.slice(0, -1) : qt;
    let best = 0;
    for (const ht of hToks) {{
      const htS = ht.length > 3 && ht.endsWith('s') ? ht.slice(0, -1) : ht;
      let s = 0;
      if (qt === ht || qtS === htS) {{ s = 1.0; }}
      else if (qtS.length >= 3 && ht.startsWith(qtS)) {{ s = 0.7; }}
      else if (htS.length >= 3 && qt.startsWith(htS)) {{ s = 0.7; }}
      if (s > best) best = s;
    }}
    score += best;
  }}
  return score;
}}

// Extract + or - lines for a section from DIFF_TEXT.
// sectionName=null → accept all lines (destination "all added" mode).
// Returns {{ lines, lineNos, matched, sectionFound, fuzzyHeader, v47Fallback, flatFile }}.
//   sectionFound:  true if a section header was located in diff (exact OR fuzzy)
//   fuzzyHeader:   the header string that was fuzzy-matched (V-47a), or null
//   v47Fallback:   true when V-47a attempted but found no qualifying header
//   flatFile:      true when the file has no ## headers in its diff block at all
function extractSectionLines(filename, sectionName, lineType) {{
  const rawLines = DIFF_TEXT.split('\\n');
  const baseName = filename.split('/').pop().toLowerCase();
  const nameLower = sectionName ? normSectionStr(sectionName) : null;
  const seenHeaders = []; // V-47a: headers collected from this file's diff block

  // strictBoundary: when true, any same-level header (including '+') closes the current section.
  // Used in the V-47a second pass so a fuzzy-matched section is properly bounded in
  // fully-added files where the original guard (type !== '+') would keep it open forever.
  function doExtract(activeName, strictBoundary) {{
    let inFile = false;
    let inSection = activeName === null;
    let sectionLevel = 0;
    let sectionEntered = false;
    const res = [], nos = [];
    let curLineNo = 0;
    for (const line of rawLines) {{
      if (line.startsWith('diff --git ')) {{
        inFile = line.toLowerCase().includes(baseName);
        inSection = activeName === null;
        sectionLevel = 0;
        continue;
      }}
      if (!inFile || line.startsWith('+++') || line.startsWith('---') || line.startsWith('index')) continue;
      if (line.startsWith('@@')) {{
        const m = line.match(/@@ -(\\d+)(?:,\\d+)? \\+(\\d+)(?:,\\d+)? @@/);
        if (m) curLineNo = lineType === '-' ? parseInt(m[1], 10) - 1 : parseInt(m[2], 10) - 1;
        continue;
      }}
      const type = line.length ? line[0] : ' ';
      if (type !== '+' && type !== '-' && type !== ' ') continue;
      const content = line.slice(1);
      if (type === ' ' || type === lineType) curLineNo++;
      const headerDepth = (content.match(/^(#+)\\s/) || [])[1]?.length ?? 0;
      // Collect section headers for V-47a on first pass; skip removed headers (gone from file)
      if (activeName === nameLower && inFile && headerDepth >= 2 && type !== '-') {{
        seenHeaders.push(content);
      }}
      if (activeName !== null) {{
        if (headerDepth > 0 && sectionHeaderMatches(content, activeName)) {{
          inSection = true; sectionLevel = headerDepth; sectionEntered = true;
        }} else if (inSection && headerDepth > 0 && headerDepth <= sectionLevel && (strictBoundary || type !== '+')) {{
          inSection = false;
        }}
      }}
      if (inSection && type === lineType) {{ res.push(content); nos.push(curLineNo); }}
    }}
    return {{ result: res, lineNos: nos, sectionEntered }};
  }}

  let result, lineNos, sectionEntered;
  ({{ result, lineNos, sectionEntered }} = doExtract(nameLower, false));

  // V-47a: fuzzy section name matching — only when exact match found nothing AND section was never entered
  let fuzzyHeader = null, v47Fallback = false, flatFile = false;
  if (result.length === 0 && sectionName !== null && !sectionEntered) {{
    const uniqueHeaders = [...new Set(seenHeaders)];
    if (uniqueHeaders.length === 0) {{
      flatFile = true; // no ## headers in this file's diff block — can't scope to a section
    }} else {{
      let bestScore = 0, bestHdr = null;
      for (const hdr of uniqueHeaders) {{
        const sc = v47aScore(hdr, nameLower);
        if (sc > bestScore) {{ bestScore = sc; bestHdr = hdr; }}
      }}
      if (bestHdr !== null && bestScore >= 0.5) {{
        fuzzyHeader = bestHdr;
        const fuzzyNameLower = normSectionStr(bestHdr);
        // strictBoundary=true: allow +/- headers to close sections in the fuzzy pass
        ({{ result, lineNos, sectionEntered }} = doExtract(fuzzyNameLower, true));
        console.debug('V-47a: fuzzy match', {{ sectionName, matchedHeader: bestHdr, score: bestScore }});
      }} else {{
        v47Fallback = true;
        console.warn('V-47a: no fuzzy match for section', sectionName, 'in', filename, '(headers:', uniqueHeaders, ')');
      }}
    }}
  }}

  // V-P (duplicate detection): warn if the same content line appears more than once
  const _seenContents = new Map();
  result.forEach((l, i) => {{ const n = normLine(l); _seenContents.set(n, (_seenContents.get(n) || 0) + 1); }});
  const _dupCount = [..._seenContents.values()].filter(c => c > 1).length;
  if (_dupCount > 0) console.warn('V-P (dup): duplicate lines in section extract', {{ filename, sectionName, dupCount: _dupCount }});

  return {{ lines: result, lineNos, matched: result.length > 0,
           sectionFound: sectionEntered || fuzzyHeader !== null,
           fuzzyHeader, v47Fallback, flatFile }};
}}

// Classify destination added lines as "moved" (matches source) or "new" (no match)
// Shared normaliser: strip date tags + hashtags, collapse whitespace, lowercase
const normLine = s => s.replace(/>\\d{{4}}-\\d{{2}}-\\d{{2}}/g, '').replace(/#\\w+/g, '').replace(/\\s+/g, ' ').trim().toLowerCase();
const bodyText = s => s.replace(/^[-*]\\s*\\[[x ]\\]\\s*/i, '').trim();

function classifyDestLines(removedLines, addedLines) {{
  const norm = normLine;
  const body = bodyText;
  // Keep original index alongside norm so matchIdx maps back to removedLines correctly
  const removedEntries = removedLines
    .map((l, origIdx) => {{ const n = norm(l); return {{ line: l, n, b: body(n), origIdx }}; }})
    .filter(e => e.n.length > 3 && !isNoiseLine(e.line)); // exclude headers/noise — must match countableRemoved
  const moved = [], newContent = [];
  const movedPairs = new Map(); // destLine → srcLine (for grouped source panel)
  for (const line of addedLines) {{
    const n = norm(line);
    if (!n || n.length <= 2) continue; // skip empty/blank lines — not real content
    const nb = body(n);
    const matchIdx = removedEntries.findIndex(e => {{
      if (n === e.n) return true;
      const pLen = Math.min(50, Math.min(n.length, e.n.length));
      if (pLen >= 10 && (n.startsWith(e.n.slice(0, pLen)) || e.n.startsWith(n.slice(0, pLen)))) return true;
      if (!e.b || e.b.length < 8 || nb.length < 8) return false;
      const bLen = Math.min(40, Math.min(nb.length, e.b.length));
      return nb.startsWith(e.b.slice(0, bLen)) || e.b.startsWith(nb.slice(0, bLen));
    }});
    if (matchIdx >= 0) {{
      moved.push(line);
      movedPairs.set(line, removedEntries[matchIdx].line); // use original line, not filtered index
    }} else {{
      newContent.push(line);
    }}
  }}
  return {{ moved, newContent, movedPairs }};
}}

// Shared pair validator — same logic as showSectionModal's validation pass.
// Returns only the moved lines whose (destLine, srcLine) pair passes norm-match.
// Used by both classifyRow and showSectionModal so tooltip counts == modal counts.
// Check if a line already exists in the destination file (pre-existing from a prior sweep).
// destRaw = destination stem (no .md, no [[]]). Returns true if line is found on disk.
function isLineInDestFile(line, destRaw) {{
  const key = destRaw.toLowerCase();
  const fileLines = DEST_FILE_LINES[key];
  if (!fileLines) return false;
  const sn = normLine(line);
  if (!sn || sn.length <= 4) return false;
  return fileLines.some(dn => dn === sn || (sn.length >= 10 && (dn.startsWith(sn.slice(0,40)) || sn.startsWith(dn.slice(0,40)))));
}}

function filterValidPairs(moved, movedPairs, removedLines) {{
  const removedSet = new Set(removedLines);
  return moved.filter(destLine => {{
    const srcLine = movedPairs.get(destLine);
    if (!srcLine || !removedSet.has(srcLine)) return false;
    const dn = normLine(destLine), sn = normLine(srcLine);
    const db = bodyText(dn), sb = bodyText(sn);
    const pLen = Math.min(50, Math.min(dn.length, sn.length));
    const bLen = Math.min(40, Math.min(db.length, sb.length));
    return dn === sn ||
      (pLen >= 10 && (dn.startsWith(sn.slice(0, pLen)) || sn.startsWith(dn.slice(0, pLen)))) ||
      (sb.length >= 8 && db.length >= 8 && bLen >= 8 &&
        (db.startsWith(sb.slice(0, bLen)) || sb.startsWith(db.slice(0, bLen))));
  }});
}}

// Noise filter — shared by classifyRow and showSectionModal
const isNoiseLine = line => {{
  if (/^#+\\s/.test(line.trim())) return true;          // markdown headings never move
  const n = normLine(line);
  if (n.length <= 3) return true;
  if (/^`+(\\w*)$/.test(n)) return true;
  if (/^-{{2,}}$/.test(n) || /^—{{1,}}$/.test(n)) return true;
  if (/^[-*]\\s*\\[\\s*\\]\\s*$/.test(n)) return true;
  return false;
}};

// Row classification cache: idx → {{type, movedCount, newCount}}
const _rowClassifications = new Map();
// Layer 3/4 support: movedPairs per row, stored so cross-row pass can inspect them
const _rowMovedPairs = new Map(); // idx → movedPairs Map (destLine → srcLine)
// Layer 2: row-level validation issues
const _rowValidation = new Map(); // idx → [issue strings]
// Layer 4: cross-row issues
const _crossRowIssues = [];

// Classify a narrative row by running extract + classify (same logic as showSectionModal).
// Result is cached so badge updates and modal opens share the same computation.
function classifyRow(idx) {{
  if (_rowClassifications.has(idx)) return _rowClassifications.get(idx);
  const row = MODAL_ROWS[idx];
  if (!row) return null;

  const sectionName = row.section.replace(/^#+\\s*/, '').trim();
  const srcResult = extractSectionLines(row.source_file, sectionName, '-');
  let removedLines = srcResult.lines;

  const destRaw = row.destination.replace(/\\[\\[([^\\]]+)\\]\\]/g, '$1').trim().replace(/\\.md$/, '');
  const destFile = allParsedFiles.find(f => {{
    const stem = (f.filename || '').split('/').pop().replace(/\\.md$/, '');
    return stem === destRaw || (f.filename || '').endsWith(destRaw + '.md');
  }});
  const destGroups = destFile ? extractDestWithContext(destFile.filename) : [];
  // V-47: scope added lines to the matching section in dest first; fall back to full file.
  // V-47a: sectionFound=true when the section was located (exact or fuzzy) — don't fall back
  //        even if the section was empty; an empty scoped result is correct (not anomalous).
  const destFilenameC = destFile ? destFile.filename : (destRaw + '.md');
  const destSectionResult = extractSectionLines(destFilenameC, sectionName, '+');
  let addedLines = (destSectionResult.lines.length > 0 || destSectionResult.sectionFound)
    ? destSectionResult.lines
    : destGroups.flatMap(g => g.lines);

  if (!srcResult.matched && addedLines.length > 0) {{
    const allSrc = extractSectionLines(row.source_file, null, '-').lines;
    const destNorms = new Set(addedLines.map(normLine).filter(s => s.length > 5));
    removedLines = allSrc.filter(l => {{
      const n = normLine(l);
      if (n.length < 5) return false;
      if (destNorms.has(n)) return true;
      return [...destNorms].some(dn => {{
        const pLen = Math.min(40, Math.min(n.length, dn.length));
        return pLen >= 10 && (n.startsWith(dn.slice(0, pLen)) || dn.startsWith(n.slice(0, pLen)));
      }});
    }});
  }}

  const {{ moved, newContent, movedPairs }} = classifyDestLines(removedLines, addedLines);
  const validMoved = filterValidPairs(moved, movedPairs, removedLines);
  const movedCount = validMoved.length;
  // Score = Moved / removedLines.length — measures whether source lines arrived.
  // "New" lines in destination are a separate anomaly concern and do NOT affect migration score.
  // Cross lines (from other source files) are also excluded — they have their own rows.
  const globalMap = getGlobalRemovedMap();
  const srcStem = row.source_file.split('/').pop().replace(/\\.md$/, '');
  let trueNewCount = 0;
  for (const line of newContent) {{
    if (isNoiseLine(line)) continue;
    const n = normLine(line);
    const fromStem = globalMap.get(n);
    if (!fromStem || fromStem === srcStem) trueNewCount++;
  }}
  // Denominator: count only non-empty, non-noise source lines — blank lines are skipped
  // by classifyDestLines so they must not inflate the denominator either.
  // For inferred rows the section boundary is unknown so use movedCount (only judge what matched).
  const destRawC = row.destination.replace(/\\[\\[([^\\]]+)\\]\\]/g, '$1').trim().replace(/\\.md$/, '');
  const countableRemoved = removedLines.filter(l => normLine(l).length > 2 && !isNoiseLine(l));
  const total = srcResult.matched ? countableRemoved.length : movedCount;
  const destMissing = !DIFF_TEXT.toLowerCase().includes((destRawC + '.md').toLowerCase());
  const srcMissing  = !DIFF_TEXT.toLowerCase().includes(row.source_file.split('/').pop().toLowerCase());

  // Binary classification: every source line either arrived (move) or didn't (lost).
  // No partial — a row with any lost lines is Lost, even if others moved.
  let type, emptyReason = '';
  if (srcMissing)  {{ type = 'empty'; emptyReason = 'source file not in diff'; }}
  else if (destMissing) {{ type = 'empty'; emptyReason = 'destination file not in diff'; }}
  else if (total === 0 && addedLines.length === 0) {{
    type = 'empty';
    emptyReason = srcResult.matched
      ? 'section has no content lines'
      : 'section not found + destination is empty';
  }}
  // B-14: if dest was newly created, its additions are portal boilerplate + swept content —
  // not anomalous. Classify as empty (nothing to verify from this row's source).
  // B-13: filter addedLines by two layers of claimed norms:
  //  1. Sibling rows' removed norms — lines attributed to another row pointing to the same dest
  //  2. Global removed map — lines removed from ANY source file in this diff (section name may not match)
  // A dest addition is a true anomaly only if it appears in neither layer.
  else if (total === 0 && addedLines.length > 0) {{
    if (destFile && destFile.isNewFile) {{
      type = 'empty';
    }} else {{
      const siblingNorms = getDestSiblingNorms().get(destRawC) || new Set();
      const globalMap = getGlobalRemovedMap();
      const unclaimedAdded = addedLines.filter(l => {{
        if (isNoiseLine(l)) return false;
        const n = normLine(l);
        return n.length > 2 && !siblingNorms.has(n) && !globalMap.has(n);
      }});
      type = unclaimedAdded.length > 0 ? 'anomaly' : 'empty';
      if (unclaimedAdded.length === 0 && addedLines.length > 0) {{
        console.debug('B-13: all additions claimed by diff sources → empty', {{ idx, destRawC }});
      }}
    }}
  }}
  else if (movedCount === total) type = 'move';   // ALL source lines arrived
  else type = 'lost';                              // ANY source line missing → lost

  const lostCount = total - movedCount;
  // Mixed = some lines moved, some didn't — sweep should have split this into two rows
  const mixed = type === 'lost' && movedCount > 0 && lostCount > 0;
  // V-P4: movedCount must not exceed total (clamp and log)
  if (movedCount > total) {{ console.error('V-P4: movedCount > total', idx, movedCount, total); }}
  // V-P5: assert all line numbers > 0
  const _srcLineNosCheck = new Map();
  srcResult.lines.forEach((l, i) => {{ if (!_srcLineNosCheck.has(l)) _srcLineNosCheck.set(l, srcResult.lineNos?.[i]); }});
  if ([..._srcLineNosCheck.values()].some(n => n != null && n <= 0)) console.warn('V-P5: invalid line numbers', idx);
  // V-P3: warn when source lines normalize to empty — they were silently excluded from matching
  const noisyExcluded = removedLines.filter(l => isNoiseLine(l) || normLine(l).length <= 2);
  if (noisyExcluded.length > 0) console.debug('V-P3:', noisyExcluded.length, 'source lines normalized to empty (excluded from match)', idx);
  // Store movedPairs for cross-row pass (Layer 4)
  _rowMovedPairs.set(idx, movedPairs);
  const result = {{ type, movedCount, lostCount, newCount: trueNewCount, mixed, emptyReason }};
  _rowClassifications.set(idx, result);
  return result;
}}

const _badgeLabels   = {{ move: '→', lost: '✗', anomaly: '+', empty: '·', mixed: '⚡' }};
const _badgeTitles   = {{
  move:    'Move — all source lines confirmed at destination',
  lost:    'Lost — one or more source lines did not arrive at destination',
  anomaly: 'Anomaly — destination has additions with no matching source',
  empty:   'Empty — nothing to verify',
  mixed:   'Mixed — some lines moved, some lost. This section should have been split into separate rows during sweep.',
}};

function injectMixedLostSubRow(idx, lostCount) {{
  const tr = document.querySelector(`tr[data-row-idx="${{idx}}"]`);
  if (!tr) return;
  // Don't inject twice
  if (tr.nextSibling?.dataset?.mixedLostFor === String(idx)) return;
  const row = MODAL_ROWS[idx];
  const subTr = document.createElement('tr');
  subTr.className = 'mixed-lost-sub-row';
  subTr.dataset.mixedLostFor = String(idx);
  subTr.dataset.rowType = 'lost';  // participates in type filter as Lost
  subTr.title = 'Click to open modal — scroll to Lost section';
  subTr.onclick = () => {{ showSectionModal(idx, true); }};
  subTr.innerHTML = `
    <td style="padding:3px 6px;text-align:center"><span class="row-badge rb-lost">✗</span></td>
    <td class="count-col" style="width:48px;text-align:center;font-size:10px;color:#f85149;font-family:monospace">${{lostCount}}</td>
    <td class="section-col" style="color:#f85149">↳ Lost (${{lostCount}} line${{lostCount!==1?'s':''}}) — not found at destination</td>
    <td class="summary-col" style="color:#6e7681">Needs separate row — split this section during sweep</td>
    <td class="src-col" style="color:#6e7681">—</td>
    <td class="dest-col" style="color:#6e7681">?? unknown</td>
    <td style="padding:3px 6px;text-align:center"><button class="view-btn" onclick="event.stopPropagation();showSectionModal(${{idx}}, true)">⌕</button></td>
  `;
  tr.after(subTr);
  // Apply current type filter to sub-row
  if (activeType !== 'all' && activeType !== 'lost') subTr.style.display = 'none';
  // Upgrade parent badge from ⚡ mixed → → move (the lost block is now its own sub-row)
  const parentBadge = tr.querySelector('.row-badge');
  if (parentBadge) {{
    parentBadge.className = 'row-badge rb-move';
    parentBadge.textContent = '→';
    parentBadge.title = 'Move — moved lines confirmed at destination (lost lines split below)';
  }}
  tr.dataset.rowType = 'move';
  if (activeType !== 'all' && activeType !== 'move') tr.style.display = 'none';
}}

function updateRowBadge(idx, classification) {{
  const tr = document.querySelector(`tr[data-row-idx="${{idx}}"]`);
  if (!tr) return;
  const badge = tr.querySelector('.row-badge');
  if (!badge) return;
  const {{ type, movedCount, lostCount, newCount, mixed }} = classification;
  // Mixed rows: parent always shows → Move (the lost block is owned by the sub-row)
  const displayType = mixed ? 'move' : type;
  badge.className = `row-badge rb-${{displayType}}`;
  badge.textContent = _badgeLabels[displayType] || '?';
  let counts = '';
  if (mixed)                   counts = ` (${{movedCount}} moved — ${{lostCount}} lost split below)`;
  else if (type === 'move')    counts = ` (${{movedCount}} line${{movedCount!==1?'s':''}} moved)`;
  else if (type === 'lost')    counts = ` (${{lostCount}} line${{lostCount!==1?'s':''}} not arrived)`;
  else if (type === 'anomaly') counts = newCount ? ` (${{newCount}} unexpected)` : '';
  const emptyDetail = (displayType === 'empty' && classification.emptyReason)
    ? ` — ${{classification.emptyReason}}` : '';
  badge.title = (_badgeTitles[displayType] || displayType) + counts + emptyDetail;
  // Mark destination cell for lost rows — "intended but not confirmed"
  const destCell = tr.querySelector('.dest-col');
  if (destCell) {{
    if (type === 'lost' || (type === 'empty' && !mixed)) {{
      destCell.style.opacity = '0.45';
      destCell.title = 'Intended destination — content was NOT confirmed moved here';
    }} else {{
      destCell.style.opacity = '';
      destCell.title = destCell.querySelector('a')?.textContent || '';
    }}
  }}
  // Populate count cell
  const countCell = tr.querySelector('.count-col');
  if (countCell) {{
    if (mixed)                   {{ countCell.textContent = `${{movedCount}}+${{lostCount}}`; countCell.title = `${{movedCount}} moved, ${{lostCount}} lost`; }}
    else if (type === 'move')    {{ countCell.textContent = movedCount; countCell.title = `${{movedCount}} lines moved`; countCell.style.color = '#3fb950'; }}
    else if (type === 'lost')    {{ countCell.textContent = lostCount; countCell.title = `${{lostCount}} lines not arrived`; countCell.style.color = '#f85149'; }}
    else if (type === 'anomaly') {{ countCell.textContent = newCount ? `+${{newCount}}` : '+?'; countCell.title = `${{newCount}} unexpected lines`; countCell.style.color = '#e3b341'; }}
    else                         {{ countCell.textContent = '·'; countCell.style.color = '#484f58'; }}
  }}
  // Lost/anomaly/empty badges are clickable — open the modal directly
  if (displayType === 'lost' || displayType === 'anomaly' || displayType === 'empty') {{
    badge.style.cursor = 'pointer';
    badge.onclick = (e) => {{ e.stopPropagation(); showSectionModal(idx); }};
  }} else {{
    badge.style.cursor = '';
    badge.onclick = null;
  }}
  tr.dataset.rowType = displayType;
  if (activeType !== 'all' && displayType !== activeType) tr.style.display = 'none';
  // Inject synthetic Lost sub-row (idempotent — guard inside)
  if (mixed) injectMixedLostSubRow(idx, lostCount);
}}

// ── Layer 2: Row integrity validation ─────────────────────────────────────
function annotateRowWarnings(idx, issues) {{
  if (!issues || !issues.length) return;
  _rowValidation.set(idx, issues);
  const tr = document.querySelector(`tr[data-row-idx="${{idx}}"]`);
  if (!tr) return;
  // Insert ⚠ span next to the badge, avoid duplicates
  if (tr.querySelector('.row-warn')) return;
  const badgeCell = tr.querySelector('td:first-child');
  if (!badgeCell) return;
  const span = document.createElement('span');
  span.className = 'row-warn';
  span.textContent = '⚠';
  span.title = issues.join('\\n');
  badgeCell.appendChild(span);
}}

function validateRowIntegrity(idx, row, seen) {{
  const issues = [];
  if (!row) return;
  const diffLower = DIFF_TEXT.toLowerCase();

  // V-R1: source_file appears in DIFF_TEXT
  const srcStem = (row.source_file || '').split('/').pop().toLowerCase();
  if (srcStem && !diffLower.includes(srcStem)) {{
    issues.push(`V-R1: source_file '${{srcStem}}' not found in diff`);
  }}

  // V-R2: destination (normalized) appears in DIFF_TEXT
  const destRaw = (row.destination || '').replace(/\\[\\[([^\\]]+)\\]\\]/g, '$1').trim().replace(/\\.md$/, '');
  const destStem = (destRaw.split('/').pop() + '.md').toLowerCase();
  if (destStem && destStem !== '.md' && !diffLower.includes(destStem)) {{
    issues.push(`V-R2: destination '${{destStem}}' not found in diff`);
  }}

  // V-R3: section name found as real header (srcResult.matched == false means inferred)
  const cached = _rowClassifications.get(idx);
  // We re-run extractSectionLines to check .matched — use cached result if classifyRow already ran
  // classifyRow stores result but not srcResult.matched; re-check via a lightweight extract
  const sectionName = (row.section || '').replace(/^#+\\s*/, '').trim();
  const chk = extractSectionLines(row.source_file, sectionName, '-');
  if (!chk.matched) {{
    issues.push(`V-R3: section '${{sectionName}}' not found as a real header in source diff — inferred`);
  }}

  // V-R4: no duplicate (source_file × section × destination)
  const tupleKey = `${{row.source_file}}|${{row.section}}|${{row.destination}}`;
  if (seen.has(tupleKey)) {{
    issues.push(`V-R4: duplicate row (source_file × section × destination): ${{tupleKey}}`);
  }} else {{
    seen.set(tupleKey, idx);
  }}

  // V-R5: source_file path ≠ destination path (self-migration)
  const srcStemFull = (row.source_file || '').replace(/\\.md$/, '');
  if (srcStemFull && destRaw && srcStemFull.endsWith(destRaw)) {{
    issues.push(`V-R5: self-migration — source_file and destination resolve to the same file`);
  }}

  if (issues.length) annotateRowWarnings(idx, issues);
}}

// ── Layer 4: Cross-row consistency ────────────────────────────────────────
function validateCrossRowConsistency() {{
  const destLineOwners = new Map(); // normLine(destLine) → [idx, ...]
  const srcLineOwners  = new Map(); // normLine(srcLine)  → [idx, ...]
  const destMovedTotals = new Map(); // destStem → total moved lines claimed

  for (const [idx, pairs] of _rowMovedPairs) {{
    const row = MODAL_ROWS[idx];
    if (!row || !pairs) continue;
    const dStem = normDest(row.destination);
    if (!destMovedTotals.has(dStem)) destMovedTotals.set(dStem, 0);
    destMovedTotals.set(dStem, destMovedTotals.get(dStem) + pairs.size);
    for (const [destLine, srcLine] of pairs) {{
      const dn = normLine(destLine);
      const sn = normLine(srcLine);
      // V-C2: no destLine claimed by two rows
      if (!destLineOwners.has(dn)) destLineOwners.set(dn, []);
      destLineOwners.get(dn).push(idx);
      // V-C3: no srcLine sent to two different destinations
      if (!srcLineOwners.has(sn)) srcLineOwners.set(sn, []);
      srcLineOwners.get(sn).push(idx);
    }}
  }}

  // V-C1: per-destination total moved ≤ total added lines for that dest in diff
  // Parse added line counts per dest file from DIFF_TEXT
  const destAddedCounts = new Map(); // destStem → count of '+' content lines in diff
  let curFile = null;
  for (const line of DIFF_TEXT.split('\\n')) {{
    const fm = line.match(/^\\+\\+\\+ b\\/.*?([^\\/]+)\\.md$/);
    if (fm) {{ curFile = fm[1]; continue; }}
    if (line.startsWith('--- ') || line.startsWith('diff ') || line.startsWith('index ') || line.startsWith('@@')) {{ continue; }}
    if (curFile && line.startsWith('+') && !line.startsWith('+++')) {{
      const c = normLine(line.slice(1));
      if (c.length > 2 && !isNoiseLine(line.slice(1))) {{
        destAddedCounts.set(curFile, (destAddedCounts.get(curFile) || 0) + 1);
      }}
    }}
  }}
  let c1count = 0;
  for (const [dStem, claimed] of destMovedTotals) {{
    const available = destAddedCounts.get(dStem) ?? 0;
    if (claimed > available) {{
      c1count++;
      _crossRowIssues.push(`V-C1: ${{dStem}} claims ${{claimed}} moved lines but diff only has ${{available}} additions`);
    }}
  }}

  let c2count = 0, c3count = 0;
  for (const [dn, idxs] of destLineOwners) {{
    const unique = [...new Set(idxs)];
    if (unique.length > 1) {{
      c2count++;
      _crossRowIssues.push(`V-C2: dest line claimed by rows ${{unique.join(', ')}}: ${{dn.slice(0, 60)}}`);
    }}
  }}
  for (const [sn, idxs] of srcLineOwners) {{
    const unique = [...new Set(idxs)];
    if (unique.length > 1) {{
      c3count++;
      _crossRowIssues.push(`V-C3: src line sent to multiple rows (${{unique.join(', ')}}): ${{sn.slice(0, 60)}}`);
    }}
  }}
  if (c1count || c2count || c3count) {{
    console.warn('[V-C] Cross-row issues:', _crossRowIssues.length, 'total', {{c1count, c2count, c3count}});
  }}
  updateValidationBanner();
}}

function updateValidationBanner() {{
  const banner = document.getElementById('validation-banner');
  if (!banner) return;
  const rowWarnCount = _rowValidation.size;
  const crossCount = _crossRowIssues.length;
  if (rowWarnCount === 0 && crossCount === 0) {{
    banner.className = 'ok';
    banner.textContent = '✓ All rows validated — no integrity issues found';
  }} else {{
    const parts = [];
    if (rowWarnCount) parts.push(`${{rowWarnCount}} row${{rowWarnCount !== 1 ? 's' : ''}} with integrity warnings (V-R)`);
    if (crossCount)   parts.push(`${{crossCount}} cross-row consistency issue${{crossCount !== 1 ? 's' : ''}} (V-C) — some destination lines may be double-claimed`);
    banner.className = 'warn';
    banner.textContent = '⚠ ' + parts.join(' · ');
  }}
}}

let _modalMovedLines = [], _modalNewLines = [], _modalCrossLines = [];
let _modalMovedPairs = new Map(); // destLine → srcLine, populated by classifyDestLines
let _modalDestGroups = []; // [{{header, lines}}] — all dest + lines with their section context

// Global removed-lines map: normLine → source filename stem (lazy, built once per page)
let _globalRemovedMap = null;
function getGlobalRemovedMap() {{
  if (_globalRemovedMap) return _globalRemovedMap;
  _globalRemovedMap = new Map();
  const rawLines = DIFF_TEXT.split('\\n');
  let curStem = '';
  for (const line of rawLines) {{
    if (line.startsWith('diff --git ')) {{
      // extract b-side filename stem
      const m = line.match(/b\\/(.+)$/);
      curStem = m ? m[1].split('/').pop().replace(/\\.md$/, '') : '';
      continue;
    }}
    if (line.startsWith('-') && line.length > 1) {{
      const n = normLine(line.slice(1));
      if (n.length > 5 && !_globalRemovedMap.has(n)) _globalRemovedMap.set(n, curStem);
    }}
  }}
  return _globalRemovedMap;
}}

// B-13: Sibling norms map — for each dest stem, the union of normLine(removed lines) from
// ALL narrative rows pointing to that dest. Used to subtract cross-row additions from the
// anomaly check: if an added line is already claimed by a sibling row's removed lines, it
// is not a true anomaly for the current row.
let _destSiblingNorms = null;
function getDestSiblingNorms() {{
  if (_destSiblingNorms) return _destSiblingNorms;
  _destSiblingNorms = new Map();
  for (const row of MODAL_ROWS) {{
    const destStem = row.destination.replace(/\\[\\[([^\\]]+)\\]\\]/g, '$1').trim().replace(/\\.md$/, '');
    const sec = row.section.replace(/^#+\\s*/, '').trim();
    const removed = extractSectionLines(row.source_file, sec, '-').lines;
    if (!_destSiblingNorms.has(destStem)) _destSiblingNorms.set(destStem, new Set());
    const norms = _destSiblingNorms.get(destStem);
    for (const l of removed) {{
      const n = normLine(l);
      if (n.length > 2 && !isNoiseLine(l)) norms.add(n);
    }}
  }}
  return _destSiblingNorms;
}}

// Walk dest file diff, grouping + lines by nearest preceding # header in context lines.
// Returns [{{header: string|null, lines: string[], lineNos: number[]}}]
function extractDestWithContext(filename) {{
  const rawLines = DIFF_TEXT.split('\\n');
  const baseName = filename.split('/').pop().toLowerCase();
  let inFile = false, curHeader = null;
  const groups = [];
  let curGroup = null;
  let curLineNo = 0;

  for (const line of rawLines) {{
    if (line.startsWith('diff --git ')) {{
      inFile = line.toLowerCase().includes(baseName);
      curHeader = null; curGroup = null;
      continue;
    }}
    if (!inFile || line.startsWith('+++') || line.startsWith('---') || line.startsWith('index')) continue;
    if (line.startsWith('@@')) {{
      const m = line.match(/@@ -\\d+(?:,\\d+)? \\+(\\d+)(?:,\\d+)? @@/);
      if (m) curLineNo = parseInt(m[1], 10) - 1;
      curGroup = null;
      continue;
    }}
    const type = line.length ? line[0] : ' ';
    if (type !== '+' && type !== '-' && type !== ' ') continue;
    const content = line.slice(1);

    if (type === ' ') {{
      curLineNo++;
      if (/^#+\\s/.test(content)) curHeader = content;
      curGroup = null;
    }} else if (type === '+') {{
      curLineNo++;
      if (/^#+\\s/.test(content)) {{
        curHeader = content;
        curGroup = null;
      }} else {{
        if (!curGroup || curGroup.header !== curHeader) {{
          curGroup = {{ header: curHeader, lines: [], lineNos: [] }};
          groups.push(curGroup);
        }}
        curGroup.lines.push(content);
        curGroup.lineNos.push(curLineNo);
      }}
    }} else {{
      curGroup = null; // deleted line breaks adjacency
    }}
  }}
  return groups;
}}

function renderDestGroups(groups, lineSet, cls, pairIds) {{
  let html = '';
  for (const g of groups) {{
    const idxs = g.lines.map((l, i) => i).filter(i => lineSet.has(g.lines[i]));
    if (!idxs.length) continue;
    if (g.header) {{
      html += `<div class="diff-ctx-hdr">${{esc(g.header)}}</div><div class="diff-ctx-skip">…</div>`;
    }}
    html += idxs.map(i => {{
      const lno = g.lineNos?.[i];
      const lnoHtml = lno ? `<span class="line-no">${{lno}}</span>` : '';
      const pid = pairIds?.get(g.lines[i]);
      const pidAttr = pid != null ? ` data-pair-id="${{pid}}"` : '';
      return `<div class="diff-line ${{cls}}"${{pidAttr}}>${{lnoHtml}}${{esc(g.lines[i])}}</div>`;
    }}).join('');
  }}
  return html || '<div class="modal-empty">No lines in this category</div>';
}}

// Render source lines grouped by the destination section each landed in.
// Mirrors renderDestGroups but shows srcLine (via movedPairs) instead of destLine.
function renderSrcGrouped(destGroups, movedSet, movedPairs, srcLineNos, pairIds) {{
  let html = '';
  const renderedSrc = new Set(); // prevent same source line appearing under multiple dest sections
  for (const g of destGroups) {{
    const srcLines = [];
    for (const destLine of g.lines) {{
      if (!movedSet.has(destLine)) continue;
      const srcLine = movedPairs.get(destLine) || destLine;
      if (renderedSrc.has(srcLine)) continue;
      renderedSrc.add(srcLine);
      srcLines.push(srcLine);
    }}
    if (!srcLines.length) continue;
    if (g.header) {{
      html += `<div class="diff-ctx-hdr">${{esc(g.header)}}</div><div class="diff-ctx-skip">…</div>`;
    }}
    html += srcLines.map(l => {{
      const lno = srcLineNos?.get(l);
      const lnoHtml = lno ? `<span class="line-no">${{lno}}</span>` : '';
      const pid = pairIds?.get(l);
      const pidAttr = pid != null ? ` data-pair-id="${{pid}}"` : '';
      return `<div class="diff-line removed"${{pidAttr}}>${{lnoHtml}}${{esc(l)}}</div>`;
    }}).join('');
  }}
  return html || '<div class="modal-empty">No source lines matched</div>';
}}

function switchDestTab(type, btn) {{
  document.querySelectorAll('.mpanel-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  const lines = type === 'moved' ? _modalMovedLines : _modalNewLines;
  const cls   = type === 'moved' ? 'added' : 'new-content';
  document.getElementById('modal-dest-lines').innerHTML = renderDestGroups(_modalDestGroups, new Set(lines), cls);
}}

function showSectionModal(idx, focusLost = false) {{
  const row = MODAL_ROWS[idx];
  if (!row) return;
  // Auto-mode flags: lost → focusLost single panel; anomaly → focusAnomaly single panel
  let focusAnomaly = false;
  if (!focusLost) {{
    const cached = _rowClassifications.get(idx);
    if (cached && cached.type === 'lost' && !cached.mixed) focusLost = true;
    if (cached && cached.type === 'empty') focusLost = true;
    if (cached && cached.type === 'anomaly') focusAnomaly = true;
  }}

  const sectionName = row.section.replace(/^#+\\s*/, '').trim();
  let destRaw = row.destination.replace(/\\[\\[([^\\]]+)\\]\\]/g, '$1').trim().replace(/\\.md$/, '');

  const srcResult  = extractSectionLines(row.source_file, sectionName, '-');
  let removedLines = srcResult.lines;

  const destFile = allParsedFiles.find(f => {{
    const stem = (f.filename || '').split('/').pop().replace(/\\.md$/, '');
    return stem === destRaw || (f.filename || '').endsWith(destRaw + '.md');
  }});
  _modalDestGroups = destFile ? extractDestWithContext(destFile.filename) : [];
  // V-47: scope added lines to the matching section in dest first; fall back to full file.
  // V-47a: sectionFound=true when section was located (exact or fuzzy) — empty scoped result is correct.
  const _destFilenameM = destFile ? destFile.filename : (destRaw + '.md');
  const _destSectionM = extractSectionLines(_destFilenameM, sectionName, '+');
  const addedLines = (_destSectionM.lines.length > 0 || _destSectionM.sectionFound)
    ? _destSectionM.lines
    : _modalDestGroups.flatMap(g => g.lines);

  // Section header not found (synthetic section name) — infer removed lines by
  // content-matching ALL source removed lines against what landed in the destination.
  let _allSrcResult = null;
  if (!srcResult.matched && addedLines.length > 0) {{
    _allSrcResult = extractSectionLines(row.source_file, null, '-');
    const allSrcLines = _allSrcResult.lines;
    const destNorms = new Set(addedLines.map(normLine).filter(s => s.length > 5));
    removedLines = allSrcLines.filter(l => {{
      const n = normLine(l);
      if (n.length < 5) return false;
      if (destNorms.has(n)) return true;
      return [...destNorms].some(dn => {{
        const pLen = Math.min(40, Math.min(n.length, dn.length));
        return pLen >= 10 && (n.startsWith(dn.slice(0, pLen)) || dn.startsWith(n.slice(0, pLen)));
      }});
    }});
  }}

  // ── Line classification mental model ────────────────────────────────────
  // Each breadcrumb row = one (source_date × section) → destination pair.
  // The modal answers: "did THIS row's chunk land at the destination?"
  //
  // Moved   = lines removed from THIS source that appear in the destination.
  //           These confirm the sweep worked for this specific row.
  //
  // Cross   = lines in the destination that came from a DIFFERENT source file.
  //           If that other source has its own breadcrumb row → it shows as
  //           Moved in THAT row's modal. Cross only matters when no breadcrumb
  //           accounts for it = a sweep that happened without a record = anomaly.
  //           Cross lines are NOT shown in this modal at all.
  //
  // New     = lines in the destination with no match in ANY removed lines
  //           across the entire diff. Truly net-new content. Anomaly if unexpected.
  //
  // Noise   = formatting artifacts (code fences, empty checkboxes, HRs) that
  //           appear as +lines due to section restructuring. Not real content.
  // ─────────────────────────────────────────────────────────────────────────

  const {{ moved, newContent, movedPairs }} = classifyDestLines(removedLines, addedLines);
  _modalMovedLines = moved;
  _modalMovedPairs = movedPairs;

  // ── Validation pass ────────────────────────────────────────────────────────
  // Verify every moved pair: destLine must norm-match its srcLine, and srcLine
  // must actually be present in removedLines. Flags bad pairs so phantom matches
  // never silently inflate the "N lines confirmed moved" count.
  const removedSet = new Set(removedLines);
  const badPairs = [];
  for (const [destLine, srcLine] of movedPairs) {{
    if (!removedSet.has(srcLine)) {{
      badPairs.push({{ reason: 'src not in removed', destLine, srcLine }});
      continue;
    }}
    const dn = normLine(destLine), sn = normLine(srcLine);
    const db = bodyText(dn), sb = bodyText(sn);
    const pLen = Math.min(50, Math.min(dn.length, sn.length));
    const bLen = Math.min(40, Math.min(db.length, sb.length));
    const passes =
      dn === sn ||
      (pLen >= 10 && (dn.startsWith(sn.slice(0, pLen)) || sn.startsWith(dn.slice(0, pLen)))) ||
      (sb.length >= 8 && db.length >= 8 && bLen >= 8 &&
        (db.startsWith(sb.slice(0, bLen)) || sb.startsWith(db.slice(0, bLen))));
    if (!passes) badPairs.push({{ reason: 'norm mismatch', destLine, srcLine }});
  }}
  if (badPairs.length > 0) {{
    console.warn('[sweep-review] validation: bad moved pairs for row', idx, badPairs);
  }}

  // Separate New from Cross; drop noise from both.
  // Cross lines are retained internally for future anomaly detection but not displayed.
  const globalMap = getGlobalRemovedMap();
  const srcStem = row.source_file.split('/').pop().replace(/\\.md$/, '');

  _modalCrossLines = [];
  _modalNewLines = [];
  for (const line of newContent) {{
    if (isNoiseLine(line)) continue;
    const n = normLine(line);
    const fromStem = globalMap.get(n);
    if (fromStem && fromStem !== srcStem) {{
      _modalCrossLines.push(line);
    }} else {{
      _modalNewLines.push(line);
    }}
  }}

  // Source panel — use inferred lines when header match failed but content inference succeeded
  const srcName = `<span style="color:#e6edf3;font-family:monospace;font-size:11px">${{esc(row.source_file.split('/').pop())}}</span>`;
  const didInfer = !srcResult.matched && removedLines.length > 0;
  let srcBody;
  // Source tab bar — mirrors the dest panel's tab bar height for alignment
  const inferTag = didInfer
    ? `<span style="color:#8b949e;font-size:10px;margin-left:8px">⚙ inferred</span>`
    : '';
  const srcTabBar = `<div class="modal-panel-tabs">${{inferTag}}</div>`;

  // Pair ID maps hoisted to function scope so renderDestGroups (called after this block) can use them
  let destPairIds = null, srcPairIds = null;

  if (removedLines.length > 0) {{
    // Build srcLine → lineNo map; use allSrc result in the inferred case (srcResult had no match)
    const _srcForNos = _allSrcResult || srcResult;
    const srcLineNos = new Map();
    _srcForNos.lines.forEach((l, i) => {{ if (!srcLineNos.has(l)) srcLineNos.set(l, _srcForNos.lineNos[i]); }});
    // Build pair ID maps for hover sync + click-to-scroll: same ID on the matching src and dest line
    destPairIds = new Map(); srcPairIds = new Map();
    let _pid = 0;
    for (const [destLine, srcLine] of movedPairs) {{
      destPairIds.set(destLine, _pid);
      srcPairIds.set(srcLine, _pid);
      _pid++;
    }}
    // Group source lines by the destination section each landed in — mirrors right panel layout
    const srcGrouped = renderSrcGrouped(_modalDestGroups, new Set(moved), movedPairs, srcLineNos, srcPairIds);
    // Lost lines: source lines that are countable but didn't arrive at destination
    const matchedSrcSet = new Set([...movedPairs.values()]);
    const lostLines = removedLines.filter(l => !matchedSrcSet.has(l) && normLine(l).length > 2 && !isNoiseLine(l));
    const isMixed = lostLines.length > 0 && moved.length > 0;
    let lostHtml = '';
    if (lostLines.length > 0) {{
      const lostLineHtml = lostLines.map(l => {{
        const lno = srcLineNos?.get(l);
        const lnoHtml = lno ? `<span class="line-no">${{lno}}</span>` : '';
        return `<div class="diff-line removed">${{lnoHtml}}${{esc(l)}}</div>`;
      }}).join('');
      if (isMixed) {{
        // Mixed row: prominent labeled split between moved and lost blocks
        lostHtml = `<div style="margin-top:10px;border-top:2px solid #e3b341;padding-top:6px">` +
          `<div style="color:#e3b341;font-size:11px;font-weight:600;padding:2px 0 6px">` +
          `⚡ ✗ Lost (${{lostLines.length}} line${{lostLines.length>1?'s':''}}) — not found at destination — sweep should have split this section</div>` +
          lostLineHtml + `</div>`;
      }} else {{
        lostHtml = `<div style="margin-top:8px;border-top:1px solid #30363d;padding-top:6px">` +
          `<div style="color:#f85149;font-size:10px;padding:2px 0 4px">✗ ${{lostLines.length}} line${{lostLines.length>1?'s':''}} not found at destination</div>` +
          lostLineHtml + `</div>`;
      }}
    }}
    const movedHeader = isMixed && !focusLost
      ? `<div style="color:#3fb950;font-size:11px;font-weight:600;padding:2px 0 6px">✓ Moved (${{moved.length}} line${{moved.length!==1?'s':''}}) — arrived at destination</div>`
      : '';
    if (focusLost) {{
      const cached = _rowClassifications.get(idx);
      if (cached?.type === 'empty') {{
        // Empty row — explain why, no diff lines to show
        const reason = cached.emptyReason || 'no content found';
        const emptyMsg = reason.includes('empty')
          ? `<div style="color:#f85149;padding:12px 0">⚠ Destination file was created empty — content was never written.<br><br>During the next sweep, ensure content is actually written to <strong>${{esc(destRaw)}}</strong> or route it to an existing destination.</div>`
          : `<div style="color:#e3b341;padding:12px 0">⚠ ${{esc(reason)}}<br><br>Cannot verify this row — open the source file to inspect manually.</div>`;
        srcBody = `${{srcTabBar}}<div class="diff-lines">${{emptyMsg}}</div>`;
      }} else {{
        // Lost-focus mode: render lost lines directly — no mixed-row header, no moved content
        const lostLineHtmlClean = lostLines.map(l => {{
          const lno = srcLineNos?.get(l);
          const lnoHtml = lno ? `<span class="line-no">${{lno}}</span>` : '';
          return `<div class="diff-line removed">${{lnoHtml}}${{esc(l)}}</div>`;
        }}).join('');
        const lostFocusHtml = lostLines.length > 0
          ? lostLineHtmlClean
          : '<div class="modal-empty" style="color:#6e7681">No unmatched lines found — these lines may already be in the destination file from a prior sweep.</div>';
        srcBody = `${{srcTabBar}}<div class="diff-lines">${{lostFocusHtml}}</div>`;
      }}
    }} else {{
      srcBody = `${{srcTabBar}}<div class="diff-lines">${{movedHeader}}${{srcGrouped}}${{lostHtml}}</div>`;
    }}
  }} else {{
    // No lines found — show collapsed fallback
    const allRemoved = extractSectionLines(row.source_file, null, '-').lines;
    const allHtml = allRemoved.map(l => `<div class="diff-line removed">${{esc(l)}}</div>`).join('') || '<div class="modal-empty">No removed lines in file</div>';
    srcBody = `${{srcTabBar}}<div class="modal-empty" style="color:#d29922;margin-bottom:8px">
      ⚠️ Section header "<strong>${{esc(sectionName)}}</strong>" not found — synthesized grouping name.
    </div>
    <details>
      <summary style="cursor:pointer;color:#58a6ff;font-size:12px;padding:4px 0">Show all ${{allRemoved.length}} removed lines from this file</summary>
      <div class="diff-lines" style="margin-top:6px">${{allHtml}}</div>
    </details>`;
  }}
  // ── Anomaly modal — single panel showing unexpected additions at destination ──
  if (focusAnomaly) {{
    const destName = destFile ? destFile.filename.split('/').pop() : destRaw;
    const anomalyLines = _modalNewLines.length > 0 ? _modalNewLines : addedLines.filter(l => normLine(l).length > 2 && !isNoiseLine(l));
    const anomalyHtml = anomalyLines.length > 0
      ? anomalyLines.map(l => `<div class="diff-line new-content">${{esc(l)}}</div>`).join('')
      : '<div class="modal-empty" style="color:#6e7681">No traceable additions — lines may be noise or already classified by another row.</div>';
    const anomalyPanel = `<div>
      <div class="modal-panel-hdr">Unexpected additions in destination — <span style="color:#e6edf3;font-family:monospace;font-size:11px">${{esc(destName)}}</span></div>
      <div style="color:#e3b341;font-size:10px;padding:2px 0 6px">
        + ${{anomalyLines.length}} line${{anomalyLines.length!==1?'s':''}} added with no matching source section — not from this sweep's breadcrumb.
        May be from another row, a manual edit, or a missed breadcrumb.
      </div>
      <div class="diff-lines" id="modal-dest-lines">${{anomalyHtml}}</div>
    </div>`;
    document.getElementById('modal-title').textContent = sectionName + ' → ' + normDest(row.destination) + ' — + Anomaly';
    const modalBodyEl = document.getElementById('modal-body');
    modalBodyEl.style.gridTemplateColumns = '1fr';
    modalBodyEl.innerHTML = anomalyPanel;
    document.getElementById('modal-overlay').classList.add('open');
    updateRowBadge(idx);
    return;
  }}

  const srcPanel = `<div><div class="modal-panel-hdr">Removed from source — ${{srcName}}</div>${{srcBody}}</div>`;

  // Destination panel — PURE migration view. Only shows lines confirmed moved from
  // THIS row's source. No tabs. No New, no Cross.
  // New + Cross are anomalies that will surface as separate rows in the table (Phase A).
  const destName = destFile ? destFile.filename.split('/').pop() : destRaw;
  const destHdr = `Added to destination — <span style="color:#e6edf3;font-family:monospace;font-size:11px">${{esc(destName)}}</span>`;
  const validMoved = filterValidPairs(moved, movedPairs, removedLines);
  const destBody = renderDestGroups(_modalDestGroups, new Set(validMoved), 'added', destPairIds);
  const validationWarning = badPairs.length > 0
    ? `<div style="color:#e3b341;font-size:10px;padding:2px 0 4px">⚠ ${{badPairs.length}} unverified pair${{badPairs.length>1?'s':''}} excluded</div>`
    : '';
  // Diagnose empty-panel cases so the user knows WHY nothing is shown
  const destNotInDiff = !DIFF_TEXT.toLowerCase().includes((destRaw + '.md').toLowerCase());
  const srcNotInDiff  = !DIFF_TEXT.toLowerCase().includes(row.source_file.split('/').pop().toLowerCase());
  let countLabel;
  if (validMoved.length === 0 && removedLines.length === 0 && addedLines.length === 0) {{
    // Check if dest file is in diff but empty (new empty file — index 0000000..e69de29)
    const destInDiff = !destNotInDiff;
    const destFileSection = destInDiff && (
      DIFF_TEXT.includes(`/${{destRaw}}.md\nnew file`) ||
      DIFF_TEXT.includes(`/${{destRaw}}.md b/`) && DIFF_TEXT.includes('index 0000000..e69de29')
    );
    const why = destNotInDiff
      ? `<span style="color:#e3b341;font-size:10px">⚠ destination not found in diff</span>`
      : srcNotInDiff
        ? `<span style="color:#e3b341;font-size:10px">⚠ source file not found in diff</span>`
        : destFileSection
          ? `<span style="color:#f85149;font-size:10px">⚠ destination file was created empty — content was never written</span>`
          : `<span style="color:#8b949e;font-size:10px">— no content lines found in source section</span>`;
    countLabel = `<div class="modal-panel-tabs">${{why}}</div>`;
  }} else if (validMoved.length === 0) {{
    countLabel = `<div class="modal-panel-tabs"><span style="color:#f85149;font-size:10px">✗ 0 lines confirmed moved</span>${{validationWarning}}</div>`;
  }} else {{
    const countableForMixed = removedLines.filter(l => normLine(l).length > 2 && !isNoiseLine(l));
    const totalForMixed = srcResult.matched ? countableForMixed.length : validMoved.length;
    const lostForMixed = totalForMixed - validMoved.length;
    const mixedWarning = lostForMixed > 0
      ? `<span style="color:#e3b341;font-size:10px;margin-left:8px">⚡ ${{lostForMixed}} lost — should be split into separate rows during sweep</span>`
      : '';
    countLabel = `<div class="modal-panel-tabs"><span style="color:#3fb950;font-size:10px">✓ ${{validMoved.length}} line${{validMoved.length!==1?'s':''}} confirmed moved</span>${{mixedWarning}}${{validationWarning}}</div>`;
  }}

  let destPanel;
  if (focusLost) {{
    destPanel = '';  // No destination panel for lost rows — full width for source
  }} else {{
    destPanel = `<div>
      <div class="modal-panel-hdr">${{destHdr}}</div>
      ${{countLabel}}
      <div class="diff-lines" id="modal-dest-lines">${{destBody}}</div>
    </div>`;
  }}

  const titleSuffix = focusLost ? ' — ✗ Lost lines' : ' → ' + normDest(row.destination);
  document.getElementById('modal-title').textContent = sectionName + titleSuffix;
  const modalBodyEl = document.getElementById('modal-body');
  // Lost mode: single-column full-width; normal: two-column side-by-side
  modalBodyEl.style.gridTemplateColumns = focusLost ? '1fr' : '';
  modalBodyEl.innerHTML = srcPanel + destPanel;
  // V-P6: src and dest panels should have the same number of paired lines
  if (!focusLost && !focusAnomaly) {{
    const srcPaired  = modalBodyEl.querySelectorAll('#modal-src-lines [data-pair-id]').length;
    const destPaired = modalBodyEl.querySelectorAll('#modal-dest-lines [data-pair-id]').length;
    if (srcPaired !== destPaired) console.warn('V-P6: panel pair count mismatch', {{idx, srcPaired, destPaired}});
  }}
  document.getElementById('modal-overlay').classList.add('open');

  // Update table badge — score = Moved / removedLines.length (direct) or Moved (inferred).
  // New lines in destination are a separate anomaly, not part of migration score.
  const movedCount = validMoved.length;
  const trueNewCount = _modalNewLines.length;
  const countableRemovedM = removedLines.filter(l => normLine(l).length > 2 && !isNoiseLine(l));
  const srcTotal = srcResult.matched ? countableRemovedM.length : movedCount;
  let type;
  if (destNotInDiff || srcNotInDiff) type = 'empty';
  else if (srcTotal === 0 && addedLines.length === 0) type = 'empty';
  else if (srcTotal === 0 && addedLines.length > 0) type = 'anomaly';
  else if (movedCount === srcTotal) type = 'move';  // all arrived
  else type = 'lost';                               // any missing → lost
  const lostCountM = srcTotal - movedCount;
  const mixed = type === 'lost' && movedCount > 0 && lostCountM > 0;
  const classification = {{ type, movedCount, lostCount: lostCountM, newCount: trueNewCount, mixed }};
  _rowClassifications.set(idx, classification);
  updateRowBadge(idx, classification);
}}

// ── Tab switching ──────────────────────────────────────────────────────────
function showTab(name) {{
  document.getElementById('narrative').style.display = name === 'narrative' ? '' : 'none';
  document.getElementById('diff').style.display      = name === 'diff'      ? '' : 'none';
  document.getElementById('sidebar').style.display   = name === 'diff'      ? '' : 'none';
  document.getElementById('filter-bar').style.display = name === 'narrative' ? '' : 'none';
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.textContent.includes(name === 'narrative' ? 'Narrative' : 'Diff')));
}}

// ── Domain helpers ─────────────────────────────────────────────────────────
function inferDomain(dest) {{
  if (/🏢|ServiceNow/.test(dest)) return 'work';
  if (/👥|EarlBear/.test(dest))   return 'earlbear';
  if (/☕|NaqshCoffee/.test(dest)) return 'coffee';
  if (/🏡|Personal/.test(dest))   return 'personal';
  return 'other';
}}

function normDest(dest) {{
  let s = dest.replace(/\\[\\[([^\\]]+)\\]\\]/g, '$1');
  const slash = s.lastIndexOf('/');
  if (slash >= 0) s = s.slice(slash + 1);
  return s.replace(/\\.md$/, '') || dest;
}}

let activeDomain = 'all';
let activeType = 'all';

function setDomain(d) {{
  activeDomain = d;
  activeType = 'all'; // reset type filter on domain change — indices will shift
  document.querySelectorAll('.domain-chip').forEach(c =>
    c.classList.toggle('active', c.dataset.domain === d));
  document.querySelectorAll('.type-chip').forEach(c =>
    c.classList.toggle('active', c.dataset.type === 'all'));
  renderNarrative();
}}

function setType(t) {{
  activeType = t;
  document.querySelectorAll('.type-chip').forEach(c =>
    c.classList.toggle('active', c.dataset.type === t));
  // Show/hide rows by their current classified type (no re-render needed)
  document.querySelectorAll('tr[data-row-idx], tr[data-mixed-lost-for]').forEach(tr => {{
    const rowType = tr.dataset.rowType || 'pending';
    tr.style.display = (t === 'all' || rowType === t) ? '' : 'none';
  }});
  // Also hide/show day separator rows — hide if all their rows are hidden
  document.querySelectorAll('tr.day-sep-row').forEach(sep => {{
    let next = sep.nextElementSibling;
    let anyVisible = false;
    while (next && !next.classList.contains('day-sep-row')) {{
      if (next.style.display !== 'none' && !next.classList.contains('mixed-lost-sub-row') && !next.classList.contains('src-sep-row')) anyVisible = true;
      next = next.nextElementSibling;
    }}
    sep.style.display = anyVisible ? '' : 'none';
  }});
  // Also hide/show src-sep-row — hide if all following rows (until next sep) are hidden
  document.querySelectorAll('tr.src-sep-row').forEach(sep => {{
    let next = sep.nextElementSibling;
    let anyVisible = false;
    while (next && !next.classList.contains('day-sep-row') && !next.classList.contains('src-sep-row')) {{
      if (next.style.display !== 'none' && !next.classList.contains('mixed-lost-sub-row')) anyVisible = true;
      next = next.nextElementSibling;
    }}
    sep.style.display = anyVisible ? '' : 'none';
  }});
}}

// ── Narrative renderer ─────────────────────────────────────────────────────
function renderNarrative() {{
  const el = document.getElementById('narrative');
  MODAL_ROWS.length = 0;

  if (!NARRATIVE.length) {{
    el.innerHTML = '<div class="empty">No sweep breadcrumb data found.<br>Breadcrumb tables are written to each swept Calendar note.</div>';
    showTab('diff');
    return;
  }}

  const isSepRow = r => /^-+$/.test((r.section || '').trim()) || /^-+$/.test((r.destination || '').trim());

  const rows = (activeDomain === 'all'
    ? NARRATIVE
    : NARRATIVE.filter(r => inferDomain(r.destination) === activeDomain)
  ).filter(r => !isSepRow(r));

  if (!rows.length) {{
    el.innerHTML = '<div class="empty">No sections match the selected domain filter.</div>';
    return;
  }}

  const byDate = {{}};
  rows.forEach(r => {{
    const d = r.date || 'Unknown';
    if (!byDate[d]) byDate[d] = [];
    byDate[d].push(r);
  }});

  const dayNames = {{ '1':'Mon','2':'Tue','3':'Wed','4':'Thu','5':'Fri','6':'Sat','7':'Sun' }};

  // Single table for aligned columns across all days
  let tbody = '';
  for (const [d, dayRows] of Object.entries(byDate).sort()) {{
    let label = d;
    try {{
      const dt = new Date(d + 'T12:00:00');
      const dow = dayNames[String(((dt.getDay() + 6) % 7) + 1)] || '';
      label = `${{d}} (${{dow}})`;
    }} catch(e) {{}}

    tbody += `<tr class="day-sep-row"><td colspan="7">📅 ${{esc(label)}} — ${{dayRows.length}} section${{dayRows.length !== 1 ? 's' : ''}} swept</td></tr>`;

    // Sort within day by source file so rows from the same file are adjacent
    const sortedDayRows = [...dayRows].sort((a, b) => {{
      const sa = a.source_file || '';
      const sb = b.source_file || '';
      return sa < sb ? -1 : sa > sb ? 1 : 0;
    }});

    let lastSrcStem = null;
    tbody += sortedDayRows.map(r => {{
      const idx = MODAL_ROWS.push(r) - 1;
      const srcStem = r.source_file.split('/').pop().replace(/\\.md$/, '');
      const srcUrl = `noteplan://x-callback-url/openNote?filename=${{srcStem}}`;
      let sepRow = '';
      if (srcStem !== lastSrcStem) {{
        if (lastSrcStem !== null) {{
          // thin visual break between source files within the same day
          sepRow = `<tr class="src-sep-row"><td colspan="7">📄 ${{esc(srcStem)}}</td></tr>`;
        }}
        lastSrcStem = srcStem;
      }}
      return sepRow + `<tr data-row-idx="${{idx}}">
        <td style="padding:3px 6px;text-align:center"><span class="row-badge rb-pending" title="Not yet classified">·</span></td>
        <td class="count-col" style="width:48px;text-align:center;font-size:10px;color:#484f58;font-family:monospace">—</td>
        <td class="section-col"><button class="sec-toggle" onclick="toggleSectionItems(${{idx}},this)" title="Expand items">▶</button>${{esc(r.section)}}</td>
        <td class="summary-col">${{esc(r.summary)}}</td>
        <td class="src-col"><a class="dest-link" href="${{srcUrl}}" title="${{esc(r.source_file)}}">${{srcStem}}</a></td>
        <td class="dest-col" title="${{esc(r.destination)}}"><a class="dest-link" href="${{xcallbackUrl(r.destination)}}">${{esc(normDest(r.destination))}}</a></td>
        <td style="padding:3px 6px;text-align:center"><button class="view-btn" onclick="showSectionModal(${{idx}})">⌕</button></td>
      </tr>`;
    }}).join('');
  }}

  let html = `<table class="nav-tbl">
    <thead><tr><th></th><th style="width:48px;text-align:center">#</th><th>Section</th><th>Summary</th><th>Source</th><th>Destination</th><th></th></tr></thead>
    <tbody>${{tbody}}</tbody>
  </table>`;

  // Orphaned: SOURCE Calendar files swept but with no breadcrumb rows written.
  // Exclude target notes (files that appear as destinations — content was swept INTO them).
  const sourcesWithBreadcrumbs = new Set(NARRATIVE.map(r => r.source_file));
  const destCalStems = new Set(
    NARRATIVE.map(r => normDest(r.destination)).filter(d => /^\\d{{8}}$/.test(d))
  );
  const orphaned = CHANGED_CALENDAR_FILES.filter(f => {{
    const stem = f.split('/').pop().replace(/\\.md$/, '');
    return !sourcesWithBreadcrumbs.has(f) && !destCalStems.has(stem);
  }});
  if (orphaned.length) {{
    html += `<div class="orphaned-block">
      <div class="orphaned-hdr">⚠️ ${{orphaned.length}} swept file${{orphaned.length !== 1 ? 's' : ''}} with no breadcrumb rows</div>
      <ul>${{orphaned.map(f => `<li>${{esc(f.split('/').pop())}}</li>`).join('')}}</ul>
    </div>`;
  }}

  el.innerHTML = html;
}}

// ── Copy narrative as Markdown ─────────────────────────────────────────────
function copyNarrative() {{
  const rows = activeDomain === 'all'
    ? NARRATIVE
    : NARRATIVE.filter(r => inferDomain(r.destination) === activeDomain);
  const byDate = {{}};
  rows.forEach(r => {{ if (!byDate[r.date]) byDate[r.date] = []; byDate[r.date].push(r); }});
  const lines = ['# Sweep — Narrative'];
  for (const [d, dayRows] of Object.entries(byDate).sort()) {{
    lines.push('', `## ${{d}}`, '', '| Section | Summary | Destination |', '|---|---|---|');
    dayRows.forEach(r => {{ lines.push(`| ${{r.section}} | ${{r.summary}} | ${{normDest(r.destination)}} |`); }});
  }}
  const md = lines.join('\\n');
  navigator.clipboard.writeText(md).then(() => {{
    const btn = document.getElementById('copy-btn');
    const orig = btn.textContent;
    btn.textContent = '✓ Copied';
    setTimeout(() => btn.textContent = orig, 1500);
  }}).catch(() => {{
    const w = window.open('');
    if (w) w.document.write('<pre>' + md.replace(/</g, '&lt;') + '</pre>');
  }});
}}

// ── Unified diff parser ────────────────────────────────────────────────────
function parseDiff(text) {{
  const files = [];
  let cur = null;
  let leftN = 0, rightN = 0;
  const lines = text.split('\\n');
  for (let i = 0; i < lines.length; i++) {{
    const l = lines[i];
    if (l.startsWith('diff --git ')) {{
      if (cur) files.push(cur);
      cur = {{ filename: '', hunks: [] }};
      continue;
    }}
    if (!cur) continue;
    if (l.startsWith('+++ ')) {{
      // Handle both: `+++ b/path` and `+++ "b/path"` (already decoded by Python)
      let p = l.slice(4).trim();
      if (p.startsWith('"') && p.endsWith('"')) p = p.slice(1, -1);
      if (p.startsWith('b/')) cur.filename = p.slice(2);
      // else: deleted file (+++ /dev/null) — keep filename from --- line set below
      continue;
    }}
    if (l.startsWith('--- ')) {{
      // Fallback filename source for deleted files (--- a/path, +++ /dev/null)
      if (!cur.filename) {{
        let p = l.slice(4).trim();
        if (p.startsWith('"') && p.endsWith('"')) p = p.slice(1, -1);
        if (p.startsWith('a/')) cur.filename = p.slice(2);
      }}
      continue;
    }}
    if (l.startsWith('new file')) {{ cur.isNewFile = true; continue; }}
    if (l.startsWith('index ') || l.startsWith('deleted file') || l.startsWith('old mode') || l.startsWith('new mode')) continue;
    if (l.startsWith('@@')) {{
      const m = l.match(/@@ -(\\d+)(?:,\\d+)? \\+(\\d+)(?:,\\d+)? @@/);
      if (m) {{ leftN = parseInt(m[1]); rightN = parseInt(m[2]); }}
      cur.hunks.push({{ hdr: l, left: [], right: [] }});
      continue;
    }}
    if (!cur.hunks.length) continue;
    const hunk = cur.hunks[cur.hunks.length - 1];
    if (l.startsWith('+')) {{
      hunk.right.push({{ n: rightN++, c: l.slice(1) }});
    }} else if (l.startsWith('-')) {{
      hunk.left.push({{ n: leftN++, c: l.slice(1) }});
    }} else {{
      hunk.left.push({{ n: leftN++, c: l.slice(1) }});
      hunk.right.push({{ n: rightN++, c: l.slice(1) }});
    }}
  }}
  if (cur) files.push(cur);
  return files;
}}

// ── Side-by-side renderer ──────────────────────────────────────────────────
function esc(s) {{
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

// Build map: normLine(content) → [destFilename, ...]  (all + lines across all files)
function buildMoveMap(files) {{
  const map = new Map();
  for (const f of files) {{
    for (const hunk of f.hunks) {{
      for (const r of hunk.right) {{
        const n = normLine(r.c);
        if (n.length < 6) continue;
        if (!map.has(n)) map.set(n, []);
        map.get(n).push(f.filename);
      }}
    }}
  }}
  return map;
}}

function renderHunk(hunk, srcFilename, moveMap) {{
  const llen = hunk.left.length, rlen = hunk.right.length;
  const total = Math.max(llen, rlen);
  let leftRows = '', rightRows = '';

  for (let i = 0; i < total; i++) {{
    const l = i < llen ? hunk.left[i] : null;
    const r = i < rlen ? hunk.right[i] : null;
    const isCtx = l && r && l.c === r.c;
    const lCls = isCtx ? 'ctx' : (l ? 'del' : 'ctx');
    const rCls = isCtx ? 'ctx' : (r ? 'add' : 'ctx');

    let annotation = '';
    if (!isCtx && l && lCls === 'del' && moveMap) {{
      const n = normLine(l.c);
      if (n.length >= 6) {{
        const dests = (moveMap.get(n) || []).filter(f => f !== srcFilename);
        if (dests.length > 0) {{
          const stem = dests[0].split('/').pop().replace(/\\.md$/, '');
          const cb = 'noteplan://x-callback-url/openNote?noteTitle=' + encodeURIComponent(stem);
          const label = stem.replace(/^\\S+\\s*/, '').slice(0, 28) || stem.slice(0, 28);
          annotation = `<a href="${{cb}}" class="move-badge" title="Moved to ${{esc(stem)}}">→ ${{esc(label)}}</a>`;
        }} else {{
          annotation = `<span class="lost-badge">✗ lost</span>`;
        }}
      }}
    }}

    leftRows  += `<div class="row ${{lCls}}" style="align-items:center"><span class="ln">${{l ? l.n : ''}}</span><span class="lc">${{l ? esc(l.c) : ''}}</span>${{annotation}}</div>`;
    rightRows += `<div class="row ${{rCls}}"><span class="ln">${{r ? r.n : ''}}</span><span class="lc">${{r ? esc(r.c) : ''}}</span></div>`;
  }}

  return `
    <div class="sbs">
      <div class="sbs-col">
        <div class="col-hdr">Before</div>
        <div class="row hdr"><span class="ln"></span><span class="lc">${{esc(hunk.hdr)}}</span></div>
        ${{leftRows}}
      </div>
      <div class="sbs-col">
        <div class="col-hdr">After</div>
        <div class="row hdr"><span class="ln"></span><span class="lc">${{esc(hunk.hdr)}}</span></div>
        ${{rightRows}}
      </div>
    </div>`;
}}

function renderDiffFiles(files) {{
  const sidebar = document.getElementById('sidebar');
  const diff = document.getElementById('diff');

  sidebar.innerHTML = files.map((f, fi) => {{
    const adds = f.hunks.reduce((s, h) => s + h.right.length, 0);
    const dels = f.hunks.reduce((s, h) => s + h.left.length, 0);
    const isAdd = adds > 0 && dels === 0;
    const isDel = dels > 0 && adds === 0;
    const badge = isAdd ? `<span class="badge ba">+${{adds}}</span>` :
                  isDel ? `<span class="badge bd">-${{dels}}</span>` :
                          `<span class="badge bm">~</span>`;
    const name = (f.filename || '(unknown)').split('/').pop() || f.filename || '(unknown)';
    return `<div class="fi" id="nav-${{fi}}" onclick="scrollToFile(${{fi}});setActive(${{fi}})">${{badge}}<span class="name" title="${{esc(f.filename || '')}}">${{esc(name)}}</span></div>`;
  }}).join('');

  const moveMap = buildMoveMap(files);

  diff.innerHTML = files.map((f, fi) => {{
    const adds = f.hunks.reduce((s, h) => s + h.right.length, 0);
    const dels = f.hunks.reduce((s, h) => s + h.left.length, 0);
    const hunksHtml = f.hunks.map(h => renderHunk(h, f.filename, moveMap)).join('');
    const displayName = f.filename || '(unknown file)';
    return `<div class="fd" id="file-${{fi}}">
      <div class="fdh">
        <span class="fn">${{esc(displayName)}}</span>
        <span><span style="color:#3fb950">+${{adds}}</span> <span style="color:#f85149">-${{dels}}</span></span>
      </div>
      ${{hunksHtml}}
    </div>`;
  }}).join('');
}}

function scrollToFile(fi) {{
  const el = document.getElementById('file-' + fi);
  if (el) el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
}}
function setActive(fi) {{
  document.querySelectorAll('.fi').forEach(e => e.classList.remove('active'));
  const el = document.getElementById('nav-' + fi);
  if (el) el.classList.add('active');
}}

// ── Init ──────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {{
  const statLines = STAT_TEXT.trim().split('\\n');
  document.getElementById('stat-line').textContent = statLines[statLines.length - 1] || '';

  // Date range from swept Calendar filenames (YYYYMMDD.md)
  const calDates = CHANGED_CALENDAR_FILES
    .map(f => {{ const m = f.match(/(\\d{{8}})\\.md$/); return m ? m[1] : null; }})
    .filter(Boolean).sort();
  if (calDates.length > 0) {{
    const fmt = d => `${{d.slice(0,4)}}-${{d.slice(4,6)}}-${{d.slice(6,8)}}`;
    const rangeStr = calDates.length === 1
      ? fmt(calDates[0])
      : `${{fmt(calDates[0])}} → ${{fmt(calDates[calDates.length - 1])}}`;
    document.getElementById('date-range').textContent = rangeStr;
  }}

  renderNarrative();

  allParsedFiles = parseDiff(DIFF_TEXT);
  renderDiffFiles(allParsedFiles);

  // Background scan: classify all rows in idle time, 10 per frame
  // Layer 2 (validateRowIntegrity) runs alongside each row classification.
  // Layer 4 (validateCrossRowConsistency) runs once after all rows are done.
  function classifyAllRows() {{
    let i = 0;
    const seen = new Map(); // for V-R4 duplicate check
    function batch() {{
      const end = Math.min(i + 10, MODAL_ROWS.length);
      for (; i < end; i++) {{
        const c = classifyRow(i);
        if (c) updateRowBadge(i, c);
        validateRowIntegrity(i, MODAL_ROWS[i], seen);
      }}
      if (i < MODAL_ROWS.length) {{
        requestIdleCallback(batch);
      }} else {{
        // All rows done — run cross-row consistency pass (Layer 4)
        validateCrossRowConsistency();
      }}
    }}
    if (MODAL_ROWS.length > 0) {{
      requestIdleCallback(batch);
    }} else {{
      updateValidationBanner();
    }}
  }}
  classifyAllRows();

  // Hover sync + click-to-scroll: pair src/dest lines by data-pair-id
  const modalBody = document.getElementById('modal-body');
  modalBody.addEventListener('mouseover', e => {{
    const el = e.target.closest('[data-pair-id]');
    const id = el?.dataset.pairId;
    modalBody.querySelectorAll('[data-pair-id]').forEach(n => {{
      n.classList.toggle('pair-highlight', n.dataset.pairId === id && id != null);
    }});
  }});
  modalBody.addEventListener('mouseleave', () => {{
    modalBody.querySelectorAll('.pair-highlight').forEach(n => n.classList.remove('pair-highlight'));
  }});
  modalBody.addEventListener('click', e => {{
    const el = e.target.closest('[data-pair-id]');
    if (!el) return;
    const id = el.dataset.pairId;
    const peer = [...modalBody.querySelectorAll(`[data-pair-id="${{id}}"]`)].find(n => n !== el);
    if (peer) peer.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
  }});
}});
</script>
<div id="modal-overlay" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-hdr">
      <span class="modal-title" id="modal-title"></span>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-body" id="modal-body"></div>
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTML data extraction helpers (module-level for testability)
# ---------------------------------------------------------------------------

def _extract_js_str(html: str, var: str) -> str:
    """Extract a JSON string value assigned to `var` in the snapshot HTML."""
    marker = f'const {var} = '
    idx = html.find(marker)
    if idx == -1:
        return ""
    start = idx + len(marker)
    try:
        value, _ = json.JSONDecoder().raw_decode(html, start)
        return value if isinstance(value, str) else ""
    except Exception:
        return ""


def _extract_js_val(html: str, var: str) -> object:
    """Extract a JSON array/object value assigned to `var` in the snapshot HTML."""
    marker = f'const {var} = '
    idx = html.find(marker)
    if idx == -1:
        return []
    start = idx + len(marker)
    try:
        value, _ = json.JSONDecoder().raw_decode(html, start)
        return value if isinstance(value, (list, dict)) else []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# sweep-review-compile
# ---------------------------------------------------------------------------

def cmd_sweep_review_compile(args):
    root = _np_root()
    sweeps = _sweeps_dir(root)

    date_str = args.date or date.today().strftime("%Y-%m-%d")
    run_n = args.run

    if run_n is None:
        d, n = _latest_run(sweeps, date_str)
        if d is None:
            utils.err(f"No snapshot found for {date_str}. Run sweep-review-generate first.")
            sys.exit(utils.EXIT_NOT_FOUND)
        date_str, run_n = d, n

    run_id = f"{date_str}-{run_n:02d}"
    snapshot_path = sweeps / f"{run_id}.snapshot.html"

    if not snapshot_path.exists():
        utils.err(f"Snapshot not found: {snapshot_path}")
        sys.exit(utils.EXIT_NOT_FOUND)

    # Collect all comment rounds
    comment_rounds = sorted(sweeps.glob(f"{run_id}-r*.comments.jsonl"))
    all_comments: list = []
    for cf in comment_rounds:
        try:
            for line in cf.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    all_comments.append(json.loads(line))
        except Exception:
            pass

    # Deduplicate: latest entry per anchor wins
    by_anchor: dict = {}
    for entry in all_comments:
        anchor = entry.get("anchor", "")
        if anchor:
            by_anchor[anchor] = entry

    merged_comments = list(by_anchor.values())

    # Always rebuild review.html from current source code, extracting embedded data
    # from the snapshot. This ensures latest JS/CSS + decoded emoji paths.
    snapshot_html = snapshot_path.read_text(encoding="utf-8")

    diff_text = _extract_js_str(snapshot_html, "DIFF_TEXT")
    stat_text = _extract_js_str(snapshot_html, "STAT_TEXT")
    narrative = _extract_js_val(snapshot_html, "NARRATIVE")
    changed_cal = _extract_js_val(snapshot_html, "CHANGED_CALENDAR_FILES")

    # Re-apply path decoding to fix old snapshots that stored octal-quoted paths
    diff_text = _decode_git_quoted_paths(diff_text)
    stat_text = _decode_git_quoted_paths(stat_text)

    # Extract sha from header span in snapshot
    sha_m = re.search(r'sha: ([0-9a-f]{7,40})', snapshot_html)
    sha = sha_m.group(1) if sha_m else run_id

    review_path = sweeps / f"{run_id}.review.html"
    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would write {review_path} with {len(merged_comments)} comment(s)")
        return

    # Layer 1 — Diff integrity checks (non-blocking, warns to stderr)
    for w in _validate_diff_integrity(diff_text, narrative or []):
        utils.err(f"[V-D] {w}")

    new_html = _build_snapshot_html(run_id, date_str, sha, stat_text, diff_text, merged_comments, narrative, changed_cal)
    review_path.write_text(new_html, encoding="utf-8")
    cmt_note = f"{len(merged_comments)} comment(s) from {len(comment_rounds)} round(s)" if merged_comments else "no comments"
    utils.log(f"sweep-review-compile: wrote {review_path} ({cmt_note})")


# ---------------------------------------------------------------------------
# sweep-review-squash
# ---------------------------------------------------------------------------

def cmd_sweep_review_squash(args):
    root = _np_root()
    sweeps = _sweeps_dir(root)

    date_str = args.date or date.today().strftime("%Y-%m-%d")
    run_n = args.run

    if run_n is None:
        d, n = _latest_run(sweeps, date_str)
        if d is None:
            utils.err(f"No snapshot found for {date_str}.")
            sys.exit(utils.EXIT_NOT_FOUND)
        date_str, run_n = d, n

    run_id = f"{date_str}-{run_n:02d}"
    rounds = sorted(sweeps.glob(f"{run_id}-r*.comments.jsonl"))

    if len(rounds) <= 1:
        utils.log(f"sweep-review-squash: only {len(rounds)} round(s) — nothing to squash.")
        return

    all_comments: list = []
    for cf in rounds:
        for line in cf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                all_comments.append(json.loads(line))

    # Deduplicate: latest wins
    by_anchor: dict = {}
    for entry in all_comments:
        by_anchor[entry.get("anchor", "")] = entry
    merged = list(by_anchor.values())

    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would squash {len(rounds)} rounds → {run_id}-r1.comments.jsonl ({len(merged)} unique comments)")
        return

    # Back up originals
    for cf in rounds:
        bak = Path(str(cf) + ".bak")
        cf.rename(bak)

    r1 = sweeps / f"{run_id}-r1.comments.jsonl"
    r1.write_text("\n".join(json.dumps(c) for c in merged) + "\n", encoding="utf-8")
    utils.log(f"sweep-review-squash: squashed {len(rounds)} rounds → {r1} ({len(merged)} unique comments)")


# ---------------------------------------------------------------------------
# sweep-review-list
# ---------------------------------------------------------------------------

def cmd_sweep_review_list(args):
    root = _np_root()
    sweeps = _sweeps_dir(root)

    date_filter = args.date

    snapshots = sorted(sweeps.glob("*.snapshot.html"))
    if not snapshots:
        utils.log("No sweep reviews found.")
        return

    # Group by date
    by_date: dict[str, list] = {}
    for s in snapshots:
        m = re.match(r'(\d{4}-\d{2}-\d{2})-(\d+)\.snapshot', s.stem)
        if not m:
            continue
        d, n = m.group(1), int(m.group(2))
        if date_filter and d != date_filter:
            continue
        by_date.setdefault(d, []).append(n)

    for d in sorted(by_date.keys(), reverse=True):
        print(f"\n{d}")
        for n in sorted(by_date[d]):
            run_id = f"{d}-{n:02d}"
            rounds = list(sweeps.glob(f"{run_id}-r*.comments.jsonl"))
            compiled = (sweeps / f"{run_id}.review.html").exists()
            compiled_mark = "✓" if compiled else "·"
            rounds_str = f"{len(rounds)} comment round(s)" if rounds else "no comments"
            print(f"  [{compiled_mark}] run {n:02d}  {run_id}  {rounds_str}")


# ---------------------------------------------------------------------------
# sweep-review-open
# ---------------------------------------------------------------------------

def cmd_sweep_review_open(args):
    root = _np_root()
    sweeps = _sweeps_dir(root)

    date_str = args.date or date.today().strftime("%Y-%m-%d")
    run_n = args.run

    if run_n is None:
        d, n = _latest_run(sweeps, date_str)
        if d is None:
            utils.err(f"No snapshot found for {date_str}.")
            sys.exit(utils.EXIT_NOT_FOUND)
        date_str, run_n = d, n

    run_id = f"{date_str}-{run_n:02d}"

    if args.snapshot:
        path = sweeps / f"{run_id}.snapshot.html"
    else:
        review = sweeps / f"{run_id}.review.html"
        path = review if review.exists() else sweeps / f"{run_id}.snapshot.html"

    if not path.exists():
        utils.err(f"File not found: {path}")
        sys.exit(utils.EXIT_NOT_FOUND)

    import subprocess as sp
    sp.run(["open", str(path)])
    utils.log(f"sweep-review-open: opened {path}")


# ---------------------------------------------------------------------------
# sweep-review-export
# ---------------------------------------------------------------------------

def cmd_sweep_review_export(args):
    """Export raw sweep data (diff, narrative, stats, rows) as JSON to stdout or a file."""
    root = _np_root()
    sweeps = _sweeps_dir(root)

    date_str = args.date or date.today().strftime("%Y-%m-%d")
    run_n = args.run

    if run_n is None:
        d, n = _latest_run(sweeps, date_str)
        if d is None:
            utils.err(f"No snapshot found for {date_str}.")
            sys.exit(utils.EXIT_NOT_FOUND)
        date_str, run_n = d, n

    run_id = f"{date_str}-{run_n:02d}"
    snap_path = sweeps / f"{run_id}.snapshot.html"
    if not snap_path.exists():
        utils.err(f"Snapshot not found: {snap_path}. Run sweep-review-generate first.")
        sys.exit(utils.EXIT_NOT_FOUND)

    html = snap_path.read_text(encoding="utf-8")
    diff_text  = _extract_js_str(html, "DIFF_TEXT")
    stat_text  = _extract_js_str(html, "STAT_TEXT")
    narrative  = _extract_js_val(html, "NARRATIVE")
    modal_rows = _extract_js_val(html, "MODAL_ROWS")
    cal_files  = _extract_js_val(html, "CHANGED_CALENDAR_FILES")

    # Extract sweep SHA from snapshot comment header
    sha_m = re.search(r'sha:\s*([0-9a-f]{7,40})', html)
    sweep_sha = sha_m.group(1) if sha_m else ""

    payload = {
        "run_id":   run_id,
        "date":     date_str,
        "sha":      sweep_sha,
        "stats":    stat_text,
        "diff":     diff_text,
        "narrative": narrative,
        "modal_rows": modal_rows,
        "changed_calendar_files": cal_files,
    }

    out = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(out, encoding="utf-8")
        utils.log(f"sweep-review-export: wrote {out_path}")
    else:
        print(out)


# ---------------------------------------------------------------------------
# sweep-review-audit
# ---------------------------------------------------------------------------

def _norm_line(s: str) -> str:
    """Python mirror of JS normLine — strips date tags, hashtags, collapses whitespace."""
    import re as _re
    s = _re.sub(r'>\d{4}-\d{2}-\d{2}', '', s)
    s = _re.sub(r'#\w+', '', s)
    s = _re.sub(r'\s+', ' ', s).strip().lower()
    return s

def _find_dest_on_disk(root: Path, dest_stem: str) -> Path | None:
    """Search for a destination .md file by stem anywhere under the Notes dir."""
    notes = root / "Notes"
    if not notes.exists():
        return None
    target = dest_stem.lower() + '.md'
    for p in notes.rglob('*.md'):
        if p.name.lower() == target:
            return p
    return None

def _fuzzy_match(a: str, b: str) -> bool:
    """Python mirror of classifyDestLines prefix/body matching."""
    if not a or not b:
        return False
    if a == b:
        return True
    p = min(50, min(len(a), len(b)))
    if p >= 10 and (a.startswith(b[:p]) or b.startswith(a[:p])):
        return True
    body_a = re.sub(r'^[-*]\s*\[[x ]\]\s*', '', a, flags=re.I).strip()
    body_b = re.sub(r'^[-*]\s*\[[x ]\]\s*', '', b, flags=re.I).strip()
    if len(body_a) >= 8 and len(body_b) >= 8:
        bl = min(40, min(len(body_a), len(body_b)))
        if bl >= 8 and (body_a.startswith(body_b[:bl]) or body_b.startswith(body_a[:bl])):
            return True
    return False

def _is_noise(line: str) -> bool:
    if re.match(r'^#+\s', line.strip()): return True   # markdown headings never move
    n = _norm_line(line)
    if len(n) <= 3: return True
    if re.match(r'^`+\w*$', n): return True
    if re.match(r'^-{2,}$', n) or re.match(r'^—+$', n): return True
    if re.match(r'^[-*]\s*\[\s*\]\s*$', n): return True
    return False


def _validate_diff_integrity(diff_text: str, narrative: list) -> list[str]:
    """Layer 1 — Diff integrity checks. Returns list of warning strings."""
    warnings: list[str] = []

    # V-D1: diff is non-empty
    if not diff_text or not diff_text.strip():
        warnings.append("V-D1: diff_text is empty — report has no diff data")
        return warnings  # further checks meaningless

    # V-D2: at least one Calendar file (YYYYMMDD.md) appears in diff
    if not re.search(r'\b\d{8}\.md\b', diff_text):
        warnings.append("V-D2: no Calendar file (YYYYMMDD.md) found in diff — sweep may not have touched any daily notes")

    # V-D3: all @@ hunk headers match @@ -N[,N] +N[,N] @@
    for hunk in re.findall(r'@@[^@\n]*@@', diff_text):
        if not re.match(r'^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@', hunk):
            warnings.append(f"V-D3: malformed hunk header: {hunk!r}")

    # V-D4: no residual octal escapes (\NNN) in filenames after path decoding
    for line in diff_text.splitlines():
        if line.startswith('diff --git ') or line.startswith('+++ ') or line.startswith('--- '):
            if re.search(r'\\[0-7]{3}', line):
                warnings.append(f"V-D4: residual octal escape in filename line: {line!r}")

    # V-D5: every source_file in narrative rows appears in the diff
    for row in (narrative or []):
        sf = row.get('source_file', '')
        if not sf:
            continue
        stem = sf.split('/')[-1]
        if stem and stem.lower() not in diff_text.lower():
            warnings.append(f"V-D5: source_file '{stem}' not found in diff")

    return warnings

def _parse_diff_sections(diff_text: str) -> dict:
    """Parse diff into {filename: {removed: [lines], added: [lines]}}."""
    files: dict = {}
    cur: dict | None = None
    for line in diff_text.splitlines():
        if line.startswith('diff --git '):
            m = re.search(r'b/(.+)$', line)
            fname = m.group(1) if m else ''
            cur = {'removed': [], 'added': []}
            files[fname] = cur
        elif cur is None:
            continue
        elif line.startswith('---') or line.startswith('+++') or line.startswith('index') or line.startswith('@@'):
            continue
        elif line.startswith('-') and len(line) > 1:
            cur['removed'].append(line[1:])
        elif line.startswith('+') and len(line) > 1:
            cur['added'].append(line[1:])
    return files


def _extract_section_lines(diff_text: str, filename: str, section_name: str, line_type: str) -> list[str]:
    """Python mirror of JS extractSectionLines — returns lines of given type within a section."""
    base = filename.split('/')[-1].lower()
    name_lower = section_name.lower().strip() if section_name else None
    in_file = False
    in_section = section_name is None
    section_level = 0
    result = []

    def header_matches(content: str) -> bool:
        h = re.sub(r'^#+\s*', '', content).strip().lower()
        n = name_lower or ''
        if h == n: return True
        if h.startswith(n + ' ') or h.startswith(n + ':'): return True
        if n.startswith(h + ' ') or n.startswith(h + ':'): return False
        # Last-token check: query's last token (≥3 chars) as whole word in header
        q_toks = [w for w in n.split() if len(w) >= 3]
        if q_toks:
            last = re.escape(q_toks[-1])
            if re.search(rf'\b{last}\b', h): return True
        return False

    for raw in diff_text.splitlines():
        if raw.startswith('diff --git '):
            in_file = base in raw.lower()
            in_section = section_name is None
            section_level = 0
            continue
        if not in_file:
            continue
        if raw.startswith('+++') or raw.startswith('---') or raw.startswith('index') or raw.startswith('@@'):
            continue
        if not raw:
            continue
        t = raw[0]
        if t not in ('+', '-', ' '):
            continue
        content = raw[1:]
        hm = re.match(r'^(#+)\s', content)
        depth = len(hm.group(1)) if hm else 0

        if section_name is not None:
            if depth > 0 and header_matches(content):
                in_section = True
                section_level = depth
            elif in_section and depth > 0 and depth <= section_level and t != '+':
                in_section = False

        if in_section and t == line_type:
            result.append(content)

    # Fallback: if section not found, return empty (caller handles inferred match)
    return result


def _v47a_score(hdr: str, name_lower: str) -> float:
    """Python mirror of JS v47aScore: score a candidate diff header for fuzzy section matching.
    Returns 999 for exact/existing sectionHeaderMatches-style hit, or a token-overlap score.
    Caller accepts if score >= 0.5.
    """
    hdr_norm = re.sub(r'^#+\s*', '', hdr).strip().lower()
    n, h = name_lower.strip(), hdr_norm
    # Mirror of header_matches (existing sectionHeaderMatches logic)
    if h == n: return 999.0
    if h.startswith(n + ' ') or h.startswith(n + ':'): return 999.0
    if n.startswith(h + ' ') or n.startswith(h + ':'): return 0.0  # parent — reject
    q_toks_exact = [w for w in n.split() if len(w) >= 3]
    if q_toks_exact:
        last = re.escape(q_toks_exact[-1])
        if re.search(rf'\b{last}\b', h): return 999.0
    # Token-level de-plural prefix overlap
    q_toks = [w for w in re.split(r'[\s/\-,\.]+', n) if len(w) >= 3]
    h_toks = [w for w in re.split(r'[\s/\-,\.]+', h) if len(w) >= 3]
    if not q_toks or not h_toks:
        return 0.0
    score = 0.0
    for qt in q_toks:
        qt_s = qt[:-1] if len(qt) > 3 and qt.endswith('s') else qt
        best = 0.0
        for ht in h_toks:
            ht_s = ht[:-1] if len(ht) > 3 and ht.endswith('s') else ht
            s = 0.0
            if qt == ht or qt_s == ht_s:
                s = 1.0
            elif len(qt_s) >= 3 and ht.startswith(qt_s):
                s = 0.7
            elif len(ht_s) >= 3 and qt.startswith(ht_s):
                s = 0.7
            if s > best:
                best = s
        score += best
    return score


def _extract_section_lines_scoped(diff_text: str, filename: str, section_name: str,
                                   line_type: str) -> tuple[list[str], bool]:
    """Python mirror of JS extractSectionLines with V-47a fuzzy fallback.
    Returns (lines, section_found) where section_found=True if the section was located
    (exact or fuzzy) — callers should NOT fall back to full-file when section_found=True
    even if lines is empty (empty section is a correct, non-anomalous result).
    """
    if not section_name:
        return _extract_section_lines(diff_text, filename, None, line_type), True

    base = filename.split('/')[-1].lower()
    name_lower = section_name.lower().strip()
    seen_headers: list[str] = []

    def header_matches_py(content: str, active_name: str) -> bool:
        h = re.sub(r'^#+\s*', '', content).strip().lower()
        n = active_name
        if h == n: return True
        if h.startswith(n + ' ') or h.startswith(n + ':'): return True
        if n.startswith(h + ' ') or n.startswith(h + ':'): return False
        q_toks = [w for w in n.split() if len(w) >= 3]
        if q_toks:
            last = re.escape(q_toks[-1])
            if re.search(rf'\b{last}\b', h): return True
        return False

    def do_extract(active_name: str, strict_boundary: bool) -> tuple[list[str], bool]:
        nonlocal seen_headers
        in_file = False
        in_section = False
        section_level = 0
        section_entered = False
        res: list[str] = []
        for raw in diff_text.splitlines():
            if raw.startswith('diff --git '):
                in_file = base in raw.lower()
                in_section = False
                section_level = 0
                continue
            if not in_file:
                continue
            if raw.startswith('+++') or raw.startswith('---') or raw.startswith('index') or raw.startswith('@@'):
                continue
            if not raw:
                continue
            t = raw[0]
            if t not in ('+', '-', ' '):
                continue
            content = raw[1:]
            hm = re.match(r'^(#+)\s', content)
            depth = len(hm.group(1)) if hm else 0
            # Collect headers for V-47a on first pass (active_name == name_lower), skip removed
            if active_name == name_lower and in_file and depth >= 2 and t != '-':
                seen_headers.append(content)
            if depth > 0 and header_matches_py(content, active_name):
                in_section = True
                section_level = depth
                section_entered = True
            elif in_section and depth > 0 and depth <= section_level and (strict_boundary or t != '+'):
                in_section = False
            if in_section and t == line_type:
                res.append(content)
        return res, section_entered

    result, section_entered = do_extract(name_lower, False)
    if result or section_entered:
        return result, section_entered or bool(result)

    # V-47a: fuzzy matching — only when exact match found nothing and section was never entered
    unique_headers = list(dict.fromkeys(seen_headers))
    if not unique_headers:
        return [], False  # flat file — no ## headers in diff block

    best_score, best_hdr = 0.0, None
    for hdr in unique_headers:
        sc = _v47a_score(hdr, name_lower)
        if sc > best_score:
            best_score, best_hdr = sc, hdr

    if best_hdr is not None and best_score >= 0.5:
        fuzzy_name = re.sub(r'^#+\s*', '', best_hdr).strip().lower()
        result, section_entered = do_extract(fuzzy_name, True)  # strict: any header closes section
        return result, True

    return [], False

def cmd_sweep_review_audit(args):
    """Data quality audit: classify all rows, report lost lines, mixed rows, and structural issues."""
    root = _np_root()
    sweeps = _sweeps_dir(root)

    date_str = args.date or date.today().strftime("%Y-%m-%d")
    run_n = args.run
    if run_n is None:
        d, n = _latest_run(sweeps, date_str)
        if d is None:
            utils.err(f"No snapshot found for {date_str}.")
            sys.exit(utils.EXIT_NOT_FOUND)
        date_str, run_n = d, n

    run_id = f"{date_str}-{run_n:02d}"
    snap_path = sweeps / f"{run_id}.snapshot.html"
    if not snap_path.exists():
        utils.err(f"Snapshot not found: {snap_path}")
        sys.exit(utils.EXIT_NOT_FOUND)

    html = snap_path.read_text(encoding="utf-8")
    diff_text  = _extract_js_str(html, "DIFF_TEXT")
    narrative  = _extract_js_val(html, "NARRATIVE")

    if not diff_text:
        utils.err("Empty diff — nothing to audit.")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    # Build global diff index
    diff_index = _parse_diff_sections(diff_text)
    diff_lower = {k.lower(): v for k, v in diff_index.items()}

    def get_file(name: str) -> dict | None:
        stem = name.split('/')[-1].lower()
        for k, v in diff_lower.items():
            if k.endswith(stem):
                return v
        return None

    # B-13 layer 1: per-dest union of all sibling rows' removed norms.
    def _build_sibling_norms() -> dict:
        result: dict[str, set] = {}
        for r in narrative:
            d = re.sub(r'\[\[([^\]]+)\]\]', r'\1', r.get('destination', '')).strip()
            d = re.sub(r'\.md$', '', d).strip()
            sec = re.sub(r'^#+\s*', '', r.get('section', '')).strip()
            src = (r.get('source_file') or '').split('/')[-1]
            lines = _extract_section_lines(diff_text, src, sec, '-')
            norms = {_norm_line(l) for l in lines if not _is_noise(l) and len(_norm_line(l)) > 2}
            result.setdefault(d, set()).update(norms)
        return result

    # B-13 layer 2: global removed norms — all lines removed from ANY source file in diff.
    # Catches lines that were swept under an unmatched section name (V-47 scope miss).
    def _build_global_removed_norms() -> set:
        norms: set = set()
        for line in diff_text.split('\n'):
            if line.startswith('-') and len(line) > 1:
                n = _norm_line(line[1:])
                if len(n) > 5:
                    norms.add(n)
        return norms

    _sibling_norms = _build_sibling_norms()
    _global_removed_norms = _build_global_removed_norms()

    def classify_row(row: dict) -> dict:
        src_file  = (row.get('source_file') or '').split('/')[-1]
        dest_raw  = re.sub(r'\[\[([^\]]+)\]\]', r'\1', row.get('destination', '')).strip()
        dest_raw  = re.sub(r'\.md$', '', dest_raw).strip()
        section   = re.sub(r'^#+\s*', '', row.get('section', '')).strip()

        issues = []
        src_in_diff  = any(k.endswith(src_file.lower()) for k in diff_lower)
        dest_in_diff = any(k.endswith((dest_raw + '.md').lower()) for k in diff_lower)
        if not src_in_diff:  issues.append('src_not_in_diff')
        if not dest_in_diff: issues.append('dest_not_in_diff')
        if src_file.lower() == (dest_raw + '.md').lower(): issues.append('self_migration')

        if not src_in_diff or not dest_in_diff:
            return {'type': 'empty', 'issues': issues, 'moved': [], 'lost': [], 'new': []}

        # Extract SECTION-scoped removed lines (mirrors JS extractSectionLines)
        raw_removed = _extract_section_lines(diff_text, src_file, section, '-')

        # Infer from full file if section not found
        if not raw_removed:
            all_removed = _extract_section_lines(diff_text, src_file, None, '-')
            dest_added_all = _extract_section_lines(diff_text, dest_raw + '.md', None, '+')
            dest_norms_all = {_norm_line(l) for l in dest_added_all if len(_norm_line(l)) > 5}
            raw_removed = [l for l in all_removed
                           if not _is_noise(l) and len(_norm_line(l)) > 4
                           and any(_fuzzy_match(_norm_line(l), dn) for dn in dest_norms_all)]

        removed = [l for l in raw_removed if not _is_noise(l) and len(_norm_line(l)) > 2]
        if not removed:
            # B-14: newly created plan/note files have portal-generated boilerplate and
            # swept content as additions. When source has no countable removed lines and
            # the dest was created in this diff, treat as 'empty' — nothing to verify.
            _dest_stem_lower = (dest_raw.split('/')[-1] + '.md').lower()
            _dest_is_new = any(
                'new file mode' in blk
                for blk in re.split(r'(?=diff --git )', diff_text)
                if _dest_stem_lower in blk.lower()
            )
            if _dest_is_new:
                return {'type': 'empty', 'issues': issues + ['new_file'],
                        'moved': [], 'lost': [], 'new': []}
            # V-47a: try section-scoped dest extraction (fuzzy match if needed).
            # If the section was located (even if empty), don't fall back to full-file.
            dest_added, dest_section_found = _extract_section_lines_scoped(
                diff_text, dest_raw + '.md', section, '+'
            )
            if not dest_section_found:
                dest_added = _extract_section_lines(diff_text, dest_raw + '.md', None, '+')
            # B-13: subtract additions claimed by sibling rows (layer 1) OR any diff source (layer 2)
            sibling_norms = _sibling_norms.get(dest_raw, set())
            dest_content = [
                l for l in dest_added
                if not _is_noise(l) and len(_norm_line(l)) > 2
                and _norm_line(l) not in sibling_norms
                and _norm_line(l) not in _global_removed_norms
            ]
            return {'type': 'anomaly' if dest_content else 'empty', 'issues': issues,
                    'moved': [], 'lost': [], 'new': dest_content[:5]}

        # Match removed lines against destination added lines (diff only)
        dest_added = _extract_section_lines(diff_text, dest_raw + '.md', None, '+')
        dest_norms = [(_norm_line(l), l) for l in dest_added
                      if not _is_noise(l) and len(_norm_line(l)) > 2]

        moved, lost = [], []
        for src_line in removed:
            sn = _norm_line(src_line)
            matched = any(_fuzzy_match(sn, dn) for dn, _ in dest_norms)
            (moved if matched else lost).append(src_line)

        # Secondary grep: lines not found in diff may already exist in dest file on disk
        # (moved by a prior sweep — not a +line, so not in diff)
        already_present = []
        if lost:
            dest_file_path = _find_dest_on_disk(root, dest_raw)
            if dest_file_path:
                dest_text_norm = _norm_line(dest_file_path.read_text(errors='replace'))
                # Use full file text for substring search (faster than line-by-line for audit)
                dest_full = dest_file_path.read_text(errors='replace')
                dest_file_norms = {_norm_line(l) for l in dest_full.splitlines()
                                   if len(_norm_line(l)) > 4}
                truly_lost = []
                for l in lost:
                    sn = _norm_line(l)
                    if any(_fuzzy_match(sn, dn) for dn in dest_file_norms):
                        already_present.append(l)
                    else:
                        truly_lost.append(l)
                lost = truly_lost

        mixed = bool(moved and lost)
        row_type = 'move' if (moved and not lost) else 'mixed' if mixed else 'lost'
        if not lost and not moved and already_present: row_type = 'move'  # all present on disk
        if mixed: issues.append('needs_split')
        if already_present: issues.append(f'{len(already_present)} line(s) already in dest file')

        return {'type': row_type, 'issues': issues, 'moved': moved, 'lost': lost,
                'already_present': already_present, 'new': []}

    # Run audit
    sep = lambda: '─' * 60
    lines_out = [f"Sweep audit — {run_id}", sep()]

    isSep = lambda r: re.match(r'^-+$', (r.get('section') or '').strip())
    rows = [r for r in (narrative or []) if not isSep(r)]

    counts: dict = {'move': 0, 'lost': 0, 'mixed': 0, 'anomaly': 0, 'empty': 0}
    problems = []

    for row in rows:
        result = classify_row(row)
        t = result['type']
        counts[t] = counts.get(t, 0) + 1

        if result['issues'] or result['lost'] or result['new'] or result['type'] == 'mixed' or result.get('already_present'):
            problems.append((row, result))

    total = sum(counts.values())
    lines_out.append(f"  {total} rows — ✓ {counts.get('move',0)} moved  ✗ {counts.get('lost',0)} lost  ⚡ {counts.get('mixed',0)} mixed  + {counts.get('anomaly',0)} anomaly  · {counts.get('empty',0)} empty")
    lines_out.append(sep())

    if not problems:
        lines_out.append("  No issues found.")
    else:
        for row, result in problems:
            src  = row.get('source_file', '?').split('/')[-1]
            dest = re.sub(r'\[\[([^\]]+)\]\]', r'\1', row.get('destination', '?')).strip()
            sect = row.get('section', '?')
            type_label = '⚡ MIXED' if result['type'] == 'mixed' else result['type'].upper()
            lines_out.append(f"\n  {type_label}  {sect}  →  {dest}  [{src}]")
            for issue in result['issues']:
                lines_out.append(f"    ⚠  {issue.replace('_', ' ')}")
            if result['type'] == 'mixed':
                for l in result['moved'][:3]:
                    lines_out.append(f"    →  {l[:80]}")
                if len(result['moved']) > 3:
                    lines_out.append(f"    →  … {len(result['moved'])-3} more moved lines")
            for l in result['lost'][:5]:
                lines_out.append(f"    ✗  {l[:80]}")
            if len(result['lost']) > 5:
                lines_out.append(f"    ✗  … {len(result['lost'])-5} more lost lines")
            for l in result.get('already_present', [])[:3]:
                lines_out.append(f"    ✓~  {l[:80]}  (already in dest file)")
            if len(result.get('already_present', [])) > 3:
                lines_out.append(f"    ✓~  … {len(result['already_present'])-3} more already present")
            for l in result['new'][:3]:
                lines_out.append(f"    +  {l[:80]}")
            if len(result['new']) > 3:
                lines_out.append(f"    +  … {len(result['new'])-3} more new lines")

    lines_out.append('')
    report = '\n'.join(lines_out)

    if args.output:
        Path(args.output).write_text(report, encoding='utf-8')
        utils.log(f"sweep-review-audit: wrote {args.output}")
    else:
        print(report)

    # Auto-append to quality log so sweep-review-quality can track trends over time
    _append_quality_log(root, run_id, counts, problems)


def _quality_log_path(root: Path) -> Path:
    return root / "sweeps" / "quality-log.jsonl"


def _resolution_cache_path(root: Path) -> Path:
    return root / "sweeps" / "resolutions.jsonl"


def _append_quality_log(root: Path, run_id: str, counts: dict, problems: list) -> None:
    """Append one structured entry per audit run to quality-log.jsonl."""
    from datetime import datetime as _dt
    entry = {
        "run_id": run_id,
        "generated_at": _dt.now().isoformat(timespec='seconds'),
        "by_type": counts,
        "total": sum(counts.values()),
        "issues": [
            {
                "source": row.get("source_file", ""),
                "section": row.get("section", ""),
                "dest": row.get("destination", ""),
                "type": result["type"],
                "issue_tags": result.get("issues", []),
                "lost_count": len(result.get("lost", [])),
                "new_count": len(result.get("new", [])),
                "already_present_count": len(result.get("already_present", [])),
                "lost_lines": result.get("lost", [])[:3],
                "new_lines": result.get("new", [])[:3],
            }
            for row, result in problems
        ],
    }
    log_path = _quality_log_path(root)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def _load_resolutions(root: Path) -> set:
    """Load the set of (source_file, section, dest) tuples marked as resolved."""
    path = _resolution_cache_path(root)
    resolved = set()
    if not path.exists():
        return resolved
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
            resolved.add((e.get('source', ''), e.get('section', ''), e.get('dest', '')))
        except Exception:
            pass
    return resolved


# sweep-review-quality
def cmd_sweep_review_quality(args) -> None:
    """Read quality-log.jsonl across all runs and surface patterns + suggested fixes."""
    root = _np_root()
    log_path = _quality_log_path(root)

    if not log_path.exists():
        utils.err("No quality log found. Run sweep-review-audit first.")
        sys.exit(utils.EXIT_NOT_FOUND)

    entries = []
    for line in log_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass

    if not entries:
        print("Quality log is empty.")
        return

    resolutions = _load_resolutions(root)

    # Aggregate across all runs
    total_runs = len(entries)
    all_issues = [i for e in entries for i in e.get('issues', [])]
    # Filter out resolved rows
    open_issues = [
        i for i in all_issues
        if (i['source'], i['section'], i['dest']) not in resolutions
    ]

    # Count by type and tag
    from collections import Counter, defaultdict
    type_counts = Counter(i['type'] for i in open_issues)
    tag_counts  = Counter(t for i in open_issues for t in i.get('issue_tags', []))

    # Top recurring anomaly destinations
    anomaly_dests  = Counter(i['dest'] for i in open_issues if i['type'] == 'anomaly')
    # Top recurring lost sections
    lost_sections  = Counter(i['section'] for i in open_issues if i['type'] in ('lost', 'mixed'))
    # Sections where dest_not_in_diff — likely sectionHeaderMatches false match
    fp_sections    = Counter(
        i['section'] for i in open_issues if 'dest_not_in_diff' in i.get('issue_tags', [])
    )

    sep = '─' * 64
    print(f"Sweep quality report — {total_runs} run(s) in log")
    print(sep)

    # Summary
    print(f"  Open issues across all runs: {len(open_issues)}")
    print(f"  Resolved (suppressed):       {len(all_issues) - len(open_issues)}")
    print(f"  By type:  " + "  ".join(f"{t}: {n}" for t, n in type_counts.most_common()))
    if tag_counts:
        print(f"  By tag:   " + "  ".join(f"{t}: {n}" for t, n in tag_counts.most_common(5)))
    print(sep)

    # Anomaly hotspots — destinations that repeatedly receive untraced additions
    if anomaly_dests:
        print("\n  Anomaly hotspots (recurring + destinations with no source trace):")
        for dest, n in anomaly_dests.most_common(5):
            dest_clean = re.sub(r'\[\[([^\]]+)\]\]', r'\1', dest).strip()
            print(f"    + {dest_clean}  ({n}×)")
        print(f"\n  → These destinations may need their own breadcrumb rows, or the")
        print(f"    anomaly lines are from a different source file not yet covered.")

    # Lost section hotspots
    if lost_sections:
        print("\n  Lost section hotspots (sections that repeatedly lose lines):")
        for sect, n in lost_sections.most_common(5):
            print(f"    ✗ {sect}  ({n}×)")
        print(f"\n  → Check if these sections are being split during sweep.")
        print(f"    If the lines are truly lost, run /noteplan-manager:sweep-remediate.")

    # False positive patterns (dest_not_in_diff → portal showed row but dest wasn't modified)
    if fp_sections:
        print("\n  Likely false positives (dest not in diff — breadcrumb but no dest change):")
        for sect, n in fp_sections.most_common(5):
            print(f"    ⚠ {sect}  ({n}×)")
        print(f"\n  → These rows may be from stale breadcrumbs or mismatched section names.")
        print(f"    Code location: sectionHeaderMatches() in sweep_review.py")
        print(f"    Check: does the section name in the breadcrumb match any ## header in the diff?")

    # Per-run trend
    print(f"\n{sep}")
    print("  Trend (newest first):")
    for e in reversed(entries[-5:]):
        t = e.get('by_type', {})
        run_open = [i for i in e.get('issues', [])
                    if (i['source'], i['section'], i['dest']) not in resolutions]
        print(f"    {e['run_id']}  total={e['total']}  "
              f"✓{t.get('move',0)} ✗{t.get('lost',0)} ⚡{t.get('mixed',0)} +{t.get('anomaly',0)} "
              f"open_issues={len(run_open)}")

    print(f"\n  To mark a row as resolved/intentional, run:")
    print(f"    noteplan-sweep sweep-review-resolve <run_id> <section>")
    print(f"  To remediate open issues:")
    print(f"    /noteplan-manager:sweep-remediate")


# sweep-review-resolve
def cmd_sweep_review_resolve(args) -> None:
    """Mark a (source × section × dest) tuple as resolved so it won't re-appear in quality reports."""
    root = _np_root()
    log_path = _quality_log_path(root)

    if not log_path.exists():
        utils.err("No quality log found. Run sweep-review-audit first.")
        sys.exit(utils.EXIT_NOT_FOUND)

    # Find matching issues in the log
    run_id = args.run_id
    section_query = args.section.lower().strip()

    matches = []
    for line in log_path.read_text(encoding='utf-8').splitlines():
        try:
            e = json.loads(line)
            if e.get('run_id') != run_id:
                continue
            for i in e.get('issues', []):
                if section_query in i.get('section', '').lower():
                    matches.append(i)
        except Exception:
            pass

    if not matches:
        utils.err(f"No issues found matching run={run_id!r} section={section_query!r}")
        sys.exit(utils.EXIT_NOT_FOUND)

    from datetime import datetime as _dt
    res_path = _resolution_cache_path(root)
    res_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with res_path.open('a', encoding='utf-8') as f:
        for i in matches:
            entry = {
                "source": i['source'], "section": i['section'], "dest": i['dest'],
                "resolved_at": _dt.now().isoformat(timespec='seconds'),
                "run_id": run_id, "reason": args.reason or "intentional",
            }
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            written += 1

    utils.log(f"sweep-review-resolve: marked {written} issue(s) as resolved in {res_path}")


# ---------------------------------------------------------------------------
# scan_sweep_runs — used by dashboard.py to populate the Sweep Reviews tab
# ---------------------------------------------------------------------------

def scan_sweep_runs(root: Path) -> list[dict]:
    """Return metadata for all sweep runs, newest first."""
    sweeps = root / "sweeps"
    if not sweeps.exists():
        return []
    runs = []
    for snap in sorted(sweeps.glob("*.snapshot.html"), reverse=True):
        m = re.match(r'(\d{4}-\d{2}-\d{2})-(\d+)\.snapshot', snap.stem)
        if not m:
            continue
        date_str, run_n = m.group(1), int(m.group(2))
        run_id = f"{date_str}-{run_n:02d}"
        review_path = sweeps / f"{run_id}.review.html"
        comment_files = sorted(sweeps.glob(f"{run_id}-r*.comments.jsonl"))
        sha = ""
        stats = ""
        try:
            content = snap.read_text(encoding="utf-8", errors="replace")
            sha_m = re.search(r'sha:\s*([0-9a-f]{7,40})', content)
            if sha_m:
                sha = sha_m.group(1)[:7]
            stat_m = re.search(r'const STAT_TEXT = "([^"]+)"', content)
            if stat_m:
                raw = stat_m.group(1).replace("\\n", "\n").replace("\\t", "\t")
                stats = raw.split("\n")[0].strip()
        except Exception:
            pass
        runs.append({
            "run_id": run_id,
            "date": date_str,
            "run_n": run_n,
            "sha": sha,
            "stats": stats,
            "has_review": review_path.exists(),
            "comment_rounds": len(comment_files),
        })
    return runs
