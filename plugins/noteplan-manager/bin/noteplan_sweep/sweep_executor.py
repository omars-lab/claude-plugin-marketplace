"""
sweep_executor.py — Hash-anchored apply + finalize for the interactive review UI.

The executor performs ONLY the mechanical moves a manifest describes, and only
after the user approves them. Every apply is stateless with respect to prior
applies: it trusts the file's current content on disk plus the manifest entry —
never a remembered line-number offset. This is what keeps moves correct when the
user approves them out of order (each applied move shifts later line numbers) and
when NotePlan itself rewrites a note between proposal and approval.

Correctness model (find_anchor):
  1. Fast path — the stored line texts are exactly at the stored offset.
  2. Raw scan — the exact texts appear as one contiguous run elsewhere (an
     earlier move shifted them). Ambiguous duplicates → refuse (Stale).
  3. Normalized scan — only a date-tag/hashtag-drifted match exists → Stale,
     but refreshable (the UI can mechanically rebase to the current text).
  4. Nothing matches → Stale(content_drift), unless the move is already applied
     on disk (crash recovery / idempotence).

File writes go through an atomic temp-file + os.replace so NotePlan never
observes a half-written note.
"""

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import noteplan_sweep.movement as movement
import noteplan_sweep.source as source
import noteplan_sweep.sweep_manifest as sm


# ---------------------------------------------------------------------------
# Normalization (mirrors ui_common.JS normLine / sweep_review._norm_line)
# ---------------------------------------------------------------------------

_DATE_TAG_RE = re.compile(r">\d{4}-\d{2}-\d{2}")
_HASHTAG_RE = re.compile(r"#\w+")
_WS_RE = re.compile(r"\s+")


def norm_line(s: str) -> str:
    """Strip trailing date tags + hashtags, collapse whitespace, lowercase.

    Used ONLY for staleness classification (cosmetic drift) — never for hashing
    or for deciding what bytes to delete.
    """
    s = _DATE_TAG_RE.sub("", s)
    s = _HASHTAG_RE.sub("", s)
    s = _WS_RE.sub(" ", s)
    return s.strip().lower()


# ---------------------------------------------------------------------------
# Anchor results
# ---------------------------------------------------------------------------

@dataclass
class Anchor:
    pos: int          # 0-based index into split("\n") lines where the run begins
    kind: str         # exact | relocated | relocated_nearest
    ok: bool = True


@dataclass
class Stale:
    reason: str                      # cosmetic_drift | content_drift | ambiguous | empty
    refreshable: bool = False
    pos: int | None = None           # for cosmetic_drift: where the drifted run is
    current_texts: list[str] = field(default_factory=list)  # disk text at pos
    ok: bool = False


def find_anchor(current_lines: list[str], texts: list[str],
                expected_start: int) -> Anchor | Stale:
    """Locate the contiguous run matching `texts` in `current_lines`.

    `expected_start` is 0-based (manifest line_start - 1). Returns Anchor on a
    confident match, else Stale.
    """
    k = len(texts)
    n = len(current_lines)
    if k == 0:
        return Stale("empty")

    # 1. Fast path
    if 0 <= expected_start and expected_start + k <= n \
            and current_lines[expected_start:expected_start + k] == texts:
        return Anchor(expected_start, "exact")

    # 2. Raw scan for exact contiguous runs
    raw = [i for i in range(0, n - k + 1) if current_lines[i:i + k] == texts]
    if len(raw) == 1:
        return Anchor(raw[0], "relocated")
    if len(raw) > 1:
        raw.sort(key=lambda i: (abs(i - expected_start), i))
        if abs(raw[0] - expected_start) < abs(raw[1] - expected_start):
            return Anchor(raw[0], "relocated_nearest")
        return Stale("ambiguous")

    # 3. Normalized scan (cosmetic drift — date tag / hashtag changed)
    norm_texts = [norm_line(t) for t in texts]
    norm_cur = [norm_line(l) for l in current_lines]
    normm = [i for i in range(0, n - k + 1) if norm_cur[i:i + k] == norm_texts]
    if len(normm) == 1:
        pos = normm[0]
        return Stale("cosmetic_drift", refreshable=True, pos=pos,
                     current_texts=current_lines[pos:pos + k])
    if len(normm) > 1:
        return Stale("ambiguous")

    # 4. Nothing matches
    return Stale("content_drift")


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------

