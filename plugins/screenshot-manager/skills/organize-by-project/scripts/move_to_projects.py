#!/usr/bin/env python3
"""Plan, make and undo the moves from the Desktop into the projects folder.

    # 0. Batch: split the screenshots the name match could not place into batch files,
    #    one per image-check agent. Each agent writes vision_answers_<n>.json.
    python3 move_to_projects.py batch --root "<projects root>" --shots shots.json \
        --size 40 --out-dir <work dir>

    # 1. Plan: read the matches, print the table, write the plan. Moves nothing.
    python3 move_to_projects.py plan --root "<projects root>" --shots shots.json \
        --folders folders.json [--vision vision_answers_0.json ...] --out plan.json

    # 2. Apply: write the undo list to <root>/.moves/<UTC time>.json FIRST, then move.
    python3 move_to_projects.py apply --plan plan.json [--only shots|folders]

    # 3. Undo one batch: move everything back where it came from, newest first.
    python3 move_to_projects.py undo --log "<root>/.moves/<UTC time>.json"

Layout (chosen 2026-10-16): grouped by company.
    <root>/<org>/<project>/screenshots/<screenshot>   a loose Desktop screenshot
    <root>/<org>/<project>/<Desktop folder>/          a Desktop folder, moved whole, name kept
    <root>/<org>/screenshots/ and <root>/<org>/<Desktop folder>/   work on the company as a whole
org is "personal" for ~/Workspace/git, else the git-<org> folder's name.

A screenshot's project comes from the image check (--vision) when there is one, else from
the name match. "none" and "unsure" stay on the Desktop. An unsure screenshot taken within
--burst seconds of a decided one takes that one's project.

Never moved: a folder with key or secret files in it (listed, for you to sort by hand),
and an iCloud placeholder (".name.icloud": the file is not on this Mac yet).
"""
import argparse
import json
import os
import shutil
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


def key(path: str) -> str:
    """macOS puts a narrow no-break space before AM/PM; image checkers often write a space."""
    return unicodedata.normalize("NFC", path).replace(" ", " ")


def log(ev: str, **kv) -> None:
    parts = " ".join(f"{k}={json.dumps(str(v), ensure_ascii=False) if ' ' in str(v) else v}"
                     for k, v in kv.items())
    print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} pid={os.getpid()} ev={ev} {parts}",
          file=sys.stderr)


def free_name(dst: Path, taken: set[str]) -> Path:
    """dst, or 'name (2).png' if dst (or a planned move) already uses that name."""
    n, cand = 2, dst
    while cand.exists() or str(cand) in taken:
        cand = dst.with_name(f"{dst.stem} ({n}){dst.suffix}")
        n += 1
    return cand


def batch(a) -> None:
    """Every unclear AND every none shot gets a look: "none" only means no project words."""
    root = a.root.expanduser()
    projects = json.loads((root / ".projects.json").read_text())["projects"]
    plist = [{k: p[k] for k in ("name", "org", "title", "active")} for p in projects]
    plist += [{"name": o, "org": o, "title": f"{o}: work on the company as a whole (no single repo)",
               "active": True} for o in sorted({p["org"] for p in projects}) if o != "personal"]
    todo = [s for s in json.loads(a.shots.read_text()) if s["status"] != "matched"]
    a.out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for n, i in enumerate(range(0, len(todo), a.size)):
        part = todo[i: i + a.size]
        f = a.out_dir / f"vision_batch_{n}.json"
        f.write_text(json.dumps({"projects": plist, "shots": [{"file": s["file"], "candidates": s.get("candidates", [])}
                                                               for s in part]}, indent=1, ensure_ascii=False))
        print(f"{f}  {len(part)} shots")
    print(f"{len(todo)} shots in {n + 1 if todo else 0} batches; answers go to vision_answers_<n>.json")


