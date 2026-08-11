"""
sweep_api.py — Pure request handlers for the interactive sweep review UI.

Each function takes (root, ...) and returns (http_status, dict). server.py wires
these into the HTTP handler; keeping them HTTP-free means they are unit-testable
without a socket. Mutating handlers enforce optimistic concurrency via
`expect_seq` (the seq the client last saw) and journal every decision/execution.

The only endpoint that writes notes is `approve` (apply with hash validation)
and `finalize` (breadcrumbs + clear-source + commit). Everything else journals a
decision or reads state.
"""

import json
import sys
from pathlib import Path

import noteplan_sweep.sweep_executor as ex
import noteplan_sweep.sweep_manifest as sm
import noteplan_sweep.sweep_session as ss
import noteplan_sweep.utils as utils


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(root: Path, run_id: str):
    manifest = ss.read_manifest(root, run_id)
    journal = ss.read_journal(root, run_id)
    return manifest, journal


def _fresh(root: Path, run_id: str) -> dict:
    manifest, journal = _load(root, run_id)
    return ss.fold_state(manifest, journal)


def _seq_conflict(body: dict, journal: list) -> bool:
    """True if the client sent an expect_seq that no longer matches."""
    exp = body.get("expect_seq")
    return exp is not None and exp != len(journal)


def _resolve_under_root(root: Path, rel: str) -> Path | None:
    """Resolve a relative path strictly under root (reject traversal)."""
    if rel.startswith("/") or ".." in Path(rel).parts:
        return None
    try:
        p = (root / rel).resolve()
        p.relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    return p


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

def list_sessions(root: Path) -> tuple[int, dict]:
    out = []
    for run_id in ss.list_sessions(root):
        try:
            manifest, journal = _load(root, run_id)
            summ = ss.status_summary(manifest, journal)
            out.append({"run_id": run_id, **summ})
        except Exception as e:  # noqa: BLE001 — surface unreadable sessions, don't crash the list
            out.append({"run_id": run_id, "error": str(e)})
    return 200, {"ok": True, "sessions": out}


def get_session(root: Path, run_id: str) -> tuple[int, dict]:
    if not ss.manifest_path(root, run_id).exists():
        return 404, {"ok": False, "error": f"no such session: {run_id}"}
    manifest, journal = _load(root, run_id)
    state = ss.fold_state(manifest, journal)
    return 200, {"ok": True, "manifest": manifest, "state": state}


def get_status(root: Path, run_id: str) -> tuple[int, dict]:
    if not ss.manifest_path(root, run_id).exists():
        return 404, {"ok": False, "error": f"no such session: {run_id}"}
    manifest, journal = _load(root, run_id)
    return 200, {"ok": True, **ss.status_summary(manifest, journal)}


def get_file(root: Path, params: dict) -> tuple[int, dict]:
    """Return live file content (optionally sliced) or its section headers.

    params: path (required, .md, under root), start/end (1-based inclusive,
    optional), sections ("1" to list headers only).
    """
    rel = (params.get("path") or "").strip()
    if not rel:
        return 400, {"ok": False, "error": "path required"}
    if not rel.endswith(".md"):
        return 400, {"ok": False, "error": "only .md paths allowed"}
    p = _resolve_under_root(root, rel)
    if p is None:
        return 400, {"ok": False, "error": "path escapes note root"}
    if not p.exists():
        return 200, {"ok": True, "exists": False, "path": rel}

    text = p.read_text(encoding="utf-8")
    lines = text.split("\n")
    stat = p.stat()
    result = {"ok": True, "exists": True, "path": rel,
              "mtime": stat.st_mtime, "line_count": len(lines)}

    if params.get("sections"):
        headers = [{"n": i + 1, "text": ln}
                   for i, ln in enumerate(lines) if ln.startswith("#")]
        result["sections"] = headers
        return 200, result

    start = params.get("start")
    end = params.get("end")
    if start is not None and end is not None:
        try:
            s, e = int(start), int(end)
        except ValueError:
            return 400, {"ok": False, "error": "start/end must be integers"}
        s0 = max(0, s - 1)
        result["start"] = s0 + 1
        result["lines"] = lines[s0:e]
    else:
        result["lines"] = lines
    return 200, result


def search_files(root: Path, query: str, limit: int = 50) -> tuple[int, dict]:
    """Fuzzy (substring) search over .md stems for the re-route picker."""
    q = (query or "").strip().lower()
    notes = root / "Notes"
    out = []
    if notes.exists():
        for p in notes.rglob("*.md"):
            if "@Backup" in str(p) or "@Trash" in str(p):
                continue
            if not q or q in p.stem.lower():
                out.append({"stem": p.stem,
                            "path": str(p.relative_to(root))})
                if len(out) >= limit:
                    break
    out.sort(key=lambda d: d["stem"].lower())
    return 200, {"ok": True, "files": out}


