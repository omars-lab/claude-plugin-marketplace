#!/usr/bin/env python3
"""Send the shareable technique content to the studio folder, adding to what is already there,
so new techniques show up where posts get written.

Two ways to reach the folder, picked by where the script runs:
    local  this Mac has iCloud Drive and dest is inside it: write into it directly, and iCloud
           carries it to the studio. No SSH.
    ssh    otherwise: rsync over SSH to the studio, as before.
The same studio.json works on both Macs, because dest is relative to the home folder.

The folder is shared: more than one Mac adds techniques to it. Each technique's own files are
added or updated, never removed, and the two files every technique shares (content/index.json
and the gallery, pages/index.html) are rebuilt from what is already there plus what is sent, so
techniques another Mac sent stay listed. A slug sent from here replaces the same slug there.

Only shareable material is sent, and it is staged first:
    <dest>/pages/              the post view (pages/post/: pages, gallery, _lib)
    <dest>/content/<slug>.json the redacted spec of each technique (lib.post_spec)
    <dest>/content/index.json  one line per technique: slug, title, mechanism, why, taken, page,
                               status and confirmed focus (from the hub)
Never sent: the internal view, the original screenshots, the unredacted specs, sessions.

Settings live outside the repo, in ~/.config/technique-manager/studio.json:
    {"host": "<ssh host alias>", "dest": "<folder on that Mac; relative = from its home>"}
host can be left out on a Mac that always writes locally.

Usage:
    python3 sync_studio.py --setup --host my-mac --dest "Library/Mobile Documents/com~apple~CloudDocs/.../claude-techniques"
    python3 sync_studio.py --dry-run          # show what would change
    python3 sync_studio.py                    # sync
    python3 sync_studio.py --prune            # also delete files there that are gone here; refused
                                              # while the folder holds techniques from another Mac

Output (JSON on stdout): {"mode", "host", "dest", "staged": N, "kept": [slugs already there],
                          "total": N, "sent": [...], "dry_run": bool}
Exit 1 (with the reason) if the folder can't be reached or rsync fails.
"""
import argparse
import html
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "recreate-technique" / "scripts"))
import lib  # noqa: E402
import scan_privacy  # noqa: E402

CONFIG = Path.home() / ".config" / "technique-manager" / "studio.json"
ICLOUD = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
GALLERY = SKILLS / "package-gallery" / "templates" / "gallery.html"


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


def local_target(dest: str) -> Path | None:
    """The folder on this Mac when dest is inside iCloud Drive and this Mac has iCloud Drive;
    else None (go over SSH). Checks the iCloud root, not dest, so a first run still goes local."""
    target = Path(dest).expanduser()
    target = target if target.is_absolute() else Path.home() / target
    if ICLOUD.is_dir() and (target == ICLOUD or ICLOUD in target.parents):
        return target
    return None


def stage(root: Path, out: Path) -> tuple[list[dict], set[str]]:
    """Copy the post view and the redacted specs into out; refuse anything with findings.
    Returns the index rows staged, and every slug this root knows (staged or not)."""
    post = lib.pages_dir(root, "post")
    if not (post / "index.html").exists():
        raise SystemExit("No pages/post/index.html; run render_page.py --all and build_gallery.py first")
    shutil.copytree(post, out / "pages", ignore=shutil.ignore_patterns("_check", ".DS_Store"))
    content = out / "content"
    content.mkdir()
    index, known = [], set()
    for raw in lib.load_specs(root):
        slug = raw["slug"]
        known.add(slug)
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
    return index, known


def existing_index(host: str | None, dest: str, local: Path | None) -> list[dict]:
    """content/index.json as it is in the folder now ([] on a first sync). Refuses when iCloud
    has evicted it to a placeholder: reading nothing there would drop every listed technique."""
    if local:
        f = local / "content" / "index.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        if (f.parent / ".index.json.icloud").exists():
            raise SystemExit(f"{f} is in iCloud but not downloaded; run `brctl download {shlex.quote(str(f))}`, then sync again")
        return []
    f = shlex.quote(dest.rstrip("/") + "/content/index.json")
    stub = shlex.quote(dest.rstrip("/") + "/content/.index.json.icloud")
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host,
                        f"if [ -f {f} ]; then cat {f}; elif [ -e {stub} ]; then echo __evicted__; else echo __none__; fi"],
                       capture_output=True, text=True)
    out = r.stdout.strip()
    if r.returncode != 0:
        raise SystemExit(f"Can't read the index on {host}: {r.stderr.strip()}")
    if out == "__evicted__":
        raise SystemExit(f"{host}:{dest}/content/index.json is in iCloud but not downloaded there; open the folder on that Mac, then sync again")
    return [] if out == "__none__" else json.loads(out)


