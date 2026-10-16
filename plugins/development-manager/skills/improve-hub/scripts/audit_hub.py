# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Check one hub against the mechanical rows of RUBRIC.md and print a scorecard.

    uv run audit_hub.py --repo <repo>                 # every hub in the repo's hub.yaml
    uv run audit_hub.py --repo <repo> --hub <id>      # one hub
    uv run audit_hub.py --repo <repo> --json          # for a script

It only reads: files, git, and what lsof says is listening. It starts, stops and changes
nothing. The hubs catalog repo is --hubs, else $HUBS_REPO, else ~/Workspace/git/hubs; without it
the catalog rows say SKIP. Exit 1 when any row FAILs.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

LOOPBACK = {"127.0.0.1", "[::1]", "localhost", "::1"}
WRITE_ROUTES = (
    r"req\.method *[!=]==? *['\"](POST|PUT|PATCH|DELETE)"
    r"|\.(post|put|patch|delete)\( *['\"]/"
    r"|def do_(POST|PUT|PATCH|DELETE)"
    r"|methods *= *\[[^]]*(POST|PUT|PATCH|DELETE)"
)
SITEMAP_STALE_DAYS = 14
COMMENT_PORTS = range(8766, 8800)  # where page-comments looks for a free port
EPHEMERAL = 49152  # ports the system hands out for a moment


def run(cmd, cwd=None, timeout=60):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, "", str(e)


def git_grep(repo, pattern, *, word=False, extended=False, exclude=()):
    cmd = ["git", "-C", str(repo), "grep", "-n", "-I"]
    if word:
        cmd.append("-w")
    if extended:
        cmd.append("-E")
    cmd += ["-e", pattern, "--", "."] + [f":!{x}" for x in exclude]
    _, out, _ = run(cmd)
    return [line for line in out.splitlines() if line]


def worktrees(repo):
    _, out, _ = run(["git", "-C", str(repo), "worktree", "list", "--porcelain"])
    paths = [Path(line[9:]) for line in out.splitlines() if line.startswith("worktree ")]
    return paths or [repo]


def listeners():
    """(port, addr, pid, cmd) for every TCP listener, from lsof."""
    _, out, _ = run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-Fpcn"], timeout=15)
    rows, pid, cmd = [], None, None
    for line in out.splitlines():
        tag, val = line[:1], line[1:]
        if tag == "p":
            pid = int(val)
        elif tag == "c":
            cmd = val
        elif tag == "n" and ":" in val:
            addr, _, port = val.rpartition(":")
            if port.isdigit():
                rows.append((int(port), addr, pid, cmd))
    return rows


def cwd_of(pid):
    _, out, _ = run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], timeout=10)
    for line in out.splitlines():
        if line.startswith("n"):
            return Path(line[1:])
    return None


def row(rid, name, status, detail):
    return {"id": rid, "check": name, "status": status, "detail": detail}