def get_summary(root: Path, run_id: str) -> tuple[int, dict]:
    """Finalize preview: proposed commit message + provenance tallies."""
    if not ss.manifest_path(root, run_id).exists():
        return 404, {"ok": False, "error": f"no such session: {run_id}"}
    manifest, journal = _load(root, run_id)
    state = ss.fold_state(manifest, journal)
    applied = [m for m in state["moves"] if m["status"] == "applied"]
    tally = {"verbatim": 0, "transformed": 0, "added": 0}
    for m in applied:
        for cl in m["content"]["lines"]:
            tally[cl.get("provenance", "verbatim")] = tally.get(
                cl.get("provenance", "verbatim"), 0) + 1
    files = ex.touched_files(manifest, state)
    msg = ex._build_commit_message(root, files)
    return 200, {"ok": True, "commit_message": msg, "provenance": tally,
                 "files": files, "counts": state["counts"],
                 "can_finalize": state["can_finalize"]}


# ---------------------------------------------------------------------------
# Mutating endpoints
# ---------------------------------------------------------------------------

def post_decision(root: Path, run_id: str, body: dict) -> tuple[int, dict]:
    """Journal a non-executing decision: skip/unskip/keep/reroute/edit/refresh."""
    manifest, journal = _load(root, run_id)
    if _seq_conflict(body, journal):
        return 409, {"ok": False, "error": "stale seq", "state": ss.fold_state(manifest, journal)}
    move_id = body.get("move_id")
    action = body.get("action")
    if action not in ("skip", "unskip", "keep", "reroute", "edit", "refresh"):
        return 400, {"ok": False, "error": f"bad action: {action}"}

    # refresh is mechanical: recompute the source lines from disk
    if action == "refresh":
        state = ss.fold_state(manifest, journal)
        move = next((m for m in state["moves"] if m["id"] == move_id), None)
        if move is None:
            return 404, {"ok": False, "error": f"no such move: {move_id}"}
        rebased = ex.rebase_move(root, move)
        if rebased is None:
            return 409, {"ok": False, "error": "cannot rebase — content drifted too far"}
        ss.append_event(root, run_id, {"type": "decision", "move_id": move_id,
                                       "action": "refresh",
                                       "payload": {"lines": rebased["lines"],
                                                   "content_lines": rebased["content_lines"]}})
    else:
        ss.append_event(root, run_id, {"type": "decision", "move_id": move_id,
                                       "action": action,
                                       "payload": body.get("payload") or {}})
    return 200, {"ok": True, "state": _fresh(root, run_id)}


def post_approve(root: Path, run_id: str, body: dict) -> tuple[int, dict]:
    """Apply one or more approved moves with hash validation.

    Applies in the given order, journaling apply_started before each write and
    apply_done/apply_failed after. A stale move fails (409-ish per-move) without
    writing; the batch continues so the UI can show per-move outcomes.
    """
    manifest, journal = _load(root, run_id)
    if _seq_conflict(body, journal):
        return 409, {"ok": False, "error": "stale seq", "state": ss.fold_state(manifest, journal)}

    state = ss.fold_state(manifest, journal)
    if state["state"] != "open":
        return 409, {"ok": False, "error": f"session is {state['state']}"}

    move_ids = body.get("move_ids")
    if not move_ids:
        single = body.get("move_id")
        move_ids = [single] if single else []
    if not move_ids:
        return 400, {"ok": False, "error": "move_ids required"}

    by_id = {m["id"]: m for m in state["moves"]}
    results = []
    for mid in move_ids:
        move = by_id.get(mid)
        if move is None:
            results.append({"id": mid, "ok": False, "error": "no such move"})
            continue
        if move["status"] == ss.STATUS_APPLIED:
            results.append({"id": mid, "ok": True, "already_applied": True})
            continue
        ss.append_event(root, run_id, {"type": "apply_started", "move_id": mid})
        res = ex.apply_move(root, move)
        if res.ok:
            ss.append_event(root, run_id, {
                "type": "apply_done", "move_id": mid,
                "dst_file": res.dst_file, "dst_section": res.dst_section,
                "inserted": res.inserted, "removed": res.removed,
                "anchor": res.anchor})
            results.append({"id": mid, "ok": True,
                            "already_applied": res.already_applied,
                            "created_file": res.created_file})
        else:
            reason = (res.stale or {}).get("reason") if res.stale else "error"
            ss.append_event(root, run_id, {
                "type": "apply_failed", "move_id": mid,
                "reason": reason, "detail": res.stale or {"error": res.error}})
            results.append({"id": mid, "ok": False, "stale": res.stale,
                            "error": res.error})

    return 200, {"ok": True, "results": results, "state": _fresh(root, run_id)}


