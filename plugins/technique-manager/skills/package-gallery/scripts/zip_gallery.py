#!/usr/bin/env python3
"""Zip the shareable gallery (pages/post/: pages, index, component library) so it opens offline.

Only the post view is zipped. The internal view, the original screenshots and the specs
(which hold the real names and values) never go in.

Checks that every local src/href in every page resolves inside pages/post/ before zipping,
so a zip never ships with a broken link.

Usage:
    python3 zip_gallery.py [--root <dir>] [--out <file.zip>]

Output (JSON on stdout):
    {"zip": "<path>", "files": N, "bytes": N, "broken": [{"page", "ref"}]}

Exit code 1 (and no zip) if any page has a broken local reference.
"""
import argparse
import datetime as dt
import json
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "recreate-technique" / "scripts"))
import lib  # noqa: E402

REF = re.compile(r"""(?:src|href)=["']([^"'#]+)""")


def broken_refs(pages: Path) -> list[dict]:
    out = []
    for page in sorted(p for p in pages.rglob("*.html") if "_check" not in p.relative_to(pages).parts):
        for ref in REF.findall(page.read_text(encoding="utf-8")):
            if re.match(r"^[a-z]+:", ref):  # http:, data:, mailto:
                continue
            target = (page.parent / unquote(ref)).resolve()
            if not target.exists() or pages.resolve() not in target.parents and target != pages.resolve():
                out.append({"page": str(page.relative_to(pages)), "ref": ref})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("--out", help="zip path (default: <root>/techniques-YYYYMMDD.zip)")
    args = ap.parse_args()

    root = lib.find_root(args.root)
    pages = lib.pages_dir(root, "post")
    if not (pages / "index.html").exists():
        raise SystemExit("No pages/post/index.html; run build_gallery.py first")

    broken = broken_refs(pages)
    if broken:
        print(json.dumps({"zip": None, "broken": broken}, indent=2))
        return 1

    out = Path(args.out).expanduser() if args.out else root / f"techniques-{dt.date.today():%Y%m%d}.zip"
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(pages.rglob("*")):
            rel = f.relative_to(pages)
            if f.is_dir() or f.name == ".DS_Store" or rel.parts[0] == "_check":
                continue
            z.write(f, Path("techniques") / rel)
            count += 1
    print(json.dumps({"zip": str(out), "files": count, "bytes": out.stat().st_size, "broken": []}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
