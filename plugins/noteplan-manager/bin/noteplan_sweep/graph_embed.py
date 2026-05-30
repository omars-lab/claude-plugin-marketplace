"""
graph_embed.py — Vector embedding for the conversation graph (CG-C + CG-D).

Binary format matches icon-kit's cosine.js:
  graph.embeddings.keys  — newline-separated "<node_id>@<model>" entries
  graph.embeddings.bin   — packed Float32 little-endian, row-major

Commands:
  graph-embed    Embed all unembedded graph nodes (incremental; --force to re-embed all)
  graph-build    Build networkx DiGraph + load embeddings → write graph.json summary stats
  graph-query-vec  Cosine similarity search over embedded nodes
"""

import json
import re
import struct
import sys
from pathlib import Path
from typing import Callable

import noteplan_sweep.utils as utils

# ---------------------------------------------------------------------------
# Binary I/O (mirrors cosine.js)
# ---------------------------------------------------------------------------

def load_embeddings_bin(dash_dir: Path, dims: int) -> dict[str, list[float]]:
    """Load graph.embeddings.bin + graph.embeddings.keys → {node_id@model: [float]}."""
    bin_path = dash_dir / "graph.embeddings.bin"
    keys_path = dash_dir / "graph.embeddings.keys"
    if not bin_path.exists() or not keys_path.exists():
        return {}

    keys = [k for k in keys_path.read_text(encoding="utf-8").strip().split("\n") if k]
    raw = bin_path.read_bytes()
    n_floats = len(raw) // 4
    expected = len(keys) * dims
    if n_floats != expected:
        utils.verbose(f"[embed] Warning: bin has {n_floats} floats, expected {expected}. Returning empty.")
        return {}

    embed_map: dict[str, list[float]] = {}
    for i, key in enumerate(keys):
        offset = i * dims * 4
        vec = list(struct.unpack_from(f"<{dims}f", raw, offset))
        embed_map[key] = vec
    return embed_map


def save_embeddings_bin(embed_map: dict[str, list[float]], dash_dir: Path, dims: int):
    """Save embed_map → graph.embeddings.bin + graph.embeddings.keys."""
    dash_dir.mkdir(exist_ok=True)
    keys = list(embed_map.keys())
    buf = bytearray(len(keys) * dims * 4)
    for i, key in enumerate(keys):
        vec = embed_map[key]
        for j in range(dims):
            struct.pack_into("<f", buf, (i * dims + j) * 4, vec[j] if j < len(vec) else 0.0)
    (dash_dir / "graph.embeddings.keys").write_text("\n".join(keys), encoding="utf-8")
    (dash_dir / "graph.embeddings.bin").write_bytes(bytes(buf))


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = sum(x * x for x in vec) ** 0.5
    if norm < 1e-9:
        return vec
    return [x / norm for x in vec]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# Embedding backends
# ---------------------------------------------------------------------------

