"""
sweep_manifest.py — Move-manifest schema, hashing, validation, and folding.

The manifest is the immutable artifact Claude emits at the end of classification:
one JSON file per sweep session (sweeps/<run_id>.manifest.json) describing every
proposed move from a daily note into a destination file. The server/executor
never classifies — it only performs the mechanical moves this manifest describes,
after the user approves them in the review UI.

This module is pure (no disk writes, no git). It provides:
  - line_hash()            raw-line content hash (anchors deletions on disk)
  - validate_manifest()    schema + overlap + hash self-consistency checks
  - build_move()           helper to assemble a move dict with hashes
  - effective_move()       fold reroute/edit/refresh amendments onto a move
  - split_move()           partial re-route → child move dicts (pure)

See sweep_session.py for the journal (decisions/execution log) and
sweep_executor.py for the hash-anchored apply.
"""

import hashlib

SCHEMA_VERSION = 1

PROVENANCE = ("verbatim", "transformed", "added")
CONFIDENCE = ("high", "medium", "low")
MODES = ("work", "personal", "both")
CREATE_KINDS = ("plan", "list", "research", "meeting")


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def line_hash(text: str) -> str:
    """Return the first 16 hex chars of SHA-256 over the RAW line text.

    Raw (not normalized) on purpose: the hash guards the executor's deletion of
    exact bytes from disk. Any edit to the line — even a trailing date tag —
    changes the hash, forcing a staleness check rather than a silent apply.
    The trailing newline is never included.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def hash_lines(texts: list[str]) -> list[str]:
    return [line_hash(t) for t in texts]


# ---------------------------------------------------------------------------
# Construction helpers
# ---------------------------------------------------------------------------

def build_source_lines(line_start: int, texts: list[str]) -> list[dict]:
    """Build the source.lines array (n/text/h) from a 1-based start + texts."""
    return [
        {"n": line_start + i, "text": t, "h": line_hash(t)}
        for i, t in enumerate(texts)
    ]


def build_move(
    move_id: str,
    src_file: str,
    section_header: str,
    line_start: int,
    src_texts: list[str],
    dst_file: str,
    dst_section: str,
    content_lines: list[dict],
    *,
    dst_exists: bool = True,
    create: dict | None = None,
    date_subheader: str | None = None,
    context_before: list[str] | None = None,
    context_after: list[str] | None = None,
    confidence: str = "high",
    rationale: str = "",
    alternatives: list[dict] | None = None,
    breadcrumb: dict | None = None,
) -> dict:
    """Assemble a fully-formed move dict (hashes computed for you)."""
    return {
        "id": move_id,
        "source": {
            "file": src_file,
            "section_header": section_header,
            "line_start": line_start,
            "line_end": line_start + len(src_texts) - 1,
            "lines": build_source_lines(line_start, src_texts),
            "context_before": context_before or [],
            "context_after": context_after or [],
        },
        "destination": {
            "file": dst_file,
            "exists": dst_exists,
            "create": create,
            "section_header": dst_section,
            "date_subheader": date_subheader,
        },
        "content": {"lines": content_lines},
        "classification": {
            "confidence": confidence,
            "rationale": rationale,
            "alternatives": alternatives or [],
        },
        "breadcrumb": breadcrumb or {},
    }


def content_line(text: str, provenance: str = "verbatim",
                 source_n: int | None = None, original: str | None = None) -> dict:
    """Build one destination content line with provenance metadata."""
    d = {"text": text, "provenance": provenance}
    if source_n is not None:
        d["source_n"] = source_n
    if original is not None:
        d["original"] = original
    return d


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ManifestError(ValueError):
    """Raised when a manifest is structurally invalid."""


def _require(cond: bool, msg: str, errors: list[str]):
    if not cond:
        errors.append(msg)


def validate_manifest(manifest: dict) -> list[str]:
    """Return a list of structural errors ([] if valid).

    Checks: schema version, required top-level + per-move fields, provenance /
    confidence enums, hash self-consistency (each source line's h matches
    line_hash(text)), and non-overlapping line ranges within a single source
    file. Does NOT touch disk — see sweep_executor for disk staleness.
    """
    errors: list[str] = []

    if not isinstance(manifest, dict):
        return ["manifest is not a JSON object"]

    ver = manifest.get("schema_version")
    _require(ver == SCHEMA_VERSION,
             f"schema_version must be {SCHEMA_VERSION} (got {ver!r})", errors)
    _require(bool(manifest.get("run_id")), "run_id is required", errors)
    mode = manifest.get("mode")
    _require(mode in MODES, f"mode must be one of {MODES} (got {mode!r})", errors)

    moves = manifest.get("moves")
    if not isinstance(moves, list):
        errors.append("moves must be a list")
        return errors

    seen_ids: set[str] = set()
    # source file -> list of (start, end, move_id) for overlap detection
    ranges: dict[str, list[tuple[int, int, str]]] = {}

    for i, mv in enumerate(moves):
        where = f"moves[{i}]"
        mid = mv.get("id")
        if not mid:
            errors.append(f"{where}: missing id")
            mid = where
        if mid in seen_ids:
            errors.append(f"{where}: duplicate move id {mid!r}")
        seen_ids.add(mid)

        src = mv.get("source") or {}
        dst = mv.get("destination") or {}
        content = mv.get("content") or {}

        sfile = src.get("file")
        _require(bool(sfile), f"{mid}: source.file required", errors)
        ls, le = src.get("line_start"), src.get("line_end")
        _require(isinstance(ls, int) and isinstance(le, int) and ls >= 1 and le >= ls,
                 f"{mid}: source.line_start/line_end invalid ({ls}, {le})", errors)

        slines = src.get("lines")
        if not isinstance(slines, list) or not slines:
            errors.append(f"{mid}: source.lines must be a non-empty list")
        else:
            if isinstance(ls, int) and isinstance(le, int):
                _require(le - ls + 1 == len(slines),
                         f"{mid}: line range spans {le - ls + 1} but "
                         f"source.lines has {len(slines)} entries", errors)
            for j, ln in enumerate(slines):
                txt, h = ln.get("text"), ln.get("h")
                if txt is None or h is None:
                    errors.append(f"{mid}: source.lines[{j}] missing text/h")
                    continue
                if line_hash(txt) != h:
                    errors.append(f"{mid}: source.lines[{j}] hash mismatch "
                                  f"(stored {h!r}, recomputed {line_hash(txt)!r})")

        _require(bool(dst.get("file")), f"{mid}: destination.file required", errors)
        _require(bool(dst.get("section_header")),
                 f"{mid}: destination.section_header required", errors)
        create = dst.get("create")
        if not dst.get("exists", True):
            if not isinstance(create, dict):
                errors.append(f"{mid}: destination.exists=false requires a create block")
            else:
                _require(create.get("kind") in CREATE_KINDS,
                         f"{mid}: create.kind must be one of {CREATE_KINDS}", errors)
                _require(bool(create.get("h1")), f"{mid}: create.h1 required", errors)

        clines = content.get("lines")
        if not isinstance(clines, list) or not clines:
            errors.append(f"{mid}: content.lines must be a non-empty list")
        else:
            for j, cl in enumerate(clines):
                prov = cl.get("provenance")
                if prov not in PROVENANCE:
                    errors.append(f"{mid}: content.lines[{j}].provenance "
                                  f"must be one of {PROVENANCE} (got {prov!r})")
                if prov == "transformed" and cl.get("original") is None:
                    errors.append(f"{mid}: content.lines[{j}] transformed line "
                                  f"missing 'original'")
                if cl.get("text") is None:
                    errors.append(f"{mid}: content.lines[{j}] missing text")

        conf = (mv.get("classification") or {}).get("confidence", "high")
        _require(conf in CONFIDENCE,
                 f"{mid}: confidence must be one of {CONFIDENCE} (got {conf!r})", errors)

        if sfile and isinstance(ls, int) and isinstance(le, int):
            ranges.setdefault(sfile, []).append((ls, le, mid))

    # Overlap detection within each source file
    for sfile, spans in ranges.items():
        spans.sort()
        for a in range(len(spans) - 1):
            s1, e1, id1 = spans[a]
            s2, e2, id2 = spans[a + 1]
            if s2 <= e1:
                errors.append(
                    f"overlapping source ranges in {sfile}: "
                    f"{id1} (lines {s1}-{e1}) and {id2} (lines {s2}-{e2})")

    return errors


# ---------------------------------------------------------------------------
# Folding: apply journal amendments to a manifest move
# ---------------------------------------------------------------------------

def effective_move(move: dict, amendments: list[dict]) -> dict:
    """Return a deep-ish copy of `move` with reroute/edit/refresh amendments
    applied in order.

    Amendments are the payloads of `decision` journal events for this move:
      - {"action": "reroute", "dest": {file, section_header, exists?, create?,
                                        date_subheader?}}
      - {"action": "edit",    "content_lines": [ {...}, ... ]}
      - {"action": "refresh", "lines": [ {n, text, h}, ... ]}  (mechanical rebase)
    Unknown actions are ignored (skip/keep/unskip affect status, not content).
    """
    import copy
    eff = copy.deepcopy(move)
    for am in amendments:
        action = am.get("action")
        if action == "reroute":
            dest = am.get("dest") or {}
            for key in ("file", "section_header", "date_subheader"):
                if key in dest:
                    eff["destination"][key] = dest[key]
            if "exists" in dest:
                eff["destination"]["exists"] = dest["exists"]
            if "create" in dest:
                eff["destination"]["create"] = dest["create"]
        elif action == "edit":
            if isinstance(am.get("content_lines"), list):
                eff["content"]["lines"] = am["content_lines"]
            if isinstance(am.get("section_header"), str):
                eff["destination"]["section_header"] = am["section_header"]
        elif action == "refresh":
            new_lines = am.get("lines")
            if isinstance(new_lines, list) and new_lines:
                eff["source"]["lines"] = new_lines
                eff["source"]["line_start"] = new_lines[0].get("n", eff["source"]["line_start"])
                eff["source"]["line_end"] = new_lines[-1].get("n", eff["source"]["line_end"])
            if isinstance(am.get("content_lines"), list) and am["content_lines"]:
                eff["content"]["lines"] = am["content_lines"]
    return eff


def source_texts(move: dict) -> list[str]:
    """The exact raw source line texts a move expects to remove from disk."""
    return [ln["text"] for ln in move["source"]["lines"]]


def content_texts(move: dict) -> list[str]:
    """The exact lines a move inserts into its destination section."""
    return [ln["text"] for ln in move["content"]["lines"]]


# ---------------------------------------------------------------------------
# Split: partial re-route (pure)
# ---------------------------------------------------------------------------

def split_move(parent: dict, parts: list[dict],
               child_id_fn=None) -> list[dict]:
    """Split a parent move into child moves by source-line index.

    `parts` is a list of {line_idxs: [int,...], dest?: {...}, keep_in_source?: bool}
    where line_idxs index into parent.source.lines (0-based). Parts must be
    disjoint and collectively a subset of the parent's lines. A part with
    keep_in_source=True yields no move (those lines stay in the daily note); a
    part with a dest overrides destination, otherwise it inherits the parent's.

    Child content lines are the subset of parent.content.lines whose source_n
    maps into the part's chosen source lines, PLUS regenerated agent-added lines
    are the caller's responsibility (agent-added lines are not split here — they
    have no source_n and are dropped from children; the executor/skill re-adds
    date subheaders/breadcrumbs per child).

    Returns a list of fully-formed child move dicts (hashes preserved from the
    parent since the underlying line texts are unchanged).
    """
    import copy
    src_lines = parent["source"]["lines"]
    n = len(src_lines)
    if child_id_fn is None:
        base = parent["id"]
        child_id_fn = lambda k: f"{base}-{chr(ord('a') + k)}"

    # Validate disjoint subset
    seen: set[int] = set()
    for p in parts:
        for idx in p.get("line_idxs", []):
            if idx < 0 or idx >= n:
                raise ManifestError(f"split index {idx} out of range 0..{n - 1}")
            if idx in seen:
                raise ManifestError(f"split index {idx} appears in more than one part")
            seen.add(idx)

    # Map source line n -> content lines that reference it
    content_by_n: dict[int, list[dict]] = {}
    for cl in parent["content"]["lines"]:
        sn = cl.get("source_n")
        if sn is not None:
            content_by_n.setdefault(sn, []).append(cl)

    children: list[dict] = []
    k = 0
    for p in parts:
        idxs = sorted(p.get("line_idxs", []))
        if not idxs:
            continue
        if p.get("keep_in_source"):
            continue  # these lines are removed from the move entirely
        chosen = [src_lines[i] for i in idxs]
        child = copy.deepcopy(parent)
        child["id"] = child_id_fn(k)
        child["source"]["lines"] = chosen
        child["source"]["line_start"] = chosen[0]["n"]
        child["source"]["line_end"] = chosen[-1]["n"]
        # content: keep only content lines whose source_n is in this part
        chosen_ns = {ln["n"] for ln in chosen}
        new_content = [
            cl for cl in parent["content"]["lines"]
            if cl.get("source_n") in chosen_ns
        ]
        child["content"]["lines"] = new_content
        # destination override
        if p.get("dest"):
            dest = p["dest"]
            for key in ("file", "section_header", "date_subheader"):
                if key in dest:
                    child["destination"][key] = dest[key]
            if "exists" in dest:
                child["destination"]["exists"] = dest["exists"]
            if "create" in dest:
                child["destination"]["create"] = dest["create"]
        children.append(child)
        k += 1

    return children
