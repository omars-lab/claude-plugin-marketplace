"""
sweep_session.py — Append-only decision journal + state folding for a review session.

A sweep review session has two files under sweeps/:
  <run_id>.manifest.json    immutable — what Claude proposed (see sweep_manifest.py)
  <run_id>.decisions.jsonl  append-only — every user decision + execution record

Current state is always fold(manifest, journal). The journal is the single source
of truth for "what happened"; the manifest never changes. `seq` (the count of
journal events) is a monotonic optimistic-concurrency token: the UI sends the seq
it last saw, and a mutating request whose seq is stale gets a 409 + fresh state.

Event types (one JSON object per line):
  session_created  {run_id}
  decision         {move_id, action: skip|unskip|keep|reroute|edit|refresh, payload}
  split            {parent_id, children: [<full move dicts>]}
  apply_started    {move_id}
  apply_done       {move_id, dst_file, dst_section, inserted, removed, anchor}
  apply_failed     {move_id, reason, detail}
  finalize_started {}
  finalize_done    {commit_sha}
  finalize_failed  {report}
  aborted          {}

Every event carries an assigned `seq` (1-based) and an ISO `ts`.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import noteplan_sweep.sweep_manifest as sm

# Per-run locks so concurrent appends within one process serialize.
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()

# Terminal / active status vocabulary used across server + UI.
STATUS_PENDING = "pending"
STATUS_APPLYING = "applying"
STATUS_APPLIED = "applied"
STATUS_SKIPPED = "skipped"
STATUS_KEPT = "kept"
STATUS_STALE = "stale"
STATUS_FAILED = "failed"
STATUS_SUPERSEDED = "superseded"

RESOLVED_STATUSES = {STATUS_APPLIED, STATUS_SKIPPED, STATUS_KEPT}
UNRESOLVED_STATUSES = {STATUS_PENDING, STATUS_APPLYING, STATUS_STALE, STATUS_FAILED}


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def sweeps_dir(root: Path) -> Path:
    d = root / "sweeps"
    d.mkdir(exist_ok=True)
    return d


def manifest_path(root: Path, run_id: str) -> Path:
    return sweeps_dir(root) / f"{run_id}.manifest.json"


def journal_path(root: Path, run_id: str) -> Path:
    return sweeps_dir(root) / f"{run_id}.decisions.jsonl"


def _lock_for(run_id: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lk = _LOCKS.get(run_id)
        if lk is None:
            lk = threading.Lock()
            _LOCKS[run_id] = lk
        return lk


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def read_manifest(root: Path, run_id: str) -> dict:
    p = manifest_path(root, run_id)
    return json.loads(p.read_text(encoding="utf-8"))


def read_journal(root: Path, run_id: str) -> list[dict]:
    p = journal_path(root, run_id)
    if not p.exists():
        return []
    events = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # tolerate a torn final line from a crash mid-write
    return events


def current_seq(root: Path, run_id: str) -> int:
    return len(read_journal(root, run_id))


def list_sessions(root: Path) -> list[str]:
    """Run IDs that have a manifest, newest first."""
    d = sweeps_dir(root)
    ids = [p.name[: -len(".manifest.json")]
           for p in d.glob("*.manifest.json")]
    return sorted(ids, reverse=True)


# ---------------------------------------------------------------------------
# Append
# ---------------------------------------------------------------------------

def append_event(root: Path, run_id: str, event: dict, *, ts: str | None = None) -> dict:
    """Append one event, assigning seq (= new event count) and ts. Returns the
    stored event (with seq/ts filled in). Crash-safe: a single line + flush.
    """
    lk = _lock_for(run_id)
    with lk:
        path = journal_path(root, run_id)
        existing = read_journal(root, run_id)
        seq = len(existing) + 1
        stored = dict(event)
        stored["seq"] = seq
        stored["ts"] = ts or datetime.now(timezone.utc).isoformat()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(stored, ensure_ascii=False) + "\n")
            fh.flush()
        return stored


def ensure_session_created(root: Path, run_id: str) -> None:
    """Write a session_created event if the journal is empty."""
    if not read_journal(root, run_id):
        append_event(root, run_id, {"type": "session_created", "run_id": run_id})


# ---------------------------------------------------------------------------
# Fold: manifest + journal -> current state
# ---------------------------------------------------------------------------

def fold_state(manifest: dict, journal: list[dict]) -> dict:
    """Compute the full session state from the immutable manifest + journal.

    Returns:
      {
        run_id, seq, state: open|finalized|failed|aborted, commit_sha?,
        finalize_error?,
        moves: [ {<effective move>, status, rerouted, applied_detail?} ],
        counts: {total, pending, applying, applied, skipped, kept, stale,
                 failed, resolved, unresolved},
        can_finalize: bool,
      }
    """
    run_id = manifest.get("run_id")

    # 1. Universe of moves: manifest moves + split children; parents superseded.
    base_moves: dict[str, dict] = {mv["id"]: mv for mv in manifest.get("moves", [])}
    order: list[str] = [mv["id"] for mv in manifest.get("moves", [])]
    superseded: set[str] = set()

    for ev in journal:
        if ev.get("type") == "split":
            parent = ev.get("parent_id")
            if parent in base_moves:
                superseded.add(parent)
            for child in ev.get("children", []):
                cid = child["id"]
                base_moves[cid] = child
                # place child near its parent for stable ordering
                if parent in order:
                    idx = order.index(parent)
                    order.insert(idx + 1, cid)
                else:
                    order.append(cid)

    # 2. Per-move amendment payloads (for effective_move) + status timeline.
    amendments: dict[str, list[dict]] = {mid: [] for mid in base_moves}
    status: dict[str, str] = {mid: STATUS_PENDING for mid in base_moves}
    rerouted: dict[str, bool] = {mid: False for mid in base_moves}
    applied_detail: dict[str, dict] = {}

    for ev in journal:
        etype = ev.get("type")
        mid = ev.get("move_id")
        if etype == "decision" and mid in status:
            action = ev.get("action")
            payload = ev.get("payload") or {}
            payload = {"action": action, **payload}
            if action == "skip":
                status[mid] = STATUS_SKIPPED
            elif action == "keep":
                status[mid] = STATUS_KEPT
            elif action == "unskip":
                status[mid] = STATUS_PENDING
            elif action == "reroute":
                rerouted[mid] = True
                amendments[mid].append(payload)
                if status[mid] in (STATUS_STALE, STATUS_FAILED):
                    status[mid] = STATUS_PENDING
            elif action == "edit":
                amendments[mid].append(payload)
            elif action == "refresh":
                amendments[mid].append(payload)
                if status[mid] in (STATUS_STALE, STATUS_FAILED):
                    status[mid] = STATUS_PENDING
        elif etype == "apply_started" and mid in status:
            status[mid] = STATUS_APPLYING
        elif etype == "apply_done" and mid in status:
            status[mid] = STATUS_APPLIED
            applied_detail[mid] = {
                "dst_file": ev.get("dst_file"),
                "dst_section": ev.get("dst_section"),
                "inserted": ev.get("inserted", []),
                "removed": ev.get("removed", []),
                "anchor": ev.get("anchor"),
            }
        elif etype == "apply_failed" and mid in status:
            status[mid] = STATUS_STALE if ev.get("reason") in (
                "cosmetic_drift", "content_drift", "ambiguous", "stale") else STATUS_FAILED

    for mid in superseded:
        status[mid] = STATUS_SUPERSEDED

    # 3. Session-level state.
    state = "open"
    commit_sha = None
    finalize_error = None
    for ev in journal:
        if ev.get("type") == "finalize_done":
            state = "finalized"
            commit_sha = ev.get("commit_sha")
        elif ev.get("type") == "aborted":
            state = "aborted"
        elif ev.get("type") == "finalize_failed":
            finalize_error = ev.get("report")
    # finalize_done / aborted win over a prior finalize_failed
    for ev in reversed(journal):
        if ev.get("type") in ("finalize_done", "aborted", "finalize_failed"):
            if ev.get("type") == "finalize_failed":
                state = "open"  # still open for retry
            break

    # 4. Assemble effective moves + counts.
    moves_out = []
    counts = {k: 0 for k in (
        STATUS_PENDING, STATUS_APPLYING, STATUS_APPLIED, STATUS_SKIPPED,
        STATUS_KEPT, STATUS_STALE, STATUS_FAILED, STATUS_SUPERSEDED)}
    for mid in order:
        if mid not in base_moves:
            continue
        eff = sm.effective_move(base_moves[mid], amendments[mid])
        st = status[mid]
        counts[st] = counts.get(st, 0) + 1
        entry = dict(eff)
        entry["status"] = st
        entry["rerouted"] = rerouted[mid]
        if mid in applied_detail:
            entry["applied_detail"] = applied_detail[mid]
        moves_out.append(entry)

    visible_total = sum(v for k, v in counts.items() if k != STATUS_SUPERSEDED)
    resolved = counts[STATUS_APPLIED] + counts[STATUS_SKIPPED] + counts[STATUS_KEPT]
    unresolved = (counts[STATUS_PENDING] + counts[STATUS_APPLYING]
                  + counts[STATUS_STALE] + counts[STATUS_FAILED])

    result = {
        "run_id": run_id,
        "seq": len(journal),
        "state": state,
        "moves": moves_out,
        "counts": {
            "total": visible_total,
            "resolved": resolved,
            "unresolved": unresolved,
            **counts,
        },
        "can_finalize": state == "open" and unresolved == 0 and visible_total > 0,
    }
    if commit_sha:
        result["commit_sha"] = commit_sha
    if finalize_error:
        result["finalize_error"] = finalize_error
    return result


def status_summary(manifest: dict, journal: list[dict]) -> dict:
    """Small payload for agent polling / status endpoint."""
    st = fold_state(manifest, journal)
    return {
        "run_id": st["run_id"],
        "state": st["state"],
        "seq": st["seq"],
        "counts": st["counts"],
        "can_finalize": st["can_finalize"],
        **({"commit_sha": st["commit_sha"]} if "commit_sha" in st else {}),
    }