def atomic_write(path: Path, text: str) -> None:
    """Write text to path atomically (temp file in same dir + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# New-file creation
# ---------------------------------------------------------------------------

def render_new_file(create: dict) -> str:
    """Render a to-be-created destination file from a manifest create block.

    The executor writes exactly what Claude authored — frontmatter dict, H1,
    and boilerplate lines — inventing nothing.
    """
    lines: list[str] = []
    fm = create.get("frontmatter") or {}
    if fm:
        lines.append("---")
        for k, v in fm.items():
            lines.append(f"{k}: {v}")
        lines.append("---")
    h1 = create.get("h1")
    if h1:
        lines.append(h1)
    for b in create.get("boilerplate_lines", []) or []:
        lines.append(b)
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    return text


# ---------------------------------------------------------------------------
# Idempotence
# ---------------------------------------------------------------------------

def _content_present(dst_text: str, content_texts: list[str]) -> bool:
    """True if all (normalized, non-blank) content lines already appear in dst."""
    dst_norm = {norm_line(l) for l in dst_text.split("\n") if l.strip()}
    for t in content_texts:
        if not t.strip():
            continue
        if norm_line(t) not in dst_norm:
            return False
    return True


def already_applied_on_disk(root: Path, move: dict) -> bool:
    """Detect a move that already ran but whose apply_done was lost (crash).

    True when the content lines are present under the destination AND the source
    lines can no longer be anchored in the source file.
    """
    src_path = root / move["source"]["file"]
    dst_path = root / move["destination"]["file"]
    texts = sm.source_texts(move)
    if src_path.exists():
        cur = src_path.read_text(encoding="utf-8").split("\n")
        anchor = find_anchor(cur, texts, move["source"]["line_start"] - 1)
        if isinstance(anchor, Anchor):
            return False  # source still holds the lines → not applied
    if not dst_path.exists():
        return False
    return _content_present(dst_path.read_text(encoding="utf-8"), sm.content_texts(move))


# ---------------------------------------------------------------------------
# Apply a single move
# ---------------------------------------------------------------------------

@dataclass
class ApplyResult:
    ok: bool
    already_applied: bool = False
    created_file: bool = False
    anchor: int | None = None
    dst_file: str | None = None
    dst_section: str | None = None
    inserted: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    stale: dict | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        d = {"ok": self.ok}
        for k in ("already_applied", "created_file", "anchor", "dst_file",
                  "dst_section", "inserted", "removed", "stale", "error"):
            v = getattr(self, k)
            if v:
                d[k] = v
        return d


def apply_move(root: Path, move: dict) -> ApplyResult:
    """Apply one EFFECTIVE move (after reroute/edit/refresh folding).

    Reads the source fresh, anchors by content, creates the destination file if
    needed, inserts the content and removes the source lines, and writes both
    files atomically (destination first, source second — mirroring
    cmd_move_range so a crash leaves the source intact rather than duplicated).
    Never applies a stale move.
    """
    src_rel = move["source"]["file"]
    dst_rel = move["destination"]["file"]
    src_path = root / src_rel
    dst_path = root / dst_rel
    section = move["destination"]["section_header"]
    date = move["destination"].get("date_subheader")
    texts = sm.source_texts(move)
    content = sm.content_texts(move)

    # Disk-level idempotence (crash recovery)
    if already_applied_on_disk(root, move):
        return ApplyResult(ok=True, already_applied=True,
                           dst_file=dst_rel, dst_section=section,
                           inserted=content, removed=texts)

    if not src_path.exists():
        return ApplyResult(ok=False, error=f"source file not found: {src_rel}",
                           stale={"reason": "content_drift"})

    src_text = src_path.read_text(encoding="utf-8")
    src_lines = src_text.split("\n")

    anchor = find_anchor(src_lines, texts, move["source"]["line_start"] - 1)
    if isinstance(anchor, Stale):
        return ApplyResult(ok=False, stale={
            "reason": anchor.reason,
            "refreshable": anchor.refreshable,
            "pos": anchor.pos,
            "current_texts": anchor.current_texts,
        }, dst_file=dst_rel, dst_section=section)

    # Create destination file if needed
    created = False
    create_spec = move["destination"].get("create")
    if not dst_path.exists():
        if create_spec:
            atomic_write(dst_path, render_new_file(create_spec))
            created = True
        else:
            atomic_write(dst_path, "")
            created = True

    dst_text = dst_path.read_text(encoding="utf-8")

    # Compute both new contents BEFORE writing either (compute-both-then-write)
    try:
        new_dst_text = movement.insert_into_section(dst_text, section, content, date)
    except ValueError as e:
        return ApplyResult(ok=False, error=str(e))

    pos = anchor.pos
    k = len(texts)
    new_src_lines = src_lines[:pos] + src_lines[pos + k:]
    new_src_text = "\n".join(new_src_lines)
    if not new_src_text.endswith("\n"):
        new_src_text += "\n"

    # Write destination first, then source (source-loss-safe ordering)
    atomic_write(dst_path, new_dst_text)
    atomic_write(src_path, new_src_text)

    return ApplyResult(ok=True, created_file=created, anchor=pos,
                       dst_file=dst_rel, dst_section=section,
                       inserted=content, removed=texts)


# ---------------------------------------------------------------------------
# Refresh (mechanical rebase of a cosmetically-drifted move)
# ---------------------------------------------------------------------------

def refresh_move_lines(root: Path, move: dict) -> list[dict] | None:
    """Re-locate a move's source lines against current disk and return updated
    {n, text, h} entries (raw current text), or None if it can't be rebased
    unambiguously. Mechanical only — no intent decisions.
    """
    src_path = root / move["source"]["file"]
    if not src_path.exists():
        return None
    cur = src_path.read_text(encoding="utf-8").split("\n")
    texts = sm.source_texts(move)
    anchor = find_anchor(cur, texts, move["source"]["line_start"] - 1)
    if isinstance(anchor, Anchor):
        pos = anchor.pos
    elif isinstance(anchor, Stale) and anchor.refreshable and anchor.pos is not None:
        pos = anchor.pos
    else:
        return None
    k = len(texts)
    new_texts = cur[pos:pos + k]
    return [{"n": pos + 1 + i, "text": t, "h": sm.line_hash(t)}
            for i, t in enumerate(new_texts)]


def rebase_move(root: Path, move: dict) -> dict | None:
    """Rebase a cosmetically-drifted move against current disk.

    Returns {"lines": <new source lines>, "content_lines": <new content>} or
    None if it can't be rebased. Verbatim content lines are re-pointed to the
    current disk text (so a date tag NotePlan added on disk is carried into the
    destination rather than silently dropped); transformed/added lines keep the
    text Claude authored, only their source_n is remapped.
    """
    new_lines = refresh_move_lines(root, move)
    if new_lines is None:
        return None
    old = move["source"]["lines"]
    # old source_n (i-th) -> (new_n, new_text)
    remap = {old[i]["n"]: (new_lines[i]["n"], new_lines[i]["text"])
             for i in range(min(len(old), len(new_lines)))}
    new_content = []
    for cl in move["content"]["lines"]:
        nc = dict(cl)
        sn = cl.get("source_n")
        if sn in remap:
            new_n, new_text = remap[sn]
            nc["source_n"] = new_n
            if cl.get("provenance") == "verbatim":
                nc["text"] = new_text
        new_content.append(nc)
    return {"lines": new_lines, "content_lines": new_content}


# ---------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------

def _git(args: list[str], root: Path, *, input_bytes: bytes | None = None,
         timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        capture_output=True, input=input_bytes, timeout=timeout, cwd=str(root))


def _stage_md(root: Path, rel_paths: list[str]) -> tuple[bool, str]:
    """Stage the given .md paths (NUL pathspec handles emoji/space names)."""
    if not rel_paths:
        return True, ""
    nul = "\0".join(rel_paths).encode("utf-8")
    r = _git(["add", "--pathspec-from-file=-", "--pathspec-file-nul"],
             root, input_bytes=nul)
    if r.returncode != 0:
        return False, r.stderr.decode(errors="replace").strip()
    return True, ""


# ---------------------------------------------------------------------------
# Diff parsing for finalize validation
# ---------------------------------------------------------------------------

_NORM_ANNOT_RE = re.compile(r'(\s+(>\d{4}-\d{2}-\d{2}|>\d{8}|#\w+))+$')


def _norm_diff_line(content: str) -> str:
    """Normalize a diff content line the way Phase 7 does: drop trailing date
    tags / hashtags so date-forwarding doesn't read as content loss."""
    return _NORM_ANNOT_RE.sub('', content)