def _embed_lmstudio(texts: list[str], host: str = "localhost", port: int = 1234,
                    model: str = "nomic-embed-text-v1.5") -> list[list[float] | None]:
    """Call LM Studio's /v1/embeddings endpoint."""
    import http.client, json as _json
    conn = http.client.HTTPConnection(host, port, timeout=30)
    body = _json.dumps({"input": texts, "model": model})
    try:
        conn.request("POST", "/v1/embeddings",
                     body=body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        if resp.status != 200:
            return [None] * len(texts)
        data = _json.loads(resp.read())
        result_map = {item["index"]: item["embedding"] for item in data.get("data", [])}
        return [result_map.get(i) for i in range(len(texts))]
    except Exception as e:
        utils.verbose(f"[embed] LM Studio error: {e}")
        return [None] * len(texts)
    finally:
        conn.close()


def _embed_sentence_transformers(texts: list[str],
                                  model_name: str = "all-MiniLM-L6-v2") -> list[list[float] | None]:
    """Use sentence-transformers (must be installed in venv)."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)
        vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vecs]
    except ImportError:
        utils.verbose("[embed] sentence-transformers not installed.")
        return [None] * len(texts)
    except Exception as e:
        utils.verbose(f"[embed] sentence-transformers error: {e}")
        return [None] * len(texts)


def _embed_batch(texts: list[str], backend: str, **kwargs) -> list[list[float] | None]:
    if backend == "lmstudio":
        return _embed_lmstudio(texts, **kwargs)
    elif backend == "sentence-transformers":
        return _embed_sentence_transformers(texts, **kwargs)
    return [None] * len(texts)


# ---------------------------------------------------------------------------
# Node text builder
# ---------------------------------------------------------------------------

def _node_embed_text(node: dict) -> str:
    """Build the text to embed for a node."""
    t = node["type"]
    label = node.get("label", "")
    attrs = node.get("attrs", {})
    if t == "Session":
        project = attrs.get("project", "")
        use_case = attrs.get("use_case", "")
        files = " ".join(attrs.get("files_written", [])[:5]) if isinstance(attrs.get("files_written"), list) else ""
        return f"{label} | {use_case} | {project} | {files}"
    elif t == "Plan":
        desc = attrs.get("description", "")
        project = attrs.get("project", "")
        ws = attrs.get("workstream", "")
        return f"{label} | {project} | {ws} | {desc}"
    elif t == "Repo":
        domain = attrs.get("domain", "")
        return f"{label} | {domain}"
    elif t == "Skill":
        group = attrs.get("group", "")
        preview = attrs.get("content_preview", "")[:200]
        return f"{label} | {group} | {preview}"
    elif t == "UseCase":
        return label
    elif t == "App":
        return f"{label} | app | {attrs.get('normalized', '')}"
    return label


# ---------------------------------------------------------------------------
# Command: graph-embed
# ---------------------------------------------------------------------------

_MODEL_DIMS = {
    "nomic-embed-text-v1.5": 768,
    "all-MiniLM-L6-v2": 384,
    "nomic-embed-text": 768,
}
_DEFAULT_MODEL = "nomic-embed-text-v1.5"
_DEFAULT_DIMS = 768
_BATCH_SIZE = 32


def cmd_graph_embed(args):
    root = utils.noteplan_root()
    dash_dir = root / "dashboard"
    graph_path = dash_dir / "graph.json"

    if not graph_path.exists():
        utils.err("dashboard/graph.json not found. Run graph-extract first.")
        sys.exit(utils.EXIT_NOT_FOUND)

    backend = getattr(args, "backend", "lmstudio")
    model = getattr(args, "model", _DEFAULT_MODEL)
    force = getattr(args, "force", False)
    lmstudio_port = getattr(args, "port", 1234)
    dims = _MODEL_DIMS.get(model, _DEFAULT_DIMS)

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = graph["nodes"]

    # Load existing embeddings
    embed_map = load_embeddings_bin(dash_dir, dims)
    utils.verbose(f"[embed] Loaded {len(embed_map)} existing embeddings (dims={dims})")

    # Determine which nodes need embedding
    to_embed = []
    for node in nodes:
        key = f"{node['id']}@{model}"
        if force or key not in embed_map:
            to_embed.append(node)

    if not to_embed:
        utils.log(f"graph-embed: all {len(nodes)} nodes already embedded. Use --force to re-embed.")
        return

    utils.log(f"graph-embed: embedding {len(to_embed)} nodes via {backend} ({model})...")

    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would embed {len(to_embed)} nodes")
        return

    embedded = 0
    failed = 0
    kwargs = {}
    if backend == "lmstudio":
        kwargs = {"host": "localhost", "port": lmstudio_port, "model": model}
    elif backend == "sentence-transformers":
        kwargs = {"model_name": model}

    for i in range(0, len(to_embed), _BATCH_SIZE):
        batch = to_embed[i:i + _BATCH_SIZE]
        texts = [_node_embed_text(n) for n in batch]
        vecs = _embed_batch(texts, backend, **kwargs)

        all_failed = all(v is None for v in vecs)
        if all_failed and i == 0:
            utils.err(f"[embed] Backend '{backend}' unreachable — aborting.")
            sys.exit(1)

        for node, vec in zip(batch, vecs):
            if vec is None:
                failed += 1
                continue
            norm_vec = _l2_normalize(vec[:dims])
            embed_map[f"{node['id']}@{model}"] = norm_vec
            embedded += 1

        # Checkpoint after each batch
        save_embeddings_bin(embed_map, dash_dir, dims)
        pct = min(100, round((i + len(batch)) / len(to_embed) * 100))
        utils.verbose(f"  [{pct}%] {min(i + _BATCH_SIZE, len(to_embed))}/{len(to_embed)}")

    utils.log(f"graph-embed: {embedded} embedded, {failed} failed → graph.embeddings.bin")


# ---------------------------------------------------------------------------
# Command: graph-query-vec (cosine similarity search)
# ---------------------------------------------------------------------------

def cmd_graph_query_vec(args):
    root = utils.noteplan_root()
    dash_dir = root / "dashboard"
    graph_path = dash_dir / "graph.json"

    if not graph_path.exists():
        utils.err("dashboard/graph.json not found. Run graph-extract first.")
        sys.exit(utils.EXIT_NOT_FOUND)

    model = getattr(args, "model", _DEFAULT_MODEL)
    dims = _MODEL_DIMS.get(model, _DEFAULT_DIMS)
    query = args.query
    top_k = getattr(args, "top_k", 10)
    backend = getattr(args, "backend", "lmstudio")
    lmstudio_port = getattr(args, "port", 1234)

    embed_map = load_embeddings_bin(dash_dir, dims)
    if not embed_map:
        utils.err("No embeddings found. Run graph-embed first.")
        sys.exit(utils.EXIT_NOT_FOUND)

    # Embed the query
    kwargs = {"host": "localhost", "port": lmstudio_port, "model": model} if backend == "lmstudio" \
        else {"model_name": model}
    vecs = _embed_batch([query], backend, **kwargs)
    if not vecs or vecs[0] is None:
        utils.err(f"Could not embed query via {backend}. Is the server running?")
        sys.exit(1)
    q_vec = _l2_normalize(vecs[0][:dims])

    # Score all embeddings with dot product (L2-normalized = cosine)
    suffix = f"@{model}"
    scores: list[tuple[str, float]] = []
    for key, vec in embed_map.items():
        if not key.endswith(suffix):
            continue
        node_id = key[: -len(suffix)]
        score = _dot(q_vec, vec)
        scores.append((node_id, score))

    scores.sort(key=lambda x: -x[1])

    # Load graph for label lookup
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    node_by_id = {n["id"]: n for n in graph["nodes"]}

    print(f"\nTop {min(top_k, len(scores))} results for: '{query}'\n")
    for node_id, score in scores[:top_k]:
        node = node_by_id.get(node_id, {})
        label = node.get("label", node_id)
        ntype = node.get("type", "?")
        print(f"  {score:.3f}  [{ntype}] {label}")
    print()


# ---------------------------------------------------------------------------
# Command: graph-build (CG-D) — validate + update stats in graph.json
# ---------------------------------------------------------------------------

def cmd_graph_build(args):
    """Re-load graph.json + embeddings, update stats, write summary."""
    root = utils.noteplan_root()
    dash_dir = root / "dashboard"
    graph_path = dash_dir / "graph.json"

    if not graph_path.exists():
        utils.err("dashboard/graph.json not found. Run graph-extract first.")
        sys.exit(utils.EXIT_NOT_FOUND)

    model = getattr(args, "model", _DEFAULT_MODEL)
    dims = _MODEL_DIMS.get(model, _DEFAULT_DIMS)

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    embed_map = load_embeddings_bin(dash_dir, dims)

    embedded_ids = {k.split("@")[0] for k in embed_map}
    total = len(graph["nodes"])
    embedded_count = sum(1 for n in graph["nodes"] if n["id"] in embedded_ids)

    # Patch graph with embedding coverage
    graph["embedding_meta"] = {
        "model": model,
        "dims": dims,
        "embedded_count": embedded_count,
        "total_count": total,
        "coverage_pct": round(embedded_count / total * 100, 1) if total else 0,
    }

    if utils.DRY_RUN:
        utils.log(f"[dry-run] graph-build: {embedded_count}/{total} nodes embedded ({graph['embedding_meta']['coverage_pct']}%)")
        return

    graph_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
    utils.log(f"graph-build: {embedded_count}/{total} nodes embedded "
              f"({graph['embedding_meta']['coverage_pct']}% coverage) — updated {graph_path}")
