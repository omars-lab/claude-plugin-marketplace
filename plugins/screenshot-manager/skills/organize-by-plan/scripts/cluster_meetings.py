#!/usr/bin/env python3
"""Cluster Desktop screenshots into probable meeting/session groups using
temporal proximity and OCR-extracted meeting signals.

Usage:
    python3 cluster_meetings.py --ocr OCR_JSON [--gap-minutes 60] [--out CLUSTERS_JSON]

Input:
    OCR_JSON: {"<abs_path>": {"text": "...", "error": null}, ...}

Output:
    JSON array: [{
      cluster_id, date, time_window, file_count,
      files: [abs_path, ...],
      title_guess, attendees_guess, tool_guess, ocr_signals
    }]
"""
import json
import sys
import os
import re
import unicodedata
from pathlib import Path
from datetime import datetime, timedelta

# macOS screenshot: "Screenshot YYYY-MM-DD at H.MM.SS AM.png" (U+202F or space before AM/PM)
SCREENSHOT_RE = re.compile(
    r"Screenshot\s+(\d{4})-(\d{2})-(\d{2})\s+at\s+(\d+)\.(\d{2})\.(\d{2})[\s ]+(AM|PM)",
    re.IGNORECASE,
)

# Meeting tool detection patterns
ZOOM_RE = re.compile(r"zoom (meeting|call|video|webinar|room)?", re.IGNORECASE)
GMEET_RE = re.compile(r"meet\.google\.com|google meet", re.IGNORECASE)
TEAMS_RE = re.compile(r"microsoft teams|teams meeting", re.IGNORECASE)
SLACK_RE = re.compile(r"slack (huddle|call|connect)", re.IGNORECASE)

# Name extraction patterns
NAME_RE = re.compile(r"\b([A-Z][a-z]{2,}(?:\s[A-Z][a-z]+)?)\b")

# Calendar/meeting title patterns
ZOOM_TITLE_RE = re.compile(r"Zoom(?: Meeting)?\s*[-–]\s*(.+?)(?:\n|$)", re.IGNORECASE)
GCAL_INVITE_RE = re.compile(r"([A-Z][^|:\n]{5,60})\s*(?:\||\n|$)")


def parse_datetime(path_str: str):
    name = Path(path_str).name
    name = unicodedata.normalize("NFC", name)
    m = SCREENSHOT_RE.search(name)
    if not m:
        return None
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hour, minute, second = int(m.group(4)), int(m.group(5)), int(m.group(6))
    ampm = m.group(7).upper()
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    return datetime(year, month, day, hour, minute, second)


def detect_tool(text: str) -> str:
    if ZOOM_RE.search(text):
        return "Zoom"
    if GMEET_RE.search(text):
        return "Google Meet"
    if TEAMS_RE.search(text):
        return "Teams"
    if SLACK_RE.search(text):
        return "Slack"
    return "unknown"


def extract_title_guess(text: str) -> str:
    # Zoom window title
    m = ZOOM_TITLE_RE.search(text)
    if m:
        return m.group(1).strip()
    # Calendar event title (first capitalized phrase)
    for m in GCAL_INVITE_RE.finditer(text):
        candidate = m.group(1).strip()
        if len(candidate) > 5 and not candidate.startswith("Screenshot"):
            return candidate
    return ""


def extract_attendees(text: str) -> list:
    """Extract probable person names from OCR text."""
    # Look for names near participant-list indicators
    names = []
    if re.search(r"(participants?|attendees?|people|members?)", text, re.IGNORECASE):
        # Find capitalized name patterns after those words
        section = re.sub(r".*(participants?|attendees?|people|members?)", "", text, flags=re.IGNORECASE)
        names = NAME_RE.findall(section[:500])
    # Also check for Zoom participant panel (lines with just a name)
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^[A-Z][a-z]{2,}(?:\s[A-Z][a-z]+)?$", line):
            names.append(line)
    # Deduplicate
    seen = set()
    result = []
    for n in names:
        if n.lower() not in seen and len(n) > 2:
            seen.add(n.lower())
            result.append(n)
    return result[:10]


def cluster_by_gap(entries: list, gap_minutes: int) -> list:
    """entries: [(dt, path, ocr_text)] sorted by dt. Returns list of clusters."""
    if not entries:
        return []
    clusters = []
    current = [entries[0]]
    for prev, curr in zip(entries, entries[1:]):
        gap = (curr[0] - prev[0]).total_seconds() / 60
        if gap > gap_minutes:
            clusters.append(current)
            current = [curr]
        else:
            current.append(curr)
    clusters.append(current)
    return clusters


def build_cluster(cluster_entries: list, cluster_id: str) -> dict:
    dts = [e[0] for e in cluster_entries]
    paths = [e[1] for e in cluster_entries]
    ocr_texts = [e[2] for e in cluster_entries if e[2]]
    combined_ocr = " ".join(ocr_texts[:5])  # first 5 files' OCR for signal extraction

    date_str = dts[0].strftime("%Y-%m-%d")
    time_start = dts[0].strftime("%I:%M %p")
    time_end = dts[-1].strftime("%I:%M %p")

    tool = detect_tool(combined_ocr)
    title_guess = extract_title_guess(combined_ocr)
    attendees = extract_attendees(combined_ocr)

    if not title_guess:
        title_guess = f"Screenshots {time_start}–{time_end}"

    return {
        "cluster_id": cluster_id,
        "date": date_str,
        "time_window": f"{time_start} – {time_end}",
        "file_count": len(paths),
        "files": paths,
        "title_guess": title_guess,
        "attendees_guess": attendees,
        "tool_guess": tool,
        "ocr_signals": combined_ocr[:300],
    }


def cluster_meetings(ocr_data: dict, gap_minutes: int = 60) -> list:
    # Parse datetime for each screenshot
    entries = []
    for path_str, ocr_entry in ocr_data.items():
        dt = parse_datetime(path_str)
        if dt is None:
            continue
        ocr_text = ocr_entry.get("text", "") or ""
        entries.append((dt, path_str, ocr_text))

    # Group by date
    by_date = {}
    for dt, path, text in entries:
        date_key = dt.strftime("%Y-%m-%d")
        by_date.setdefault(date_key, []).append((dt, path, text))

    clusters = []
    for date_key in sorted(by_date):
        day_entries = sorted(by_date[date_key], key=lambda e: e[0])
        day_clusters = cluster_by_gap(day_entries, gap_minutes)
        for i, clust in enumerate(day_clusters):
            cluster_id = f"{date_key.replace('-', '')}-{i+1:03d}"
            clusters.append(build_cluster(clust, cluster_id))

    return clusters


def main():
    args = sys.argv[1:]
    ocr_path = None
    gap_minutes = 60
    out_path = None

    if "--ocr" in args:
        idx = args.index("--ocr")
        ocr_path = args[idx + 1]
    if "--gap-minutes" in args:
        idx = args.index("--gap-minutes")
        gap_minutes = int(args[idx + 1])
    if "--out" in args:
        idx = args.index("--out")
        out_path = args[idx + 1]

    if not ocr_path:
        print("Usage: cluster_meetings.py --ocr OCR_JSON [--gap-minutes 60]", file=sys.stderr)
        sys.exit(1)

    with open(ocr_path, encoding="utf-8") as f:
        ocr_data = json.load(f)

    clusters = cluster_meetings(ocr_data, gap_minutes)
    output = json.dumps(clusters, indent=2, ensure_ascii=False)

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
