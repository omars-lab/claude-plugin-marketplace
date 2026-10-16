#!/usr/bin/env python3
"""Render technique specs into HTML pages that use the shared claude-ui component library.

A page is the templates/page.html shell plus its spec. All markup and styling comes from
components/claude-ui.js and claude-ui.css, which are copied into each view's _lib on every run.

Each spec renders into two views (see lib.VIEWS):
    pages/internal/<slug>.html   faithful, with the original screenshot, replacements and session
    pages/post/<slug>.html       redactions applied, no screenshot: the shareable page
The post page is not written while scan_privacy.py still finds something in it.

Usage:
    python3 render_page.py --spec <root>/pages/specs/<slug>.json
    python3 render_page.py --all                 # every spec in the specs folder
    python3 render_page.py --all --root <dir>    # a techniques folder other than the default

Output (JSON on stdout):
    {"rendered": [{"slug", "internal", "post", "image"}], "errors": [{"spec", "problems": [...]}]}

Exit code 1 if any spec has problems (unknown block type, missing title, missing screenshot,
or identifiers left in the post view).
"""
import argparse
import json
import shutil
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
import scan_privacy  # noqa: E402


def find_file(folder: Path, name: str) -> Path | None:
    for form in ("NFC", "NFD"):
        p = folder / unicodedata.normalize(form, name)
        if p.exists():
            return p
    # macOS puts U+202F before AM/PM; a spec may have been typed with a plain space.
    want = unicodedata.normalize("NFC", name).replace(" ", " ")
    for p in folder.iterdir():
        if unicodedata.normalize("NFC", p.name).replace(" ", " ") == want:
            return p
    return None


def check(spec: dict, known: set[str]) -> list[str]:
    problems = []
    if not spec.get("slug"):
        problems.append("missing slug")
    if not (spec.get("technique") or {}).get("title"):
        problems.append("missing technique.title")
    blocks = spec.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        problems.append("blocks must be a non-empty list")
    else:
        for i, b in enumerate(blocks):
            t = b.get("type")
            if t not in known:
                problems.append(f"block {i}: no component for type {t!r}; add it to claude-ui.js first")
    # Hub fields (all optional). A bad value is an error, not a silent skip.
    if spec.get("status") is not None and spec["status"] not in lib.STATUSES:
        problems.append(f"status {spec['status']!r} is not one of {', '.join(lib.STATUSES)}")
    focus = spec.get("focus")
    if focus is not None:
        if not isinstance(focus, dict):
            problems.append("focus must be an object: {line, blocks, confirmed, source}")
        else:
            if "line" in focus and not isinstance(focus["line"], str):
                problems.append("focus.line must be text")
            n = len(blocks) if isinstance(blocks, list) else 0
            bad = [b for b in focus.get("blocks", []) if not isinstance(b, int) or not 0 <= b < n]
            if bad:
                problems.append(f"focus.blocks {bad} are not block indexes (0 to {n - 1})")
            if focus.get("confirmed") and not focus.get("line"):
                problems.append("focus.confirmed needs focus.line")
    post = spec.get("post") or {}
    if post.get("trim") and not (focus or {}).get("blocks"):
        problems.append("post.trim needs focus.blocks: nothing to trim to")
    return problems


def render(spec_path: Path, root: Path, known: set[str]) -> dict:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    problems = check(spec, known)
    image = src = None
    internal = lib.pages_dir(root, "internal")
    src_name = (spec.get("source") or {}).get("file")
    # The copy made by an earlier render. A background job (launchd) can't read ~/Desktop, which
    # macOS protects, so it re-renders from this copy instead of failing.
    kept = next(iter(sorted((internal / "img").glob(f"{spec.get('slug')}.*"))), None) if (internal / "img").exists() else None
    if src_name:
        try:
            src = find_file(lib.screenshots_dir(root), src_name)
        except (OSError, SystemExit):
            src = None
        if src is None and kept is None:
            problems.append(f"screenshot not found in the screenshots folder: {src_name}")
    if problems:
        return {"spec": str(spec_path), "problems": problems}

    if src is not None:
        (internal / "img").mkdir(parents=True, exist_ok=True)
        image = f"img/{spec['slug']}{src.suffix.lower()}"
        try:
            shutil.copy2(src, internal / image)
        except OSError:
            if not (internal / image).exists():
                raise
        spec["source"]["image"] = image
    elif kept is not None:
        image = f"img/{kept.name}"
        spec["source"]["image"] = image
    spec["view"] = "internal"
    spec["applied_redactions"] = lib.redactions_for(spec, root)
    spec["status"] = lib.effective_status(spec)
    ctx = (spec.get("context") or {}).get("file")
    if ctx and (root / ctx).exists():
        spec["context_href"] = (root / ctx).resolve().as_uri()
    out_internal = internal / f"{spec['slug']}.html"
    out_internal.write_text(lib.fill(lib.PAGE_TEMPLATE, spec["technique"]["title"], spec,
                                     lib.prerender("Page", {"spec": spec, "backHref": "index.html"})), encoding="utf-8")

    post = lib.post_spec({k: v for k, v in spec.items() if k != "applied_redactions"}, root)
    left = scan_privacy.scan(post, tuple(r["replace"] for r in lib.redactions_for(spec, root)))
    out_post = lib.pages_dir(root, "post") / f"{spec['slug']}.html"
    if left:
        if out_post.exists():
            out_post.unlink()  # never leave a stale post page that predates the new findings
        return {"spec": str(spec_path), "internal": str(out_internal),
                "problems": [f"post view still shows {h['kind']} {h['match']!r} at {h['where']}; add a redaction" for h in left]}
    out_post.write_text(lib.fill(lib.PAGE_TEMPLATE, post["technique"]["title"], post,
                                 lib.prerender("Page", {"spec": post, "backHref": "index.html"})), encoding="utf-8")
    return {"slug": spec["slug"], "internal": str(out_internal), "post": str(out_post), "image": image}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", help="techniques folder (default: ~/Desktop/📸 Screenshots of Techniques)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--spec", action="append", help="spec file to render (repeatable)")
    g.add_argument("--all", action="store_true", help="render every spec in the specs folder")
    args = ap.parse_args()

    root = lib.find_root(args.root)
    for view in lib.VIEWS:
        lib.pages_dir(root, view).mkdir(parents=True, exist_ok=True)
        lib.sync_lib(lib.pages_dir(root, view))
    known = lib.block_types()

    paths = lib.spec_paths(root) if args.all else [Path(s).expanduser() for s in args.spec]
    result = {"rendered": [], "errors": []}
    for p in paths:
        r = render(p, root, known)
        result["errors" if "problems" in r else "rendered"].append(r)
    if not shutil.which("node"):
        result["warning"] = "Node isn't installed, so pages are JavaScript-only and show blank in Quick Look previews"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