def _parse_staged_diff(root: Path, base_sha: str) -> dict:
    """Parse `git diff --cached <base>` (staged tree vs base) into per-file
    removed/added line sets (raw + normalized) and detected file deletions.

    Uses core.quotepath=false so emoji/UTF-8 paths are unquoted.
    """
    r = _git(["-c", "core.quotepath=false", "diff", "--cached",
              "--unified=0", base_sha], root)
    text = r.stdout.decode("utf-8", errors="replace")

    removed_by_file: dict[str, set] = {}
    added_raw: set[str] = set()
    added_norm: set[str] = set()
    current_file = ""
    for line in text.split("\n"):
        if line.startswith("+++ "):
            rest = line[4:].strip().strip('"')
            current_file = rest[2:] if rest.startswith("b/") else rest
            continue
        if (line.startswith("--- ") or line.startswith("@@")
                or line.startswith("diff ") or line.startswith("index ")
                or line.startswith("new file") or line.startswith("deleted file")
                or line.startswith("rename ") or line.startswith("similarity ")):
            continue
        if current_file.endswith(".json") or "Backup" in current_file:
            continue
        if line.startswith("-") and not line.startswith("---"):
            content = line[1:].rstrip()
            removed_by_file.setdefault(current_file, {"raw": set(), "norm": set()})
            removed_by_file[current_file]["raw"].add(content)
            removed_by_file[current_file]["norm"].add(_norm_diff_line(content))
        elif line.startswith("+") and not line.startswith("+++"):
            content = line[1:].rstrip()
            added_raw.add(content)
            added_norm.add(_norm_diff_line(content))

    # Deleted files
    ns = _git(["-c", "core.quotepath=false", "diff", "--cached",
               "--name-status", base_sha], root)
    deleted = []
    for line in ns.stdout.decode("utf-8", errors="replace").split("\n"):
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].startswith("D"):
            deleted.append(parts[1])

    return {
        "removed_by_file": removed_by_file,
        "added_raw": added_raw,
        "added_norm": added_norm,
        "deleted": deleted,
    }


