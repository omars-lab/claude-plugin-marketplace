"""
conversation_mine.py — Transcript mining for noteplan-sweep.

Commands:
  conversation-mine    Parse Claude transcripts, cross-map with plans, write dashboard outputs
"""

import json
import os
import re
import sys
from datetime import datetime, date, timezone
from pathlib import Path

import noteplan_sweep.utils as utils


# ---------------------------------------------------------------------------
# Path sanitizer (mirrors Claude Code's project key derivation)
# ---------------------------------------------------------------------------

def sanitize_cwd(path: str) -> str:
    """Convert an absolute path to the Claude project directory key."""
    # Claude replaces leading / with - then replaces non-[A-Za-z0-9_-] with -
    result = re.sub(r'[^A-Za-z0-9_\-]', '-', path)
    if not result.startswith('-'):
        result = '-' + result
    # Collapse multiple dashes
    result = re.sub(r'-+', '-', result)
    return result


def find_claude_projects_dir() -> Path:
    return Path.home() / ".claude" / "projects"


def find_transcript_root(cwd: str | None = None) -> Path | None:
    """Return the Claude projects sub-directory for the given cwd (default: NP root)."""
    if cwd is None:
        cwd = str(utils.noteplan_root())
    key = sanitize_cwd(cwd)
    candidate = find_claude_projects_dir() / key
    if candidate.exists():
        return candidate
    # Fallback: list all project dirs and find the best match
    projects = find_claude_projects_dir()
    if not projects.exists():
        return None
    # Pick the dir whose name is closest to our key
    for d in projects.iterdir():
        if d.is_dir() and cwd.replace(' ', '-') in str(d):
            return d
    return None


# ---------------------------------------------------------------------------
# Transcript locator
# ---------------------------------------------------------------------------

def find_transcripts(project_dir: Path, since: datetime | None = None) -> list[Path]:
    """Return all root-level JSONL transcript files in a project directory."""
    if not project_dir.exists():
        return []
    results = []
    for p in project_dir.iterdir():
        if p.suffix != ".jsonl":
            continue
        if since is not None:
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            if mtime < since:
                continue
        results.append(p)
    return sorted(results, key=lambda p: p.stat().st_mtime)


# ---------------------------------------------------------------------------
# Transcript parser
# ---------------------------------------------------------------------------

WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}
_WIKILINK_RE = re.compile(r'\[\[([^\]]+)\]\]')
_IMPERATIVE_RE = re.compile(
    r'\b(?:build|create|add|implement|write|fix|make|update|generate|refactor|design)\s+(.{5,80})',
    re.IGNORECASE
)
_IDEA_TRIGGER_RE = re.compile(
    r'\b(?:'
    r'idea[:\s]|what if\b|i want to\b|we should\b|could we\b|let\'s\b'
    r'|i\'m thinking\b|imagine if\b|what about\b|how about\b'
    r'|wouldn\'t it be\b|it would be (?:cool|great|nice|awesome)\b'
    r'|someday\b|eventually we\b|we could\b|maybe we\b'
    r'|feature(?:\s+request)?\b|wishlist\b'
    r'|(?:^|\s)IDEA\b|(?:^|\s)FUTURE\b'
    r')',
    re.IGNORECASE
)


