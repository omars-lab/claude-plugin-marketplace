#!/usr/bin/env python3
"""Extract URLs from screenshots using macOS Vision OCR.

Scans a single file or a directory of images, runs OCR on each,
and parses URLs from the extracted text — including browser address
bars, in-page links, and any URL-shaped strings.

Usage:
    python3 extract_urls.py --file /path/to/screenshot.png
    python3 extract_urls.py --dir  /path/to/Screenshots/GSIP Workshop
    python3 extract_urls.py --dir  /path/to/Screenshots  --recursive

Output (JSON):
    {
      "/path/to/screenshot.png": {
        "urls": ["https://...", "https://..."],
        "address_bar": "https://...",   # best candidate for browser URL bar
        "error": null
      },
      ...
    }

Requirements:
    pyobjc-framework-Vision  (install into 'screenshot-ocr' conda env)
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

EXTS = {".png", ".jpg", ".jpeg", ".heic"}

# Match http/https URLs (greedy up to whitespace or quote-like chars)
URL_RE = re.compile(
    r"https?://"
    r"[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+"
)

# Patterns that look like a browser address bar:
#   - Starts at the very beginning of a line (after optional spaces)
#   - Is the longest URL on that line
ADDRESS_BAR_LINE_RE = re.compile(r"^\s*(https?://\S+)\s*$", re.MULTILINE)


def resolve_path(raw: str) -> Path:
    """Resolve path accounting for Unicode normalization and U+202F in filenames."""
    for form in ("NFC", "NFD"):
        p = Path(unicodedata.normalize(form, raw))
        if p.exists():
            return p
    # Fallback: scan parent directory for a close match
    p = Path(raw)
    parent = p.parent
    name_norm = unicodedata.normalize("NFC", p.name).replace("\u202f", " ")
    for form in ("NFC", "NFD"):
        try:
            parent_norm = Path(unicodedata.normalize(form, str(parent)))
            for entry in parent_norm.iterdir():
                if unicodedata.normalize("NFC", entry.name).replace("\u202f", " ") == name_norm:
                    return parent_norm / entry.name
        except FileNotFoundError:
            pass
    return p


def extract_text(image_path: Path) -> str:
    """Run macOS Vision OCR on a single image. Returns extracted text."""
    try:
        import Vision
        from Foundation import NSURL
    except ImportError:
        raise RuntimeError(
            "pyobjc-framework-Vision not found. "
            "Run: conda run -n screenshot-ocr pip install pyobjc-framework-Vision"
        )

    url = NSURL.fileURLWithPath_(str(image_path))
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)

    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, None)
    success, error = handler.performRequests_error_([request], None)
    if not success:
        raise RuntimeError(f"Vision request failed: {error}")

    observations = request.results() or []
    lines = []
    for obs in observations:
        candidates = obs.topCandidates_(1)
        if candidates:
            lines.append(candidates[0].string())
    return "\n".join(lines)


def parse_urls(text: str) -> tuple[list[str], str | None]:
    """Extract all URLs and identify the most likely browser address bar URL.

    Returns:
        (urls, address_bar)
        urls        — deduplicated list, ordered by first appearance
        address_bar — single best candidate for the browser URL bar, or None
    """
    all_urls = URL_RE.findall(text)

    # Deduplicate preserving order
    seen: set[str] = set()
    urls: list[str] = []
    for u in all_urls:
        # Strip trailing punctuation that OCR often attaches (., ), >, …)
        u = u.rstrip(".,)>;\"'")
        if u not in seen:
            seen.add(u)
            urls.append(u)

    # Address bar heuristic:
    #   1. Prefer URLs that appear alone on a line (address bar is typically
    #      the only content on its line in the OCR stream)
    #   2. Among those, prefer the longest (full URL vs link text)
    address_bar: str | None = None
    solo_matches = ADDRESS_BAR_LINE_RE.findall(text)
    solo_urls = [u.rstrip(".,)>;\"'") for u in solo_matches]
    if solo_urls:
        address_bar = max(solo_urls, key=len)
    elif urls:
        # Fallback: longest URL overall
        address_bar = max(urls, key=len)

    return urls, address_bar


def process_file(path: Path) -> dict:
    resolved = resolve_path(str(path))
    if not resolved.exists():
        return {"urls": [], "address_bar": None, "error": f"File not found: {path}"}
    try:
        text = extract_text(resolved)
        urls, address_bar = parse_urls(text)
        return {"urls": urls, "address_bar": address_bar, "error": None}
    except Exception as e:
        return {"urls": [], "address_bar": None, "error": str(e)}


def collect_images(path: Path, recursive: bool = False) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in EXTS else []
    pattern = "**/*" if recursive else "*"
    return sorted(
        f for f in path.glob(pattern)
        if f.is_file() and f.suffix.lower() in EXTS
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract URLs from screenshots via OCR")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to a single screenshot")
    group.add_argument("--dir", help="Path to a directory of screenshots")
    parser.add_argument(
        "--recursive", action="store_true",
        help="Recurse into subdirectories (only with --dir)"
    )
    args = parser.parse_args()

    target = Path(args.file if args.file else args.dir)
    images = collect_images(target, recursive=args.recursive)

    if not images:
        print(json.dumps({"error": f"No image files found at: {target}"}, ensure_ascii=False))
        sys.exit(1)

    results: dict[str, dict] = {}
    for img in images:
        results[str(img)] = process_file(img)

    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
