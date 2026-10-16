#!/usr/bin/env python3
"""Back up the hub's private folders that git doesn't hold to the upstream machine, with rsync
over SSH. Adds and updates only: nothing on the other side is ever deleted (no --delete), so a
screenshot or session removed here stays in the backup.

    archive/                      copies of linked sessions        → <dest>/archive/
    <shotsDir>/page-comments/<hub> comment screenshots (page comments' shotsDir, or
                                   .page-comments/shots when that is the fallback) → <dest>/shots/

Settings in hub.json: "backup": {"host": "<ssh alias>", "dest": "<folder there; relative = home>"}

Usage:
    python3 backup_hub.py [--root R] [--dry-run] [--text]
Output (JSON): {"host", "dest", "folders": [{"name", "src", "sent": N} | {"name", "skipped": reason}]}
"""
import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "recreate-technique" / "scripts"))
sys.path.insert(0, str(SKILLS / "sync-studio" / "scripts"))
import lib  # noqa: E402
from sync_studio import remote_path  # noqa: E402


def shots_dir(root: Path) -> Path:
    """Where page comments save screenshots for this repo (see enable-page-comments)."""
    cfg = root / ".page-comments" / "config.json"
    shots = json.loads(cfg.read_text(encoding="utf-8")).get("shotsDir") if cfg.exists() else None
    if shots:
        d = Path(shots).expanduser() / "page-comments" / root.name
        if d.exists():
            return d
    return root / ".page-comments" / "shots"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--text", action="store_true", help="one line per folder instead of JSON")
    args = ap.parse_args()
    root = lib.find_root(args.root)
    backup = lib.hub_settings(root).get("backup") or {}
    host, dest = backup.get("host"), backup.get("dest")
    if not (host and dest):
        raise SystemExit('No "backup": {"host", "dest"} in hub.json')

    probe = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host,
                            f"mkdir -p {shlex.quote(dest)}/archive {shlex.quote(dest)}/shots && echo ok"],
                           capture_output=True, text=True)
    if probe.returncode != 0 or "ok" not in probe.stdout:
        raise SystemExit(f"Can't reach {host}: {(probe.stderr or probe.stdout).strip().splitlines()[-1:] or ['no output']}")

    folders = []
    for name, src in (("archive", lib.archive_dir(root).parent), ("shots", shots_dir(root))):
        if not src.exists():
            folders.append({"name": name, "skipped": f"{src} doesn't exist yet"})
            continue
        cmd = ["rsync", "-a", "--itemize-changes", "--exclude", ".DS_Store"]  # never --delete
        if args.dry_run:
            cmd.append("--dry-run")
        cmd += [f"{src}/", f"{host}:{remote_path(dest.rstrip('/') + '/' + name + '/')}"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"rsync {name} failed: {r.stderr.strip()}")
        sent = [l for l in r.stdout.splitlines() if l[:1] in "<>c" and not l.endswith("/")]
        folders.append({"name": name, "src": str(src), "sent": len(sent)})
    if args.text:
        for f in folders:
            print(f"{f['name']:8} → {host}:{dest}/{f['name']}  " + (f"{f['sent']} files" if "sent" in f else f["skipped"]))
    else:
        print(json.dumps({"host": host, "dest": dest, "dry_run": args.dry_run, "folders": folders},
                         ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
