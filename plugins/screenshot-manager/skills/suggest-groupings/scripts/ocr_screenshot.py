#!/usr/bin/env python3
"""Extract text from a screenshot using macOS Vision OCR.

Usage:
    python3 ocr_screenshot.py <path_to_image>

Output:
    JSON: {"path": "<path>", "text": "<extracted text>"}

Requirements:
    pyobjc-framework-Vision (pre-installed on modern macOS)
    Install if missing: pip3 install pyobjc-framework-Vision
"""
import json
import os
import sys
import unicodedata
from pathlib import Path


def resolve_path(raw: str) -> Path:
    """Resolve a path that may have Unicode normalization or NNBSP issues.

    macOS screenshot filenames use U+202F (NARROW NO-BREAK SPACE) before
    AM/PM, e.g. "Screenshot 2026-02-13 at 3.13.34\u202fPM.png".
    Shell ls displays this identically to a regular space, so callers may
    pass a path with a regular space.  We try NFC/NFD first, then fall back
    to scanning the parent directory for a close match.
    """
    for form in ("NFC", "NFD"):
        p = Path(unicodedata.normalize(form, raw))
        if p.exists():
            return p

    # Fallback: scan parent dir for a file whose normalized name matches
    p = Path(raw)
    parent = p.parent
    name_norm = unicodedata.normalize("NFC", p.name).replace("\u202f", " ")
    for form in ("NFC", "NFD"):
        try:
            parent_norm = Path(unicodedata.normalize(form, str(parent)))
            for entry in os.listdir(parent_norm):
                entry_norm = unicodedata.normalize("NFC", entry).replace("\u202f", " ")
                if entry_norm == name_norm:
                    return parent_norm / entry
        except FileNotFoundError:
            pass

    return p  # return original; caller handles not-found


def extract_text(image_path: str) -> str:
    try:
        import Vision
        from Foundation import NSURL
    except ImportError:
        raise RuntimeError(
            "pyobjc-framework-Vision not found. Install with: pip3 install pyobjc-framework-Vision"
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
    texts = []
    for obs in observations:
        candidates = obs.topCandidates_(1)
        if candidates:
            texts.append(candidates[0].string())

    return "\n".join(texts)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: ocr_screenshot.py <image_path>"}))
        sys.exit(1)

    path = resolve_path(sys.argv[1])

    if not path.exists():
        print(json.dumps({"path": str(path), "error": f"File not found: {path}"}))
        sys.exit(1)

    try:
        text = extract_text(str(path))
        print(json.dumps({"path": str(path), "text": text}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"path": str(path), "error": str(e)}, ensure_ascii=False))
        sys.exit(1)