def audit(repo: Path, hub_id: str | None, hubs_repo: Path | None):
    out = []
    manifest = repo / "hub.yaml"
    if not manifest.is_file():
        out.append(row("C1", "in the catalog", "FAIL", "no hub.yaml at the repo root; follow the join checklist"))
        return out, []
    out.append(row("C1", "in the catalog", "PASS", "hub.yaml found"))
    doc = yaml.safe_load(manifest.read_text()) or {}
    runners = {r["id"]: r for r in doc.get("runners") or []}
    hubs = [h for h in doc.get("hubs") or [] if not hub_id or h.get("id") == hub_id]
    if hub_id and not hubs:
        out.append(row("C1", "in the catalog", "FAIL", f"no hub with id {hub_id} in hub.yaml"))
        return out, []
    ports = {r["port"] for r in runners.values() if "port" in r}

    # C2: the catalog's own check, for this repo only.
    if hubs_repo and (hubs_repo / "launcher" / "check.py").is_file():
        code, text, err = run(["uv", "run", "--quiet", str(hubs_repo / "launcher" / "check.py"),
                               "--repo", str(repo)], cwd=hubs_repo, timeout=120)
        lines = [l for l in text.splitlines() if l.startswith(("error", "to-do"))]
        errors = [l for l in lines if l.startswith("error")]
        status = "FAIL" if errors or code else ("INFO" if lines else "PASS")
        detail = "; ".join(lines) if lines else ("clean" if not code else (err.strip() or "check failed")[:300])
        out.append(row("C2", "catalog check", status, detail))
    else:
        out.append(row("C2", "catalog check", "SKIP", "hubs repo not found (--hubs or $HUBS_REPO)"))

    # P1: each runner's port is set in the repo's own config, not worked out at run time.
    for rid, r in runners.items():
        port = r.get("port")
        hits = git_grep(repo, str(port), word=True, exclude=("hub.yaml", "*.md", "*.tsv", "*.json.lock", "yarn.lock"))
        if hits:
            out.append(row("P1", f"port {port} pinned ({rid})", "PASS", hits[0][:160]))
        else:
            out.append(row("P1", f"port {port} pinned ({rid})", "FAIL",
                           "the port is in hub.yaml only; the server must work it out some other way (a folder-name hash, a default)"))

    # P2: Vite servers fail on a taken port instead of moving.
    _, files, _ = run(["git", "-C", str(repo), "ls-files", "*vite.config.*"])
    vite = [f for f in files.splitlines() if f]
    if vite:
        loose = [f for f in vite if not re.search(r"strictPort\s*:\s*true", (repo / f).read_text(errors="ignore"))]
        out.append(row("P2", "Vite strictPort", "FAIL" if loose else "PASS",
                       ("no strictPort: true in " + ", ".join(loose)) if loose else ", ".join(vite)))
    else:
        out.append(row("P2", "Vite strictPort", "SKIP", "no Vite config"))

    # P3 and P4: what this repo (or any worktree of it) is serving right now, and where.
    trees = [t.resolve() for t in worktrees(repo)]
    mine = []
    for port, addr, pid, cmd in listeners():
        cwd = cwd_of(pid)
        if cwd and any(cwd == t or t in cwd.parents for t in trees):
            mine.append((port, addr, pid, cmd, cwd))
    if not mine:
        out.append(row("P3", "listens on this Mac only", "SKIP", "nothing from this repo is running"))
        out.append(row("P4", "runs on the hub.yaml port", "SKIP", "nothing from this repo is running"))
    else:
        wide = [m for m in mine if m[1].split("%")[0] not in LOOPBACK]
        out.append(row("P3", "listens on this Mac only", "FAIL" if wide else "PASS",
                       "; ".join(f"{a}:{p} ({c}, {w})" for p, a, _, c, w in (wide or mine))))
        # Page-comments servers and the system's throwaway ports are not the hub serving elsewhere.
        odd = sorted({m[0] for m in mine if m[0] not in COMMENT_PORTS and m[0] < EPHEMERAL} - ports)
        up = sorted(ports & {m[0] for m in mine})
        if odd:
            out.append(row("P4", "runs on the hub.yaml port", "FAIL",
                           f"listening on {odd}, hub.yaml lists {sorted(ports)}; the launcher and router can't see it"))
        elif up:
            out.append(row("P4", "runs on the hub.yaml port", "PASS", f"up on {up}"))
        else:
            out.append(row("P4", "runs on the hub.yaml port", "SKIP", "the hub's server is not running (only helper servers)"))

    # S1: requests that change data, and whether anything beyond this Mac can reach them.
    writes = git_grep(repo, WRITE_ROUTES, extended=True, exclude=("*.md", "*test*", "*spec*", "node_modules"))
    files_with = sorted({w.split(":", 1)[0] for w in writes})
    exposed = any(r["check"] == "listens on this Mac only" and r["status"] == "FAIL" for r in out)
    if not files_with:
        out.append(row("S1", "writes need a sign-in when exposed", "PASS", "no write routes found"))
    else:
        out.append(row("S1", "writes need a sign-in when exposed", "FAIL" if exposed else "INFO",
                       f"{len(writes)} write routes in {', '.join(files_with[:5])}"
                       + ("; reachable beyond this Mac with no sign-in" if exposed else "; loopback only, fine for now")))

    # F1: page comments.
    pc = (repo / ".page-comments" / "config.json").is_file()
    out.append(row("F1", "page comments on", "PASS" if pc else "FAIL",
                   ".page-comments/config.json" if pc else "run development-manager:enable-page-comments"))

    # V1: a recent site map with no failed pages, per hub.
    for h in hubs:
        if not hubs_repo:
            out.append(row("V1", f"site map ({h['id']})", "SKIP", "hubs repo not found"))
            continue
        m = hubs_repo / ".cache" / "sitemaps" / h["id"] / "map.json"
        if not m.is_file():
            out.append(row("V1", f"site map ({h['id']})", "FAIL", f"none yet; make -C {hubs_repo} sitemap HUB={h['id']}"))
            continue
        data = json.loads(m.read_text())
        age = (time.time() - m.stat().st_mtime) / 86400
        bad = [n["path"] + (f" ({n['note']})" if n.get("note") else "") for n in data.get("nodes", []) if n.get("note")]
        status = "FAIL" if bad else ("INFO" if age > SITEMAP_STALE_DAYS else "PASS")
        detail = f"{len(data.get('nodes', []))} pages, {age:.0f} days old"
        if data.get("capped"):
            detail += ", stopped at the page cap"
        if bad:
            detail += "; failed: " + ", ".join(bad[:5])
        out.append(row("V1", f"site map ({h['id']})", status, detail))
    return out, [h["id"] for h in hubs]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--hub", help="one hub id from hub.yaml; default all")
    ap.add_argument("--hubs", type=Path, help="the hubs catalog repo")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    repo = args.repo.expanduser().resolve()
    hubs_repo = args.hubs or Path(os.environ.get("HUBS_REPO", "~/Workspace/git/hubs"))
    hubs_repo = hubs_repo.expanduser().resolve()
    if not hubs_repo.is_dir():
        hubs_repo = None
    rows, hub_ids = audit(repo, args.hub, hubs_repo)

    if args.json:
        print(json.dumps({"repo": str(repo), "hubs": hub_ids, "rows": rows}, indent=1))
    else:
        print(f"{repo.name}: {', '.join(hub_ids) or 'no hubs'}")
        for r in rows:
            print(f"  {r['status']:4}  {r['id']:3} {r['check']:38} {r['detail']}")
        counts = {s: sum(r["status"] == s for r in rows) for s in ("PASS", "FAIL", "INFO", "SKIP")}
        print("  " + ", ".join(f"{n} {s.lower()}" for s, n in counts.items() if n))
    return 1 if any(r["status"] == "FAIL" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
