#!/usr/bin/env python3
"""Build <view>/index.html: a gallery card for every rendered technique page, for each view
(pages/post/ is the shareable gallery; pages/internal/ is the checking one, with thumbnails).

The gallery renders with the same claude-ui component library as the pages
(<Gallery> and <TechniqueCard> in claude-ui.js), and re-syncs pages/_lib first.

Usage:
    python3 build_gallery.py [--root <dir>] [--title "Claude techniques"] [--view post|internal]

Output (JSON on stdout), one entry per view:
    [{"view", "index": "<path>", "cards": N, "skipped": [{"slug", "reason"}]}]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "recreate-technique" / "scripts"))
import lib  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "gallery.html"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("--title", default="Claude techniques")
    ap.add_argument("--view", choices=lib.VIEWS, help="build one view's gallery (default: both)")
    args = ap.parse_args()

    root = lib.find_root(args.root)
    report = [build(root, view, args.title) for view in ([args.view] if args.view else lib.VIEWS)]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cards_for(root: Path, view: str) -> tuple[list[dict], list[dict]]:
    """One card per rendered page in this view, newest first; and the specs left out."""
    pages = lib.pages_dir(root, view)
    cards, skipped = [], []
    for raw in lib.load_specs(root):
        # The post gallery shows the redacted title and summary, never the original screenshot.
        spec = lib.post_spec(raw, root) if view == "post" else raw
        slug = spec.get("slug", "")
        if not (pages / f"{slug}.html").exists():
            skipped.append({"slug": slug, "reason": "no rendered page; run render_page.py"})
            continue
        t, src = spec.get("technique") or {}, spec.get("source") or {}
        image = f"img/{slug}.png" if view == "internal" else None
        focus = spec.get("focus") or {}
        cards.append({
            "slug": slug,
            "href": f"{slug}.html",
            # Hub fields (internal view only): where the technique stands, and its confirmed focus.
            "status": lib.effective_status(spec) if view == "internal" else None,
            "focus": focus.get("line") if view == "internal" and focus.get("confirmed") else None,
            "title": t.get("title", slug),
            "mechanism": t.get("mechanism"),
            "why": t.get("why"),
            "taken": src.get("taken"),
            "image": image if image and (pages / image).exists() else None,
        })
    cards.sort(key=lambda c: c.get("taken") or "", reverse=True)
    return cards, skipped


def build(root: Path, view: str, title: str) -> dict:
    pages = lib.pages_dir(root, view)
    pages.mkdir(parents=True, exist_ok=True)
    lib.sync_lib(pages)
    cards, skipped = cards_for(root, view)

    index = pages / "index.html"
    label = title if view == "post" else f"{title} (internal)"
    index.write_text(lib.fill(TEMPLATE, label, cards, lib.prerender("Gallery", {"title": label, "cards": cards})),
                     encoding="utf-8")
    return {"view": view, "index": str(index), "cards": len(cards), "skipped": skipped}


if __name__ == "__main__":
    sys.exit(main())