def parse_transcript(jsonl_path: Path) -> dict | None:
    """Parse a single JSONL transcript and return a signal dict."""
    messages = []
    try:
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        return None

    if not messages:
        return None

    session_id = None
    session_date = None
    cwd = None
    files_written: set = set()
    user_texts: list = []
    assistant_texts: list = []

    for msg in messages:
        if not session_id:
            session_id = msg.get("sessionId")
        if not cwd:
            cwd = msg.get("cwd")

        ts = msg.get("timestamp")
        if ts and not session_date:
            try:
                session_date = ts[:10]  # YYYY-MM-DD
            except Exception:
                pass

        msg_type = msg.get("type")

        if msg_type == "user":
            content = msg.get("message", {}).get("content", "")
            if isinstance(content, str):
                user_texts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        user_texts.append(block.get("text", ""))

        elif msg_type == "assistant":
            content = msg.get("message", {}).get("content", [])
            if isinstance(content, str):
                assistant_texts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            assistant_texts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use" and block.get("name") in WRITE_TOOLS:
                            fp = block.get("input", {}).get("file_path", "")
                            if fp:
                                files_written.add(fp)

    if not session_id:
        return None

    # Extract signals from user prompts
    all_user_text = "\n".join(user_texts)
    wikilinks = _WIKILINK_RE.findall(all_user_text)
    imperative_phrases = [m.group(0).strip()[:80] for m in _IMPERATIVE_RE.finditer(all_user_text)]
    idea_lines = [
        line.strip()[:120]
        for line in all_user_text.splitlines()
        if _IDEA_TRIGGER_RE.search(line) and len(line.strip()) > 10
    ]

    return {
        "session_id": session_id,
        "date": session_date or "unknown",
        "cwd": cwd or "",
        "transcript_path": str(jsonl_path),
        "files_written": sorted(files_written),
        "wikilinks_mentioned": list(dict.fromkeys(wikilinks)),  # dedup, preserve order
        "imperative_phrases": imperative_phrases[:20],
        "idea_lines": idea_lines[:20],
        "user_message_count": len(user_texts),
    }


# ---------------------------------------------------------------------------
# Plan cross-mapping (CM-B)
# ---------------------------------------------------------------------------

_EMOJI_STRIP_RE = re.compile(
    r'^[\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF\U0001F300-\U0001F9FF'
    r'\U0001FA00-\U0001FA9F\u200d\ufe0f\U0001F1E0-\U0001F1FF\U00002702-\U000027B0]+'
)
_YYMMDD_RE = re.compile(r'^\d{6}')


def _normalize_stem(stem: str) -> str:
    """Strip leading emoji + YYMMDD prefix, lowercase, strip punctuation."""
    s = _EMOJI_STRIP_RE.sub('', stem).strip()
    s = _YYMMDD_RE.sub('', s).strip()
    s = re.sub(r'[^\w\s]', ' ', s).lower()
    return ' '.join(s.split())