def combine(staged: list[dict], there: list[dict]) -> tuple[list[dict], list[str]]:
    """Every technique already listed, with the staged ones added or replacing theirs, newest first."""
    mine = {r["slug"] for r in staged}
    kept = [r for r in there if r.get("slug") not in mine]
    rows = sorted(kept + staged, key=lambda r: r.get("taken") or "", reverse=True)
    return rows, [r["slug"] for r in kept]


def write_index(out: Path, rows: list[dict], title: str | None) -> None:
    """content/index.json and the post gallery, both from the combined rows. The gallery keeps
    the title it was built with here ("Technique hub" from a hub) unless --title is given."""
    if not title:
        m = re.search(r"<title>(.*?)</title>", (out / "pages" / "index.html").read_text(encoding="utf-8"), re.S)
        title = html.unescape(m.group(1)) if m else "Claude techniques"
    (out / "content" / "index.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # The same card fields build_gallery.cards_for gives the post view.
    cards = [{"slug": r["slug"], "href": f"{r['slug']}.html", "status": None, "focus": None,
              "title": r.get("title") or r["slug"], "mechanism": r.get("mechanism"), "why": r.get("why"),
              "taken": r.get("taken"), "image": None} for r in rows]
    (out / "pages" / "index.html").write_text(
        lib.fill(GALLERY, title, cards, lib.prerender("Gallery", {"title": title, "cards": cards})), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("--setup", action="store_true", help="save --host and --dest to the config")
    ap.add_argument("--host")
    ap.add_argument("--dest")
    ap.add_argument("--title", help="the gallery's title (default: the one it was built with)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune", action="store_true", help="delete files in dest that are gone here")
    args = ap.parse_args()

    cfg = load_config()
    if args.setup:
        if not args.dest or not (args.host or local_target(args.dest)):
            raise SystemExit("--setup needs --dest, and --host unless dest is in this Mac's iCloud Drive")
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        saved = {k: v for k, v in (("host", args.host), ("dest", args.dest)) if v}
        CONFIG.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"config": str(CONFIG), **saved}, indent=2))
        return 0
    host, dest = args.host or cfg.get("host"), args.dest or cfg.get("dest")
    if not dest:
        raise SystemExit(f"No dest; run with --setup first (config: {CONFIG})")
    local = local_target(dest)
    if not (local or host):
        raise SystemExit(f"{dest} isn't in this Mac's iCloud Drive and there is no host to reach it over SSH")

    if local:
        local.mkdir(parents=True, exist_ok=True)
    else:
        # Reach the host and create the folder. BatchMode: fail instead of prompting for a password.
        probe = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host,
                                f"mkdir -p {shlex.quote(dest)} && echo ok"], capture_output=True, text=True)
        if probe.returncode != 0 or "ok" not in probe.stdout:
            raise SystemExit(f"Can't reach {host}: {(probe.stderr or probe.stdout).strip().splitlines()[-1:] or ['no output']}")

    root = lib.find_root(args.root)
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "techniques"
        staged.mkdir()
        rows, known = stage(root, staged)
        there = existing_index(host, dest, local)
        foreign = sorted({r.get("slug") for r in there} - known)
        if args.prune and foreign:
            raise SystemExit(f"--prune would delete {len(foreign)} techniques this root never had "
                             f"(another Mac sent them), e.g. {foreign[0]}; sync without --prune")
        combined, kept = combine(rows, there)
        write_index(staged, combined, args.title)

        # --checksum: pages rebuilt on another Mac have new times but the same bytes; send only real changes.
        cmd = ["rsync", "-a", "--checksum", "--itemize-changes", "--exclude", ".DS_Store"]
        if args.dry_run:
            cmd.append("--dry-run")
        if args.prune:
            cmd.append("--delete")
        # A local path goes unquoted: remote_path's quoting is for the remote shell only.
        target = f"{local}/" if local else f"{host}:{remote_path(dest.rstrip('/') + '/')}"
        r = subprocess.run(cmd + [f"{staged}/", target], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"rsync failed: {r.stderr.strip()}")
        sent = [line.split(" ", 1)[1] for line in r.stdout.splitlines()
                if line[:1] in "<>c*" and " " in line and not line.endswith("/")]
    print(json.dumps({"mode": "local" if local else "ssh", "host": None if local else host,
                      "dest": str(local) if local else dest, "staged": len(rows), "kept": kept,
                      "total": len(combined), "sent": sent, "dry_run": args.dry_run},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
