#!/usr/bin/env python3
"""Move Claude Code session history from one project path to another.

Usage:
  move-claude-sessions.py OLD_PROJECT_PATH NEW_PROJECT_PATH [--apply]
                          [--rewrite-content] [--migrate-history] [--delete-source]

Default is a DRY RUN: prints the full plan and all validation results.
Re-run with --apply to execute.

What it does:
  1. Computes the slug dirs under ~/.claude/projects/ for both paths
     (slug = absolute path with every non-alphanumeric char replaced by '-').
  2. Validates: source exists, no live sessions, no sessionId collisions,
     embedded cwd values actually match OLD_PROJECT_PATH.
  3. Copies <id>.jsonl transcripts + <id>/ sidecar dirs (tool-results) +
     memory/ into the destination slug dir.
  4. Rewrites the top-level "cwd" field of every transcript line
     (JSON-aware, NOT sed) from OLD prefix to NEW prefix.
  5. Deletes sessions-index.json in src and dst (it is a cache; regenerated).
  6. Optionally rewrites OLD->NEW path strings inside message content
     (--rewrite-content) and migrates ~/.claude/history.jsonl prompt
     history entries (--migrate-history).
"""

EXAMPLES = """\
examples:
  # dry run a whole-project move (writes nothing)
  move-claude-sessions ~/old/place/myrepo ~/new/place/myrepo

  # execute it, repointing prompt history too
  move-claude-sessions ~/old/place/myrepo ~/new/place/myrepo --apply --migrate-history

  # move ONE session between two projects
  move-claude-sessions ~/work/repo-a ~/work/repo-b \\
      --session 4d55bb57-01f0-41ff-9fb8-f93315ef3414 --apply

  # after verifying the copy, remove the originals
  move-claude-sessions ~/old/place/myrepo ~/new/place/myrepo --apply --delete-source

risks:
  --apply            rewrites top-level "cwd" in the COPIED transcripts
                     (JSON-aware; source files are untouched until --delete-source)
  --delete-source    DESTRUCTIVE: removes source transcripts after a size-check;
                     run a plain --apply first and verify before using this
  --rewrite-content  edits historical message content (old->new path strings);
                     each line is re-parsed to guarantee valid JSON, but the
                     transcript no longer reflects what literally happened
  --migrate-history  edits ~/.claude/history.jsonl (a .bak backup is written)
  live sessions      moving a session that is currently open corrupts it;
                     the script refuses (checks ~/.claude/sessions/ locks)
"""

import argparse
import json
import os
import re
import shutil
import sys

CLAUDE_DIR = os.path.expanduser("~/.claude")
PROJECTS_DIR = os.path.join(CLAUDE_DIR, "projects")
LOCKS_DIR = os.path.join(CLAUDE_DIR, "sessions")
HISTORY = os.path.join(CLAUDE_DIR, "history.jsonl")

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jsonl$"
)