def _keyword_overlap(a: str, b: str) -> float:
    """Jaccard similarity of word sets between two strings."""
    stop = {'the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'for', 'with', 'on', 'at', 'by', 'is', 'are', 'was'}
    wa = {w for w in re.findall(r'\w+', a.lower()) if len(w) > 2 and w not in stop}
    wb = {w for w in re.findall(r'\w+', b.lower()) if len(w) > 2 and w not in stop}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def load_plan_index(notes_root: Path) -> list[dict]:
    """Load all plan files and build a cross-mapping index."""
    from noteplan_sweep.dashboard import parse_frontmatter, PLAN_PATH_RE
    plans = []
    for p in sorted(notes_root.rglob("*.md")):
        if any(x in str(p) for x in ("@Backup", "@Trash", "@Archive", "@Templates")):
            continue
        rel = str(p.relative_to(notes_root))
        if not PLAN_PATH_RE.search(rel):
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            continue
        fm, _ = parse_frontmatter(content)
        stem = p.stem
        title = fm.get("title", stem)
        plans.append({
            "stem": stem,
            "norm_stem": _normalize_stem(stem),
            "title": title,
            "norm_title": _normalize_stem(title),
            "description": fm.get("description", ""),
            "status": fm.get("status", ""),
            "path": str(p),
        })
    return plans


def cross_map_session(session: dict, plan_index: list[dict]) -> list[str]:
    """Return list of plan stems that match this session's signals.

    Match priority:
    1. File written whose path contains the plan stem (direct write)
    2. [[wikilink]] exact match to plan stem or title
    3. Keyword overlap ≥ 0.25 between user text and plan title/description
    """
    matched: set = set()

    # 1. Direct file writes
    for fp in session.get("files_written", []):
        fp_stem = Path(fp).stem
        for plan in plan_index:
            if plan["stem"] == fp_stem:
                matched.add(plan["stem"])
                break
            # Partial match: plan stem appears in file path
            if plan["stem"] in fp:
                matched.add(plan["stem"])

    # 2. Wikilinks
    wikilinks = {w.strip() for w in session.get("wikilinks_mentioned", [])}
    for plan in plan_index:
        if plan["stem"] in wikilinks or plan["title"] in wikilinks:
            matched.add(plan["stem"])
        # Normalize match
        for wl in wikilinks:
            if _normalize_stem(wl) == plan["norm_stem"] or _normalize_stem(wl) == plan["norm_title"]:
                matched.add(plan["stem"])

    # 3. Keyword overlap on user text
    all_user_text = " ".join(session.get("imperative_phrases", []) + session.get("idea_lines", []))
    if all_user_text:
        for plan in plan_index:
            if plan["stem"] in matched:
                continue
            target = f"{plan['norm_title']} {plan['description']}"
            if _keyword_overlap(all_user_text, target) >= 0.25:
                matched.add(plan["stem"])

    return sorted(matched)


def build_plan_sessions_map(sessions: list[dict], plan_index: list[dict]) -> dict[str, list[dict]]:
    """Return {plan_stem: [{session_id, date, summary}]} with cross-mapped sessions."""
    result: dict[str, list] = {}
    for s in sessions:
        matched = cross_map_session(s, plan_index)
        for stem in matched:
            result.setdefault(stem, [])
            entry = {
                "session_id": s["session_id"],
                "date": s.get("date", ""),
                "files_written": [
                    fp for fp in s.get("files_written", [])
                    if stem in fp or Path(fp).stem == stem
                ],
                "wikilinks": [w for w in s.get("wikilinks_mentioned", []) if stem in w or w in stem],
            }
            result[stem].append(entry)
    return result


# ---------------------------------------------------------------------------
# Idea dedup helpers (CM-C+D)
# ---------------------------------------------------------------------------

import hashlib


def _fingerprint(text: str) -> str:
    """Stable 12-char fingerprint for dedup: sorted normalized tokens."""
    normalized = re.sub(r'[^\w]', ' ', text.lower())
    tokens = sorted(normalized.split())
    return hashlib.md5(' '.join(tokens).encode()).hexdigest()[:12]


def extract_notefile_ideas(notes_root: Path, calendar_root: Path) -> list[dict]:
    """Extract idea lines from NotePlan markdown files using dashboard scanner."""
    from noteplan_sweep.dashboard import scan_tasks_and_ideas
    _, raw_ideas = scan_tasks_and_ideas(notes_root, calendar_root)
    result = []
    for idea in raw_ideas:
        text = idea.get("text", "").strip()
        if len(text) < 8:
            continue
        result.append({
            "text": text,
            "fingerprint": _fingerprint(text),
            "source_type": "notefile",
            "source": idea.get("source", ""),
            "section": idea.get("section", ""),
            "xcallback": idea.get("xcallback", ""),
            "date": "",
            "tagged": idea.get("tagged", False),
            "matched_plan": None,
        })
    return result


def build_discovered_ideas(
    transcript_ideas: list[dict],
    notefile_ideas: list[dict],
    plan_index: list[dict],
) -> list[dict]:
    """Merge transcript + notefile ideas, dedup by fingerprint, cross-map plans."""
    seen_fps: set = set()
    merged: list[dict] = []

    def _cross_map_idea(text: str) -> str | None:
        for plan in plan_index:
            if _keyword_overlap(text, f"{plan['norm_title']} {plan['description']}") >= 0.28:
                return plan["stem"]
        return None

    for idea in transcript_ideas + notefile_ideas:
        fp = idea.get("fingerprint") or _fingerprint(idea.get("text", ""))
        if fp in seen_fps:
            continue
        seen_fps.add(fp)
        if not idea.get("matched_plan"):
            idea = {**idea, "matched_plan": _cross_map_idea(idea.get("text", ""))}
        merged.append(idea)

    # Sort: notefile ideas first (they have cleaner text), then by date desc
    merged.sort(key=lambda x: (0 if x.get("source_type") == "notefile" else 1, x.get("date", ""), x.get("text", "")))
    return merged


# ---------------------------------------------------------------------------
# Cursor (incremental mode)
# ---------------------------------------------------------------------------

def load_cursor(dashboard_dir: Path) -> dict:
    cursor_path = dashboard_dir / "mine-cursor.json"
    if cursor_path.exists():
        try:
            return json.loads(cursor_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_session_id": None, "last_ts": None, "processed_sessions": []}


def save_cursor(dashboard_dir: Path, cursor: dict):
    cursor_path = dashboard_dir / "mine-cursor.json"
    cursor_path.write_text(json.dumps(cursor, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

def cmd_conversation_mine(args):
    root = utils.noteplan_root()
    dash_dir = root / "dashboard"
    dash_dir.mkdir(exist_ok=True)

    gitkeep = dash_dir / ".gitkeep"
    if not gitkeep.exists() and not utils.DRY_RUN:
        gitkeep.touch()

    # Resolve project directory
    project_dirs: list[Path] = []

    if hasattr(args, 'projects') and args.projects:
        for raw in args.projects.split(","):
            raw = raw.strip()
            d = find_transcript_root(raw) if raw != "auto" else find_transcript_root()
            if d:
                project_dirs.append(d)
    else:
        d = find_transcript_root(str(root))
        if d:
            project_dirs.append(d)

    if not project_dirs:
        utils.err("Could not locate Claude transcript directory. Check ~/.claude/projects/")
        sys.exit(utils.EXIT_NOT_FOUND)

    # Load cursor
    cursor = load_cursor(dash_dir) if not getattr(args, 'full', False) else {"last_session_id": None, "last_ts": None, "processed_sessions": []}

    # Parse --since flag
    since_dt: datetime | None = None
    if hasattr(args, 'since') and args.since:
        try:
            since_dt = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
        except ValueError:
            utils.err(f"Invalid --since date: {args.since}. Use YYYY-MM-DD.")
            sys.exit(utils.EXIT_VALIDATION_FAILURE)

    already_processed: set = set(cursor.get("processed_sessions", []))

    all_sessions: list[dict] = []
    new_sessions: list[dict] = []

    for project_dir in project_dirs:
        transcripts = find_transcripts(project_dir, since=since_dt)
        utils.verbose(f"Found {len(transcripts)} transcripts in {project_dir}")

        for t in transcripts:
            session_id = t.stem  # UUID
            if session_id in already_processed and not getattr(args, 'full', False):
                utils.verbose(f"  skip (already processed): {session_id[:8]}")
                continue

            utils.verbose(f"  parsing: {session_id[:8]}")
            result = parse_transcript(t)
            if result:
                new_sessions.append(result)
                all_sessions.append(result)

    # Merge with existing sessions.json
    sessions_path = dash_dir / "sessions.json"
    existing_sessions: list[dict] = []
    if sessions_path.exists():
        try:
            existing_sessions = json.loads(sessions_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Replace/add new sessions (keyed by session_id)
    existing_by_id = {s["session_id"]: s for s in existing_sessions}
    for s in new_sessions:
        existing_by_id[s["session_id"]] = s
    merged_sessions = sorted(existing_by_id.values(), key=lambda s: s.get("date", ""))

    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would process {len(new_sessions)} new session(s), total {len(merged_sessions)} in sessions.json")
        return

    # Write sessions.json
    sessions_path.write_text(
        json.dumps(merged_sessions, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    utils.log(f"conversation-mine: processed {len(new_sessions)} new session(s) → {sessions_path}")

    # CM-B: Cross-map all sessions against plan index
    utils.verbose("Cross-mapping sessions against plan files...")
    notes_root = root / "Notes"
    plan_index = load_plan_index(notes_root)
    utils.verbose(f"  Plan index: {len(plan_index)} plans")

    plan_sessions_rich = build_plan_sessions_map(merged_sessions, plan_index)

    # Enrich each session with its matched plans
    ps_by_id = {s["session_id"]: s for s in merged_sessions}
    for stem, session_list in plan_sessions_rich.items():
        for entry in session_list:
            sid = entry["session_id"]
            if sid in ps_by_id:
                plans_touched = ps_by_id[sid].setdefault("plans_touched", [])
                if stem not in plans_touched:
                    plans_touched.append(stem)

    # Re-write enriched sessions.json
    sessions_path.write_text(
        json.dumps(merged_sessions, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # Write plan-sessions.json with rich cross-map data
    plan_sessions_path = dash_dir / "plan-sessions.json"
    plan_sessions_path.write_text(
        json.dumps(plan_sessions_rich, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    utils.log(f"  Cross-mapped {len(plan_sessions_rich)} plan(s) to sessions")

    # Write ideas.json: transcript-derived idea lines (dedup by fingerprint)
    existing_ideas_path = dash_dir / "ideas.json"
    existing_ideas: list[dict] = []
    if existing_ideas_path.exists():
        try:
            existing_ideas = json.loads(existing_ideas_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    existing_fps = {i.get("fingerprint") for i in existing_ideas if i.get("fingerprint")}
    new_ideas: list[dict] = []
    for s in new_sessions:
        session_plans = s.get("plans_touched", [])
        for line in s.get("idea_lines", []):
            fp_hash = _fingerprint(line)
            if fp_hash not in existing_fps:
                matched_plan = session_plans[0] if session_plans else None
                if not matched_plan:
                    for plan in plan_index:
                        if _keyword_overlap(line, f"{plan['norm_title']} {plan['description']}") >= 0.3:
                            matched_plan = plan["stem"]
                            break
                new_ideas.append({
                    "text": line,
                    "fingerprint": fp_hash,
                    "source_type": "transcript",
                    "session_id": s["session_id"],
                    "date": s["date"],
                    "matched_plan": matched_plan,
                })
                existing_fps.add(fp_hash)

    all_transcript_ideas = existing_ideas + new_ideas
    existing_ideas_path.write_text(
        json.dumps(all_transcript_ideas, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # CM-D: Build discovered_ideas.json — merge transcript + notefile ideas, dedup
    utils.verbose("Scanning NotePlan files for idea lines...")
    calendar_root = root / "Calendar"
    notefile_ideas = extract_notefile_ideas(notes_root, calendar_root)
    utils.verbose(f"  Found {len(notefile_ideas)} ideas in NotePlan files")

    discovered = build_discovered_ideas(all_transcript_ideas, notefile_ideas, plan_index)
    discovered_path = dash_dir / "discovered_ideas.json"
    discovered_path.write_text(
        json.dumps(discovered, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    utils.log(f"  discovered_ideas: {len(discovered)} total ({len(notefile_ideas)} from files, {len(all_transcript_ideas)} from transcripts)")

    # Update cursor
    new_cursor = {
        "last_ts": datetime.now(tz=timezone.utc).isoformat(),
        "processed_sessions": list({s["session_id"] for s in merged_sessions}),
    }
    save_cursor(dash_dir, new_cursor)

    utils.log(f"  sessions: {len(merged_sessions)} total | plan-sessions: {len(plan_sessions_rich)} plans | ideas: {len(all_ideas)} ({len(new_ideas)} new)")