def plan(a) -> None:
    root = a.root.expanduser()
    projects = json.loads((root / ".projects.json").read_text())["projects"]
    org_of = {p["name"]: p["org"] for p in projects}
    orgs = {p["org"] for p in projects}
    vision: dict[str, dict] = {}
    for f in a.vision or []:
        vision.update({key(k): v for k, v in json.loads(f.read_text()).items()})

    def home(project: str) -> Path | None:
        if project in orgs:
            return root / project
        if project in org_of:
            return root / org_of[project] / project
        return None

    shots = json.loads(a.shots.read_text()) if a.shots else []
    decided = []
    for s in shots:
        v = vision.get(key(s["file"]))
        project = v["project"] if v else (s["project"] if s["status"] == "matched" else "none")
        why = (f"image: {v['reason']}" if v else "name on screen: " + ", ".join(s["why"][:3]))
        decided.append({**s, "project": project, "why": why})
    # Unsure shots borrow a project from a decided shot taken moments before or after.
    timed = sorted((d for d in decided if d["time"]), key=lambda d: d["time"])
    for i, d in enumerate(timed):
        if d["project"] != "unsure":
            continue
        t = datetime.fromisoformat(d["time"])
        near = [o for o in timed[max(0, i - 4): i + 5] if o["project"] not in ("unsure", "none")
                and abs((datetime.fromisoformat(o["time"]) - t).total_seconds()) <= a.burst]
        if near:
            o = min(near, key=lambda o: abs((datetime.fromisoformat(o["time"]) - t).total_seconds()))
            d.update(project=o["project"], why=f"taken moments after/before {Path(o['file']).name}")

    moves, held, taken = [], [], set()
    for d in decided:
        src = Path(d["file"])
        dest = home(d["project"])
        if dest is None:
            held.append({"src": str(src), "reason": d["project"], "why": d["why"]})
            continue
        dst = free_name(dest / "screenshots" / src.name, taken)
        taken.add(str(dst))
        moves.append({"kind": "shot", "project": d["project"], "src": str(src), "dst": str(dst), "why": d["why"]})
    for f in json.loads(a.folders.read_text()) if a.folders else []:
        dest = home(f["project"]) if f["project"] else None
        if dest is None or f["kind"] == "unclear":
            continue
        src = Path(f["folder"])
        if f.get("secrets"):
            held.append({"src": str(src), "reason": "has key/secret files", "why": ", ".join(f["secrets"][:3])})
            continue
        dst = free_name(dest / src.name, taken)
        taken.add(str(dst))
        moves.append({"kind": "folder", "project": f["project"], "src": str(src), "dst": str(dst),
                      "why": f["why"], "files": f["files"], "non_images": f["non_images"]})
    out = {"root": str(root), "planned": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "moves": moves, "held": held}
    a.out.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    by: dict[str, list[int]] = {}
    for m in moves:
        rel = str(Path(m["dst"]).parent.relative_to(root)).removesuffix("/screenshots")
        c = by.setdefault(rel, [0, 0, 0])
        if m["kind"] == "shot":
            c[0] += 1
        else:
            c[1] += 1
            c[2] += m["files"]
    print(f"{'destination':42} {'shots':>5} {'folders':>7} {'files in them':>13}")
    for rel, (s, n, f) in sorted(by.items()):
        print(f"{rel:42} {s:5} {n:7} {f:13}")
    print(f"\n{len(moves)} moves planned; {len(held)} left on the Desktop "
          f"({sum(1 for h in held if h['reason'] == 'none')} not project work, "
          f"{sum(1 for h in held if h['reason'] == 'unsure')} unsure, "
          f"{sum(1 for h in held if h['reason'] == 'has key/secret files')} folders with keys)")
    print(f"plan written to {a.out}", file=sys.stderr)


def resolve(raw: str) -> Path | None:
    p = Path(raw)
    if p.exists():
        return p
    try:
        for entry in os.listdir(p.parent):
            if key(entry) == key(p.name):
                return p.parent / entry
    except FileNotFoundError:
        pass
    return None


def apply(a) -> None:
    pl = json.loads(a.plan.read_text())
    moves = [m for m in pl["moves"] if not a.only or m["kind"] == a.only.rstrip("s")]
    logdir = Path(pl["root"]) / ".moves"
    logdir.mkdir(parents=True, exist_ok=True)
    logfile = logdir / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    # The undo list goes to disk before the first move, so a crash mid-way can be undone.
    logfile.write_text(json.dumps({"plan": str(a.plan), "moves": moves}, indent=2, ensure_ascii=False))
    log("undo_list_written", path=logfile, moves=len(moves))
    done, failed = [], []
    for m in moves:
        src = resolve(m["src"])
        if src is None:
            failed.append({**m, "error": "not found"})
            log("move_skip", src=m["src"], reason="not_found")
            continue
        if src.name.endswith(".icloud") or (src.parent / f".{src.name}.icloud").exists():
            failed.append({**m, "error": "iCloud placeholder"})
            log("move_skip", src=src, reason="icloud_placeholder")
            continue
        dst = Path(m["dst"])
        if dst.exists():
            failed.append({**m, "error": "destination exists"})
            log("move_skip", src=src, reason="dst_exists")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        log("move_start", src=src, dst=dst)
        shutil.move(str(src), str(dst))
        done.append({**m, "src": str(src)})
    logfile.write_text(json.dumps({"plan": str(a.plan), "moves": done, "failed": failed}, indent=2,
                                  ensure_ascii=False))
    log("apply_done", moved=len(done), failed=len(failed), undo=logfile)
    print(f"moved {len(done)}, skipped {len(failed)}. To undo: move_to_projects.py undo --log \"{logfile}\"")


def undo(a) -> None:
    moves = json.loads(a.log.read_text())["moves"]
    back = 0
    for m in reversed(moves):
        dst, src = Path(m["dst"]), Path(m["src"])
        if not dst.exists() or src.exists():
            log("undo_skip", dst=dst, reason="gone" if not dst.exists() else "src_taken")
            continue
        src.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dst), str(src))
        back += 1
    log("undo_done", moved_back=back, of=len(moves))
    print(f"moved {back} of {len(moves)} back")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("batch")
    p.add_argument("--root", type=Path, required=True, help="the projects folder")
    p.add_argument("--shots", type=Path, required=True, help="match_projects.py shots --out")
    p.add_argument("--size", type=int, default=40, help="shots per image-check agent")
    p.add_argument("--out-dir", type=Path, required=True)
    p = sub.add_parser("plan")
    p.add_argument("--root", type=Path, required=True, help="the projects folder")
    p.add_argument("--shots", type=Path, help="match_projects.py shots --out")
    p.add_argument("--folders", type=Path, help="match_projects.py folders --out")
    p.add_argument("--vision", type=Path, action="append", help="image-check answers (repeatable)")
    p.add_argument("--burst", type=int, default=120)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("apply")
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--only", choices=["shots", "folders"])
    p = sub.add_parser("undo")
    p.add_argument("--log", type=Path, required=True)
    a = ap.parse_args()
    {"batch": batch, "plan": plan, "apply": apply, "undo": undo}[a.cmd](a)


if __name__ == "__main__":
    main()