def _cleanup_by_file(manifest: dict) -> dict:
    return {sf["file"]: sf.get("cleanup", {})
            for sf in manifest.get("source_files", [])}


_STRUCTURAL_ALLOWED = [
    re.compile(r'^# \[\['),                       # wikilink section headers
    re.compile(r'^#'),                            # any header (normalized may keep leading #)
    re.compile(r'^## \d{4}-\d{2}-\d{2}'),         # date subheaders / meeting headers
    re.compile(r'^---$'),                         # frontmatter delimiters
    re.compile(r'^(doctype|status|started|namespace|workstream|plantype|'
               r'contributors|description|completed|title):'),
    re.compile(r'^\| '),                          # breadcrumb table rows
    re.compile(r'^\* \[ \] Is \[\['),             # plan boilerplate question
]


def _is_structural(norm_l: str) -> bool:
    s = norm_l.strip()
    if not s:
        return True
    return any(p.match(s) or p.match(norm_l) for p in _STRUCTURAL_ALLOWED)


def validate_session_diff(root: Path, base_sha: str, manifest: dict,
                          state: dict) -> dict:
    """Manifest-aware port of the Phase 7 diff integrity check.

    Run AFTER breadcrumbs + clear-source + staging, BEFORE commit. Asserts:
      - No content loss: every removed content line reappears as an added line
        somewhere, OR its source file opted into clear_source (intentional drop).
      - No invention: every added content line is a manifest content line,
        new-file boilerplate, a structural header/table row, or blank.
      - Completed [x] tasks are never removed from Calendar notes.
      - Verbatim moved lines land byte-identical (indentation preserved).
      - No daily-note files deleted.

    Returns {ok, errors: [...], stats: {...}}.
    """
    diff = _parse_staged_diff(root, base_sha)
    cleanup = _cleanup_by_file(manifest)
    errors: list[str] = []

    applied = [m for m in state.get("moves", []) if m.get("status") == "applied"]

    # Allowed additions: manifest content (applied) + create boilerplate.
    allowed_norm: set[str] = set()
    verbatim_raw: set[str] = set()
    for m in applied:
        for cl in m["content"]["lines"]:
            allowed_norm.add(_norm_diff_line(cl["text"].rstrip()))
            if cl.get("provenance") == "verbatim":
                verbatim_raw.add(cl["text"].rstrip())
        create = m["destination"].get("create")
        if create:
            fm = create.get("frontmatter") or {}
            for k, v in fm.items():
                allowed_norm.add(_norm_diff_line(f"{k}: {v}"))
            if create.get("h1"):
                allowed_norm.add(_norm_diff_line(create["h1"]))
            for b in create.get("boilerplate_lines", []) or []:
                allowed_norm.add(_norm_diff_line(b.rstrip()))

    # 1. No content loss (per file)
    for fpath, sets in diff["removed_by_file"].items():
        clear = bool(cleanup.get(fpath, {}).get("clear_source"))
        for raw in sets["raw"]:
            norm = _norm_diff_line(raw)
            stripped = norm.strip()
            if not stripped or stripped.startswith("#"):
                continue  # blank / header removals are expected
            # completed task must never be removed from a calendar note
            if fpath.startswith("Calendar/") and re.match(r'^[-*] \[x\] ', raw.strip(), re.I):
                errors.append(f"completed task removed from {fpath}: {raw!r}")
                continue
            if norm in diff["added_norm"]:
                continue  # moved somewhere → fine
            if clear:
                continue  # intentional clear-source drop
            errors.append(f"content lost (removed, not re-added) in {fpath}: {raw!r}")

    # 2. No invention
    genuinely_new = diff["added_norm"] - {
        _norm_diff_line(r) for s in diff["removed_by_file"].values() for r in s["raw"]
    }
    for norm in genuinely_new:
        if not norm.strip():
            continue
        if norm in allowed_norm or _is_structural(norm):
            continue
        errors.append(f"unexplained new line added: {norm!r}")

    # 3. Verbatim lines land byte-identical
    for raw in verbatim_raw:
        if raw.strip() and raw not in diff["added_raw"]:
            # normalized present but raw absent → indentation/whitespace altered
            if _norm_diff_line(raw) in diff["added_norm"]:
                errors.append(f"verbatim line altered on insert: {raw!r}")

    # 4. No daily-note deletions
    for d in diff["deleted"]:
        if d.startswith("Calendar/"):
            errors.append(f"daily note deleted: {d}")

    return {
        "ok": not errors,
        "errors": errors,
        "stats": {
            "removed": sum(len(s["raw"]) for s in diff["removed_by_file"].values()),
            "added": len(diff["added_raw"]),
            "applied_moves": len(applied),
        },
    }


