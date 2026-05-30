#!/usr/bin/env python3
"""Match Desktop screenshots to active NotePlan plans using OCR text + temporal signals.

This is a pre-pass that narrows each screenshot to a shortlist of candidate plans.
Claude's Vision (Phase 6.5 in the skill) then reads each image alongside its OCR
text + candidates to make the final classification call.

Usage:
    python3 match_screenshots.py --ocr OCR_JSON --plans PLANS_JSON
                                 [--threshold 3] [--out MANIFEST_JSON]

Input:
    OCR_JSON:   {"<abs_path>": {"text": "...", "error": null}, ...}
    PLANS_JSON: output of scan_plans.py

Output (stdout or --out file):
    JSON array: [{
      src, filename_date, filename_time, ocr_excerpt,
      candidates: [{plan_file, subdir_name, ocr_score, temporal_match}],
      top_candidate: {...} | null,
      confidence: "high" | "medium" | "low" | "unmatched"
    }]
"""
import json
import sys
import os
import re
import unicodedata
from pathlib import Path
from datetime import datetime, timedelta

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "it", "this", "that", "was", "are", "be", "by",
    "from", "as", "has", "have", "had", "not", "you", "your", "we", "i",
    "my", "he", "she", "they", "if", "so", "do", "all", "its", "up", "out",
    "can", "will", "just", "no", "more", "also", "than", "then", "when",
    "where", "which", "who", "what", "how", "any", "some", "would",
}

# macOS screenshot filename: "Screenshot YYYY-MM-DD at H.MM.SS AM.png" (U+202F before AM/PM)
SCREENSHOT_RE = re.compile(
    r"Screenshot\s+(\d{4})-(\d{2})-(\d{2})\s+at\s+(\d+)\.(\d{2})\.(\d{2})[\s ]+(AM|PM)",
    re.IGNORECASE,
)


def parse_screenshot_datetime(path_str: str):
    name = Path(path_str).name
    name = unicodedata.normalize("NFC", name)
    m = SCREENSHOT_RE.search(name)
    if not m:
        return None, None
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hour, minute, second = int(m.group(4)), int(m.group(5)), int(m.group(6))
    ampm = m.group(7).upper()
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    dt = datetime(year, month, day, hour, minute, second)
    return f"{year:04d}-{month:02d}-{day:02d}", dt.strftime("%H:%M:%S")


def tokenize(text: str) -> set:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]*", text.lower())
    return {t for t in tokens if t not in STOPWORDS and len(t) > 2}


def plan_corpus(plan: dict) -> str:
    parts = [
        plan.get("title", "") * 3,      # 3x weight
        plan.get("description", "") * 2, # 2x weight
        " ".join(plan.get("headings", [])),
        plan.get("body_snippet", "")[:250],
    ]
    return " ".join(parts)


def temporal_match(screenshot_date: str, plan: dict, buffer_days: int = 3) -> bool:
    if not screenshot_date:
        return False
    try:
        ss_dt = datetime.strptime(screenshot_date, "%Y-%m-%d")
    except ValueError:
        return False
    # Plan activity window: [started - buffer, max(mtime, today) + buffer]
    plan_mtime = plan.get("mtime", "")
    plan_started = plan.get("started", "")
    try:
        mtime_dt = datetime.strptime(plan_mtime, "%Y-%m-%d") if plan_mtime else datetime.now()
    except ValueError:
        mtime_dt = datetime.now()
    try:
        started_dt = datetime.strptime(plan_started, "%Y-%m-%d") if plan_started else mtime_dt
    except ValueError:
        started_dt = mtime_dt
    window_start = started_dt - timedelta(days=buffer_days)
    window_end = max(mtime_dt, datetime.now()) + timedelta(days=buffer_days)
    return window_start <= ss_dt <= window_end


def score_plan(ocr_tokens: set, plan: dict) -> int:
    corpus_tokens = tokenize(plan_corpus(plan))
    return len(ocr_tokens & corpus_tokens)


def classify_confidence(score: int, temporal: bool, threshold: int) -> str:
    if not temporal:
        return "unmatched"
    if score >= threshold * 2:
        return "high"
    if score >= threshold:
        return "medium"
    return "low"


def match(ocr_data: dict, plans: list, threshold: int) -> list:
    results = []
    for path_str, ocr_entry in ocr_data.items():
        ocr_text = ocr_entry.get("text", "") or ""
        ocr_tokens = tokenize(ocr_text)
        ss_date, ss_time = parse_screenshot_datetime(path_str)
        candidates = []
        for plan in plans:
            t_match = temporal_match(ss_date, plan)
            if not t_match:
                continue
            score = score_plan(ocr_tokens, plan)
            candidates.append({
                "plan_file": plan["file"],
                "subdir_name": plan["subdir_name"],
                "title": plan["title"],
                "domain_emoji": plan["domain_emoji"],
                "ocr_score": score,
                "temporal_match": t_match,
                "description": plan.get("description", ""),
            })
        # Sort by score descending, keep top 3
        candidates.sort(key=lambda c: c["ocr_score"], reverse=True)
        top3 = candidates[:3]
        top = top3[0] if top3 else None
        confidence = (
            classify_confidence(top["ocr_score"], top["temporal_match"], threshold)
            if top else "unmatched"
        )
        results.append({
            "src": path_str,
            "filename_date": ss_date,
            "filename_time": ss_time,
            "ocr_excerpt": ocr_text[:200],
            "candidates": top3,
            "top_candidate": top,
            "confidence": confidence,
        })
    return results


def main():
    args = sys.argv[1:]
    ocr_path = None
    plans_path = None
    threshold = 3
    out_path = None

    if "--ocr" in args:
        idx = args.index("--ocr")
        ocr_path = args[idx + 1]
    if "--plans" in args:
        idx = args.index("--plans")
        plans_path = args[idx + 1]
    if "--threshold" in args:
        idx = args.index("--threshold")
        threshold = int(args[idx + 1])
    if "--out" in args:
        idx = args.index("--out")
        out_path = args[idx + 1]

    if not ocr_path or not plans_path:
        print("Usage: match_screenshots.py --ocr OCR_JSON --plans PLANS_JSON", file=sys.stderr)
        sys.exit(1)

    with open(ocr_path, encoding="utf-8") as f:
        ocr_data = json.load(f)
    with open(plans_path, encoding="utf-8") as f:
        plans = json.load(f)

    results = match(ocr_data, plans, threshold)
    output = json.dumps(results, indent=2, ensure_ascii=False)

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
