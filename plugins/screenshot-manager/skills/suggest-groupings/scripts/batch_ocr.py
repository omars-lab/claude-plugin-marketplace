#!/usr/bin/env python3
"""Batch OCR all images in one or more directories (or explicit file paths).

Usage:
    # OCR all images on the Desktop:
    python3 batch_ocr.py --desktop

    # OCR all images under a Screenshots root (one subdir per source):
    python3 batch_ocr.py --root ~/Library/CloudStorage/OneDrive-ServiceNow/"📸 Screenshots"

    # OCR all images in a specific subdirectory:
    python3 batch_ocr.py --dir "/path/to/GSIP Workshop"

    # OCR explicit files:
    python3 batch_ocr.py --files file1.png file2.png

    # OCR the files listed in a text file (one path per line), writing the JSON to a file:
    python3 batch_ocr.py --list to_read.txt --out ocr.json

--out writes the JSON there instead of printing it, and progress goes to stderr as
ev=ocr_progress lines, so a long run can be watched with grep.

Output:
    JSON: {
        "<path>": {"text": "...", "error": null},
        ...
    }

Requirements:
    pyobjc-framework-Vision  (run inside screenshot-ocr conda env)
"""
import json
import os
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

EXTS = {".png", ".jpg", ".jpeg", ".heic"}


def collect_files(args: list[str]) -> list[Path]:
    """Parse CLI args and return a flat list of image paths to OCR."""
    paths: list[Path] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--desktop":
            desktop = Path.home() / "Desktop"
            paths.extend(
                sorted(f for f in desktop.iterdir() if f.suffix.lower() in EXTS)
            )
        elif arg == "--root":
            i += 1
            root = Path(unicodedata.normalize("NFC", os.path.expanduser(args[i])))
            for d in sorted(root.iterdir()):
                if d.is_dir():
                    paths.extend(
                        sorted(f for f in d.iterdir() if f.suffix.lower() in EXTS)
                    )
        elif arg == "--dir":
            i += 1
            d = Path(unicodedata.normalize("NFC", os.path.expanduser(args[i])))
            paths.extend(sorted(f for f in d.iterdir() if f.suffix.lower() in EXTS))
        elif arg == "--list":
            i += 1
            for line in Path(os.path.expanduser(args[i])).read_text().splitlines():
                if line.strip():
                    paths.append(Path(unicodedata.normalize("NFC", line.strip())))
        elif arg == "--out":
            i += 1
        elif arg == "--files":
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                paths.append(Path(unicodedata.normalize("NFC", os.path.expanduser(args[i]))))
                i += 1
            continue
        i += 1
    return paths


def extract_text(image_path: Path) -> tuple[str | None, str | None]:
    """Return (text, error). Uses macOS Vision OCR."""
    try:
        import Vision
        from Foundation import NSURL
    except ImportError:
        return None, "pyobjc-framework-Vision not installed"

    url = NSURL.fileURLWithPath_(str(image_path))
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, None)
    success, error = handler.performRequests_error_([request], None)
    if not success:
        return None, f"Vision request failed: {error}"
    observations = request.results() or []
    texts = []
    for obs in observations:
        candidates = obs.topCandidates_(1)
        if candidates:
            texts.append(candidates[0].string())
    return "\n".join(texts), None


def main():
    args = sys.argv[1:]
    if not args:
        print(json.dumps({"error": "No input specified. Use --desktop, --root, --dir, or --files."}))
        sys.exit(1)

    files = collect_files(args)
    if not files:
        print(json.dumps({"error": "No image files found for the given inputs."}))
        sys.exit(1)

    out = Path(os.path.expanduser(args[args.index("--out") + 1])) if "--out" in args else None
    results: dict = {}
    for n, f in enumerate(files, 1):
        if not f.exists():
            results[str(f)] = {"text": None, "error": f"File not found: {f}"}
            continue
        text, error = extract_text(f)
        results[str(f)] = {"text": text, "error": error}
        if n % 25 == 0 or n == len(files):
            print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} pid={os.getpid()} "
                  f"ev=ocr_progress done={n} of={len(files)}", file=sys.stderr)

    if out:
        out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