# ---------------------------------------------------------------------------
# Finalize orchestration
# ---------------------------------------------------------------------------

def _build_commit_message(root: Path, md_files: list[str],
                          sweep_date: str | None = None) -> str:
    today = sweep_date or date.today().strftime("%Y-%m-%d")
    calendar = [p for p in md_files if p.startswith("Calendar/")]
    plans = [p for p in md_files if "Plans/" in p or "Lists/" in p]
    other = [p for p in md_files if p not in calendar and p not in plans]
    task_count = 0
    for rel in calendar:
        try:
            task_count += (root / rel).read_text(encoding="utf-8").count("- [x]")
        except OSError:
            pass
    n = len(md_files)
    stats = f"{n} file{'s' if n != 1 else ''} changed"
    if task_count:
        stats += f", {task_count} task{'s' if task_count != 1 else ''} completed"
    subject = f"sweep({today}): {stats}"
    body = []
    for label, group in (("Sources swept:", calendar),
                         ("Plans/lists touched:", plans),
                         ("Other files:", other)):
        if group:
            body.append(label)
            body.extend(f"  {p}" for p in sorted(group))
    return subject + "\n\n" + "\n".join(body)


def add_breadcrumbs_and_clear(root: Path, manifest: dict, state: dict,
                              sweep_date: str) -> list[str]:
    """At finalize: append one breadcrumb row per applied move (per source file,
    in source-line order) then clear each source file (keeping user 'keep' lines).
    Returns the list of source files touched.
    """
    applied = [m for m in state.get("moves", []) if m.get("status") == "applied"]
    kept = [m for m in state.get("moves", []) if m.get("status") == "kept"]

    # Group applied moves by source file, ordered by line_start
    by_src: dict[str, list[dict]] = {}
    for m in applied:
        by_src.setdefault(m["source"]["file"], []).append(m)
    for lst in by_src.values():
        lst.sort(key=lambda m: m["source"]["line_start"])

    for src_file, moves in by_src.items():
        path = root / src_file
        if not path.exists():
            continue
        for m in moves:
            bc = m.get("breadcrumb") or {}
            source.cmd_add_breadcrumb(SimpleNamespace(
                file=str(path),
                date=sweep_date,
                section=bc.get("section", m["source"].get("section_header", "")),
                summary=bc.get("summary", ""),
                destination=bc.get("destination", m["destination"]["file"]),
            ))

    # Clear each source file that opted into clear_source, preserving kept lines
    keep_by_src: dict[str, set] = {}
    for m in kept:
        for ln in m["source"]["lines"]:
            keep_by_src.setdefault(m["source"]["file"], set()).add(ln["text"])

    touched = set(by_src.keys())
    for sf in manifest.get("source_files", []):
        src_file = sf["file"]
        if not sf.get("cleanup", {}).get("clear_source"):
            continue
        path = root / src_file
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        new_text = source.clear_source_text(
            text,
            keep_completed=sf.get("cleanup", {}).get("keep_completed", True),
            keep_line_texts=keep_by_src.get(src_file, set()))
        atomic_write(path, new_text)
        touched.add(src_file)

    return sorted(touched)


