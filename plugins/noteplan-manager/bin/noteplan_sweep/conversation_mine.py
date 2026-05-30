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
    r'\b(?:idea[:\s]|what if\b|i want to\b|we should\b|could we\b|let\'s\b)',
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

    # Write plan-sessions.json: plan stem → [session_ids]
    plan_sessions: dict[str, list[str]] = {}
    for s in merged_sessions:
        for fp in s.get("files_written", []):
            if "Plans/" in fp or "📆" in fp:
                stem = Path(fp).stem
                plan_sessions.setdefault(stem, [])
                if s["session_id"] not in plan_sessions[stem]:
                    plan_sessions[stem].append(s["session_id"])
        for wl in s.get("wikilinks_mentioned", []):
            plan_sessions.setdefault(wl, [])
            if s["session_id"] not in plan_sessions[wl]:
                plan_sessions[wl].append(s["session_id"])

    plan_sessions_path = dash_dir / "plan-sessions.json"
    plan_sessions_path.write_text(
        json.dumps(plan_sessions, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # Write ideas.json: surfaced idea lines (dedup by text fingerprint)
    existing_ideas_path = dash_dir / "ideas.json"
    existing_ideas: list[dict] = []
    if existing_ideas_path.exists():
        try:
            existing_ideas = json.loads(existing_ideas_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    def _fingerprint(text: str) -> str:
        import hashlib
        normalized = re.sub(r'[^\w]', ' ', text.lower())
        tokens = sorted(normalized.split())
        return hashlib.md5(' '.join(tokens).encode()).hexdigest()[:12]

    existing_fps = {i.get("fingerprint") for i in existing_ideas if i.get("fingerprint")}
    new_ideas: list[dict] = []
    for s in new_sessions:
        for line in s.get("idea_lines", []):
            fp = _fingerprint(line)
            if fp not in existing_fps:
                new_ideas.append({
                    "text": line,
                    "fingerprint": fp,
                    "session_id": s["session_id"],
                    "date": s["date"],
                    "matched_plan": None,
                })
                existing_fps.add(fp)

    all_ideas = existing_ideas + new_ideas
    existing_ideas_path.write_text(
        json.dumps(all_ideas, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # Update cursor
    new_cursor = {
        "last_ts": datetime.now(tz=timezone.utc).isoformat(),
        "processed_sessions": list({s["session_id"] for s in merged_sessions}),
    }
    save_cursor(dash_dir, new_cursor)

    utils.log(f"  sessions: {len(merged_sessions)} total | plan-sessions: {len(plan_sessions)} plans | ideas: {len(all_ideas)} ({len(new_ideas)} new)")
