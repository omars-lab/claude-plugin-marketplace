#!/usr/bin/env python3
"""List the projects behind the git repos on this Mac, one entry per project.

A project is one repository. Its clones and worktrees (atlas, atlas-work, atlas-main ...)
fold into one entry: worktrees by their shared git folder, clones by the repo name in
their origin URL. Links between the roots (~/git -> ~/Workspace/git) are followed once.

Usage:
    python3 scan_projects.py                              # default roots, table
    python3 scan_projects.py --since-days 90 --json       # JSON, with an "active" flag
    python3 scan_projects.py --out "<projects root>/.projects.json"

Default roots: ~/Workspace/git (org "personal"), ~/Workspace/git-<org> for every other
git-* folder there. Override with --root PATH (repeatable; org is the folder name
without "git-", or "personal" for plain "git").

Each entry: name, org, checkouts (paths), main (the checkout to read), last_commit (ISO),
active (within --since-days), title (README heading), subjects (recent commit subjects),
signals (words a screenshot of this project tends to show).
"""
import argparse
import fnmatch
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKIP = ["_backups", "archive-and-backups", "*-to-delete", "*-backup"]
STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with", "is", "it",
        "add", "fix", "chore", "bump", "version", "feat", "docs", "update", "merge", "from",
        "branch", "main", "remote", "tracking", "origin", "into", "by", "at", "as", "be", "no",
        "not", "now", "when", "that", "this", "one", "new", "say", "use", "make", "its"}


def git(args: list[str], cwd: Path, timeout: int = 20) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"ev=git_timeout cwd={cwd} args={' '.join(args)}", file=sys.stderr)
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def default_roots() -> list[Path]:
    base = Path.home() / "Workspace"
    return sorted(p for p in base.glob("git*") if p.is_dir())


def org_of(root: Path) -> str:
    return "personal" if root.name == "git" else root.name.removeprefix("git-")


def repo_name(url: str) -> str:
    """'host:git/atlas.git' / 'git@github.com:o/atlas.git' / 'https://.../atlas' -> 'atlas'."""
    tail = re.split(r"[/:]", url.rstrip("/"))[-1]
    return tail.removesuffix(".git")


def title_of(checkout: Path) -> str:
    for name in ("README.md", "readme.md", "README"):
        f = checkout / name
        if f.is_file():
            for line in f.read_text(errors="ignore").splitlines()[:40]:
                if line.startswith("# "):
                    return line[2:].strip()
    return ""


def signals_of(name: str, title: str, subjects: list[str]) -> list[str]:
    words = re.findall(r"[a-z0-9][a-z0-9-]{2,}", " ".join([name, title, *subjects]).lower())
    counts: dict[str, int] = {}
    for w in words:
        for part in {w, *w.split("-")}:
            if len(part) > 2 and part not in STOP and not part.isdigit():
                counts[part] = counts.get(part, 0) + 1
    seed = [p for p in name.lower().split("-") if len(p) > 2]
    ranked = sorted(counts, key=lambda w: (-counts[w], w))
    out = list(dict.fromkeys([name.lower(), *seed, *ranked]))
    return out[:25]


def scan(roots: list[Path], since_days: int, n_subjects: int) -> list[dict]:
    seen: set[Path] = set()
    groups: dict[str, dict] = {}  # key -> project
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    for root in roots:
        real_root = root.resolve()
        org = org_of(root)
        for d in sorted(real_root.iterdir()):
            if not d.is_dir() or not (d / ".git").exists():
                continue
            if any(fnmatch.fnmatch(d.name, pat) for pat in SKIP):
                continue
            real = d.resolve()
            if real in seen:
                continue
            seen.add(real)
            common = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], real)
            url = git(["config", "--get", "remote.origin.url"], real)
            name = repo_name(url) if url else Path(common).parent.name if common else d.name
            key = f"{org}/{name}"
            p = groups.setdefault(key, {"name": name, "org": org, "checkouts": [], "common": set()})
            p["checkouts"].append(str(d))  # the name as listed (NotePlan3), not a link's target
            if common:
                p["common"].add(common)
    projects = []
    for p in groups.values():
        commons = sorted(p.pop("common"))
        # Name the project after a folder people see: the checkout named like the repo (or
        # like it with the org prefix, acme-<repo>), else the shortest real clone (.git is
        # a folder, not a worktree's .git file). The origin name only groups.
        clones = [c for c in p["checkouts"] if (Path(c) / ".git").is_dir()] or p["checkouts"]
        named = [c for c in clones if Path(c).name in (p["name"], f"{p['org']}-{p['name']}")]
        main = min(named or clones, key=lambda c: (len(Path(c).name), c))
        p["repo"] = p["name"]
        p["name"] = Path(main).name
        gd = commons[0] if commons else str(Path(main) / ".git")
        last = git(["--git-dir", gd, "log", "--all", "-1", "--format=%cI"], Path(main))
        subjects = git(["--git-dir", gd, "log", "--all", f"-{n_subjects}", "--format=%s",
                        "--no-merges"], Path(main)).splitlines()
        title = title_of(Path(main))
        active = bool(last) and datetime.fromisoformat(last) >= cutoff
        projects.append({**p, "main": main, "last_commit": last, "active": active,
                         "title": title, "subjects": subjects,
                         "signals": signals_of(p["name"], title, subjects)})
    projects.sort(key=lambda p: p["last_commit"] or "", reverse=True)
    return projects


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", action="append", type=Path, help="a folder of repos (repeatable)")
    ap.add_argument("--since-days", type=int, default=90, help="worked on within N days = active")
    ap.add_argument("--subjects", type=int, default=15, help="recent commit subjects to keep")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    ap.add_argument("--out", type=Path, help="write JSON to this file")
    a = ap.parse_args()
    roots = [r.expanduser() for r in a.root] if a.root else default_roots()
    projects = scan(roots, a.since_days, a.subjects)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps({"scanned": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                     "since_days": a.since_days, "projects": projects}, indent=2))
        print(f"wrote {len(projects)} projects to {a.out}", file=sys.stderr)
    if a.json:
        print(json.dumps(projects, indent=2))
    elif not a.out:
        active = [p for p in projects if p["active"]]
        print(f"{len(projects)} projects, {len(active)} worked on in the last {a.since_days} days\n")
        for p in projects:
            mark = "*" if p["active"] else " "
            extra = f"  (+{len(p['checkouts']) - 1} more checkouts)" if len(p["checkouts"]) > 1 else ""
            print(f"{mark} {(p['last_commit'] or '')[:10]:10}  {p['org']:12} {p['name']}{extra}")


if __name__ == "__main__":
    main()