def dest_existence_issues(root: Path, manifest: dict) -> tuple[list[str], list[str]]:
    """Cross-check each move's destination.exists claim against disk.

    Returns (errors, warnings). A create-block destination (exists=false) that
    already exists on disk is an ERROR — apply would silently append to the real
    file and the review UI would show a misleading "new file" preview with
    frontmatter that never gets written. An exists=true destination missing on
    disk is a WARNING — apply will create an empty file and insert into it,
    losing the intended template.
    """
    errors, warnings = [], []
    for mv in manifest.get("moves", []):
        dst = mv.get("destination", {})
        rel = dst.get("file", "")
        on_disk = (root / rel).exists()
        claims_new = not dst.get("exists", True)
        if claims_new and on_disk:
            errors.append(f"{mv.get('id')}: destination.exists=false (new file) but "
                          f"already exists on disk: {rel}")
        if (not claims_new) and not on_disk:
            warnings.append(f"{mv.get('id')}: destination.exists=true but not found "
                            f"on disk (will be created empty): {rel}")
    return errors, warnings


def touched_files(manifest: dict, state: dict) -> list[str]:
    """All .md files the session may have modified (sources + applied dests)."""
    files = {sf["file"] for sf in manifest.get("source_files", [])}
    for m in state.get("moves", []):
        if m.get("status") == "applied":
            files.add(m["destination"]["file"])
            files.add(m["source"]["file"])
    return sorted(files)


def finalize(root: Path, manifest: dict, state: dict,
             *, sweep_date: str | None = None,
             commit_message: str | None = None) -> dict:
    """Breadcrumbs → clear-source → stage → validate → commit.

    Returns {ok, commit_sha?, report?}. On validation failure, does NOT commit;
    files stay modified on disk for the user to fix and re-finalize.
    """
    sweep_date = sweep_date or date.today().strftime("%Y-%m-%d")

    add_breadcrumbs_and_clear(root, manifest, state, sweep_date)

    files = touched_files(manifest, state)
    ok, err = _stage_md(root, files)
    if not ok:
        return {"ok": False, "report": {"errors": [f"git add failed: {err}"]}}

    report = validate_session_diff(root, manifest["base_sha"], manifest, state)
    if not report["ok"]:
        # leave working tree as-is; unstage so a retry re-stages cleanly
        _git(["reset", "-q"], root)
        return {"ok": False, "report": report}

    msg = commit_message or _build_commit_message(root, files, sweep_date)
    c = _git(["commit", "-m", msg], root)
    if c.returncode != 0:
        return {"ok": False, "report": {
            "errors": [f"git commit failed: {c.stderr.decode(errors='replace').strip()}"]}}
    sha_r = _git(["rev-parse", "--short", "HEAD"], root)
    sha = sha_r.stdout.decode().strip() if sha_r.returncode == 0 else "?"
    return {"ok": True, "commit_sha": sha, "report": report}


def abort(root: Path, manifest: dict, state: dict) -> dict:
    """Restore every session-touched file to its committed state (nothing was
    committed since sweep-start, so base == HEAD). Tracked files are checked
    out; newly-created untracked files are removed.
    """
    restored, removed = [], []
    for rel in touched_files(manifest, state):
        path = root / rel
        ls = _git(["ls-files", "--error-unmatch", rel], root)
        if ls.returncode == 0:
            _git(["checkout", "HEAD", "--", rel], root)
            restored.append(rel)
        else:
            if path.exists():
                path.unlink()
                removed.append(rel)
    return {"ok": True, "restored": restored, "removed": removed}