def slugify(path):
    """Replicates Claude Code's project-dir naming: non-alphanumerics -> '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        # PermissionError means the pid exists but isn't ours
        return True if isinstance(pid, int) else False
    except OSError:
        return False


def live_session_ids():
    """sessionIds of currently running claude processes (from lock files)."""
    live = {}
    if not os.path.isdir(LOCKS_DIR):
        return live
    for name in os.listdir(LOCKS_DIR):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(LOCKS_DIR, name)) as f:
                lock = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        pid = lock.get("pid")
        sid = lock.get("sessionId")
        if sid and pid and pid_alive(pid):
            live[sid] = lock
    return live


def transcript_cwds(jsonl_path, limit=None):
    cwds = set()
    with open(jsonl_path, errors="replace") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(d, dict) and d.get("cwd"):
                cwds.add(d["cwd"])
    return cwds


def rewrite_jsonl(path, old, new, rewrite_content):
    """JSON-aware rewrite. Returns (lines_changed, total_lines)."""
    out_lines, changed = [], 0
    with open(path, errors="replace") as f:
        for line in f:
            stripped = line.rstrip("\n")
            if not stripped:
                out_lines.append(line)
                continue
            try:
                d = json.loads(stripped)
            except json.JSONDecodeError:
                out_lines.append(line)
                continue
            orig = stripped
            if isinstance(d, dict) and isinstance(d.get("cwd"), str):
                if d["cwd"] == old or d["cwd"].startswith(old + "/"):
                    d["cwd"] = new + d["cwd"][len(old):]
            new_line = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
            if rewrite_content and old in new_line:
                # still JSON-safe: '/' needs no escaping in JSON strings, and
                # we re-parse to guarantee we didn't corrupt the line
                candidate = new_line.replace(old, new)
                try:
                    json.loads(candidate)
                    new_line = candidate
                except json.JSONDecodeError:
                    pass
            if new_line != orig:
                changed += 1
            out_lines.append(new_line + "\n")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.writelines(out_lines)
    os.replace(tmp, path)
    return changed, len(out_lines)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old_path", help="project's OLD absolute path on disk "
                                     "(the real path, not the ~/.claude slug)")
    ap.add_argument("new_path", help="project's NEW absolute path on disk")
    ap.add_argument("--apply", action="store_true", help="execute (default: dry run)")
    ap.add_argument("--rewrite-content", action="store_true",
                    help="also rewrite OLD->NEW inside message content")
    ap.add_argument("--migrate-history", action="store_true",
                    help="repoint prompt history entries in history.jsonl")
    ap.add_argument("--delete-source", action="store_true",
                    help="remove source slug dir after a verified copy")
    ap.add_argument("--session", action="append", metavar="SESSION_ID",
                    help="move only this session id (repeatable); "
                         "default: all sessions in the source project")
    if len(sys.argv) == 1:
        ap.print_help()
        sys.exit(0)
    args = ap.parse_args()

    # --- input validation ---------------------------------------------------
    sid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    for s in args.session or []:
        if not sid_re.match(s):
            ap.error(f"--session {s!r} is not a session id "
                     "(expected a lowercase UUID like 4d55bb57-01f0-41ff-9fb8-f93315ef3414)")
    for label, p in (("old_path", args.old_path), ("new_path", args.new_path)):
        base = os.path.basename(p.rstrip("/"))
        if base.startswith("-Users-") or p.rstrip("/").endswith(".jsonl"):
            ap.error(f"{label} {p!r} looks like a ~/.claude slug dir or transcript "
                     "file — pass the project's real path on disk instead "
                     "(e.g. ~/workspace/myrepo)")
    if args.delete_source and not args.apply:
        ap.error("--delete-source requires --apply (nothing is copied in a dry run)")
    if args.rewrite_content and not args.apply:
        print("note: --rewrite-content has no effect without --apply (dry run)\n")

    old = os.path.abspath(args.old_path).rstrip("/")
    new = os.path.abspath(args.new_path).rstrip("/")
    src = os.path.join(PROJECTS_DIR, slugify(old))
    dst = os.path.join(PROJECTS_DIR, slugify(new))

    print(f"old path : {old}\nnew path : {new}")
    print(f"src slug : {src}\ndst slug : {dst}\n")

    errors, warnings = [], []

    # --- validation -------------------------------------------------------
    if not os.path.isdir(src):
        errors.append(f"source slug dir does not exist: {src}")
    if src == dst:
        errors.append("old and new paths produce the same slug — nothing to do")
    elif os.path.realpath(src) == os.path.realpath(dst):
        errors.append("src and dst slug dirs are symlinks to the SAME directory "
                      f"({os.path.realpath(src)}) — nothing to move")
    if os.path.islink(src):
        warnings.append(f"src slug is a symlink -> {os.path.realpath(src)}")
    if os.path.islink(dst):
        warnings.append(f"dst slug is a symlink -> {os.path.realpath(dst)}")
    if not os.path.isdir(new):
        warnings.append(f"new project path does not exist on disk yet: {new}")

    sessions = []
    if os.path.isdir(src):
        for name in sorted(os.listdir(src)):
            if UUID_RE.match(name):
                sessions.append(name[:-len(".jsonl")])
        if args.session:
            missing = [s for s in args.session if s not in sessions]
            for s in missing:
                errors.append(f"--session {s} not found in {src}")
            sessions = [s for s in sessions if s in set(args.session)]
        if not sessions:
            errors.append(f"no session .jsonl files found in {src}")

    live = live_session_ids()
    for sid in sessions:
        if sid in live:
            errors.append(
                f"session {sid} is LIVE (pid {live[sid]['pid']}, "
                f"status={live[sid].get('status')}) — close it first")

    if os.path.isdir(dst):
        for sid in sessions:
            if os.path.exists(os.path.join(dst, sid + ".jsonl")):
                errors.append(f"collision: {sid}.jsonl already exists in destination")
        if not args.session and os.path.isdir(os.path.join(dst, "memory")) and \
           os.path.isdir(os.path.join(src, "memory")):
            warnings.append("both src and dst have a memory/ dir — "
                            "src memory will NOT be copied; merge by hand")

    # sanity: do the transcripts actually belong to old path?
    mismatched = []
    for sid in sessions:
        cwds = transcript_cwds(os.path.join(src, sid + ".jsonl"))
        if cwds and not any(c == old or c.startswith(old + "/") for c in cwds):
            mismatched.append((sid, sorted(cwds)[:2]))
    for sid, cwds in mismatched:
        warnings.append(f"session {sid} has cwd(s) {cwds} not under old path "
                        "(it may have been moved before — cwd rewrite will no-op)")

    # --- report -----------------------------------------------------------
    print(f"sessions to move ({len(sessions)}):")
    for sid in sessions:
        sidecar = "  [+tool-results]" if os.path.isdir(os.path.join(src, sid)) else ""
        print(f"  {sid}{sidecar}")
    if not args.session and os.path.isdir(os.path.join(src, "memory")):
        print("  memory/  (project memory)")
    print()
    if args.delete_source:
        print("RISK : --delete-source will REMOVE the source copies above after "
              "a size-check (no undo)")
    if args.rewrite_content:
        print("RISK : --rewrite-content will edit historical message content, "
              "not just the cwd field")
    if args.migrate_history:
        print("note : --migrate-history edits ~/.claude/history.jsonl "
              "(backup written to history.jsonl.bak)")
    for w in warnings:
        print(f"WARN : {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        sys.exit(1)
    if not args.apply:
        print("\nDRY RUN — re-run with --apply to execute.")
        sys.exit(0)

    # --- execute ----------------------------------------------------------
    os.makedirs(dst, exist_ok=True)
    for sid in sessions:
        jf = sid + ".jsonl"
        shutil.copy2(os.path.join(src, jf), os.path.join(dst, jf))
        sidecar = os.path.join(src, sid)
        if os.path.isdir(sidecar):
            shutil.copytree(sidecar, os.path.join(dst, sid), dirs_exist_ok=False)
        changed, total = rewrite_jsonl(
            os.path.join(dst, jf), old, new, args.rewrite_content)
        print(f"copied {jf}  (rewrote {changed}/{total} lines)")

    src_mem = os.path.join(src, "memory")
    if args.session:
        src_mem = ""  # project memory stays put on single-session moves
    memory_copied = False
    if os.path.isdir(src_mem) and not os.path.isdir(os.path.join(dst, "memory")):
        shutil.copytree(src_mem, os.path.join(dst, "memory"))
        memory_copied = True
        print("copied memory/")

    for d in (src, dst):
        idx = os.path.join(d, "sessions-index.json")
        if os.path.exists(idx):
            os.remove(idx)
            print(f"deleted stale cache {idx}")

    if args.migrate_history and os.path.exists(HISTORY):
        moved_ids = set(sessions)
        out, hits = [], 0
        with open(HISTORY, errors="replace") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    out.append(line)
                    continue
                if d.get("sessionId") in moved_ids and d.get("project") == old:
                    d["project"] = new
                    hits += 1
                out.append(json.dumps(d, ensure_ascii=False) + "\n")
        shutil.copy2(HISTORY, HISTORY + ".bak")
        tmp = HISTORY + ".tmp"
        with open(tmp, "w") as f:
            f.writelines(out)
        os.replace(tmp, HISTORY)
        print(f"migrated {hits} prompt-history entries (backup: history.jsonl.bak)")

    # verify before any deletion
    ok = all(
        os.path.getsize(os.path.join(dst, sid + ".jsonl")) > 0 for sid in sessions)
    if args.delete_source:
        uncopied_memory = (not args.session and os.path.isdir(src_mem)
                           and not memory_copied)
        if ok and (args.session or uncopied_memory):
            # delete only what was copied; never rmtree a dir holding an
            # uncopied memory/ (dst already had one — merge by hand)
            for sid in sessions:
                os.remove(os.path.join(src, sid + ".jsonl"))
                sidecar = os.path.join(src, sid)
                if os.path.isdir(sidecar):
                    shutil.rmtree(sidecar)
            print(f"deleted {len(sessions)} session(s) from source")
            if uncopied_memory:
                print(f"kept {src_mem} (dst already has memory/ — merge by hand)")
        elif ok:
            shutil.rmtree(src)
            print(f"deleted source {src}")
        else:
            print("verification failed — source NOT deleted")
            sys.exit(1)
    else:
        print(f"\nsource left intact at {src} — verify, then remove with "
              "--delete-source or by hand")
    print("done.")


if __name__ == "__main__":
    main()