def post_split(root: Path, run_id: str, body: dict) -> tuple[int, dict]:
    """Split a move into children by source-line index (partial re-route)."""
    manifest, journal = _load(root, run_id)
    if _seq_conflict(body, journal):
        return 409, {"ok": False, "error": "stale seq", "state": ss.fold_state(manifest, journal)}
    state = ss.fold_state(manifest, journal)
    move = next((m for m in state["moves"] if m["id"] == body.get("move_id")), None)
    if move is None:
        return 404, {"ok": False, "error": "no such move"}
    if move["status"] not in (ss.STATUS_PENDING, ss.STATUS_STALE):
        return 409, {"ok": False, "error": f"cannot split a {move['status']} move"}
    try:
        children = sm.split_move(move, body.get("parts") or [])
    except sm.ManifestError as e:
        return 400, {"ok": False, "error": str(e)}
    if not children:
        return 400, {"ok": False, "error": "split produced no child moves"}
    ss.append_event(root, run_id, {"type": "split", "parent_id": move["id"],
                                   "children": children})
    return 200, {"ok": True, "children": [c["id"] for c in children],
                 "state": _fresh(root, run_id)}


def post_finalize(root: Path, run_id: str, body: dict) -> tuple[int, dict]:
    manifest, journal = _load(root, run_id)
    if _seq_conflict(body, journal):
        return 409, {"ok": False, "error": "stale seq", "state": ss.fold_state(manifest, journal)}
    state = ss.fold_state(manifest, journal)
    if state["state"] != "open":
        return 409, {"ok": False, "error": f"session is {state['state']}"}
    if not state["can_finalize"] and not body.get("force"):
        return 409, {"ok": False, "error": "moves still unresolved",
                     "counts": state["counts"]}

    ss.append_event(root, run_id, {"type": "finalize_started"})
    out = ex.finalize(root, manifest, state,
                      commit_message=body.get("commit_message"))
    if out["ok"]:
        ss.append_event(root, run_id, {"type": "finalize_done",
                                       "commit_sha": out["commit_sha"]})
        return 200, {"ok": True, "commit_sha": out["commit_sha"],
                     "report": out.get("report"), "state": _fresh(root, run_id)}
    ss.append_event(root, run_id, {"type": "finalize_failed",
                                   "report": out.get("report")})
    return 409, {"ok": False, "report": out.get("report"),
                 "state": _fresh(root, run_id)}


def post_abort(root: Path, run_id: str, body: dict) -> tuple[int, dict]:
    manifest, journal = _load(root, run_id)
    if _seq_conflict(body, journal):
        return 409, {"ok": False, "error": "stale seq", "state": ss.fold_state(manifest, journal)}
    state = ss.fold_state(manifest, journal)
    out = ex.abort(root, manifest, state)
    ss.append_event(root, run_id, {"type": "aborted", "restored": out["restored"],
                                   "removed": out["removed"]})
    return 200, {"ok": True, **out, "state": _fresh(root, run_id)}


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_sweep_manifest_validate(args):
    """Validate a move manifest: schema + hash self-consistency + disk-drift
    warnings, then register the session (copy into sweeps/ + journal creation).
    """
    root = utils.noteplan_root()
    path = Path(args.manifest)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        utils.err(f"cannot read manifest: {e}")
        sys.exit(utils.EXIT_NOT_FOUND)

    errors = sm.validate_manifest(manifest)
    for e in errors:
        utils.err(e)
    if errors:
        utils.err(f"{len(errors)} schema error(s) — manifest not registered")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    # Disk-drift warnings: can each move's source lines still be anchored?
    warnings = []
    for mv in manifest.get("moves", []):
        src = root / mv["source"]["file"]
        if not src.exists():
            warnings.append(f"{mv['id']}: source file missing ({mv['source']['file']})")
            continue
        cur = src.read_text(encoding="utf-8").split("\n")
        texts = [l["text"] for l in mv["source"]["lines"]]
        anchor = ex.find_anchor(cur, texts, mv["source"]["line_start"] - 1)
        if not getattr(anchor, "ok", False):
            warnings.append(f"{mv['id']}: source drifted ({anchor.reason})")
    for w in warnings:
        utils.log(f"warning: {w}")

    # Register: ensure the manifest lives at sweeps/<run_id>.manifest.json.
    run_id = manifest["run_id"]
    dest = ss.manifest_path(root, run_id)
    if path.resolve() != dest.resolve():
        dest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    ss.ensure_session_created(root, run_id)

    n = len(manifest.get("moves", []))
    extra = f" ({len(warnings)} drift warning(s))" if warnings else ""
    utils.log(f"manifest valid: {n} move(s), run {run_id}{extra}")
    utils.log(f"review at:  http://localhost:4242/review/{run_id}")


def cmd_sweep_session_status(args):
    """Print the folded status of a review session as JSON (agent polling)."""
    root = utils.noteplan_root()
    try:
        manifest = ss.read_manifest(root, args.run_id)
    except FileNotFoundError:
        utils.err(f"no such session: {args.run_id}")
        sys.exit(utils.EXIT_NOT_FOUND)
    journal = ss.read_journal(root, args.run_id)
    print(json.dumps(ss.status_summary(manifest, journal), indent=2))
