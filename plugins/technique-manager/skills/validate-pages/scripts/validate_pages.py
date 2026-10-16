#!/usr/bin/env python3
"""Load every technique page in a headless browser and check its content, not just its files.

For each page (and the gallery, and optionally the catalog), in light and dark mode and at
desktop and phone width, it checks that:
  - the page loads with no console errors or failed requests
  - React mounted (the root has content) and the title is set
  - no block fell through to the "No component for block type" placeholder
  - the number of rendered blocks equals the number of blocks in the spec
  - the technique header shows the spec's title
  - every image loaded (naturalWidth > 0)
  - nothing scrolls sideways at phone width
  - the gallery shows one card per rendered page and every card link resolves
  - in the post view, no replaced identifier appears anywhere in the rendered text
  - with JavaScript off (as macOS Quick Look and Finder previews show it), the page still
    has its content: prerender.js put the markup in, so #root isn't empty
Both views are checked (pages/internal/ and pages/post/), or one with --view.
It also saves a screenshot of each page × theme × width under pages/_check/, so the
skill can compare it with the original screenshot.

Usage:
    python3 validate_pages.py [--root <dir>] [--view post|internal] [--only <slug>] [--catalog] [--no-shots]

Output (JSON on stdout):
    {"pages": [{"view", "page", "theme", "width", "ok", "problems": [...], "shot"}],
     "summary": {"checked": N, "failed": N}}

Exit code 1 if any check failed.

Requires: pip install playwright && python -m playwright install chromium
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "recreate-technique" / "scripts"))
import lib  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    raise SystemExit("playwright is not installed: pip install playwright && python -m playwright install chromium")

WIDTHS = {"desktop": 1280, "phone": 375}
THEMES = ("light", "dark")

# Runs in the page. Counts rendered blocks as direct children of the terminal screen.
PROBE = """() => {
  const root = document.getElementById('root');
  const screen = document.querySelector('.cu-screen');
  const imgs = [...document.images].map(i => ({src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0}));
  return {
    mounted: !!root && root.children.length > 0,
    title: document.title,
    h1: (document.querySelector('.cu-header h1') || {}).textContent || null,
    blocks: screen ? screen.children.length : null,
    missing: [...document.querySelectorAll('.cu-missing')].map(e => e.textContent),
    images: imgs,
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    cards: [...document.querySelectorAll('.cu-card')].map(a => a.getAttribute('href')),
    text: document.body.innerText,
  };
}"""


def check_page(page, url: Path, expect: dict, theme: str, width_name: str, shot_dir: Path | None) -> dict:
    errors = []
    page.on("console", lambda m: errors.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"page error: {e}"))
    page.on("requestfailed", lambda r: errors.append(f"failed request: {r.url}"))
    page.emulate_media(color_scheme=theme)
    page.goto(url.as_uri())
    page.wait_for_load_state("load")
    # Open the <details> so the original screenshot loads too.
    page.evaluate("() => document.querySelectorAll('details').forEach(d => d.open = true)")
    page.wait_for_timeout(150)
    p = page.evaluate(PROBE)

    problems = list(errors)
    if not p["mounted"]:
        problems.append("React did not mount (empty #root)")
    if not p["title"]:
        problems.append("missing <title>")
    problems += [f"missing component: {m}" for m in p["missing"]]
    problems += [f"image did not load: {i['src']}" for i in p["images"] if not i["ok"]]
    if p["overflow"] > 1:
        problems.append(f"page scrolls sideways by {p['overflow']}px at {WIDTHS[width_name]}px wide")
    if "blocks" in expect and p["blocks"] != expect["blocks"]:
        problems.append(f"rendered {p['blocks']} blocks, spec has {expect['blocks']}")
    if expect.get("title") and (p["h1"] or "").strip() != expect["title"].strip():
        problems.append(f"header shows {p['h1']!r}, spec title is {expect['title']!r}")
    if "cards" in expect:
        if sorted(p["cards"]) != sorted(expect["cards"]):
            problems.append(f"gallery cards {sorted(p['cards'])} != rendered pages {sorted(expect['cards'])}")
        problems += [f"card links to missing page: {h}" for h in p["cards"] if not (url.parent / h).exists()]
    problems += [f"post view shows a replaced identifier: {f!r}" for f in expect.get("forbidden", [])
                 if lib.redaction_pattern(f).search(p["text"])]

    shot = None
    if shot_dir:
        shot = shot_dir / f"{url.stem}.{theme}.{width_name}.png"
        page.screenshot(path=str(shot), full_page=True)
    return {"view": url.parent.name, "page": url.name, "theme": theme, "width": width_name, "ok": not problems,
            "problems": problems, "shot": str(shot) if shot else None}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("--view", choices=lib.VIEWS, help="check one view (default: both)")
    ap.add_argument("--only", help="check one slug (plus the gallery)")
    ap.add_argument("--catalog", action="store_true", help="also check _lib/catalog.html")
    ap.add_argument("--no-shots", action="store_true", help="skip screenshots")
    args = ap.parse_args()

    root = lib.find_root(args.root)
    targets = []   # (url, expect, shot_dir)
    for view in [args.view] if args.view else lib.VIEWS:
        pages = lib.pages_dir(root, view)
        specs = {s["slug"]: s for s in lib.load_specs(root) if (pages / f"{s.get('slug')}.html").exists()}
        if args.only:
            specs = {k: v for k, v in specs.items() if k == args.only}
        shot_dir = None
        if not args.no_shots:
            shot_dir = pages / "_check"
            shot_dir.mkdir(exist_ok=True)
        for slug, raw in sorted(specs.items()):
            shown = lib.post_spec(raw, root) if view == "post" else raw
            expect = {"blocks": len(shown["blocks"]), "title": shown["technique"]["title"]}
            if view == "post":
                expect["forbidden"] = lib.forbidden_terms(raw, root)
            targets.append((pages / f"{slug}.html", expect, shot_dir))
        if (pages / "index.html").exists():
            all_pages = sorted(p.name for p in pages.glob("*.html") if p.name != "index.html")
            targets.append((pages / "index.html", {"cards": all_pages}, shot_dir))
        if args.catalog and view == "internal" and (pages / "_lib" / "catalog.html").exists():
            targets.append((pages / "_lib" / "catalog.html", {}, shot_dir))
    if args.only and not any(u.stem == args.only for u, _, _ in targets):
        raise SystemExit(f"No rendered page for slug {args.only!r}")

    results = []
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as e:  # missing browser download or system libraries
            raise SystemExit(f"Chromium did not launch: {str(e).splitlines()[0]}\n"
                             "Run: python -m playwright install chromium")
        for width_name, width in WIDTHS.items():
            for theme in THEMES:
                ctx = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=theme)
                for url, expect, shot_dir in targets:
                    page = ctx.new_page()
                    results.append(check_page(page, url, expect, theme, width_name, shot_dir))
                    page.close()
                ctx.close()
        # Quick Look runs no JavaScript: the pre-rendered markup must carry the page alone.
        ctx = browser.new_context(viewport={"width": WIDTHS["desktop"], "height": 900}, java_script_enabled=False)
        for url, expect, _ in targets:
            page = ctx.new_page()
            page.goto(url.as_uri())
            p = page.evaluate(PROBE)
            problems = []
            if not p["mounted"]:
                problems.append("blank without JavaScript (Quick Look shows nothing); re-render with Node installed")
            elif "blocks" in expect and p["blocks"] != expect["blocks"]:
                problems.append(f"without JavaScript: {p['blocks']} blocks, spec has {expect['blocks']}")
            results.append({"view": url.parent.name, "page": url.name, "theme": "no-js", "width": "desktop",
                            "ok": not problems, "problems": problems, "shot": None})
            page.close()
        ctx.close()
        browser.close()

    failed = sum(1 for r in results if not r["ok"])
    print(json.dumps({"pages": results, "summary": {"checked": len(results), "failed": failed}},
                     ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
