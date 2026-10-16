#!/usr/bin/env python3
"""Copy the shareable technique content to another Mac over SSH (rsync), into one
dedicated folder there, so new techniques show up where posts get written.

Only shareable material is sent, and it is staged first:
    <dest>/pages/              the post view (pages/post/: pages, gallery, _lib)
    <dest>/content/<slug>.json the redacted spec of each technique (lib.post_spec)
    <dest>/content/index.json  one line per technique: slug, title, mechanism, why, taken, page,
                               status and confirmed focus (from the hub)
Never sent: the internal view, the original screenshots, the unredacted specs, sessions.

Settings live outside the repo, in ~/.config/technique-manager/studio.json:
    {"host": "<ssh host alias>", "dest": "<folder on that Mac; relative = from its home>"}

Usage:
    python3 sync_studio.py --setup --host my-mac --dest "Documents/content/techniques"
    python3 sync_studio.py --dry-run          # show what would change
    python3 sync_studio.py                    # sync
    python3 sync_studio.py --prune            # also delete files there that are gone here

Output (JSON on stdout): {"host", "dest", "staged": N, "sent": [...], "dry_run": bool}
Exit 1 (with the reason) if the host can't be reached or rsync fails.
"""
import argparse
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "recreate-technique" / "scripts"))
import lib  # noqa: E402
import scan_privacy  # noqa: E402

CONFIG = Path.home() / ".config" / "technique-manager" / "studio.json"


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}


def remote_path(path: str) -> str:
    """rsync 3.2.4+ protects remote arguments by default, so the path goes as is. Older rsync
    (macOS's 2.6.9) and openrsync hand it to the remote shell, so it must be quoted there."""
    first = subprocess.run(["rsync", "--version"], capture_output=True, text=True).stdout.splitlines()[:1]
    parts = first[0].split() if first else []
    if len(parts) > 2 and parts[0] == "rsync" and parts[1] == "version":
        nums = tuple(int(x) for x in parts[2].split(".")[:3] if x.isdigit())
        if nums >= (3, 2, 4):
            return path
    return shlex.quote(path)


def stage(root: Path, out: Path) -> int:
    """Copy the post view and the redacted specs into out; refuse anything with findings."""
    post = lib.pages_dir(root, "post")
    if not (post / "index.html").exists():
        raise SystemExit("No pages/post/index.html; run render_page.py --all and build_gallery.py first")
    shutil.copytree(post, out / "pages", ignore=shutil.ignore_patterns("_check", ".DS_Store"))
    content = out / "content"
    content.mkdir()
    index = []
    for raw in lib.load_specs(root):
        slug = raw["slug"]
        if not (post / f"{slug}.html").exists():
            continue  # no post page means its redactions aren't done; don't send its content
        spec = lib.post_spec(raw, root)
        left = scan_privacy.scan(spec, tuple(r["replace"] for r in lib.redactions_for(raw, root)))
        if left:
            raise SystemExit(f"{slug}: the post content still shows {left[0]['match']!r}; fix its redactions first")
        (content / f"{slug}.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        t = spec.get("technique") or {}
        index.append({"slug": slug, "title": t.get("title"), "mechanism": t.get("mechanism"), "why": t.get("why"),
                      "taken": (spec.get("source") or {}).get("taken"), "page": f"pages/{slug}.html",
                      "has_backstory": bool(spec.get("backstory")),
                      # Hub: where it stands, and its confirmed focus (post_spec keeps only a confirmed one).
                      "status": lib.effective_status(raw), "focus": (spec.get("focus") or {}).get("line")})
    index.sort(key=lambda r: r.get("taken") or "", reverse=True)
    (content / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(index)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("--setup", action="store_true", help="save --host and --dest to the config")
    ap.add_argument("--host")
    ap.add_argument("--dest")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune", action="store_true", help="delete files in dest that are gone here")
    args = ap.parse_args()

    cfg = load_config()
    if args.setup:
        if not (args.host and args.dest):
            raise SystemExit("--setup needs --host and --dest")
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps({"host": args.host, "dest": args.dest}, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"config": str(CONFIG), "host": args.host, "dest": args.dest}, indent=2))
        return 0
    host, dest = args.host or cfg.get("host"), args.dest or cfg.get("dest")
    if not (host and dest):
        raise SystemExit(f"No host/dest; run with --setup first (config: {CONFIG})")

    # Reach the host and create the folder. BatchMode: fail instead of prompting for a password.
    probe = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host,
                            f"mkdir -p {shlex.quote(dest)} && echo ok"], capture_output=True, text=True)
    if probe.returncode != 0 or "ok" not in probe.stdout:
        raise SystemExit(f"Can't reach {host}: {(probe.stderr or probe.stdout).strip().splitlines()[-1:] or ['no output']}")

    root = lib.find_root(args.root)
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "techniques"
        staged.mkdir()
        count = stage(root, staged)
        cmd = ["rsync", "-a", "--itemize-changes", "--exclude", ".DS_Store"]
        if args.dry_run:
            cmd.append("--dry-run")
        if args.prune:
            cmd.append("--delete")
        cmd += [f"{staged}/", f"{host}:{remote_path(dest.rstrip('/') + '/')}"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"rsync failed: {r.stderr.strip()}")
        sent = [line.split(" ", 1)[1] for line in r.stdout.splitlines() if line[:1] in "<>c*" and " " in line]
    print(json.dumps({"host": host, "dest": dest, "staged": count, "sent": sent, "dry_run": args.dry_run},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
